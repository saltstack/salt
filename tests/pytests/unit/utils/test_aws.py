"""
    tests.unit.utils.aws_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the salt aws functions
"""

import io

import requests

from salt.utils.aws import get_metadata
from tests.support.mock import MagicMock, patch


def test_get_metadata_imdsv1():
    response = requests.Response()
    response.status_code = 200
    response.reason = "OK"
    response.raw = io.BytesIO(b"""test""")
    with patch("requests.get", return_value=response):
        result = get_metadata("/")
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
        result = get_metadata("/")
        assert result.text == "test"
