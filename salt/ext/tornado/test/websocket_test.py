# pylint: skip-file
from __future__ import absolute_import, division, print_function

import functools
import sys
import traceback

from salt.ext.tornado.concurrent import Future
from salt.ext.tornado import gen
from salt.ext.tornado.httpclient import HTTPError, HTTPRequest
from salt.ext.tornado.log import gen_log, app_log
from salt.ext.tornado.template import DictLoader
from salt.ext.tornado.testing import AsyncHTTPTestCase, gen_test, bind_unused_port, ExpectLog
from salt.ext.tornado.test.util import unittest, skipBefore35, exec_test
from salt.ext.tornado.web import Application, RequestHandler

try:
    import salt.ext.tornado.websocket  # noqa
    from salt.ext.tornado.util import _websocket_mask_python
except ImportError:
    # The unittest module presents misleading errors on ImportError
    # (it acts as if websocket_test could not be found, hiding the underlying
    # error).  If we get an ImportError here (which could happen due to
    # TORNADO_EXTENSION=1), print some extra information before failing.
    traceback.print_exc()
    raise

from salt.ext.tornado.websocket import WebSocketHandler, websocket_connect, WebSocketError

try:
    from salt.ext.tornado import speedups
except ImportError:
    speedups = None


class TestWebSocketHandler(WebSocketHandler):
    """Base class for testing handlers that exposes the on_close event.

    This allows for deterministic cleanup of the associated socket.
    """
    def initialize(self, close_future, compression_options=None):
        self.close_future = close_future
        self.compression_options = compression_options

    def get_compression_options(self):
        return self.compression_options

    def on_close(self):
        self.close_future.set_result((self.close_code, self.close_reason))


class EchoHandler(TestWebSocketHandler):
    def on_message(self, message):
        self.write_message(message, isinstance(message, bytes))


class ErrorInOnMessageHandler(TestWebSocketHandler):
    def on_message(self, message):
        1 / 0


class HeaderHandler(TestWebSocketHandler):
    def open(self):
        methods_to_test = [
            functools.partial(self.write, 'This should not work'),
            functools.partial(self.redirect, 'http://localhost/elsewhere'),
            functools.partial(self.set_header, 'X-Test', ''),
            functools.partial(self.set_cookie, 'Chocolate', 'Chip'),
            functools.partial(self.set_status, 503),
            self.flush,
            self.finish,
        ]
        for method in methods_to_test:
            try:
                # In a websocket context, many RequestHandler methods
                # raise RuntimeErrors.
                method()
                raise Exception("did not get expected exception")
            except RuntimeError:
                pass
        self.write_message(self.request.headers.get('X-Test', ''))


class HeaderEchoHandler(TestWebSocketHandler):
    def set_default_headers(self):
        self.set_header("X-Extra-Response-Header", "Extra-Response-Value")

    def prepare(self):
        for k, v in self.request.headers.get_all():
            if k.lower().startswith('x-test'):
                self.set_header(k, v)


class NonWebSocketHandler(RequestHandler):
    def get(self):
        self.write('ok')


class CloseReasonHandler(TestWebSocketHandler):
    def open(self):
        self.on_close_called = False
        self.close(1001, "goodbye")


class AsyncPrepareHandler(TestWebSocketHandler):
    @gen.coroutine
    def prepare(self):
        yield gen.moment

    def on_message(self, message):
        self.write_message(message)


class PathArgsHandler(TestWebSocketHandler):
    def open(self, arg):
        self.write_message(arg)


class CoroutineOnMessageHandler(TestWebSocketHandler):
    def initialize(self, close_future, compression_options=None):
        super(CoroutineOnMessageHandler, self).initialize(close_future,
                                                          compression_options)
        self.sleeping = 0

    @gen.coroutine
    def on_message(self, message):
        if self.sleeping > 0:
            self.write_message('another coroutine is already sleeping')
        self.sleeping += 1
        yield gen.sleep(0.01)
        self.sleeping -= 1
        self.write_message(message)


class RenderMessageHandler(TestWebSocketHandler):
    def on_message(self, message):
        self.write_message(self.render_string('message.html', message=message))


class WebSocketBaseTestCase(AsyncHTTPTestCase):
    @gen.coroutine
    def ws_connect(self, path, **kwargs):
        ws = yield websocket_connect(
            'ws://127.0.0.1:%d%s' % (self.get_http_port(), path),
            **kwargs)
        raise gen.Return(ws)

    @gen.coroutine
    def close(self, ws):
        """Close a websocket connection and wait for the server side.

        If we don't wait here, there are sometimes leak warnings in the
        tests.
        """
        ws.close()
        yield self.close_future


class WebSocketTest(WebSocketBaseTestCase):
    def get_app(self):
        self.close_future = Future()
        return Application([
            ('/echo', EchoHandler, dict(close_future=self.close_future)),
            ('/non_ws', NonWebSocketHandler),
            ('/header', HeaderHandler, dict(close_future=self.close_future)),
            ('/header_echo', HeaderEchoHandler,
             dict(close_future=self.close_future)),
            ('/close_reason', CloseReasonHandler,
             dict(close_future=self.close_future)),
            ('/error_in_on_message', ErrorInOnMessageHandler,
             dict(close_future=self.close_future)),
            ('/async_prepare', AsyncPrepareHandler,
             dict(close_future=self.close_future)),
            ('/path_args/(.*)', PathArgsHandler,
             dict(close_future=self.close_future)),
            ('/coroutine', CoroutineOnMessageHandler,
             dict(close_future=self.close_future)),
            ('/render', RenderMessageHandler,
             dict(close_future=self.close_future)),
        ], template_loader=DictLoader({
            'message.html': '<b>{{ message }}</b>',
        }))

    def tearDown(self):
        super(WebSocketTest, self).tearDown()
        RequestHandler._template_loaders.clear()

    def test_http_request(self):
        # WS server, HTTP client.
        response = self.fetch('/echo')
        self.assertEqual(response.code, 400)

    def test_missing_websocket_key(self):
        response = self.fetch('/echo',
                              headers={'Connection': 'Upgrade',
                                       'Upgrade': 'WebSocket',
                                       'Sec-WebSocket-Version': '13'})
        self.assertEqual(response.code, 400)

    def test_bad_websocket_version(self):
        response = self.fetch('/echo',
                              headers={'Connection': 'Upgrade',
                                       'Upgrade': 'WebSocket',
                                       'Sec-WebSocket-Version': '12'})
        self.assertEqual(response.code, 426)

    @gen_test
    def test_websocket_gen(self):
        ws = yield self.ws_connect('/echo')
        yield ws.write_message('hello')
        response = yield ws.read_message()
        self.assertEqual(response, 'hello')
        yield self.close(ws)

    def test_websocket_callbacks(self):
        websocket_connect(
            'ws://127.0.0.1:%d/echo' % self.get_http_port(),
            io_loop=self.io_loop, callback=self.stop)
        ws = self.wait().result()
        ws.write_message('hello')
        ws.read_message(self.stop)
        response = self.wait().result()
        self.assertEqual(response, 'hello')
        self.close_future.add_done_callback(lambda f: self.stop())
        ws.close()
        self.wait()

    @gen_test
    def test_binary_message(self):
        ws = yield self.ws_connect('/echo')
        ws.write_message(b'hello \xe9', binary=True)
        response = yield ws.read_message()
        self.assertEqual(response, b'hello \xe9')
        yield self.close(ws)

    @gen_test
    def test_unicode_message(self):
        ws = yield self.ws_connect('/echo')
        ws.write_message(u'hello \u00e9')
        response = yield ws.read_message()
        self.assertEqual(response, u'hello \u00e9')
        yield self.close(ws)

    @gen_test
    def test_render_message(self):
        ws = yield self.ws_connect('/render')
        ws.write_message('hello')
        response = yield ws.read_message()
        self.assertEqual(response, '<b>hello</b>')
        yield self.close(ws)

    @gen_test
    def test_error_in_on_message(self):
        ws = yield self.ws_connect('/error_in_on_message')
        ws.write_message('hello')
        with ExpectLog(app_log, "Uncaught exception"):
            response = yield ws.read_message()
        self.assertIs(response, None)
        yield self.close(ws)

    @gen_test
    def test_websocket_http_fail(self):
        with self.assertRaises(HTTPError) as cm:
            yield self.ws_connect('/notfound')
        self.assertEqual(cm.exception.code, 404)

    @gen_test
    def test_websocket_http_success(self):
        with self.assertRaises(WebSocketError):
            yield self.ws_connect('/non_ws')

    @gen_test
    def test_websocket_network_fail(self):
        sock, port = bind_unused_port()
        sock.close()
        with self.assertRaises(IOError):
            with ExpectLog(gen_log, ".*"):
                yield websocket_connect(
                    'ws://127.0.0.1:%d/' % port,
                    io_loop=self.io_loop,
                    connect_timeout=3600)

    @gen_test
    def test_websocket_close_buffered_data(self):
        ws = yield websocket_connect(
            'ws://127.0.0.1:%d/echo' % self.get_http_port())
        ws.write_message('hello')
        ws.write_message('world')
        # Close the underlying stream.
        ws.stream.close()
        yield self.close_future

    @gen_test
    def test_websocket_headers(self):
        # Ensure that arbitrary headers can be passed through websocket_connect.
        ws = yield websocket_connect(
            HTTPRequest('ws://127.0.0.1:%d/header' % self.get_http_port(),
                        headers={'X-Test': 'hello'}))
        response = yield ws.read_message()
        self.assertEqual(response, 'hello')
        yield self.close(ws)

    @gen_test
    def test_websocket_header_echo(self):
        # Ensure that headers can be returned in the response.
        # Specifically, that arbitrary headers passed through websocket_connect
        # can be returned.
        ws = yield websocket_connect(
            HTTPRequest('ws://127.0.0.1:%d/header_echo' % self.get_http_port(),
                        headers={'X-Test-Hello': 'hello'}))
        self.assertEqual(ws.headers.get('X-Test-Hello'), 'hello')
        self.assertEqual(ws.headers.get('X-Extra-Response-Header'), 'Extra-Response-Value')
        yield self.close(ws)

    @gen_test
    def test_server_close_reason(self):
        ws = yield self.ws_connect('/close_reason')
        msg = yield ws.read_message()
        # A message of None means the other side closed the connection.
        self.assertIs(msg, None)
        self.assertEqual(ws.close_code, 1001)
        self.assertEqual(ws.close_reason, "goodbye")
        # The on_close callback is called no matter which side closed.
        code, reason = yield self.close_future
        # The client echoed the close code it received to the server,
        # so the server's close code (returned via close_future) is
        # the same.
        self.assertEqual(code, 1001)

    @gen_test
    def test_client_close_reason(self):
        ws = yield self.ws_connect('/echo')
        ws.close(1001, 'goodbye')
        code, reason = yield self.close_future
        self.assertEqual(code, 1001)
        self.assertEqual(reason, 'goodbye')

    @gen_test
    def test_async_prepare(self):
        # Previously, an async prepare method triggered a bug that would
        # result in a timeout on test shutdown (and a memory leak).
        ws = yield self.ws_connect('/async_prepare')
        ws.write_message('hello')
        res = yield ws.read_message()
        self.assertEqual(res, 'hello')

    @gen_test
    def test_path_args(self):
        ws = yield self.ws_connect('/path_args/hello')
        res = yield ws.read_message()
        self.assertEqual(res, 'hello')

    @gen_test
    def test_coroutine(self):
        ws = yield self.ws_connect('/coroutine')
        # Send both messages immediately, coroutine must process one at a time.
        yield ws.write_message('hello1')
        yield ws.write_message('hello2')
        res = yield ws.read_message()
        self.assertEqual(res, 'hello1')
        res = yield ws.read_message()
        self.assertEqual(res, 'hello2')

    @gen_test
    def test_check_origin_valid_no_path(self):
        port = self.get_http_port()

        url = 'ws://127.0.0.1:%d/echo' % port
        headers = {'Origin': 'http://127.0.0.1:%d' % port}

        ws = yield websocket_connect(HTTPRequest(url, headers=headers),
                                     io_loop=self.io_loop)
        ws.write_message('hello')
        response = yield ws.read_message()
        self.assertEqual(response, 'hello')
        yield self.close(ws)

    @gen_test
    def test_check_origin_valid_with_path(self):
        port = self.get_http_port()

        url = 'ws://127.0.0.1:%d/echo' % port
        headers = {'Origin': 'http://127.0.0.1:%d/something' % port}

        ws = yield websocket_connect(HTTPRequest(url, headers=headers),
                                     io_loop=self.io_loop)
        ws.write_message('hello')
        response = yield ws.read_message()
        self.assertEqual(response, 'hello')
        yield self.close(ws)

    @gen_test
    def test_check_origin_invalid_partial_url(self):
        port = self.get_http_port()

        url = 'ws://127.0.0.1:%d/echo' % port
        headers = {'Origin': '127.0.0.1:%d' % port}

        with self.assertRaises(HTTPError) as cm:
            yield websocket_connect(HTTPRequest(url, headers=headers),
                                    io_loop=self.io_loop)
        self.assertEqual(cm.exception.code, 403)

    @gen_test
    def test_check_origin_invalid(self):
        port = self.get_http_port()

        url = 'ws://127.0.0.1:%d/echo' % port
        # Host is 127.0.0.1, which should not be accessible from some other
        # domain
        headers = {'Origin': 'http://somewhereelse.com'}

        with self.assertRaises(HTTPError) as cm:
            yield websocket_connect(HTTPRequest(url, headers=headers),
                                    io_loop=self.io_loop)

        self.assertEqual(cm.exception.code, 403)

    @gen_test
    def test_check_origin_invalid_subdomains(self):
        port = self.get_http_port()

        url = 'ws://localhost:%d/echo' % port
        # Subdomains should be disallowed by default.  If we could pass a
        # resolver to websocket_connect we could test sibling domains as well.
        headers = {'Origin': 'http://subtenant.localhost'}

        with self.assertRaises(HTTPError) as cm:
            yield websocket_connect(HTTPRequest(url, headers=headers),
                                    io_loop=self.io_loop)

        self.assertEqual(cm.exception.code, 403)


if sys.version_info >= (3, 5):
    NativeCoroutineOnMessageHandler = exec_test(globals(), locals(), """
class NativeCoroutineOnMessageHandler(TestWebSocketHandler):
    def initialize(self, close_future, compression_options=None):
        super().initialize(close_future, compression_options)
        self.sleeping = 0

    async def on_message(self, message):
        if self.sleeping > 0:
            self.write_message('another coroutine is already sleeping')
        self.sleeping += 1
        await gen.sleep(0.01)
        self.sleeping -= 1
        self.write_message(message)""")['NativeCoroutineOnMessageHandler']


class WebSocketNativeCoroutineTest(WebSocketBaseTestCase):
    def get_app(self):
        self.close_future = Future()
        return Application([
            ('/native', NativeCoroutineOnMessageHandler,
             dict(close_future=self.close_future))])

    @skipBefore35
    @gen_test
    def test_native_coroutine(self):
        ws = yield self.ws_connect('/native')
        # Send both messages immediately, coroutine must process one at a time.
        yield ws.write_message('hello1')
        yield ws.write_message('hello2')
        res = yield ws.read_message()
        self.assertEqual(res, 'hello1')
        res = yield ws.read_message()
        self.assertEqual(res, 'hello2')


class CompressionTestMixin(object):
    MESSAGE = 'Hello world. Testing 123 123'

    def get_app(self):
        self.close_future = Future()
        return Application([
            ('/echo', EchoHandler, dict(
                close_future=self.close_future,
                compression_options=self.get_server_compression_options())),
        ])

    def get_server_compression_options(self):
        return None

    def get_client_compression_options(self):
        return None

    @gen_test
    def test_message_sizes(self):
        ws = yield self.ws_connect(
            '/echo',
            compression_options=self.get_client_compression_options())
        # Send the same message three times so we can measure the
        # effect of the context_takeover options.
        for i in range(3):
            ws.write_message(self.MESSAGE)
            response = yield ws.read_message()
            self.assertEqual(response, self.MESSAGE)
        self.assertEqual(ws.protocol._message_bytes_out, len(self.MESSAGE) * 3)
        self.assertEqual(ws.protocol._message_bytes_in, len(self.MESSAGE) * 3)
        self.verify_wire_bytes(ws.protocol._wire_bytes_in,
                               ws.protocol._wire_bytes_out)
        yield self.close(ws)


class UncompressedTestMixin(CompressionTestMixin):
    """Specialization of CompressionTestMixin when we expect no compression."""
    def verify_wire_bytes(self, bytes_in, bytes_out):
        # Bytes out includes the 4-byte mask key per message.
        self.assertEqual(bytes_out, 3 * (len(self.MESSAGE) + 6))
        self.assertEqual(bytes_in, 3 * (len(self.MESSAGE) + 2))


class NoCompressionTest(UncompressedTestMixin, WebSocketBaseTestCase):
    pass


# If only one side tries to compress, the extension is not negotiated.
class ServerOnlyCompressionTest(UncompressedTestMixin, WebSocketBaseTestCase):
    def get_server_compression_options(self):
        return {}


class ClientOnlyCompressionTest(UncompressedTestMixin, WebSocketBaseTestCase):
    def get_client_compression_options(self):
        return {}


class DefaultCompressionTest(CompressionTestMixin, WebSocketBaseTestCase):
    def get_server_compression_options(self):
        return {}

    def get_client_compression_options(self):
        return {}

    def verify_wire_bytes(self, bytes_in, bytes_out):
        self.assertLess(bytes_out, 3 * (len(self.MESSAGE) + 6))
        self.assertLess(bytes_in, 3 * (len(self.MESSAGE) + 2))
        # Bytes out includes the 4 bytes mask key per message.
        self.assertEqual(bytes_out, bytes_in + 12)


class MaskFunctionMixin(object):
    # Subclasses should define self.mask(mask, data)
    def test_mask(self):
        self.assertEqual(self.mask(b'abcd', b''), b'')
        self.assertEqual(self.mask(b'abcd', b'b'), b'\x03')
        self.assertEqual(self.mask(b'abcd', b'54321'), b'TVPVP')
        self.assertEqual(self.mask(b'ZXCV', b'98765432'), b'c`t`olpd')
        # Include test cases with \x00 bytes (to ensure that the C
        # extension isn't depending on null-terminated strings) and
        # bytes with the high bit set (to smoke out signedness issues).
        self.assertEqual(self.mask(b'\x00\x01\x02\x03',
                                   b'\xff\xfb\xfd\xfc\xfe\xfa'),
                         b'\xff\xfa\xff\xff\xfe\xfb')
        self.assertEqual(self.mask(b'\xff\xfb\xfd\xfc',
                                   b'\x00\x01\x02\x03\x04\x05'),
                         b'\xff\xfa\xff\xff\xfb\xfe')


class PythonMaskFunctionTest(MaskFunctionMixin, unittest.TestCase):
    def mask(self, mask, data):
        return _websocket_mask_python(mask, data)


@unittest.skipIf(speedups is None, "tornado.speedups module not present")
class CythonMaskFunctionTest(MaskFunctionMixin, unittest.TestCase):
    def mask(self, mask, data):
        return speedups.websocket_mask(mask, data)


class ServerPeriodicPingTest(WebSocketBaseTestCase):
    def get_app(self):
        class PingHandler(TestWebSocketHandler):
            def on_pong(self, data):
                self.write_message("got pong")

        self.close_future = Future()
        return Application([
            ('/', PingHandler, dict(close_future=self.close_future)),
        ], websocket_ping_interval=0.01)

    @gen_test
    def test_server_ping(self):
        ws = yield self.ws_connect('/')
        for i in range(3):
            response = yield ws.read_message()
            self.assertEqual(response, "got pong")
        yield self.close(ws)
        # TODO: test that the connection gets closed if ping responses stop.


class ClientPeriodicPingTest(WebSocketBaseTestCase):
    def get_app(self):
        class PingHandler(TestWebSocketHandler):
            def on_ping(self, data):
                self.write_message("got ping")

        self.close_future = Future()
        return Application([
            ('/', PingHandler, dict(close_future=self.close_future)),
        ])

    @gen_test
    def test_client_ping(self):
        ws = yield self.ws_connect('/', ping_interval=0.01)
        for i in range(3):
            response = yield ws.read_message()
            self.assertEqual(response, "got ping")
        yield self.close(ws)
        # TODO: test that the connection gets closed if ping responses stop.


class MaxMessageSizeTest(WebSocketBaseTestCase):
    def get_app(self):
        self.close_future = Future()
        return Application([
            ('/', EchoHandler, dict(close_future=self.close_future)),
        ], websocket_max_message_size=1024)

    @gen_test
    def test_large_message(self):
        ws = yield self.ws_connect('/')

        # Write a message that is allowed.
        msg = 'a' * 1024
        ws.write_message(msg)
        resp = yield ws.read_message()
        self.assertEqual(resp, msg)

        # Write a message that is too large.
        ws.write_message(msg + 'b')
        resp = yield ws.read_message()
        # A message of None means the other side closed the connection.
        self.assertIs(resp, None)
        self.assertEqual(ws.close_code, 1009)
        self.assertEqual(ws.close_reason, "message too big")
        # TODO: Needs tests of messages split over multiple
        # continuation frames.
