"""
Manage CloudFront distributions

.. versionadded:: 2018.3.0

Create, update and destroy CloudFront distributions.

This module accepts explicit AWS credentials but can also utilize
IAM roles assigned to the instance through Instance Profiles.
Dynamic credentials are then automatically obtained from AWS API
and no further configuration is necessary.
More information available `here
<https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html>`_.

If IAM roles are not used you need to specify them,
either in a pillar file or in the minion's config file:

.. code-block:: yaml

    cloudfront.keyid: GKTADJGHEIQSXMKKRBJ08H
    cloudfront.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

It's also possible to specify ``key``, ``keyid``, and ``region`` via a profile,
either passed in as a dict, or a string to pull from pillars or minion config:

.. code-block:: yaml

    myprofile:
        keyid: GKTADJGHEIQSXMKKRBJ08H
        key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
        region: us-east-1

.. code-block:: yaml

    aws:
        region:
            us-east-1:
                profile:
                    keyid: GKTADJGHEIQSXMKKRBJ08H
                    key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
                    region: us-east-1

:depends: boto3
"""

import difflib
import logging

log = logging.getLogger(__name__)

__deprecated__ = (
    3009,
    "boto",
    "https://github.com/salt-extensions/saltext-boto",
)


def __virtual__():
    """
    Only load if boto is available.
    """
    if "boto_cloudfront.get_distribution" not in __salt__:
        msg = "The boto_cloudfront state module could not be loaded: {}."
        return (False, msg.format("boto_cloudfront exec module unavailable."))
    return "boto_cloudfront"


def present(
    name,
    config,
    tags,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Ensure the CloudFront distribution is present.

    name (string)
        Name of the CloudFront distribution

    config (dict)
        Configuration for the distribution

    tags (dict)
        Tags to associate with the distribution

    region (string)
        Region to connect to

    key (string)
        Secret key to use

    keyid (string)
        Access key to use

    profile (dict or string)
        A dict with region, key, and keyid,
        or a pillar key (string) that contains such a dict.

    Example:

    .. code-block:: yaml

        Manage my_distribution CloudFront distribution:
            boto_cloudfront.present:
              - name: my_distribution
              - config:
                  Comment: 'partial config shown, most parameters elided'
                  Enabled: True
              - tags:
                  testing_key: testing_value
    """
    ret = {
        "name": name,
        "comment": "",
        "changes": {},
    }

    res = __salt__["boto_cloudfront.get_distribution"](
        name,
        region=region,
        key=key,
        keyid=keyid,
        profile=profile,
    )
    if "error" in res:
        ret["result"] = False
        ret["comment"] = "Error checking distribution {}: {}".format(
            name,
            res["error"],
        )
        return ret

    old = res["result"]
    if old is None:
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = f"Distribution {name} set for creation."
            ret["changes"] = {"old": None, "new": name}
            return ret

        res = __salt__["boto_cloudfront.create_distribution"](
            name,
            config,
            tags,
            region=region,
            key=key,
            keyid=keyid,
            profile=profile,
        )
        if "error" in res:
            ret["result"] = False
            ret["comment"] = "Error creating distribution {}: {}".format(
                name,
                res["error"],
            )
            return ret

        ret["result"] = True
        ret["comment"] = f"Created distribution {name}."
        ret["changes"] = {"old": None, "new": name}
        return ret
    else:
        full_config_old = {
            "config": old["distribution"]["DistributionConfig"],
            "tags": old["tags"],
        }
        full_config_new = {
            "config": config,
            "tags": tags,
        }
        diffed_config = __utils__["dictdiffer.deep_diff"](
            full_config_old,
            full_config_new,
        )

        def _yaml_safe_dump(attrs):
            """
            Safely dump YAML using a readable flow style
            """
            dumper_name = "IndentedSafeOrderedDumper"
            dumper = __utils__["yaml.get_dumper"](dumper_name)
            return __utils__["yaml.dump"](
                attrs, default_flow_style=False, Dumper=dumper
            )

        changes_diff = "".join(
            difflib.unified_diff(
                _yaml_safe_dump(full_config_old).splitlines(True),
                _yaml_safe_dump(full_config_new).splitlines(True),
            )
        )

        any_changes = bool("old" in diffed_config or "new" in diffed_config)
        if not any_changes:
            ret["result"] = True
            ret["comment"] = "Distribution {} has correct config.".format(
                name,
            )
            return ret

        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "\n".join(
                [f"Distribution {name} set for new config:", changes_diff]
            )
            ret["changes"] = {"diff": changes_diff}
            return ret

        res = __salt__["boto_cloudfront.update_distribution"](
            name,
            config,
            tags,
            region=region,
            key=key,
            keyid=keyid,
            profile=profile,
        )
        if "error" in res:
            ret["result"] = False
            ret["comment"] = "Error updating distribution {}: {}".format(
                name,
                res["error"],
            )
            return ret

        ret["result"] = True
        ret["comment"] = f"Updated distribution {name}."
        ret["changes"] = {"diff": changes_diff}
        return ret
