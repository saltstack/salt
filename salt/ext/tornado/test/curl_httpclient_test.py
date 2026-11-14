# coding: utf-8
# pylint: skip-file
from __future__ import absolute_import, division, print_function

import gzip
from hashlib import md5

from salt.ext.tornado.escape import utf8
from salt.ext.tornado.httpclient import HTTPRequest
from salt.ext.tornado.stack_context import ExceptionStackContext
from salt.ext.tornado.testing import AsyncHTTPTestCase
from salt.ext.tornado.test import httpclient_test
from salt.ext.tornado.test.util import unittest
from salt.ext.tornado.web import Application, RequestHandler


try:
    import pycurl  # type: ignore
except ImportError:
    pycurl = None

if pycurl is not None:
    from salt.ext.tornado.curl_httpclient import CurlAsyncHTTPClient


@unittest.skipIf(pycurl is None, "pycurl module not present")
class CurlHTTPClientCommonTestCase(httpclient_test.HTTPClientCommonTestCase):
    def get_http_client(self):
        client = CurlAsyncHTTPClient(io_loop=self.io_loop,
                                     defaults=dict(allow_ipv6=False))
        # make sure AsyncHTTPClient magic doesn't give us the wrong class
        self.assertTrue(isinstance(client, CurlAsyncHTTPClient))
        return client


class DigestAuthHandler(RequestHandler):
    def get(self):
        realm = 'test'
        opaque = 'asdf'
        # Real implementations would use a random nonce.
        nonce = "1234"
        username = 'foo'
        password = 'bar'

        auth_header = self.request.headers.get('Authorization', None)
        if auth_header is not None:
            auth_mode, params = auth_header.split(' ', 1)
            assert auth_mode == 'Digest'
            param_dict = {}
            for pair in params.split(','):
                k, v = pair.strip().split('=', 1)
                if v[0] == '"' and v[-1] == '"':
                    v = v[1:-1]
                param_dict[k] = v
            assert param_dict['realm'] == realm
            assert param_dict['opaque'] == opaque
            assert param_dict['nonce'] == nonce
            assert param_dict['username'] == username
            assert param_dict['uri'] == self.request.path
            h1 = md5(utf8('%s:%s:%s' % (username, realm, password))).hexdigest()
            h2 = md5(utf8('%s:%s' % (self.request.method,
                                     self.request.path))).hexdigest()
            digest = md5(utf8('%s:%s:%s' % (h1, nonce, h2))).hexdigest()
            if digest == param_dict['response']:
                self.write('ok')
            else:
                self.write('fail')
        else:
            self.set_status(401)
            self.set_header('WWW-Authenticate',
                            'Digest realm="%s", nonce="%s", opaque="%s"' %
                            (realm, nonce, opaque))


class CustomReasonHandler(RequestHandler):
    def get(self):
        self.set_status(200, "Custom reason")


class CustomFailReasonHandler(RequestHandler):
    def get(self):
        self.set_status(400, "Custom reason")


@unittest.skipIf(pycurl is None, "pycurl module not present")
class CurlHTTPClientTestCase(AsyncHTTPTestCase):
    def setUp(self):
        super(CurlHTTPClientTestCase, self).setUp()
        self.http_client = self.create_client()

    def get_app(self):
        return Application([
            ('/digest', DigestAuthHandler),
            ('/custom_reason', CustomReasonHandler),
            ('/custom_fail_reason', CustomFailReasonHandler),
        ])

    def create_client(self, **kwargs):
        return CurlAsyncHTTPClient(self.io_loop, force_instance=True,
                                   defaults=dict(allow_ipv6=False),
                                   **kwargs)

    def test_prepare_curl_callback_stack_context(self):
        exc_info = []

        def error_handler(typ, value, tb):
            exc_info.append((typ, value, tb))
            self.stop()
            return True

        with ExceptionStackContext(error_handler):
            request = HTTPRequest(self.get_url('/'),
                                  prepare_curl_callback=lambda curl: 1 / 0)
        self.http_client.fetch(request, callback=self.stop)
        self.wait()
        self.assertEqual(1, len(exc_info))
        self.assertIs(exc_info[0][0], ZeroDivisionError)

    def test_digest_auth(self):
        response = self.fetch('/digest', auth_mode='digest',
                              auth_username='foo', auth_password='bar')
        self.assertEqual(response.body, b'ok')

    def test_custom_reason(self):
        response = self.fetch('/custom_reason')
        self.assertEqual(response.reason, "Custom reason")

    def test_fail_custom_reason(self):
        response = self.fetch('/custom_fail_reason')
        self.assertEqual(str(response.error), "HTTP 400: Custom reason")

    def test_failed_setup(self):
        self.http_client = self.create_client(max_clients=1)
        for i in range(5):
            response = self.fetch(u'/ユニコード')
            self.assertIsNot(response.error, None)


class ProxyAuthEchoHandler(RequestHandler):
    def get(self):
        if self.request.headers.get("Proxy-Authorization", None) is not None:
            self.write("proxy auth: %s" % self.request.headers["Proxy-Authorization"])
        else:
            self.write("no proxy auth")


@unittest.skipIf(pycurl is None, "pycurl module not present")
class CurlHTTPClientReuseProxyAuthTestCase(AsyncHTTPTestCase):
    def get_app(self):
        # Note that we don't properly support proxy-style requests, but it works
        # well enough for this test if we start the url matcher with a wildcard.
        return Application([(".*/proxy_auth", ProxyAuthEchoHandler)])

    def get_http_client(self):
        # max_clients=1 forces us to reuse curl "easy handles". This is a
        # regression test for a bug in which proxy credentials were not cleared
        # between requests.
        return CurlAsyncHTTPClient(
            self.io_loop, force_instance=True,
            defaults=dict(allow_ipv6=False), max_clients=1)

    def test_reuse_proxy_credentials(self):
        # Proxy credentials used on one request should not be automatically
        # reused by another request.
        response = self.fetch(
            "/proxy_auth",
            proxy_host="127.0.0.1",
            proxy_port=self.get_http_port(),
            proxy_username="foo",
            proxy_password="bar",
        )
        self.assertEqual(response.body, b"proxy auth: Basic Zm9vOmJhcg==")
        response = self.fetch(
            "/proxy_auth",
            proxy_host="127.0.0.1",
            proxy_port=self.get_http_port(),
        )
        self.assertEqual(response.body, b"no proxy auth")


class BombHandler(RequestHandler):
    def get(self):
        # A "decompression bomb": a small response that expands to far more
        # than max_body_size once libcurl has decompressed it.
        self.set_header("Content-Encoding", "gzip")
        self.write(gzip.compress(b"\0" * (4 * 1024 * 1024)))


class SizeHandler(RequestHandler):
    def get(self):
        size = int(self.get_argument("size"))
        self.set_header("Content-Encoding", "gzip")
        self.write(gzip.compress(b"a" * size))


@unittest.skipIf(pycurl is None, "pycurl module not present")
class CurlMaxBodySizeTest(AsyncHTTPTestCase):
    """``max_body_size`` is measured against the decompressed size, and
    applies to responses with and without a ``streaming_callback``.
    """

    def get_app(self):
        return Application([("/bomb", BombHandler), ("/size", SizeHandler)])

    def get_http_client(self):
        # max_clients=1 forces handle reuse between the tests.
        return CurlAsyncHTTPClient(
            self.io_loop, force_instance=True,
            defaults=dict(allow_ipv6=False, decompress_response=True),
            max_clients=1, max_body_size=1024 * 1024)

    def test_bomb_is_refused(self):
        response = self.fetch("/bomb")
        self.assertEqual(response.code, 599)
        self.assertIn("max_body_size", str(response.error))

    def test_bomb_is_refused_when_streaming(self):
        chunks = []
        response = self.fetch("/bomb", streaming_callback=chunks.append)
        self.assertEqual(response.code, 599)
        self.assertIn("max_body_size", str(response.error))
        self.assertLessEqual(sum(len(c) for c in chunks), 1024 * 1024)

    def test_exactly_max_body_size_is_accepted(self):
        response = self.fetch("/size?size=%d" % (1024 * 1024))
        response.rethrow()
        self.assertEqual(len(response.body), 1024 * 1024)

    def test_one_byte_over_max_body_size_is_refused(self):
        response = self.fetch("/size?size=%d" % (1024 * 1024 + 1))
        self.assertEqual(response.code, 599)
        self.assertIn("max_body_size", str(response.error))

    def test_streaming_delivers_everything_before_response(self):
        chunks = []
        response = self.fetch("/size?size=%d" % (512 * 1024),
                              streaming_callback=chunks.append)
        response.rethrow()
        self.assertEqual(sum(len(c) for c in chunks), 512 * 1024)
