"""
    Tests cases for salt.modules.tomcat
"""

import io
import urllib.request

import pytest

import salt.modules.tomcat as tomcat
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {tomcat: {}}


def test_tomcat_wget_no_bytestring():
    responses = {
        "string": io.StringIO("Best response ever\r\nAnd you know it!"),
        "bytes": io.BytesIO(b"Best response ever\r\nAnd you know it!"),
    }

    string_mock = MagicMock(return_value=responses["string"])
    bytes_mock = MagicMock(return_value=responses["bytes"])
    with patch(
        "salt.modules.tomcat._auth",
        MagicMock(
            return_value=urllib.request.build_opener(
                urllib.request.HTTPBasicAuthHandler(),
                urllib.request.HTTPDigestAuthHandler(),
            )
        ),
    ):
        with patch("urllib.request.urlopen", string_mock):
            response = tomcat._wget("tomcat.wait", url="http://localhost:8080/nofail")
            for line in response["msg"]:
                assert isinstance(line, str)

        with patch("urllib.request.urlopen", bytes_mock):
            try:
                response = tomcat._wget(
                    "tomcat.wait", url="http://localhost:8080/nofail"
                )
            except TypeError as type_error:
                if (
                    type_error.args[0]
                    == "startswith first arg must be bytes or a tuple of bytes,"
                    " not str"
                ):
                    print("Got back a byte string, should've been a string")
                else:
                    raise type_error

            for line in response["msg"]:
                assert isinstance(line, str)
