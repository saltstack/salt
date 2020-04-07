# -*- coding: utf-8 -*-
"""
Manage S3 Resources
=================

.. versionadded:: 2018.3.0

Manage S3 resources. Be aware that this interacts with Amazon's services,
and so may incur charges.

This module uses ``boto3``, which can be installed via package, or pip.

This module accepts explicit AWS credentials but can also utilize
IAM roles assigned to the instance through Instance Profiles. Dynamic
credentials are then automatically obtained from AWS API and no further
configuration is necessary. More information available `here
<http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html>`_.

If IAM roles are not used you need to specify them either in a pillar file or
in the minion's config file:

.. code-block:: yaml

    s3.keyid: GKTADJGHEIQSXMKKRBJ08H
    s3.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

It's also possible to specify ``key``, ``keyid`` and ``region`` via a profile,
either passed in as a dict, or as a string to pull from pillars or minion
config:

.. code-block:: yaml

    myprofile:
        keyid: GKTADJGHEIQSXMKKRBJ08H
        key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

.. code-block:: yaml

    Ensure s3 object exists:
        boto_s3.object_present:
            - name: s3-bucket/s3-key
            - source: /path/to/local/file
            - region: us-east-1
            - keyid: GKTADJGHEIQSXMKKRBJ08H
            - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            - profile: my-profile

:depends: boto3
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

import copy
import difflib
import logging

# Import Salt libs
import salt.ext.six as six
import salt.utils.hashutils

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load if boto is available.
    """
    if "boto_s3.get_object_metadata" not in __salt__:
        return False
    return "boto_s3"


# Keys for `extra_args` that we support.
# Currently, this excludes the `ACL` and `Grant*` keys.
# Most keys are stored and returned by AWS:
STORED_EXTRA_ARGS = frozenset(
    [
        "CacheControl",
        "ContentDisposition",
        "ContentEncoding",
        "ContentLanguage",
        "ContentType",
        "Expires",
        "Metadata",
        "ServerSideEncryption",
        "SSECustomerAlgorithm",
        "SSECustomerKeyMD5",
        "SSEKMSKeyId",
        "StorageClass",
        "WebsiteRedirectLocation",
    ]
)
# However, some keys are only specified on upload,
# but won't be stored/returned by AWS as metadata:
UPLOAD_ONLY_EXTRA_ARGS = frozenset(
    [
        # AWS doesn't store customer provided keys,
        # can use SSECustomerKeyMD5 to check for correct key
        "SSECustomerKey",
        "RequestPayer",
    ]
)
# Some extra args must also be passed along to retrive metadata,
# namely SSE-C (customer-provided encryption) and RequestPayer args.
GET_METADATA_EXTRA_ARGS = frozenset(
    ["SSECustomerAlgorithm", "SSECustomerKey", "SSECustomerKeyMD5", "RequestPayer"]
)


def object_present(
    name,
    source=None,
    hash_type=None,
    extra_args=None,
    extra_args_from_pillar="boto_s3_object_extra_args",
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Ensure object exists in S3.

    name
        The name of the state definition.
        This will be used to determine the location of the object in S3,
        by splitting on the first slash and using the first part
        as the bucket name and the remainder as the S3 key.

    source
        The source file to upload to S3,
        currently this only supports files hosted on the minion's local
        file system (starting with /).

    hash_type
        Hash algorithm to use to check that the object contents are correct.
        Defaults to the value of the `hash_type` config option.

    extra_args
        A dictionary of extra arguments to use when uploading the file.
        Note that these are only enforced if new objects are uploaded,
        and not modified on existing objects.
        The supported args are those in the ALLOWED_UPLOAD_ARGS list at
        http://boto3.readthedocs.io/en/latest/reference/customizations/s3.html.
        However, Note that the 'ACL', 'GrantFullControl', 'GrantRead',
        'GrantReadACP',  and 'GrantWriteACL' keys are currently not supported.

    extra_args_from_pillar
        Name of pillar dict that contains extra arguments.
        Extra arguments defined for this specific state will be
        merged over those from the pillar.

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string) that
        contains a dict with region, key and keyid.
    """
    ret = {
        "name": name,
        "comment": "",
        "changes": {},
    }

    if extra_args is None:
        extra_args = {}
    combined_extra_args = copy.deepcopy(
        __salt__["config.option"](extra_args_from_pillar, {})
    )
    __utils__["dictupdate.update"](combined_extra_args, extra_args)
    if combined_extra_args:
        supported_args = STORED_EXTRA_ARGS | UPLOAD_ONLY_EXTRA_ARGS
        combined_extra_args_keys = frozenset(six.iterkeys(combined_extra_args))
        extra_keys = combined_extra_args_keys - supported_args
        if extra_keys:
            msg = "extra_args keys {0} are not supported".format(extra_keys)
            return {"error": msg}

    # Get the hash of the local file
    if not hash_type:
        hash_type = __opts__["hash_type"]
    try:
        digest = salt.utils.hashutils.get_hash(source, form=hash_type)
    except IOError as e:
        ret["result"] = False
        ret["comment"] = "Could not read local file {0}: {1}".format(source, e,)
        return ret
    except ValueError as e:
        # Invalid hash type exception from get_hash
        ret["result"] = False
        ret["comment"] = "Could not hash local file {0}: {1}".format(source, e,)
        return ret

    HASH_METADATA_KEY = "salt_managed_content_hash"
    combined_extra_args.setdefault("Metadata", {})
    if HASH_METADATA_KEY in combined_extra_args["Metadata"]:
        # Be lenient, silently allow hash metadata key if digest value matches
        if combined_extra_args["Metadata"][HASH_METADATA_KEY] != digest:
            ret["result"] = False
            ret["comment"] = (
                "Salt uses the {0} metadata key internally,"
                "do not pass it to the boto_s3.object_present state."
            ).format(HASH_METADATA_KEY)
            return ret
    combined_extra_args["Metadata"][HASH_METADATA_KEY] = digest
    # Remove upload-only keys from full set of extra_args
    # to create desired dict for comparisons
    desired_metadata = dict(
        (k, v)
        for k, v in six.iteritems(combined_extra_args)
        if k not in UPLOAD_ONLY_EXTRA_ARGS
    )

    # Some args (SSE-C, RequestPayer) must also be passed to get_metadata
    metadata_extra_args = dict(
        (k, v)
        for k, v in six.iteritems(combined_extra_args)
        if k in GET_METADATA_EXTRA_ARGS
    )
    r = __salt__["boto_s3.get_object_metadata"](
        name,
        extra_args=metadata_extra_args,
        region=region,
        key=key,
        keyid=keyid,
        profile=profile,
    )
    if "error" in r:
        ret["result"] = False
        ret["comment"] = "Failed to check if S3 object exists: {0}.".format(r["error"],)
        return ret

    if r["result"]:
        # Check if content and metadata match
        # A hash of the content is injected into the metadata,
        # so we can combine both checks into one
        # Only check metadata keys specified by the user,
        # ignore other fields that have been set
        s3_metadata = dict(
            (k, r["result"][k])
            for k in STORED_EXTRA_ARGS
            if k in desired_metadata and k in r["result"]
        )
        if s3_metadata == desired_metadata:
            ret["result"] = True
            ret["comment"] = "S3 object {0} is present.".format(name)
            return ret
        action = "update"
    else:
        s3_metadata = None
        action = "create"

    def _yaml_safe_dump(attrs):
        """
        Safely dump YAML using a readable flow style
        """
        dumper_name = "IndentedSafeOrderedDumper"
        dumper = __utils__["yaml.get_dumper"](dumper_name)
        return __utils__["yaml.dump"](attrs, default_flow_style=False, Dumper=dumper)

    changes_diff = "".join(
        difflib.unified_diff(
            _yaml_safe_dump(s3_metadata).splitlines(True),
            _yaml_safe_dump(desired_metadata).splitlines(True),
        )
    )

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "S3 object {0} set to be {1}d.".format(name, action)
        ret["comment"] += "\nChanges:\n{0}".format(changes_diff)
        ret["changes"] = {"diff": changes_diff}
        return ret

    r = __salt__["boto_s3.upload_file"](
        source,
        name,
        extra_args=combined_extra_args,
        region=region,
        key=key,
        keyid=keyid,
        profile=profile,
    )

    if "error" in r:
        ret["result"] = False
        ret["comment"] = "Failed to {0} S3 object: {1}.".format(action, r["error"],)
        return ret

    ret["result"] = True
    ret["comment"] = "S3 object {0} {1}d.".format(name, action)
    ret["comment"] += "\nChanges:\n{0}".format(changes_diff)
    ret["changes"] = {"diff": changes_diff}
    return ret
