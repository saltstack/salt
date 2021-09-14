"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""

import socket
from contextlib import closing

import pytest
import salt.utils.http as http
from saltfactories.utils.tempfiles import temp_file
from tests.support.helpers import MirrorPostHandler, Webserver
from tests.support.mock import MagicMock, patch
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase, skipIf

try:
    import salt.ext.tornado.curl_httpclient  # pylint: disable=unused-import

    HAS_CURL = True
except ImportError:
    HAS_CURL = False


class HTTPTestCase(TestCase):
    """
    Unit TestCase for the salt.utils.http module.
    """

    @classmethod
    def setUpClass(cls):
        cls.post_webserver = Webserver(handler=MirrorPostHandler)
        cls.post_webserver.start()
        cls.post_web_root = cls.post_webserver.web_root

    @classmethod
    def tearDownClass(cls):
        cls.post_webserver.stop()
        del cls.post_webserver

    # sanitize_url tests

    def test_sanitize_url_hide_fields_none(self):
        """
        Tests sanitizing a url when the hide_fields kwarg is None.
        """
        mock_url = "https://api.testing.com/?&foo=bar&test=testing"
        ret = http.sanitize_url(mock_url, hide_fields=None)
        self.assertEqual(ret, mock_url)

    def test_sanitize_url_no_elements(self):
        """
        Tests sanitizing a url when no elements should be sanitized.
        """
        mock_url = "https://api.testing.com/?&foo=bar&test=testing"
        ret = http.sanitize_url(mock_url, [""])
        self.assertEqual(ret, mock_url)

    def test_sanitize_url_single_element(self):
        """
        Tests sanitizing a url with only a single element to be sanitized.
        """
        mock_url = (
            "https://api.testing.com/?&keep_it_secret=abcdefghijklmn"
            "&api_action=module.function"
        )
        mock_ret = (
            "https://api.testing.com/?&keep_it_secret=XXXXXXXXXX&"
            "api_action=module.function"
        )
        ret = http.sanitize_url(mock_url, ["keep_it_secret"])
        self.assertEqual(ret, mock_ret)

    def test_sanitize_url_multiple_elements(self):
        """
        Tests sanitizing a url with multiple elements to be sanitized.
        """
        mock_url = (
            "https://api.testing.com/?rootPass=badpassword%21"
            "&skipChecks=True&api_key=abcdefghijklmn"
            "&NodeID=12345&api_action=module.function"
        )
        mock_ret = (
            "https://api.testing.com/?rootPass=XXXXXXXXXX"
            "&skipChecks=True&api_key=XXXXXXXXXX"
            "&NodeID=12345&api_action=module.function"
        )
        ret = http.sanitize_url(mock_url, ["api_key", "rootPass"])
        self.assertEqual(ret, mock_ret)

    # _sanitize_components tests

    def test_sanitize_components_no_elements(self):
        """
        Tests when zero elements need to be sanitized.
        """
        mock_component_list = ["foo=bar", "bar=baz", "hello=world"]
        mock_ret = "foo=bar&bar=baz&hello=world&"
        ret = http._sanitize_url_components(mock_component_list, "api_key")
        self.assertEqual(ret, mock_ret)

    def test_sanitize_components_one_element(self):
        """
        Tests a single component to be sanitized.
        """
        mock_component_list = ["foo=bar", "api_key=abcdefghijklmnop"]
        mock_ret = "foo=bar&api_key=XXXXXXXXXX&"
        ret = http._sanitize_url_components(mock_component_list, "api_key")
        self.assertEqual(ret, mock_ret)

    def test_sanitize_components_multiple_elements(self):
        """
        Tests two componenets to be sanitized.
        """
        mock_component_list = ["foo=bar", "foo=baz", "api_key=testing"]
        mock_ret = "foo=XXXXXXXXXX&foo=XXXXXXXXXX&api_key=testing&"
        ret = http._sanitize_url_components(mock_component_list, "foo")
        self.assertEqual(ret, mock_ret)

    @pytest.mark.slow_test
    def test_query_null_response(self):
        """
        This tests that we get a null response when raise_error=False and the
        host/port cannot be reached.
        """
        host = "127.0.0.1"

        # Find unused port
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            sock.bind((host, 0))
            port = sock.getsockname()[1]

        url = "http://{host}:{port}/".format(host=host, port=port)
        result = http.query(url, raise_error=False)
        assert result == {"body": None}, result

    def test_query_error_handling(self):
        ret = http.query("http://127.0.0.1:0")
        self.assertTrue(isinstance(ret, dict))
        self.assertTrue(isinstance(ret.get("error", None), str))
        ret = http.query("http://myfoobardomainthatnotexist")
        self.assertTrue(isinstance(ret, dict))
        self.assertTrue(isinstance(ret.get("error", None), str))

    def test_parse_cookie_header(self):
        header = "; ".join(
            [
                "foo=bar",
                "expires=Mon, 03-Aug-20 14:26:27 GMT",
                "path=/",
                "domain=.mydomain.tld",
                "HttpOnly",
                "SameSite=Lax",
                "Secure",
            ]
        )
        ret = http.parse_cookie_header(header)
        cookie = ret.pop(0)
        assert cookie.name == "foo", cookie.name
        assert cookie.value == "bar", cookie.value
        assert cookie.expires == 1596464787, cookie.expires
        assert cookie.path == "/", cookie.path
        assert cookie.domain == ".mydomain.tld", cookie.domain
        assert cookie.secure
        # Only one cookie should have been returned, if anything is left in the
        # parse_cookie_header return then something went wrong.
        assert not ret


class HTTPPostTestCase(TestCase):
    """
    Unit TestCase for the salt.utils.http module when
    using POST method
    """

    @classmethod
    def setUpClass(cls):
        cls.post_webserver = Webserver(handler=MirrorPostHandler)
        cls.post_webserver.start()
        cls.post_web_root = cls.post_webserver.web_root

    @classmethod
    def tearDownClass(cls):
        cls.post_webserver.stop()
        del cls.post_webserver

    def test_requests_multipart_formdata_post(self):
        """
        Test handling of a multipart/form-data POST using the requests backend
        """
        match_this = (
            "{0}\r\nContent-Disposition: form-data;"
            ' name="fieldname_here"\r\n\r\nmydatahere\r\n{0}--\r\n'
        )
        ret = http.query(
            self.post_web_root,
            method="POST",
            data="mydatahere",
            formdata=True,
            formdata_fieldname="fieldname_here",
            backend="requests",
        )
        body = ret.get("body", "")
        boundary = body[: body.find("\r")]
        self.assertEqual(body, match_this.format(boundary))

    @skipIf(
        HAS_CURL is False, "Missing prerequisites for tornado.curl_httpclient library"
    )
    def test_query_proxy(self):
        """
        Test http.query with tornado and with proxy opts set
        and then test with no_proxy set to ensure we dont
        run into issue #55192 again.
        """
        data = "mydatahere"
        opts = {
            "proxy_host": "127.0.0.1",
            "proxy_port": 88,
            "proxy_username": "salt_test",
            "proxy_password": "super_secret",
        }

        mock_curl = MagicMock()

        with patch("tornado.httpclient.HTTPClient.fetch", mock_curl):
            ret = http.query(
                self.post_web_root,
                method="POST",
                data=data,
                backend="tornado",
                opts=opts,
            )

        for opt in opts:
            assert opt in mock_curl.call_args_list[0][1].keys()

        opts["no_proxy"] = ["127.0.0.1"]

        ret = http.query(
            self.post_web_root, method="POST", data=data, backend="tornado", opts=opts
        )
        body = ret.get("body", "")
        assert body == data


class HTTPGetTestCase(TestCase):
    """
    Unit TestCase for the salt.utils.http module when
    using Get method
    """

    @classmethod
    def setUpClass(cls):
        cls.get_webserver = Webserver()
        cls.get_webserver.start()

    @classmethod
    def tearDownClass(cls):
        cls.get_webserver.stop()
        del cls.get_webserver

    def test_backends_decode_body_false(self):
        """
        test all backends when using
        decode_body=False that it returns
        bytes and does not try to decode
        """
        for backend in ["tornado", "requests", "urllib2"]:
            ret = http.query(
                self.get_webserver.url("custom.tar.gz"),
                backend=backend,
                decode_body=False,
            )
            body = ret.get("body", "")
            assert isinstance(body, bytes)

    def test_backends_decode_body_true(self):
        """
        test all backends when using
        decode_body=True that it returns
        string and decodes it.
        """
        core_state = """
        {}:
          file:
            - managed
            - source: salt://testfile
            - makedirs: true
            """.format(
            RUNTIME_VARS.TMP
        )

        with temp_file("core.sls", core_state, self.get_webserver.root):
            for backend in ["tornado", "requests", "urllib2"]:
                ret = http.query(self.get_webserver.url("core.sls"), backend=backend)
                body = ret.get("body", "")
                assert isinstance(body, str)
