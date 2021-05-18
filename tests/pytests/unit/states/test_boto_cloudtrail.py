import logging
import random
import string

import pytest
import salt.config
import salt.loader
import salt.states.boto_cloudtrail as boto_cloudtrail
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
        {"Error": {"Code": "TrailNotFoundException", "Message": "Test-defined error"}},
        "msg",
    )
    error_content = {"Error": {"Code": 101, "Message": "Test-defined error"}}
    trail_ret = dict(
        Name="testtrail",
        IncludeGlobalServiceEvents=True,
        KmsKeyId=None,
        LogFileValidationEnabled=False,
        S3BucketName="auditinfo",
        TrailARN="arn:aws:cloudtrail:us-east-1:214351231622:trail/testtrail",
    )
    status_ret = dict(
        IsLogging=False,
        LatestCloudWatchLogsDeliveryError=None,
        LatestCloudWatchLogsDeliveryTime=None,
        LatestDeliveryError=None,
        LatestDeliveryTime=None,
        LatestDigestDeliveryError=None,
        LatestDigestDeliveryTime=None,
        LatestNotificationError=None,
        LatestNotificationTime=None,
        StartLoggingTime=None,
        StopLoggingTime=None,
    )


@pytest.fixture
def global_config():
    params = GlobalConfig()
    return params


@pytest.fixture
def configure_loader_modules():
    opts = salt.config.DEFAULT_MINION_OPTS.copy()
    opts["grains"] = salt.loader.grains(opts)
    ctx = {}
    utils = salt.loader.utils(
        opts,
        whitelist=["boto", "boto3", "args", "systemd", "path", "platform", "reg"],
        context=ctx,
    )
    serializers = salt.loader.serializers(opts)
    funcs = salt.loader.minion_mods(
        opts, context=ctx, utils=utils, whitelist=["boto_cloudtrail"]
    )
    salt_states = salt.loader.states(
        opts=opts,
        functions=funcs,
        utils=utils,
        whitelist=["boto_cloudtrail"],
        serializers=serializers,
    )
    return {
        boto_cloudtrail: {
            "__opts__": opts,
            "__salt__": funcs,
            "__utils__": utils,
            "__states__": salt_states,
            "__serializers__": serializers,
        }
    }


@pytest.mark.slow_test
def test_present_when_trail_does_not_exist(global_config):
    """
    Tests present on a trail that does not exist.
    """
    global_config.conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()

    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn

    conn.get_trail_status.side_effect = [
        global_config.not_found_error,
        global_config.status_ret,
    ]
    conn.create_trail.return_value = global_config.trail_ret
    conn.describe_trails.return_value = {"trailList": [global_config.trail_ret]}
    with patch.dict(
        boto_cloudtrail.__salt__,
        {"boto_iam.get_account_id": MagicMock(return_value="1234")},
    ):
        result = boto_cloudtrail.__states__["boto_cloudtrail.present"](
            "trail present",
            Name=global_config.trail_ret["Name"],
            S3BucketName=global_config.trail_ret["S3BucketName"],
        )

    assert result["result"]
    assert result["changes"]["new"]["trail"]["Name"] == global_config.trail_ret["Name"]


@pytest.mark.slow_test
def test_present_when_trail_exists(global_config):
    global_config.conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()

    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn

    conn.get_trail_status.return_value = global_config.status_ret
    conn.create_trail.return_value = global_config.trail_ret
    conn.describe_trails.return_value = {"trailList": [global_config.trail_ret]}
    with patch.dict(
        boto_cloudtrail.__salt__,
        {"boto_iam.get_account_id": MagicMock(return_value="1234")},
    ):
        result = boto_cloudtrail.__states__["boto_cloudtrail.present"](
            "trail present",
            Name=global_config.trail_ret["Name"],
            S3BucketName=global_config.trail_ret["S3BucketName"],
            LoggingEnabled=False,
        )
    assert result["result"]
    assert result["changes"] == {}


@pytest.mark.slow_test
def test_present_with_failure(global_config):
    global_config.conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()

    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn

    conn.get_trail_status.side_effect = [
        global_config.not_found_error,
        global_config.status_ret,
    ]
    conn.create_trail.side_effect = botocore.exceptions.ClientError(
        global_config.error_content, "create_trail"
    )
    with patch.dict(
        boto_cloudtrail.__salt__,
        {"boto_iam.get_account_id": MagicMock(return_value="1234")},
    ):
        result = boto_cloudtrail.__states__["boto_cloudtrail.present"](
            "trail present",
            Name=global_config.trail_ret["Name"],
            S3BucketName=global_config.trail_ret["S3BucketName"],
            LoggingEnabled=False,
        )
    assert not result["result"]
    assert "An error occurred" in result["comment"]


def test_absent_when_trail_does_not_exist(global_config):
    """
    Tests absent on a trail that does not exist.
    """
    global_config.conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()

    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn

    conn.get_trail_status.side_effect = global_config.not_found_error
    result = boto_cloudtrail.__states__["boto_cloudtrail.absent"]("test", "mytrail")
    assert result["result"]
    assert result["changes"] == {}


def test_absent_when_trail_exists(global_config):
    global_config.conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()

    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn

    conn.get_trail_status.return_value = global_config.status_ret
    result = boto_cloudtrail.__states__["boto_cloudtrail.absent"](
        "test", global_config.trail_ret["Name"]
    )
    assert result["result"]
    assert result["changes"]["new"]["trail"] is None


def test_absent_with_failure(global_config):
    global_config.conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()

    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn

    conn.get_trail_status.return_value = global_config.status_ret
    conn.delete_trail.side_effect = botocore.exceptions.ClientError(
        global_config.error_content, "delete_trail"
    )
    result = boto_cloudtrail.__states__["boto_cloudtrail.absent"](
        "test", global_config.trail_ret["Name"]
    )
    assert not result["result"]
    assert "An error occurred" in result["comment"]
