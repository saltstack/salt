# -*- coding: utf-8 -*-

# Import future libs
from __future__ import absolute_import, print_function, unicode_literals

# Import 3rd-party libs
from io import BytesIO, StringIO

# Import salt module
import salt.modules.tomcat as tomcat
from salt.ext.six import string_types
from salt.ext.six.moves.urllib.request import (
    HTTPBasicAuthHandler as _HTTPBasicAuthHandler,
)
from salt.ext.six.moves.urllib.request import (
    HTTPDigestAuthHandler as _HTTPDigestAuthHandler,
)
from salt.ext.six.moves.urllib.request import build_opener as _build_opener

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class TomcatTestCasse(TestCase, LoaderModuleMockMixin):
    """
    Tests cases for salt.modules.tomcat
    """

    def setup_loader_modules(self):
        return {tomcat: {}}

    def test_tomcat_wget_no_bytestring(self):
        responses = {
            "string": StringIO("Best response ever\r\nAnd you know it!"),
            "bytes": BytesIO(b"Best response ever\r\nAnd you know it!"),
        }

        string_mock = MagicMock(return_value=responses["string"])
        bytes_mock = MagicMock(return_value=responses["bytes"])
        with patch(
            "salt.modules.tomcat._auth",
            MagicMock(
                return_value=_build_opener(
                    _HTTPBasicAuthHandler(), _HTTPDigestAuthHandler()
                )
            ),
        ):
            with patch("salt.modules.tomcat._urlopen", string_mock):
                response = tomcat._wget(
                    "tomcat.wait", url="http://localhost:8080/nofail"
                )
                for line in response["msg"]:
                    self.assertIsInstance(line, string_types)

            with patch("salt.modules.tomcat._urlopen", bytes_mock):
                try:
                    response = tomcat._wget(
                        "tomcat.wait", url="http://localhost:8080/nofail"
                    )
                except TypeError as type_error:
                    if (
                        type_error.args[0]
                        == "startswith first arg must be bytes or a tuple of bytes, not str"
                    ):
                        self.fail("Got back a byte string, should've been a string")
                    else:
                        raise type_error

                for line in response["msg"]:
                    self.assertIsInstance(line, string_types)
