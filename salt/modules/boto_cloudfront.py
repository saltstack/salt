# -*- coding: utf-8 -*-
"""
Connection module for Amazon CloudFront

.. versionadded:: 2018.3.0

:depends: boto3

:configuration: This module accepts explicit AWS credentials but can also
    utilize IAM roles assigned to the instance through Instance Profiles or
    it can read them from the ~/.aws/credentials file or from these
    environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY.
    Dynamic credentials are then automatically obtained from AWS API and no
    further configuration is necessary. More information available at:

    .. code-block:: text

        http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/
            iam-roles-for-amazon-ec2.html

        http://boto3.readthedocs.io/en/latest/guide/
            configuration.html#guide-configuration

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file:

    .. code-block:: yaml

        cloudfront.keyid: GKTADJGHEIQSXMKKRBJ08H
        cloudfront.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration:

    .. code-block:: yaml

        cloudfront.region: us-east-1

    If a region is not specified, the default is us-east-1.

    It's also possible to specify key, keyid and region via a profile, either
    as a passed in dict, or as a string to pull from pillars or minion config:

    .. code-block:: yaml

        myprofile:
            keyid: GKTADJGHEIQSXMKKRBJ08H
            key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1
"""
# keep lint from choking on _get_conn and _cache_id
# pylint: disable=E0602

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import Salt libs
import salt.ext.six as six
import salt.utils.versions
from salt.utils.odict import OrderedDict

# Import third party libs
try:
    # pylint: disable=unused-import
    import boto3
    import botocore

    # pylint: enable=unused-import
    logging.getLogger("boto3").setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load if boto3 libraries exist.
    """
    has_boto_reqs = salt.utils.versions.check_boto_reqs()
    if has_boto_reqs is True:
        __utils__["boto3.assign_funcs"](__name__, "cloudfront")
    return has_boto_reqs


def _list_distributions(
    conn, name=None, region=None, key=None, keyid=None, profile=None,
):
    """
    Private function that returns an iterator over all CloudFront distributions.
    The caller is responsible for all boto-related error handling.

    name
        (Optional) Only yield the distribution with the given name
    """
    for dl_ in conn.get_paginator("list_distributions").paginate():
        distribution_list = dl_["DistributionList"]
        if "Items" not in distribution_list:
            # If there are no items, AWS omits the `Items` key for some reason
            continue
        for partial_dist in distribution_list["Items"]:
            tags = conn.list_tags_for_resource(Resource=partial_dist["ARN"])
            tags = dict((kv["Key"], kv["Value"]) for kv in tags["Tags"]["Items"])

            id_ = partial_dist["Id"]
            if "Name" not in tags:
                log.warning("CloudFront distribution %s has no Name tag.", id_)
                continue
            distribution_name = tags.pop("Name", None)
            if name is not None and distribution_name != name:
                continue

            # NOTE: list_distributions() returns a DistributionList,
            # which nominally contains a list of Distribution objects.
            # However, they are mangled in that they are missing values
            # (`Logging`, `ActiveTrustedSigners`, and `ETag` keys)
            # and moreover flatten the normally nested DistributionConfig
            # attributes to the top level.
            # Hence, we must call get_distribution() to get the full object,
            # and we cache these objects to help lessen API calls.
            distribution = _cache_id(
                "cloudfront",
                sub_resource=distribution_name,
                region=region,
                key=key,
                keyid=keyid,
                profile=profile,
            )
            if distribution:
                yield (distribution_name, distribution)
                continue

            dist_with_etag = conn.get_distribution(Id=id_)
            distribution = {
                "distribution": dist_with_etag["Distribution"],
                "etag": dist_with_etag["ETag"],
                "tags": tags,
            }
            _cache_id(
                "cloudfront",
                sub_resource=distribution_name,
                resource_id=distribution,
                region=region,
                key=key,
                keyid=keyid,
                profile=profile,
            )
            yield (distribution_name, distribution)


def get_distribution(name, region=None, key=None, keyid=None, profile=None):
    """
    Get information about a CloudFront distribution (configuration, tags) with a given name.

    name
        Name of the CloudFront distribution

    region
        Region to connect to

    key
        Secret key to use

    keyid
        Access key to use

    profile
        A dict with region, key, and keyid,
        or a pillar key (string) that contains such a dict.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cloudfront.get_distribution name=mydistribution profile=awsprofile

    """
    distribution = _cache_id(
        "cloudfront",
        sub_resource=name,
        region=region,
        key=key,
        keyid=keyid,
        profile=profile,
    )
    if distribution:
        return {"result": distribution}

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        for _, dist in _list_distributions(
            conn, name=name, region=region, key=key, keyid=keyid, profile=profile,
        ):
            # _list_distributions should only return the one distribution
            # that we want (with the given name).
            # In case of multiple distributions with the same name tag,
            # our use of caching means list_distributions will just
            # return the first one over and over again,
            # so only the first result is useful.
            if distribution is not None:
                msg = "More than one distribution found with name {0}"
                return {"error": msg.format(name)}
            distribution = dist
    except botocore.exceptions.ClientError as err:
        return {"error": __utils__["boto3.get_error"](err)}
    if not distribution:
        return {"result": None}

    _cache_id(
        "cloudfront",
        sub_resource=name,
        resource_id=distribution,
        region=region,
        key=key,
        keyid=keyid,
        profile=profile,
    )
    return {"result": distribution}


def export_distributions(region=None, key=None, keyid=None, profile=None):
    """
    Get details of all CloudFront distributions.
    Produces results that can be used to create an SLS file.

    CLI Example:

    .. code-block:: bash

        salt-call boto_cloudfront.export_distributions --out=txt |\
            sed "s/local: //" > cloudfront_distributions.sls

    """
    results = OrderedDict()
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        for name, distribution in _list_distributions(
            conn, region=region, key=key, keyid=keyid, profile=profile,
        ):
            config = distribution["distribution"]["DistributionConfig"]
            tags = distribution["tags"]

            distribution_sls_data = [
                {"name": name},
                {"config": config},
                {"tags": tags},
            ]
            results["Manage CloudFront distribution {0}".format(name)] = {
                "boto_cloudfront.present": distribution_sls_data,
            }
    except botocore.exceptions.ClientError as err:
        # Raise an exception, as this is meant to be user-invoked at the CLI
        # as opposed to being called from execution or state modules
        six.reraise(*sys.exc_info())

    dumper = __utils__["yaml.get_dumper"]("IndentedSafeOrderedDumper")
    return __utils__["yaml.dump"](results, default_flow_style=False, Dumper=dumper,)


def create_distribution(
    name, config, tags=None, region=None, key=None, keyid=None, profile=None,
):
    """
    Create a CloudFront distribution with the given name, config, and (optionally) tags.

    name
        Name for the CloudFront distribution

    config
        Configuration for the distribution

    tags
        Tags to associate with the distribution

    region
        Region to connect to

    key
        Secret key to use

    keyid
        Access key to use

    profile
        A dict with region, key, and keyid,
        or a pillar key (string) that contains such a dict.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cloudfront.create_distribution name=mydistribution profile=awsprofile \
            config='{"Comment":"partial configuration","Enabled":true}'
    """
    if tags is None:
        tags = {}
    if "Name" in tags:
        # Be lenient and silently accept if names match, else error
        if tags["Name"] != name:
            return {"error": "Must not pass `Name` in `tags` but as `name`"}
    tags["Name"] = name
    tags = {"Items": [{"Key": k, "Value": v} for k, v in six.iteritems(tags)]}

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        conn.create_distribution_with_tags(
            DistributionConfigWithTags={"DistributionConfig": config, "Tags": tags},
        )
        _cache_id(
            "cloudfront",
            sub_resource=name,
            invalidate=True,
            region=region,
            key=key,
            keyid=keyid,
            profile=profile,
        )
    except botocore.exceptions.ClientError as err:
        return {"error": __utils__["boto3.get_error"](err)}

    return {"result": True}


def update_distribution(
    name, config, tags=None, region=None, key=None, keyid=None, profile=None,
):
    """
    Update the config (and optionally tags) for the CloudFront distribution with the given name.

    name
        Name of the CloudFront distribution

    config
        Configuration for the distribution

    tags
        Tags to associate with the distribution

    region
        Region to connect to

    key
        Secret key to use

    keyid
        Access key to use

    profile
        A dict with region, key, and keyid,
        or a pillar key (string) that contains such a dict.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cloudfront.update_distribution name=mydistribution profile=awsprofile \
            config='{"Comment":"partial configuration","Enabled":true}'
    """
    distribution_ret = get_distribution(
        name, region=region, key=key, keyid=keyid, profile=profile
    )
    if "error" in distribution_ret:
        return distribution_ret
    dist_with_tags = distribution_ret["result"]

    current_distribution = dist_with_tags["distribution"]
    current_config = current_distribution["DistributionConfig"]
    current_tags = dist_with_tags["tags"]
    etag = dist_with_tags["etag"]

    config_diff = __utils__["dictdiffer.deep_diff"](current_config, config)
    if tags:
        tags_diff = __utils__["dictdiffer.deep_diff"](current_tags, tags)

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        if "old" in config_diff or "new" in config_diff:
            conn.update_distribution(
                DistributionConfig=config, Id=current_distribution["Id"], IfMatch=etag,
            )
        if tags:
            arn = current_distribution["ARN"]
            if "new" in tags_diff:
                tags_to_add = {
                    "Items": [
                        {"Key": k, "Value": v}
                        for k, v in six.iteritems(tags_diff["new"])
                    ],
                }
                conn.tag_resource(
                    Resource=arn, Tags=tags_to_add,
                )
            if "old" in tags_diff:
                tags_to_remove = {
                    "Items": list(tags_diff["old"].keys()),
                }
                conn.untag_resource(
                    Resource=arn, TagKeys=tags_to_remove,
                )
    except botocore.exceptions.ClientError as err:
        return {"error": __utils__["boto3.get_error"](err)}
    finally:
        _cache_id(
            "cloudfront",
            sub_resource=name,
            invalidate=True,
            region=region,
            key=key,
            keyid=keyid,
            profile=profile,
        )

    return {"result": True}
