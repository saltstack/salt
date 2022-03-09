"""
Manage CloudTrail Objects
=========================

.. versionadded:: 2016.3.0

Create and destroy CloudTrail objects. Be aware that this interacts with Amazon's services,
and so may incur charges.

:depends:
    - boto
    - boto3

The dependencies listed above can be installed via package or pip.

This module accepts explicit vpc credentials but can also utilize
IAM roles assigned to the instance through Instance Profiles. Dynamic
credentials are then automatically obtained from AWS API and no further
configuration is necessary. More information available `here
<http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html>`_.

If IAM roles are not used you need to specify them either in a pillar file or
in the minion's config file:

.. code-block:: yaml

    vpc.keyid: GKTADJGHEIQSXMKKRBJ08H
    vpc.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

It's also possible to specify ``key``, ``keyid`` and ``region`` via a profile,
either passed in as a dict, or as a string to pull from pillars or minion
config:

.. code-block:: yaml

    myprofile:
        keyid: GKTADJGHEIQSXMKKRBJ08H
        key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

.. code-block:: yaml

    Ensure trail exists:
        boto_cloudtrail.present:
            - Name: mytrail
            - S3BucketName: mybucket
            - S3KeyPrefix: prefix
            - region: us-east-1
            - keyid: GKTADJGHEIQSXMKKRBJ08H
            - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

"""


import logging
import os
import os.path

import salt.utils.data

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load if boto is available.
    """
    if "boto_cloudtrail.exists" in __salt__:
        return "boto_cloudtrail"
    return (False, "boto_cloudtrail module could not be loaded")


def present(
    name,
    Name,
    S3BucketName,
    S3KeyPrefix=None,
    SnsTopicName=None,
    IncludeGlobalServiceEvents=True,
    IsMultiRegionTrail=None,
    EnableLogFileValidation=False,
    CloudWatchLogsLogGroupArn=None,
    CloudWatchLogsRoleArn=None,
    KmsKeyId=None,
    LoggingEnabled=True,
    Tags=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Ensure trail exists.

    name
        The name of the state definition

    Name
        Name of the trail.

    S3BucketName
        Specifies the name of the Amazon S3 bucket designated for publishing log
        files.

    S3KeyPrefix
        Specifies the Amazon S3 key prefix that comes after the name of the
        bucket you have designated for log file delivery.

    SnsTopicName
        Specifies the name of the Amazon SNS topic defined for notification of
        log file delivery. The maximum length is 256 characters.

    IncludeGlobalServiceEvents
        Specifies whether the trail is publishing events from global services
        such as IAM to the log files.

    EnableLogFileValidation
        Specifies whether log file integrity validation is enabled. The default
        is false.

    CloudWatchLogsLogGroupArn
        Specifies a log group name using an Amazon Resource Name (ARN), a unique
        identifier that represents the log group to which CloudTrail logs will
        be delivered. Not required unless you specify CloudWatchLogsRoleArn.

    CloudWatchLogsRoleArn
        Specifies the role for the CloudWatch Logs endpoint to assume to write
        to a user's log group.

    KmsKeyId
        Specifies the KMS key ID to use to encrypt the logs delivered by
        CloudTrail. The value can be a an alias name prefixed by "alias/", a
        fully specified ARN to an alias, a fully specified ARN to a key, or a
        globally unique identifier.

    LoggingEnabled
        Whether logging should be enabled for the trail

    Tags
        A dictionary of tags that should be set on the trail

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
    ret = {"name": Name, "result": True, "comment": "", "changes": {}}

    r = __salt__["boto_cloudtrail.exists"](
        Name=Name, region=region, key=key, keyid=keyid, profile=profile
    )

    if "error" in r:
        ret["result"] = False
        ret["comment"] = "Failed to create trail: {}.".format(r["error"]["message"])
        return ret

    if not r.get("exists"):
        if __opts__["test"]:
            ret["comment"] = "CloudTrail {} is set to be created.".format(Name)
            ret["result"] = None
            return ret
        r = __salt__["boto_cloudtrail.create"](
            Name=Name,
            S3BucketName=S3BucketName,
            S3KeyPrefix=S3KeyPrefix,
            SnsTopicName=SnsTopicName,
            IncludeGlobalServiceEvents=IncludeGlobalServiceEvents,
            IsMultiRegionTrail=IsMultiRegionTrail,
            EnableLogFileValidation=EnableLogFileValidation,
            CloudWatchLogsLogGroupArn=CloudWatchLogsLogGroupArn,
            CloudWatchLogsRoleArn=CloudWatchLogsRoleArn,
            KmsKeyId=KmsKeyId,
            region=region,
            key=key,
            keyid=keyid,
            profile=profile,
        )
        if not r.get("created"):
            ret["result"] = False
            ret["comment"] = "Failed to create trail: {}.".format(r["error"]["message"])
            return ret
        _describe = __salt__["boto_cloudtrail.describe"](
            Name, region=region, key=key, keyid=keyid, profile=profile
        )
        ret["changes"]["old"] = {"trail": None}
        ret["changes"]["new"] = _describe
        ret["comment"] = "CloudTrail {} created.".format(Name)

        if LoggingEnabled:
            r = __salt__["boto_cloudtrail.start_logging"](
                Name=Name, region=region, key=key, keyid=keyid, profile=profile
            )
            if "error" in r:
                ret["result"] = False
                ret["comment"] = "Failed to create trail: {}.".format(
                    r["error"]["message"]
                )
                ret["changes"] = {}
                return ret
            ret["changes"]["new"]["trail"]["LoggingEnabled"] = True
        else:
            ret["changes"]["new"]["trail"]["LoggingEnabled"] = False

        if bool(Tags):
            r = __salt__["boto_cloudtrail.add_tags"](
                Name=Name, region=region, key=key, keyid=keyid, profile=profile, **Tags
            )
            if not r.get("tagged"):
                ret["result"] = False
                ret["comment"] = "Failed to create trail: {}.".format(
                    r["error"]["message"]
                )
                ret["changes"] = {}
                return ret
            ret["changes"]["new"]["trail"]["Tags"] = Tags
        return ret

    ret["comment"] = os.linesep.join(
        [ret["comment"], "CloudTrail {} is present.".format(Name)]
    )
    ret["changes"] = {}
    # trail exists, ensure config matches
    _describe = __salt__["boto_cloudtrail.describe"](
        Name=Name, region=region, key=key, keyid=keyid, profile=profile
    )
    if "error" in _describe:
        ret["result"] = False
        ret["comment"] = "Failed to update trail: {}.".format(
            _describe["error"]["message"]
        )
        ret["changes"] = {}
        return ret
    _describe = _describe.get("trail")

    r = __salt__["boto_cloudtrail.status"](
        Name=Name, region=region, key=key, keyid=keyid, profile=profile
    )
    _describe["LoggingEnabled"] = r.get("trail", {}).get("IsLogging", False)

    need_update = False
    bucket_vars = {
        "S3BucketName": "S3BucketName",
        "S3KeyPrefix": "S3KeyPrefix",
        "SnsTopicName": "SnsTopicName",
        "IncludeGlobalServiceEvents": "IncludeGlobalServiceEvents",
        "IsMultiRegionTrail": "IsMultiRegionTrail",
        "EnableLogFileValidation": "LogFileValidationEnabled",
        "CloudWatchLogsLogGroupArn": "CloudWatchLogsLogGroupArn",
        "CloudWatchLogsRoleArn": "CloudWatchLogsRoleArn",
        "KmsKeyId": "KmsKeyId",
        "LoggingEnabled": "LoggingEnabled",
    }

    for invar, outvar in bucket_vars.items():
        if _describe[outvar] != locals()[invar]:
            need_update = True
            ret["changes"].setdefault("new", {})[invar] = locals()[invar]
            ret["changes"].setdefault("old", {})[invar] = _describe[outvar]

    r = __salt__["boto_cloudtrail.list_tags"](
        Name=Name, region=region, key=key, keyid=keyid, profile=profile
    )
    _describe["Tags"] = r.get("tags", {})
    tagchange = salt.utils.data.compare_dicts(_describe["Tags"], Tags)
    if bool(tagchange):
        need_update = True
        ret["changes"].setdefault("new", {})["Tags"] = Tags
        ret["changes"].setdefault("old", {})["Tags"] = _describe["Tags"]

    if need_update:
        if __opts__["test"]:
            msg = "CloudTrail {} set to be modified.".format(Name)
            ret["comment"] = msg
            ret["result"] = None
            return ret

        ret["comment"] = os.linesep.join([ret["comment"], "CloudTrail to be modified"])
        r = __salt__["boto_cloudtrail.update"](
            Name=Name,
            S3BucketName=S3BucketName,
            S3KeyPrefix=S3KeyPrefix,
            SnsTopicName=SnsTopicName,
            IncludeGlobalServiceEvents=IncludeGlobalServiceEvents,
            IsMultiRegionTrail=IsMultiRegionTrail,
            EnableLogFileValidation=EnableLogFileValidation,
            CloudWatchLogsLogGroupArn=CloudWatchLogsLogGroupArn,
            CloudWatchLogsRoleArn=CloudWatchLogsRoleArn,
            KmsKeyId=KmsKeyId,
            region=region,
            key=key,
            keyid=keyid,
            profile=profile,
        )
        if not r.get("updated"):
            ret["result"] = False
            ret["comment"] = "Failed to update trail: {}.".format(r["error"]["message"])
            ret["changes"] = {}
            return ret

        if LoggingEnabled:
            r = __salt__["boto_cloudtrail.start_logging"](
                Name=Name, region=region, key=key, keyid=keyid, profile=profile
            )
            if not r.get("started"):
                ret["result"] = False
                ret["comment"] = "Failed to update trail: {}.".format(
                    r["error"]["message"]
                )
                ret["changes"] = {}
                return ret
        else:
            r = __salt__["boto_cloudtrail.stop_logging"](
                Name=Name, region=region, key=key, keyid=keyid, profile=profile
            )
            if not r.get("stopped"):
                ret["result"] = False
                ret["comment"] = "Failed to update trail: {}.".format(
                    r["error"]["message"]
                )
                ret["changes"] = {}
                return ret

        if bool(tagchange):
            adds = {}
            removes = {}
            for k, diff in tagchange.items():
                if diff.get("new", "") != "":
                    # there's an update for this key
                    adds[k] = Tags[k]
                elif diff.get("old", "") != "":
                    removes[k] = _describe["Tags"][k]
            if bool(adds):
                r = __salt__["boto_cloudtrail.add_tags"](
                    Name=Name,
                    region=region,
                    key=key,
                    keyid=keyid,
                    profile=profile,
                    **adds
                )
            if bool(removes):
                r = __salt__["boto_cloudtrail.remove_tags"](
                    Name=Name,
                    region=region,
                    key=key,
                    keyid=keyid,
                    profile=profile,
                    **removes
                )

    return ret


def absent(name, Name, region=None, key=None, keyid=None, profile=None):
    """
    Ensure trail with passed properties is absent.

    name
        The name of the state definition.

    Name
        Name of the trail.

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

    ret = {"name": Name, "result": True, "comment": "", "changes": {}}

    r = __salt__["boto_cloudtrail.exists"](
        Name, region=region, key=key, keyid=keyid, profile=profile
    )
    if "error" in r:
        ret["result"] = False
        ret["comment"] = "Failed to delete trail: {}.".format(r["error"]["message"])
        return ret

    if r and not r["exists"]:
        ret["comment"] = "CloudTrail {} does not exist.".format(Name)
        return ret

    if __opts__["test"]:
        ret["comment"] = "CloudTrail {} is set to be removed.".format(Name)
        ret["result"] = None
        return ret
    r = __salt__["boto_cloudtrail.delete"](
        Name, region=region, key=key, keyid=keyid, profile=profile
    )
    if not r["deleted"]:
        ret["result"] = False
        ret["comment"] = "Failed to delete trail: {}.".format(r["error"]["message"])
        return ret
    ret["changes"]["old"] = {"trail": Name}
    ret["changes"]["new"] = {"trail": None}
    ret["comment"] = "CloudTrail {} deleted.".format(Name)
    return ret
