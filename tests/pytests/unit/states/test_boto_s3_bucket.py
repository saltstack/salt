import logging
import random
import string
from copy import deepcopy

import pytest

import salt.loader
import salt.states.boto_s3_bucket as boto_s3_bucket
from tests.support.mock import MagicMock, patch

boto = pytest.importorskip("boto")
boto3 = pytest.importorskip("boto3", "1.2.1")
botocore = pytest.importorskip("botocore", "1.4.41")

log = logging.getLogger(__name__)


class GlobalConfig:
    region = "us-east-1"
    access_key = "GKTADJGHEIQSXMKKRBJ08H"
    secret_key = "askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs"
    conn_parameters = {
        "region": region,
        "key": access_key,
        "keyid": secret_key,
        "profile": {},
    }
    error_message = (
        "An error occurred (101) when calling the {0} operation: Test-defined error"
    )
    not_found_error = botocore.exceptions.ClientError(
        {"Error": {"Code": "404", "Message": "Test-defined error"}}, "msg"
    )
    error_content = {"Error": {"Code": 101, "Message": "Test-defined error"}}
    list_ret = {
        "Buckets": [{"Name": "mybucket", "CreationDate": None}],
        "Owner": {
            "Type": "CanonicalUser",
            "DisplayName": "testuser",
            "ID": "111111222222",
        },
        "ResponseMetadata": {"Key": "Value"},
    }
    config_in = {
        "LocationConstraint": "EU",
        "ACL": {"ACL": "public-read"},
        "CORSRules": [{"AllowedMethods": ["GET"], "AllowedOrigins": ["*"]}],
        "LifecycleConfiguration": [
            {
                "Expiration": {"Days": 1},
                "Prefix": "prefix",
                "Status": "Enabled",
                "ID": "asdfghjklpoiuytrewq",
            }
        ],
        "Logging": {"TargetBucket": "my-bucket", "TargetPrefix": "prefix"},
        "NotificationConfiguration": {
            "LambdaFunctionConfigurations": [
                {
                    "LambdaFunctionArn": (
                        "arn:aws:lambda:us-east-1:111111222222:function:my-function"
                    ),
                    "Id": "zxcvbnmlkjhgfdsa",
                    "Events": ["s3:ObjectCreated:*"],
                    "Filter": {
                        "Key": {"FilterRules": [{"Name": "prefix", "Value": "string"}]}
                    },
                }
            ]
        },
        "Policy": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "",
                    "Effect": "Allow",
                    "Principal": {"AWS": "arn:aws:iam::111111222222:root"},
                    "Action": "s3:PutObject",
                    "Resource": "arn:aws:s3:::my-bucket/*",
                }
            ],
        },
        "Replication": {
            "Role": "arn:aws:iam::11111222222:my-role",
            "Rules": [
                {
                    "ID": "r1",
                    "Prefix": "prefix",
                    "Status": "Enabled",
                    "Destination": {"Bucket": "arn:aws:s3:::my-bucket"},
                }
            ],
        },
        "RequestPayment": {"Payer": "Requester"},
        "Tagging": {"a": "b", "c": "d"},
        "Versioning": {"Status": "Enabled"},
        "Website": {
            "ErrorDocument": {"Key": "error.html"},
            "IndexDocument": {"Suffix": "index.html"},
        },
    }
    config_ret = {
        "get_bucket_acl": {
            "Grants": [
                {
                    "Grantee": {
                        "Type": "Group",
                        "URI": "http://acs.amazonaws.com/groups/global/AllUsers",
                    },
                    "Permission": "READ",
                }
            ],
            "Owner": {"DisplayName": "testuser", "ID": "111111222222"},
        },
        "get_bucket_cors": {
            "CORSRules": [{"AllowedMethods": ["GET"], "AllowedOrigins": ["*"]}]
        },
        "get_bucket_lifecycle_configuration": {
            "Rules": [
                {
                    "Expiration": {"Days": 1},
                    "Prefix": "prefix",
                    "Status": "Enabled",
                    "ID": "asdfghjklpoiuytrewq",
                }
            ]
        },
        "get_bucket_location": {"LocationConstraint": "EU"},
        "get_bucket_logging": {
            "LoggingEnabled": {"TargetBucket": "my-bucket", "TargetPrefix": "prefix"}
        },
        "get_bucket_notification_configuration": {
            "LambdaFunctionConfigurations": [
                {
                    "LambdaFunctionArn": (
                        "arn:aws:lambda:us-east-1:111111222222:function:my-function"
                    ),
                    "Id": "zxcvbnmlkjhgfdsa",
                    "Events": ["s3:ObjectCreated:*"],
                    "Filter": {
                        "Key": {"FilterRules": [{"Name": "prefix", "Value": "string"}]}
                    },
                }
            ]
        },
        "get_bucket_policy": {
            "Policy": '{"Version":"2012-10-17","Statement":[{"Sid":"","Effect":"Allow","Principal":{"AWS":"arn:aws:iam::111111222222:root"},"Action":"s3:PutObject","Resource":"arn:aws:s3:::my-bucket/*"}]}'
        },
        "get_bucket_replication": {
            "ReplicationConfiguration": {
                "Role": "arn:aws:iam::11111222222:my-role",
                "Rules": [
                    {
                        "ID": "r1",
                        "Prefix": "prefix",
                        "Status": "Enabled",
                        "Destination": {"Bucket": "arn:aws:s3:::my-bucket"},
                    }
                ],
            }
        },
        "get_bucket_request_payment": {"Payer": "Requester"},
        "get_bucket_tagging": {
            "TagSet": [{"Key": "c", "Value": "d"}, {"Key": "a", "Value": "b"}]
        },
        "get_bucket_versioning": {"Status": "Enabled"},
        "get_bucket_website": {
            "ErrorDocument": {"Key": "error.html"},
            "IndexDocument": {"Suffix": "index.html"},
        },
    }
    bucket_ret = {"Location": "EU"}


@pytest.fixture
def global_config():
    GlobalConfig.conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    params = GlobalConfig()
    return params


@pytest.fixture
def session_instance():
    with patch("boto3.session.Session") as patched_session:
        yield patched_session()


@pytest.fixture
def configure_loader_modules(minion_opts):
    ctx = {}
    utils = salt.loader.utils(
        minion_opts,
        whitelist=["boto", "boto3", "args", "systemd", "path", "platform", "reg"],
        context=ctx,
    )
    serializers = salt.loader.serializers(minion_opts)
    funcs = salt.loader.minion_mods(
        minion_opts, context=ctx, utils=utils, whitelist=["boto_s3_bucket"]
    )
    salt_states = salt.loader.states(
        opts=minion_opts,
        functions=funcs,
        utils=utils,
        whitelist=["boto_s3_bucket"],
        serializers=serializers,
    )
    return {
        boto_s3_bucket: {
            "__opts__": minion_opts,
            "__salt__": funcs,
            "__utils__": utils,
            "__states__": salt_states,
            "__serializers__": serializers,
        }
    }


@pytest.mark.slow_test
def test_present_when_bucket_does_not_exist(global_config, session_instance):
    """
    Tests present on a bucket that does not exist.
    """
    conn = MagicMock()
    session_instance.client.return_value = conn

    conn.head_bucket.side_effect = [global_config.not_found_error, None]
    conn.list_buckets.return_value = deepcopy(global_config.list_ret)
    conn.create_bucket.return_value = global_config.bucket_ret
    for key, value in global_config.config_ret.items():
        getattr(conn, key).return_value = deepcopy(value)
    with patch.dict(
        boto_s3_bucket.__salt__,
        {"boto_iam.get_account_id": MagicMock(return_value="111111222222")},
    ):
        result = boto_s3_bucket.__states__["boto_s3_bucket.present"](
            "bucket present", Bucket="testbucket", **global_config.config_in
        )

    assert result["result"]
    assert (
        result["changes"]["new"]["bucket"]["Location"]
        == global_config.config_ret["get_bucket_location"]
    )


@pytest.mark.slow_test
def test_present_when_bucket_exists_no_mods(global_config, session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn

    conn.list_buckets.return_value = deepcopy(global_config.list_ret)
    for key, value in global_config.config_ret.items():
        getattr(conn, key).return_value = deepcopy(value)
    with patch.dict(
        boto_s3_bucket.__salt__,
        {"boto_iam.get_account_id": MagicMock(return_value="111111222222")},
    ):
        result = boto_s3_bucket.__states__["boto_s3_bucket.present"](
            "bucket present", Bucket="testbucket", **global_config.config_in
        )

    assert result["result"]
    assert result["changes"] == {}


@pytest.mark.slow_test
def test_present_when_bucket_exists_all_mods(global_config, session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn

    conn.list_buckets.return_value = deepcopy(global_config.list_ret)
    for key, value in global_config.config_ret.items():
        getattr(conn, key).return_value = deepcopy(value)
    with patch.dict(
        boto_s3_bucket.__salt__,
        {"boto_iam.get_account_id": MagicMock(return_value="111111222222")},
    ):
        result = boto_s3_bucket.__states__["boto_s3_bucket.present"](
            "bucket present",
            Bucket="testbucket",
            LocationConstraint=global_config.config_in["LocationConstraint"],
        )

    assert result["result"]
    assert result["changes"] != {}


@pytest.mark.slow_test
def test_present_with_failure(global_config, session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn

    conn.head_bucket.side_effect = [global_config.not_found_error, None]
    conn.list_buckets.return_value = deepcopy(global_config.list_ret)
    conn.create_bucket.side_effect = botocore.exceptions.ClientError(
        global_config.error_content, "create_bucket"
    )
    with patch.dict(
        boto_s3_bucket.__salt__,
        {"boto_iam.get_account_id": MagicMock(return_value="111111222222")},
    ):
        result = boto_s3_bucket.__states__["boto_s3_bucket.present"](
            "bucket present", Bucket="testbucket", **global_config.config_in
        )
    assert not result["result"]
    assert "Failed to create bucket" in result["comment"]


def test_absent_when_bucket_does_not_exist(global_config, session_instance):
    """
    Tests absent on a bucket that does not exist.
    """
    conn = MagicMock()
    session_instance.client.return_value = conn

    conn.head_bucket.side_effect = [global_config.not_found_error, None]
    result = boto_s3_bucket.__states__["boto_s3_bucket.absent"]("test", "mybucket")
    assert result["result"]
    assert result["changes"] == {}


def test_absent_when_bucket_exists(global_config, session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn

    result = boto_s3_bucket.__states__["boto_s3_bucket.absent"]("test", "testbucket")
    assert result["result"]
    assert result["changes"]["new"]["bucket"] is None


def test_absent_with_failure(global_config, session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn

    conn.delete_bucket.side_effect = botocore.exceptions.ClientError(
        global_config.error_content, "delete_bucket"
    )
    result = boto_s3_bucket.__states__["boto_s3_bucket.absent"]("test", "testbucket")
    assert not result["result"]
    assert "Failed to delete bucket" in result["comment"]
