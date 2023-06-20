"""
    tests.unit.utils.aws_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the salt aws functions
"""

import io
import time
from datetime import datetime, timedelta

import requests

import salt.utils.aws as aws
from tests.support.mock import MagicMock, patch


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
