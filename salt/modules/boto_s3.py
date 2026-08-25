"""
Connection module for Amazon S3 using boto3

.. versionadded:: 2018.3.0

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

:depends: boto3
"""

# keep lint from choking on _get_conn and _cache_id
# pylint: disable=E0602


import logging

import salt.utils.versions

log = logging.getLogger(__name__)

# pylint: disable=import-error
try:
    # pylint: disable=unused-import
    import boto3

    # pylint: enable=unused-import
    import botocore

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
    return salt.utils.versions.check_boto_reqs(boto3_ver="1.2.1")


def __init__(opts):  # pylint: disable=unused-argument
    if HAS_BOTO:
        __utils__["boto3.assign_funcs"](__name__, "s3")


def get_object_metadata(
    name,
    extra_args=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Get metadata about an S3 object.
    Returns None if the object does not exist.

    You can pass AWS SSE-C related args and/or RequestPayer in extra_args.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_s3.get_object_metadata \\
                         my_bucket/path/to/object \\
                         region=us-east-1 \\
                         key=key \\
                         keyid=keyid \\
                         profile=profile \\
    """
    bucket, _, s3_key = name.partition("/")
    if extra_args is None:
        extra_args = {}

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        metadata = conn.head_object(Bucket=bucket, Key=s3_key, **extra_args)
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Message"] == "Not Found":
            return {"result": None}
        return {"error": __utils__["boto3.get_error"](e)}

    return {"result": metadata}


def upload_file(
    source,
    name,
    extra_args=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Upload a local file as an S3 object.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_s3.upload_file \\
                         /path/to/local/file \\
                         my_bucket/path/to/object \\
                         region=us-east-1 \\
                         key=key \\
                         keyid=keyid \\
                         profile=profile \\
    """
    bucket, _, s3_key = name.partition("/")

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        conn.upload_file(source, bucket, s3_key, ExtraArgs=extra_args)
    except boto3.exceptions.S3UploadFailedError as e:
        return {"error": __utils__["boto3.get_error"](e)}

    log.info("S3 object uploaded to %s", name)
    return {"result": True}
