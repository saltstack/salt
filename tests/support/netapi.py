import logging
import socket

import attr

import salt.auth
import salt.ext.tornado.escape
import salt.ext.tornado.web
from salt.ext.tornado import netutil
from salt.ext.tornado.httpclient import AsyncHTTPClient, HTTPError
from salt.ext.tornado.httpserver import HTTPServer
from salt.ext.tornado.ioloop import TimeoutError as IOLoopTimeoutError
from salt.netapi.rest_tornado import saltnado

log = logging.getLogger(__name__)


@attr.s
class TestsHttpClient:
    address = attr.ib()
    io_loop = attr.ib(repr=False)
    headers = attr.ib(default=None)
    client = attr.ib(init=False, repr=False)

    @client.default
    def _client_default(self):
        return AsyncHTTPClient(self.io_loop)

    async def fetch(self, path, **kwargs):
        if "headers" not in kwargs and self.headers:
            kwargs["headers"] = self.headers.copy()
        try:
            response = await self.client.fetch(f"{self.address}{path}", **kwargs)
            return self._decode_body(response)
        except HTTPError as exc:
            exc.response = self._decode_body(exc.response)
            raise

    def _decode_body(self, response):
        if response is None:
            return response
        if response.body:
            # Decode it
            if response.headers.get("Content-Type") == "application/json":
                response._body = response.body.decode("utf-8")
            else:
                response._body = salt.ext.tornado.escape.native_str(response.body)
        return response


@attr.s
class TestsTornadoHttpServer:
    io_loop = attr.ib(repr=False)
    app = attr.ib()
    port = attr.ib(repr=False)
    protocol = attr.ib(default="http", repr=False)
    http_server_options = attr.ib(default=attr.Factory(dict))
    sock = attr.ib(init=False, repr=False)
    address = attr.ib(init=False)
    server = attr.ib(init=False)
    client_headers = attr.ib(default=None)
    client = attr.ib(init=False, repr=False)

    @sock.default
    def _sock_default(self):
        return netutil.bind_sockets(
            self.port, "127.0.0.1", family=socket.AF_INET, reuse_port=False
        )[0]

    @port.default
    def _port_default(self):
        return self.sock.getsockname()[1]

    @address.default
    def _address_default(self):
        return f"{self.protocol}://127.0.0.1:{self.port}"

    @server.default
    def _server_default(self):
        server = HTTPServer(self.app, io_loop=self.io_loop, **self.http_server_options)
        server.add_sockets([self.sock])
        return server

    @client.default
    def _client_default(self):
        return TestsHttpClient(
            address=self.address, io_loop=self.io_loop, headers=self.client_headers
        )

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.server.stop()
        try:
            self.io_loop.run_sync(self.server.close_all_connections, timeout=10)
        except IOLoopTimeoutError:
            pass
        self.client.client.close()


def load_auth(client_config):
    return salt.auth.LoadAuth(client_config)


def auth_token(load_auth, auth_creds):
    """
    Mint and return a valid token for auth_creds
    """
    return load_auth.mk_token(auth_creds)


def build_tornado_app(
    urls, load_auth, client_config, minion_config, setup_event_listener=False
):
    application = salt.ext.tornado.web.Application(urls, debug=True)

    application.auth = load_auth
    application.opts = client_config
    application.mod_opts = minion_config
    if setup_event_listener:
        application.event_listener = saltnado.EventListener(
            minion_config, client_config
        )
    return application


def content_type_map():
    return {
        "json": "application/json",
        "json-utf8": "application/json; charset=utf-8",
        "yaml": "application/x-yaml",
        "text": "text/plain",
        "form": "application/x-www-form-urlencoded",
        "xml": "application/xml",
        "real-accept-header-json": "application/json, text/javascript, */*; q=0.01",
        "real-accept-header-yaml": "application/x-yaml, text/yaml, */*; q=0.01",
    }
