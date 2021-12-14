"""
Connection module for Amazon S3 Buckets

.. versionadded:: 2016.3.0

:depends:
    - boto
    - boto3

The dependencies listed above can be installed via package or pip.

:configuration: This module accepts explicit Lambda credentials but can also
    utilize IAM roles assigned to the instance through Instance Profiles.
    Dynamic credentials are then automatically obtained from AWS API and no
    further configuration is necessary. More Information available at:

    .. code-block:: text

        http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file:

    .. code-block:: yaml

        s3.keyid: GKTADJGHEIQSXMKKRBJ08H
        s3.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration:

    .. code-block:: yaml

        s3.region: us-east-1

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
#  disable complaints about perfectly valid non-assignment code
# pylint: disable=W0106


import logging

import salt.utils.compat
import salt.utils.json
import salt.utils.versions
from salt.exceptions import SaltInvocationError

log = logging.getLogger(__name__)


# pylint: disable=import-error
try:
    # pylint: disable=unused-import
    import boto
    import boto3

    # pylint: enable=unused-import
    from botocore.exceptions import ClientError

    logging.getLogger("boto3").setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False
# pylint: enable=import-error


def __virtual__():
    """
    Only load if boto libraries exist and if boto libraries are greater than
    a given version.
    """
    # the boto_lambda execution module relies on the connect_to_region() method
    # which was added in boto 2.8.0
    # https://github.com/boto/boto/commit/33ac26b416fbb48a60602542b4ce15dcc7029f12
    return salt.utils.versions.check_boto_reqs(boto3_ver="1.2.1")


def __init__(opts):
    if HAS_BOTO:
        __utils__["boto3.assign_funcs"](__name__, "s3")


def exists(Bucket, region=None, key=None, keyid=None, profile=None):
    """
    Given a bucket name, check to see if the given bucket exists.

    Returns True if the given bucket exists and returns False if the given
    bucket does not exist.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_s3_bucket.exists mybucket

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        buckets = conn.head_bucket(Bucket=Bucket)
        return {"exists": True}
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "404":
            return {"exists": False}
        err = __utils__["boto3.get_error"](e)
        return {"error": err}


def create(
    Bucket,
    ACL=None,
    LocationConstraint=None,
    GrantFullControl=None,
    GrantRead=None,
    GrantReadACP=None,
    GrantWrite=None,
    GrantWriteACP=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Given a valid config, create an S3 Bucket.

    Returns {created: true} if the bucket was created and returns
    {created: False} if the bucket was not created.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_s3_bucket.create my_bucket \\
                         GrantFullControl='emailaddress=example@example.com' \\
                         GrantRead='uri="http://acs.amazonaws.com/groups/global/AllUsers"' \\
                         GrantReadACP='emailaddress="exampl@example.com",id="2345678909876432"' \\
                         LocationConstraint=us-west-1

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        kwargs = {}
        for arg in (
            "ACL",
            "GrantFullControl",
            "GrantRead",
            "GrantReadACP",
            "GrantWrite",
            "GrantWriteACP",
        ):
            if locals()[arg] is not None:
                kwargs[arg] = str(locals()[arg])
        if LocationConstraint:
            kwargs["CreateBucketConfiguration"] = {
                "LocationConstraint": LocationConstraint
            }
        location = conn.create_bucket(Bucket=Bucket, **kwargs)
        conn.get_waiter("bucket_exists").wait(Bucket=Bucket)
        if location:
            log.info(
                "The newly created bucket name is located at %s", location["Location"]
            )

            return {"created": True, "name": Bucket, "Location": location["Location"]}
        else:
            log.warning("Bucket was not created")
            return {"created": False}
    except ClientError as e:
        return {"created": False, "error": __utils__["boto3.get_error"](e)}


def delete(
    Bucket,
    MFA=None,
    RequestPayer=None,
    Force=False,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Given a bucket name, delete it, optionally emptying it first.

    Returns {deleted: true} if the bucket was deleted and returns
    {deleted: false} if the bucket was not deleted.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_s3_bucket.delete mybucket

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        if Force:
            empty(
                Bucket,
                MFA=MFA,
                RequestPayer=RequestPayer,
                region=region,
                key=key,
                keyid=keyid,
                profile=profile,
            )
        conn.delete_bucket(Bucket=Bucket)
        return {"deleted": True}
    except ClientError as e:
        return {"deleted": False, "error": __utils__["boto3.get_error"](e)}


def delete_objects(
    Bucket,
    Delete,
    MFA=None,
    RequestPayer=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Delete objects in a given S3 bucket.

    Returns {deleted: true} if all objects were deleted
    and {deleted: false, failed: [key, ...]} otherwise

    CLI Example:

    .. code-block:: bash

        salt myminion boto_s3_bucket.delete_objects mybucket '{Objects: [Key: myobject]}'

    """

    if isinstance(Delete, str):
        Delete = salt.utils.json.loads(Delete)
    if not isinstance(Delete, dict):
        raise SaltInvocationError("Malformed Delete request.")
    if "Objects" not in Delete:
        raise SaltInvocationError("Malformed Delete request.")

    failed = []
    objs = Delete["Objects"]
    for i in range(0, len(objs), 1000):
        chunk = objs[i : i + 1000]
        subset = {"Objects": chunk, "Quiet": True}
        try:
            args = {"Bucket": Bucket}
            args.update({"MFA": MFA}) if MFA else None
            args.update({"RequestPayer": RequestPayer}) if RequestPayer else None
            args.update({"Delete": subset})
            conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
            ret = conn.delete_objects(**args)
            failed += ret.get("Errors", [])
        except ClientError as e:
            return {"deleted": False, "error": __utils__["boto3.get_error"](e)}

    if failed:
        return {"deleted": False, "failed": failed}
    else:
        return {"deleted": True}


def describe(Bucket, region=None, key=None, keyid=None, profile=None):
    """
    Given a bucket name describe its properties.

    Returns a dictionary of interesting properties.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_s3_bucket.describe mybucket

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        result = {}
        conn_dict = {
            "ACL": conn.get_bucket_acl,
            "CORS": conn.get_bucket_cors,
            "LifecycleConfiguration": conn.get_bucket_lifecycle_configuration,
            "Location": conn.get_bucket_location,
            "Logging": conn.get_bucket_logging,
            "NotificationConfiguration": conn.get_bucket_notification_configuration,
            "Policy": conn.get_bucket_policy,
            "Replication": conn.get_bucket_replication,
            "RequestPayment": conn.get_bucket_request_payment,
            "Versioning": conn.get_bucket_versioning,
            "Website": conn.get_bucket_website,
        }

        for key, query in conn_dict.items():
            try:
                data = query(Bucket=Bucket)
            except ClientError as e:
                if e.response.get("Error", {}).get("Code") in (
                    "NoSuchLifecycleConfiguration",
                    "NoSuchCORSConfiguration",
                    "NoSuchBucketPolicy",
                    "NoSuchWebsiteConfiguration",
                    "ReplicationConfigurationNotFoundError",
                    "NoSuchTagSet",
                ):
                    continue
                raise
            if "ResponseMetadata" in data:
                del data["ResponseMetadata"]
            result[key] = data

        tags = {}
        try:
            data = conn.get_bucket_tagging(Bucket=Bucket)
            for tagdef in data.get("TagSet"):
                tags[tagdef.get("Key")] = tagdef.get("Value")
        except ClientError as e:
            if not e.response.get("Error", {}).get("Code") == "NoSuchTagSet":
                raise
        if tags:
            result["Tagging"] = tags
        return {"bucket": result}
    except ClientError as e:
        err = __utils__["boto3.get_error"](e)
        if e.response.get("Error", {}).get("Code") == "NoSuchBucket":
            return {"bucket": None}
        return {"error": __utils__["boto3.get_error"](e)}


def empty(
    Bucket, MFA=None, RequestPayer=None, region=None, key=None, keyid=None, profile=None
):
    """
    Delete all objects in a given S3 bucket.

    Returns {deleted: true} if all objects were deleted
    and {deleted: false, failed: [key, ...]} otherwise

    CLI Example:

    .. code-block:: bash

        salt myminion boto_s3_bucket.empty mybucket

    """

    stuff = list_object_versions(
        Bucket, region=region, key=key, keyid=keyid, profile=profile
    )
    Delete = {}
    Delete["Objects"] = [
        {"Key": v["Key"], "VersionId": v["VersionId"]}
        for v in stuff.get("Versions", [])
    ]
    Delete["Objects"] += [
        {"Key": v["Key"], "VersionId": v["VersionId"]}
        for v in stuff.get("DeleteMarkers", [])
    ]
    if Delete["Objects"]:
        ret = delete_objects(
            Bucket,
            Delete,
            MFA=MFA,
            RequestPayer=RequestPayer,
            region=region,
            key=key,
            keyid=keyid,
            profile=profile,
        )
        failed = ret.get("failed", [])
        if failed:
            return {"deleted": False, "failed": ret[failed]}
    return {"deleted": True}


def list(region=None, key=None, keyid=None, profile=None):
    """
    List all buckets owned by the authenticated sender of the request.

    Returns list of buckets

    CLI Example:

    .. code-block:: yaml

        Owner: {...}
        Buckets:
          - {...}
          - {...}

    """
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        buckets = conn.list_buckets()
        if not bool(buckets.get("Buckets")):
            log.warning("No buckets found")
        if "ResponseMetadata" in buckets:
            del buckets["ResponseMetadata"]
        return buckets
    except ClientError as e:
        return {"error": __utils__["boto3.get_error"](e)}


def list_object_versions(
    Bucket,
    Delimiter=None,
    EncodingType=None,
    Prefix=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    List objects in a given S3 bucket.

    Returns a list of objects.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_s3_bucket.list_object_versions mybucket

    """

    try:
        Versions = []
        DeleteMarkers = []
        args = {"Bucket": Bucket}
        args.update({"Delimiter": Delimiter}) if Delimiter else None
        args.update({"EncodingType": EncodingType}) if Delimiter else None
        args.update({"Prefix": Prefix}) if Prefix else None
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        IsTruncated = True
        while IsTruncated:
            ret = conn.list_object_versions(**args)
            IsTruncated = ret.get("IsTruncated", False)
            if IsTruncated in ("True", "true", True):
                args["KeyMarker"] = ret["NextKeyMarker"]
                args["VersionIdMarker"] = ret["NextVersionIdMarker"]
            Versions += ret.get("Versions", [])
            DeleteMarkers += ret.get("DeleteMarkers", [])
        return {"Versions": Versions, "DeleteMarkers": DeleteMarkers}
    except ClientError as e:
        return {"error": __utils__["boto3.get_error"](e)}


def list_objects(
    Bucket,
    Delimiter=None,
    EncodingType=None,
    Prefix=None,
    FetchOwner=False,
    StartAfter=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    List objects in a given S3 bucket.

    Returns a list of objects.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_s3_bucket.list_objects mybucket

    """

    try:
        Contents = []
        args = {"Bucket": Bucket, "FetchOwner": FetchOwner}
        args.update({"Delimiter": Delimiter}) if Delimiter else None
        args.update({"EncodingType": EncodingType}) if Delimiter else None
        args.update({"Prefix": Prefix}) if Prefix else None
        args.update({"StartAfter": StartAfter}) if StartAfter else None
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        IsTruncated = True
        while IsTruncated:
            ret = conn.list_objects_v2(**args)
            IsTruncated = ret.get("IsTruncated", False)
            if IsTruncated in ("True", "true", True):
                args["ContinuationToken"] = ret["NextContinuationToken"]
            Contents += ret.get("Contents", [])
        return {"Contents": Contents}
    except ClientError as e:
        return {"error": __utils__["boto3.get_error"](e)}


def put_acl(
    Bucket,
    ACL=None,
    AccessControlPolicy=None,
    GrantFullControl=None,
    GrantRead=None,
    GrantReadACP=None,
    GrantWrite=None,
    GrantWriteACP=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Given a valid config, update the ACL for a bucket.

    Returns {updated: true} if the ACL was updated and returns
    {updated: False} if the ACL was not updated.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_s3_bucket.put_acl my_bucket 'public' \\
                         GrantFullControl='emailaddress=example@example.com' \\
                         GrantRead='uri="http://acs.amazonaws.com/groups/global/AllUsers"' \\
                         GrantReadACP='emailaddress="exampl@example.com",id="2345678909876432"'

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        kwargs = {}
        if AccessControlPolicy is not None:
            if isinstance(AccessControlPolicy, str):
                AccessControlPolicy = salt.utils.json.loads(AccessControlPolicy)
            kwargs["AccessControlPolicy"] = AccessControlPolicy
        for arg in (
            "ACL",
            "GrantFullControl",
            "GrantRead",
            "GrantReadACP",
            "GrantWrite",
            "GrantWriteACP",
        ):
            if locals()[arg] is not None:
                kwargs[arg] = str(locals()[arg])
        conn.put_bucket_acl(Bucket=Bucket, **kwargs)
        return {"updated": True, "name": Bucket}
    except ClientError as e:
        return {"updated": False, "error": __utils__["boto3.get_error"](e)}


def put_cors(Bucket, CORSRules, region=None, key=None, keyid=None, profile=None):
    """
    Given a valid config, update the CORS rules for a bucket.

    Returns {updated: true} if CORS was updated and returns
    {updated: False} if CORS was not updated.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_s3_bucket.put_cors my_bucket '[{\\
              "AllowedHeaders":[],\\
              "AllowedMethods":["GET"],\\
              "AllowedOrigins":["*"],\\
              "ExposeHeaders":[],\\
              "MaxAgeSeconds":123,\\
        }]'

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        if CORSRules is not None and isinstance(CORSRules, str):
            CORSRules = salt.utils.json.loads(CORSRules)
        conn.put_bucket_cors(Bucket=Bucket, CORSConfiguration={"CORSRules": CORSRules})
        return {"updated": True, "name": Bucket}
    except ClientError as e:
        return {"updated": False, "error": __utils__["boto3.get_error"](e)}


def put_lifecycle_configuration(
    Bucket, Rules, region=None, key=None, keyid=None, profile=None
):
    """
    Given a valid config, update the Lifecycle rules for a bucket.

    Returns {updated: true} if Lifecycle was updated and returns
    {updated: False} if Lifecycle was not updated.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_s3_bucket.put_lifecycle_configuration my_bucket '[{\\
              "Expiration": {...},\\
              "ID": "idstring",\\
              "Prefix": "prefixstring",\\
              "Status": "enabled",\\
              "Transitions": [{...},],\\
              "NoncurrentVersionTransitions": [{...},],\\
              "NoncurrentVersionExpiration": {...},\\
        }]'

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        if Rules is not None and isinstance(Rules, str):
            Rules = salt.utils.json.loads(Rules)
        conn.put_bucket_lifecycle_configuration(
            Bucket=Bucket, LifecycleConfiguration={"Rules": Rules}
        )
        return {"updated": True, "name": Bucket}
    except ClientError as e:
        return {"updated": False, "error": __utils__["boto3.get_error"](e)}


def put_logging(
    Bucket,
    TargetBucket=None,
    TargetPrefix=None,
    TargetGrants=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Given a valid config, update the logging parameters for a bucket.

    Returns {updated: true} if parameters were updated and returns
    {updated: False} if parameters were not updated.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_s3_bucket.put_logging my_bucket log_bucket '[{...}]' prefix

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        logstate = {}
        targets = {
            "TargetBucket": TargetBucket,
            "TargetGrants": TargetGrants,
            "TargetPrefix": TargetPrefix,
        }
        for key, val in targets.items():
            if val is not None:
                logstate[key] = val
        if logstate:
            logstatus = {"LoggingEnabled": logstate}
        else:
            logstatus = {}
        if TargetGrants is not None and isinstance(TargetGrants, str):
            TargetGrants = salt.utils.json.loads(TargetGrants)
        conn.put_bucket_logging(Bucket=Bucket, BucketLoggingStatus=logstatus)
        return {"updated": True, "name": Bucket}
    except ClientError as e:
        return {"updated": False, "error": __utils__["boto3.get_error"](e)}


def put_notification_configuration(
    Bucket,
    TopicConfigurations=None,
    QueueConfigurations=None,
    LambdaFunctionConfigurations=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Given a valid config, update the notification parameters for a bucket.

    Returns {updated: true} if parameters were updated and returns
    {updated: False} if parameters were not updated.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_s3_bucket.put_notification_configuration my_bucket
                [{...}] \\
                [{...}] \\
                [{...}]

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        if TopicConfigurations is None:
            TopicConfigurations = []
        elif isinstance(TopicConfigurations, str):
            TopicConfigurations = salt.utils.json.loads(TopicConfigurations)
        if QueueConfigurations is None:
            QueueConfigurations = []
        elif isinstance(QueueConfigurations, str):
            QueueConfigurations = salt.utils.json.loads(QueueConfigurations)
        if LambdaFunctionConfigurations is None:
            LambdaFunctionConfigurations = []
        elif isinstance(LambdaFunctionConfigurations, str):
            LambdaFunctionConfigurations = salt.utils.json.loads(
                LambdaFunctionConfigurations
            )
        # TODO allow the user to use simple names & substitute ARNs for those names
        conn.put_bucket_notification_configuration(
            Bucket=Bucket,
            NotificationConfiguration={
                "TopicConfigurations": TopicConfigurations,
                "QueueConfigurations": QueueConfigurations,
                "LambdaFunctionConfigurations": LambdaFunctionConfigurations,
            },
        )
        return {"updated": True, "name": Bucket}
    except ClientError as e:
        return {"updated": False, "error": __utils__["boto3.get_error"](e)}


def put_policy(Bucket, Policy, region=None, key=None, keyid=None, profile=None):
    """
    Given a valid config, update the policy for a bucket.

    Returns {updated: true} if policy was updated and returns
    {updated: False} if policy was not updated.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_s3_bucket.put_policy my_bucket {...}

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        if Policy is None:
            Policy = "{}"
        elif not isinstance(Policy, str):
            Policy = salt.utils.json.dumps(Policy)
        conn.put_bucket_policy(Bucket=Bucket, Policy=Policy)
        return {"updated": True, "name": Bucket}
    except ClientError as e:
        return {"updated": False, "error": __utils__["boto3.get_error"](e)}


def _get_role_arn(name, region=None, key=None, keyid=None, profile=None):
    if name.startswith("arn:aws:iam:"):
        return name

    account_id = __salt__["boto_iam.get_account_id"](
        region=region, key=key, keyid=keyid, profile=profile
    )
    if profile and "region" in profile:
        region = profile["region"]
    if region is None:
        region = "us-east-1"
    return "arn:aws:iam::{}:role/{}".format(account_id, name)


def put_replication(
    Bucket, Role, Rules, region=None, key=None, keyid=None, profile=None
):
    """
    Given a valid config, update the replication configuration for a bucket.

    Returns {updated: true} if replication configuration was updated and returns
    {updated: False} if replication configuration was not updated.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_s3_bucket.put_replication my_bucket my_role [...]

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        Role = _get_role_arn(
            name=Role, region=region, key=key, keyid=keyid, profile=profile
        )
        if Rules is None:
            Rules = []
        elif isinstance(Rules, str):
            Rules = salt.utils.json.loads(Rules)
        conn.put_bucket_replication(
            Bucket=Bucket, ReplicationConfiguration={"Role": Role, "Rules": Rules}
        )
        return {"updated": True, "name": Bucket}
    except ClientError as e:
        return {"updated": False, "error": __utils__["boto3.get_error"](e)}


def put_request_payment(Bucket, Payer, region=None, key=None, keyid=None, profile=None):
    """
    Given a valid config, update the request payment configuration for a bucket.

    Returns {updated: true} if request payment configuration was updated and returns
    {updated: False} if request payment configuration was not updated.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_s3_bucket.put_request_payment my_bucket Requester

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        conn.put_bucket_request_payment(
            Bucket=Bucket, RequestPaymentConfiguration={"Payer": Payer}
        )
        return {"updated": True, "name": Bucket}
    except ClientError as e:
        return {"updated": False, "error": __utils__["boto3.get_error"](e)}


def put_tagging(Bucket, region=None, key=None, keyid=None, profile=None, **kwargs):
    """
    Given a valid config, update the tags for a bucket.

    Returns {updated: true} if tags were updated and returns
    {updated: False} if tags were not updated.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_s3_bucket.put_tagging my_bucket my_role [...]

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        tagslist = []
        for k, v in kwargs.items():
            if str(k).startswith("__"):
                continue
            tagslist.append({"Key": str(k), "Value": str(v)})
        conn.put_bucket_tagging(Bucket=Bucket, Tagging={"TagSet": tagslist})
        return {"updated": True, "name": Bucket}
    except ClientError as e:
        return {"updated": False, "error": __utils__["boto3.get_error"](e)}


def put_versioning(
    Bucket,
    Status,
    MFADelete=None,
    MFA=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Given a valid config, update the versioning configuration for a bucket.

    Returns {updated: true} if versioning configuration was updated and returns
    {updated: False} if versioning configuration was not updated.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_s3_bucket.put_versioning my_bucket Enabled

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        VersioningConfiguration = {"Status": Status}
        if MFADelete is not None:
            VersioningConfiguration["MFADelete"] = MFADelete
        kwargs = {}
        if MFA is not None:
            kwargs["MFA"] = MFA
        conn.put_bucket_versioning(
            Bucket=Bucket, VersioningConfiguration=VersioningConfiguration, **kwargs
        )
        return {"updated": True, "name": Bucket}
    except ClientError as e:
        return {"updated": False, "error": __utils__["boto3.get_error"](e)}


def put_website(
    Bucket,
    ErrorDocument=None,
    IndexDocument=None,
    RedirectAllRequestsTo=None,
    RoutingRules=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Given a valid config, update the website configuration for a bucket.

    Returns {updated: true} if website configuration was updated and returns
    {updated: False} if website configuration was not updated.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_s3_bucket.put_website my_bucket IndexDocument='{"Suffix":"index.html"}'

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        WebsiteConfiguration = {}
        for key in (
            "ErrorDocument",
            "IndexDocument",
            "RedirectAllRequestsTo",
            "RoutingRules",
        ):
            val = locals()[key]
            if val is not None:
                if isinstance(val, str):
                    WebsiteConfiguration[key] = salt.utils.json.loads(val)
                else:
                    WebsiteConfiguration[key] = val
        conn.put_bucket_website(
            Bucket=Bucket, WebsiteConfiguration=WebsiteConfiguration
        )
        return {"updated": True, "name": Bucket}
    except ClientError as e:
        return {"updated": False, "error": __utils__["boto3.get_error"](e)}


def delete_cors(Bucket, region=None, key=None, keyid=None, profile=None):
    """
    Delete the CORS configuration for the given bucket

    Returns {deleted: true} if CORS was deleted and returns
    {deleted: False} if CORS was not deleted.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_s3_bucket.delete_cors my_bucket

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        conn.delete_bucket_cors(Bucket=Bucket)
        return {"deleted": True, "name": Bucket}
    except ClientError as e:
        return {"deleted": False, "error": __utils__["boto3.get_error"](e)}


def delete_lifecycle_configuration(
    Bucket, region=None, key=None, keyid=None, profile=None
):
    """
    Delete the lifecycle configuration for the given bucket

    Returns {deleted: true} if Lifecycle was deleted and returns
    {deleted: False} if Lifecycle was not deleted.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_s3_bucket.delete_lifecycle_configuration my_bucket

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        conn.delete_bucket_lifecycle(Bucket=Bucket)
        return {"deleted": True, "name": Bucket}
    except ClientError as e:
        return {"deleted": False, "error": __utils__["boto3.get_error"](e)}


def delete_policy(Bucket, region=None, key=None, keyid=None, profile=None):
    """
    Delete the policy from the given bucket

    Returns {deleted: true} if policy was deleted and returns
    {deleted: False} if policy was not deleted.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_s3_bucket.delete_policy my_bucket

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        conn.delete_bucket_policy(Bucket=Bucket)
        return {"deleted": True, "name": Bucket}
    except ClientError as e:
        return {"deleted": False, "error": __utils__["boto3.get_error"](e)}


def delete_replication(Bucket, region=None, key=None, keyid=None, profile=None):
    """
    Delete the replication config from the given bucket

    Returns {deleted: true} if replication configuration was deleted and returns
    {deleted: False} if replication configuration was not deleted.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_s3_bucket.delete_replication my_bucket

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        conn.delete_bucket_replication(Bucket=Bucket)
        return {"deleted": True, "name": Bucket}
    except ClientError as e:
        return {"deleted": False, "error": __utils__["boto3.get_error"](e)}


def delete_tagging(Bucket, region=None, key=None, keyid=None, profile=None):
    """
    Delete the tags from the given bucket

    Returns {deleted: true} if tags were deleted and returns
    {deleted: False} if tags were not deleted.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_s3_bucket.delete_tagging my_bucket

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        conn.delete_bucket_tagging(Bucket=Bucket)
        return {"deleted": True, "name": Bucket}
    except ClientError as e:
        return {"deleted": False, "error": __utils__["boto3.get_error"](e)}


def delete_website(Bucket, region=None, key=None, keyid=None, profile=None):
    """
    Remove the website configuration from the given bucket

    Returns {deleted: true} if website configuration was deleted and returns
    {deleted: False} if website configuration was not deleted.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_s3_bucket.delete_website my_bucket

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        conn.delete_bucket_website(Bucket=Bucket)
        return {"deleted": True, "name": Bucket}
    except ClientError as e:
        return {"deleted": False, "error": __utils__["boto3.get_error"](e)}
