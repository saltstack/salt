"""
    tests.unit.utils.aws_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the salt aws functions
"""

import io
import os
import time
from datetime import datetime, timedelta

import pytest
import requests
from pytest_timeout import DEFAULT_METHOD

import salt.utils.aws as aws
from tests.support.helpers import patched_environ
from tests.support.mock import MagicMock, patch

pytestmark = [
    # Skip testing on windows since it does not support signal.SIGALRM
    # which is what the timeout marker is using by default.
    pytest.mark.skip_on_windows,
    pytest.mark.timeout(60, method=DEFAULT_METHOD),
]


@pytest.fixture(autouse=True)
def _cleanup():
    # Make sure this cache is clear before each test
    aws.__AssumeCache__.clear()
    # Remove any AWS_ prefixed environment variables
    with patched_environ(
        __cleanup__=[k for k in os.environ if k.startswith("AWS_")],
    ):
        yield


def test_get_metadata_imdsv1():
    response = requests.Response()
    response.status_code = 200
    response.reason = "OK"
    response.raw = io.BytesIO(b"""test""")
    with patch("requests.get", return_value=response):
        result = aws.get_metadata("/")
        assert result.text == "test"


def test_get_metadata_imdsv2():
    mock_token = "abc123"

    def handle_get_mock(_, **args):
        response = requests.Response()
        if (
            "X-aws-ec2-metadata-token" in args["headers"]
            and args["headers"]["X-aws-ec2-metadata-token"] == mock_token
        ):
            response.status_code = 200
            response.reason = "OK"
            response.raw = io.BytesIO(b"""test""")
        else:
            response.status_code = 401
            response.reason = "Unauthorized"
        return response

    put_response = requests.Response()
    put_response.status_code = 200
    put_response.reason = "OK"
    put_response.raw = io.BytesIO(mock_token.encode("utf-8"))

    with patch("requests.get", MagicMock(side_effect=handle_get_mock)), patch(
        "requests.put", return_value=put_response
    ):
        result = aws.get_metadata("/")
        assert result.text == "test"


def test_assumed_creds_not_updating_dictionary_while_iterating():
    mock_cache = {
        "expired": {
            "Expiration": time.mktime(datetime.utcnow().timetuple()),
        },
        "not_expired_1": {
            "Expiration": time.mktime(
                (datetime.utcnow() + timedelta(days=1)).timetuple()
            ),
            "AccessKeyId": "mock_AccessKeyId",
            "SecretAccessKey": "mock_SecretAccessKey",
            "SessionToken": "mock_SessionToken",
        },
        "not_expired_2": {
            "Expiration": time.mktime(
                (datetime.utcnow() + timedelta(seconds=300)).timetuple()
            ),
        },
    }
    with patch.dict(aws.__AssumeCache__, mock_cache):
        ret = aws.assumed_creds({}, "not_expired_1")
        assert "expired" not in aws.__AssumeCache__
        assert ret == ("mock_AccessKeyId", "mock_SecretAccessKey", "mock_SessionToken")


def test_assumed_creds_deletes_expired_key():
    mock_cache = {
        "expired": {
            "Expiration": time.mktime(datetime.utcnow().timetuple()),
        },
        "not_expired_1": {
            "Expiration": time.mktime(
                (datetime.utcnow() + timedelta(days=1)).timetuple()
            ),
            "AccessKeyId": "mock_AccessKeyId",
            "SecretAccessKey": "mock_SecretAccessKey",
            "SessionToken": "mock_SessionToken",
        },
        "not_expired_2": {
            "Expiration": time.mktime(
                (datetime.utcnow() + timedelta(seconds=300)).timetuple()
            ),
        },
    }
    creds_dict = {
        "AccessKeyId": "mock_AccessKeyId",
        "SecretAccessKey": "mock_SecretAccessKey",
        "SessionToken": "mock_SessionToken",
    }
    response_mock = MagicMock()
    response_mock.status_code = 200
    response_mock.json.return_value = {
        "AssumeRoleResponse": {
            "AssumeRoleResult": {
                "Credentials": creds_dict,
            },
        },
    }
    with patch.dict(aws.__AssumeCache__, mock_cache):
        with patch.object(aws, "sig4", return_value=({}, "fakeurl.com")):
            with patch("requests.request", return_value=response_mock):
                ret = aws.assumed_creds({}, "expired")
                assert "expired" in aws.__AssumeCache__
                assert aws.__AssumeCache__["expired"] == creds_dict
                assert ret == (
                    "mock_AccessKeyId",
                    "mock_SecretAccessKey",
                    "mock_SessionToken",
                )


def test_creds_with_role_arn_should_always_call_assumed_creds():
    role_arn = "arn:aws:iam::111111111111:role/my-role-to-assume"

    access_key_id = "mock_AccessKeyId"
    secret_access_key = "mock_SecretAccessKey"
    token = "mock_Token"
    expiration = (datetime.utcnow() + timedelta(seconds=900)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    patch_expiration = patch("salt.utils.aws.__Expiration__", new=expiration)

    def handle_get_metadata_mock(path, **args):
        response_metadata = MagicMock()
        response_metadata.status_code = 200
        if path == "meta-data/iam/security-credentials/":
            response_metadata.text = "Role"
        else:
            response_metadata.json.return_value = {
                "AccessKeyId": access_key_id,
                "SecretAccessKey": secret_access_key,
                "Token": token,
                "Expiration": expiration,
            }
        return response_metadata

    patch_get_metadata = patch.object(
        aws, "get_metadata", side_effect=handle_get_metadata_mock
    )

    assumed_access_key_id = "mock_assumed_AccessKeyId"
    assumed_secret_access_key = "mock_assumed_SecretAccessKey"
    assumed_session_token = "mock_assumed_SessionToken"
    assumed_creds_ret = (
        assumed_access_key_id,
        assumed_secret_access_key,
        assumed_session_token,
    )

    patch_assumed_creds = patch.object(
        aws, "assumed_creds", return_value=assumed_creds_ret
    )

    # test for the first call, with __Expiration__ = "" (default)
    with patch_get_metadata as mock_get_metadata:
        with patch_assumed_creds:
            result = aws.creds(
                {"id": aws.IROLE_CODE, "key": aws.IROLE_CODE, "role_arn": role_arn}
            )
            assert mock_get_metadata.call_count == 2
            assert result == assumed_creds_ret

    # test for the second call, with valid __Expiration__
    with patch_get_metadata as mock_get_metadata:
        with patch_expiration, patch_assumed_creds:
            result = aws.creds(
                {"id": aws.IROLE_CODE, "key": aws.IROLE_CODE, "role_arn": role_arn}
            )
            assert mock_get_metadata.call_count == 0
            assert result == assumed_creds_ret
