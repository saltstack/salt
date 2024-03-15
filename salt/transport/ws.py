import asyncio
import logging
import multiprocessing
import socket
import time
import warnings

import aiohttp
import aiohttp.web
import tornado.ioloop

import salt.payload
import salt.transport.base
import salt.transport.frame
from salt.transport.tcp import (
    USE_LOAD_BALANCER,
    LoadBalancerServer,
    _get_bind_addr,
    _get_socket,
    _set_tcp_keepalive,
)

log = logging.getLogger(__name__)


class PublishClient(salt.transport.base.PublishClient):
    """
    Tornado based TCP Pub Client
    """

    ttype = "ws"

    async_methods = [
        "connect",
        "connect_uri",
        "recv",
        # "close",
    ]
    close_methods = [
        "close",
    ]

    def __init__(self, opts, io_loop, **kwargs):  # pylint: disable=W0231
        self.opts = opts
        self.io_loop = io_loop

        self.connected = False
        self._closing = False
        self._closing = False
        self._closed = False

        self.backoff = opts.get("tcp_reconnect_backoff", 1)
        self.poller = None

        self.host = kwargs.get("host", None)
        self.port = kwargs.get("port", None)
        self.path = kwargs.get("path", None)
        self.ssl = kwargs.get("ssl", None)
        self.source_ip = self.opts.get("source_ip")
        self.source_port = self.opts.get("source_publish_port")
        self.connect_callback = None
        self.disconnect_callback = None
        if self.host is None and self.port is None:
            if self.path is None:
                raise Exception("A host and port or a path must be provided")
        elif self.host and self.port:
            if self.path:
                raise Exception("A host and port or a path must be provided, not both")
        self._ws = None
        self._session = None
        self._closing = False
        self.on_recv_task = None

    async def _close(self):
        if self._session is not None:
            await self._session.close()
            self._session = None
        if self.on_recv_task:
            self.on_recv_task.cancel()
            await self.on_recv_task
            self.on_recv_task = None
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
        self._closed = True

    def close(self):
        if self._closing:
            return
        self._closing = True
        self.io_loop.spawn_callback(self._close)

    # pylint: disable=W1701
    def __del__(self):
        if not self._closing:
            warnings.warn(
                "unclosed publish client {self!r}", ResourceWarning, source=self
            )

    # pylint: enable=W1701
    def _decode_messages(self, messages):
        if not isinstance(messages, dict):
            body = salt.payload.loads(messages)
        else:
            body = messages
        return body

    async def getstream(self, **kwargs):
        if self.source_ip or self.source_port:
            kwargs.update(source_ip=self.source_ip, source_port=self.source_port)
        ws = None
        start = time.monotonic()
        timeout = kwargs.get("timeout", None)
        while ws is None and (not self._closed and not self._closing):
            session = None
            try:
                ctx = None
                if self.ssl is not None:
                    ctx = salt.transport.base.ssl_context(self.ssl, server_side=False)
                if self.host and self.port:
                    conn = aiohttp.TCPConnector()
                    session = aiohttp.ClientSession(connector=conn)
                    if self.ssl:
                        url = f"https://{self.host}:{self.port}/ws"
                    else:
                        url = f"http://{self.host}:{self.port}/ws"
                else:
                    conn = aiohttp.UnixConnector(path=self.path)
                    session = aiohttp.ClientSession(connector=conn)
                    if self.ssl:
                        url = "https://ipc.saltproject.io/ws"
                    else:
                        url = "http://ipc.saltproject.io/ws"
                log.error("pub client connect %r %r", url, ctx)
                ws = await asyncio.wait_for(session.ws_connect(url, ssl=ctx), 3)
            except Exception as exc:  # pylint: disable=broad-except
                log.warning(
                    "WS Message Client encountered an exception while connecting to"
                    " %s:%s %s: %r, will reconnect in %d seconds",
                    self.host,
                    self.port,
                    self.path,
                    exc,
                    self.backoff,
                )
                if session:
                    await session.close()
                if timeout and time.monotonic() - start > timeout:
                    break
                await asyncio.sleep(self.backoff)
        return ws, session

    async def _connect(self, timeout=None):
        if self._ws is None:
            self._ws, self._session = await self.getstream(timeout=timeout)
            if self.connect_callback:
                self.connect_callback(True)  # pylint: disable=not-callable
            self.connected = True

    async def connect(
        self,
        port=None,
        connect_callback=None,
        disconnect_callback=None,
        timeout=None,
    ):
        if port is not None:
            self.port = port
        if connect_callback:
            self.connect_callback = None
        if disconnect_callback:
            self.disconnect_callback = None
        await self._connect(timeout=timeout)

    async def send(self, msg):
        await self.message_client.send(msg, reply=False)

    async def recv(self, timeout=None):
        while self._ws is None:
            await self.connect()
            await asyncio.sleep(0.001)
        if timeout == 0:
            try:
                raw_msg = await asyncio.wait_for(self._ws.receive(), 0.0001)
            except TimeoutError:
                return
            if raw_msg.type == aiohttp.WSMsgType.TEXT:
                if raw_msg.data == "close":
                    await self._ws.close()
            if raw_msg.type == aiohttp.WSMsgType.BINARY:
                return salt.payload.loads(raw_msg.data, raw=True)
            elif raw_msg.type == aiohttp.WSMsgType.ERROR:
                log.error(
                    "ws connection closed with exception %s", self._ws.exception()
                )
        elif timeout:
            return await asyncio.wait_for(self.recv(), timeout=timeout)
        else:
            while True:
                raw_msg = await self._ws.receive()
                if raw_msg.type == aiohttp.WSMsgType.TEXT:
                    if raw_msg.data == "close":
                        await self._ws.close()
                if raw_msg.type == aiohttp.WSMsgType.BINARY:
                    return salt.payload.loads(raw_msg.data, raw=True)
                elif raw_msg.type == aiohttp.WSMsgType.ERROR:
                    log.error(
                        "ws connection closed with exception %s",
                        self._ws.exception(),
                    )

    async def on_recv_handler(self, callback):
        while not self._ws:
            await asyncio.sleep(0.003)
        while True:
            msg = await self.recv()
            await callback(msg)

    def on_recv(self, callback):
        """
        Register a callback for received messages (that we didn't initiate)
        """
        if self.on_recv_task:
            # XXX: We are not awaiting this canceled task. This still needs to
            # be addressed.
            self.on_recv_task.cancel()
        if callback is None:
            self.on_recv_task = None
        else:
            self.on_recv_task = asyncio.create_task(self.on_recv_handler(callback))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class PublishServer(salt.transport.base.DaemonizedPublishServer):
    """ """

    # TODO: opts!
    # Based on default used in tornado.netutil.bind_sockets()
    backlog = 128
    async_methods = [
        "publish",
        # "close",
    ]
    close_methods = [
        "close",
    ]

    def __init__(
        self,
        opts,
        pub_host=None,
        pub_port=None,
        pub_path=None,
        pull_host=None,
        pull_port=None,
        pull_path=None,
        ssl=None,
    ):
        self.opts = opts
        self.pub_host = pub_host
        self.pub_port = pub_port
        self.pub_path = pub_path
        self.pull_host = pull_host
        self.pull_port = pull_port
        self.pull_path = pull_path
        self.ssl = ssl
        self.clients = set()
        self._run = None
        self.pub_writer = None
        self.pub_reader = None
        self._connecting = None

    @property
    def topic_support(self):
        return not self.opts.get("order_masters", False)

    def __setstate__(self, state):
        self.__init__(**state)

    def __getstate__(self):
        return {
            "opts": self.opts,
            "pub_host": self.pub_host,
            "pub_port": self.pub_port,
            "pub_path": self.pub_path,
            "pull_host": self.pull_host,
            "pull_port": self.pull_port,
            "pull_path": self.pull_path,
        }

    def publish_daemon(
        self,
        publish_payload,
        presence_callback=None,
        remove_presence_callback=None,
    ):
        """
        Bind to the interface specified in the configuration file
        """
        io_loop = tornado.ioloop.IOLoop()
        io_loop.add_callback(
            self.publisher,
            publish_payload,
            presence_callback,
            remove_presence_callback,
            io_loop,
        )
        # run forever
        try:
            io_loop.start()
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            self.close()

    async def publisher(
        self,
        publish_payload,
        presence_callback=None,
        remove_presence_callback=None,
        io_loop=None,
    ):
        if io_loop is None:
            io_loop = tornado.ioloop.IOLoop.current()
        if self._run is None:
            self._run = asyncio.Event()
        self._run.set()

        ctx = None
        if self.ssl is not None:
            ctx = salt.transport.base.ssl_context(self.ssl, server_side=True)
        if self.pub_path:
            server = aiohttp.web.Server(self.handle_request)
            runner = aiohttp.web.ServerRunner(server)
            await runner.setup()
            site = aiohttp.web.UnixSite(runner, self.pub_path, ssl_context=ctx)
            log.info("Publisher binding to socket %s", self.pub_path)
        else:
            sock = _get_socket(self.opts)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # _set_tcp_keepalive(sock, self.opts)
            sock.setblocking(0)
            sock.bind((self.pub_host, self.pub_port))
            sock.listen(self.backlog)
            server = aiohttp.web.Server(self.handle_request)
            runner = aiohttp.web.ServerRunner(server)
            await runner.setup()
            site = aiohttp.web.SockSite(runner, sock, ssl_context=ctx)
            log.info("Publisher binding to socket %s:%s", self.pub_host, self.pub_port)
        await site.start()

        self._pub_payload = publish_payload
        if self.pull_path:
            with salt.utils.files.set_umask(0o177):
                self.puller = await asyncio.start_unix_server(
                    self.pull_handler, self.pull_path
                )
        else:
            self.puller = await asyncio.start_server(
                self.pull_handler, self.pull_host, self.pull_port
            )
        while self._run.is_set():
            await asyncio.sleep(0.3)
        await self.server.stop()
        await self.puller.wait_closed()

    async def pull_handler(self, reader, writer):
        unpacker = salt.utils.msgpack.Unpacker(raw=True)
        while True:
            data = await reader.read(1024)
            unpacker.feed(data)
            for msg in unpacker:
                await self._pub_payload(msg)

    def pre_fork(self, process_manager):
        """
        Do anything necessary pre-fork. Since this is on the master side this will
        primarily be used to create IPC channels and create our daemon process to
        do the actual publishing
        """
        process_manager.add_process(
            self.publish_daemon,
            args=[self.publish_payload],
            name=self.__class__.__name__,
        )

    async def handle_request(self, request):
        try:
            cert = request.get_extra_info("peercert")
        except AttributeError:
            pass
        else:
            if cert:
                name = salt.transport.base.common_name(cert)
                log.error("Request client cert %r", name)
        ws = aiohttp.web.WebSocketResponse()
        await ws.prepare(request)
        self.clients.add(ws)
        while True:
            await asyncio.sleep(1)

    async def _connect(self):
        if self.pull_path:
            self.pub_reader, self.pub_writer = await asyncio.open_unix_connection(
                self.pull_path
            )
        else:
            self.pub_reader, self.pub_writer = await asyncio.open_connection(
                self.pull_host, self.pull_port
            )
        self._connecting = None

    def connect(self):
        log.debug("Connect pusher %s", self.pull_path)
        if self._connecting is None:
            self._connecting = asyncio.create_task(self._connect())
        return self._connecting

    async def publish(
        self, payload, **kwargs
    ):  # pylint: disable=invalid-overridden-method
        """
        Publish "load" to minions
        """
        if not self.pub_writer:
            await self.connect()
        self.pub_writer.write(salt.payload.dumps(payload, use_bin_type=True))
        await self.pub_writer.drain()

    async def publish_payload(self, package, *args):
        payload = salt.payload.dumps(package, use_bin_type=True)
        for ws in list(self.clients):
            try:
                await ws.send_bytes(payload)
            except ConnectionResetError:
                self.clients.discard(ws)

    def close(self):
        if self.pub_writer:
            self.pub_writer.close()
            self.pub_writer = None
            self.pub_reader = None
        if self._run is not None:
            self._run.clear()
        if self._connecting:
            self._connecting.cancel()


class RequestServer(salt.transport.base.DaemonizedRequestServer):
    def __init__(self, opts):  # pylint: disable=W0231
        self.opts = opts
        self.site = None
        self.ssl = self.opts.get("ssl", None)

    def pre_fork(self, process_manager):
        """
        Pre-fork we need to create the zmq router device
        """
        if USE_LOAD_BALANCER:
            self.socket_queue = multiprocessing.Queue()
            process_manager.add_process(
                LoadBalancerServer,
                args=(self.opts, self.socket_queue),
                name="LoadBalancerServer",
            )
        elif not salt.utils.platform.is_windows():
            self._socket = _get_socket(self.opts)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            _set_tcp_keepalive(self._socket, self.opts)
            self._socket.setblocking(0)
            self._socket.bind(_get_bind_addr(self.opts, "ret_port"))

    def post_fork(self, message_handler, io_loop):
        """
        After forking we need to create all of the local sockets to listen to the
        router

        message_handler: function to call with your payloads
        """
        self.message_handler = message_handler
        self._run = asyncio.Event()
        self._run.set()

        async def server():
            server = aiohttp.web.Server(self.handle_message)
            runner = aiohttp.web.ServerRunner(server)
            await runner.setup()
            ctx = None
            if self.ssl is not None:
                ctx = tornado.netutil.ssl_options_to_context(self.ssl, server_side=True)
            self.site = aiohttp.web.SockSite(runner, self._socket, ssl_context=ctx)
            log.info("Worker binding to socket %s", self._socket)
            await self.site.start()
            # pause here for very long time by serving HTTP requests and
            # waiting for keyboard interruption
            while self._run.is_set():
                await asyncio.sleep(0.3)
            await self.site.stop()

        io_loop.spawn_callback(server)

    async def handle_message(self, request):
        try:
            cert = request.get_extra_info("peercert")
        except AttributeError:
            pass
        else:
            if cert:
                name = salt.transport.base.common_name(cert)
                log.error("Request client cert %r", name)
        ws = aiohttp.web.WebSocketResponse()
        await ws.prepare(request)
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                if msg.data == "close":
                    await ws.close()
            if msg.type == aiohttp.WSMsgType.BINARY:
                payload = salt.payload.loads(msg.data)
                reply = await self.message_handler(payload)
                await ws.send_bytes(salt.payload.dumps(reply))
            elif msg.type == aiohttp.WSMsgType.ERROR:
                log.error("ws connection closed with exception %s", ws.exception())

    def close(self):
        self._run.clear()


class RequestClient(salt.transport.base.RequestClient):

    ttype = "ws"

    def __init__(self, opts, io_loop):  # pylint: disable=W0231
        self.opts = opts
        self.sending = False
        self.ws = None
        self.session = None
        self.io_loop = io_loop
        self._closing = False
        self._closed = False
        self.ssl = self.opts.get("ssl", None)

    async def connect(self):  # pylint: disable=invalid-overridden-method
        ctx = None
        if self.ssl is not None:
            ctx = tornado.netutil.ssl_options_to_context(self.ssl, server_side=False)
        self.session = aiohttp.ClientSession()
        URL = self.get_master_uri(self.opts)
        log.error("Connect to %s %s", URL, ctx)
        self.ws = await self.session.ws_connect(URL, ssl=ctx)

    async def send(self, load, timeout=60):
        if self.sending or self._closing:
            await asyncio.sleep(0.03)
        self.sending = True
        try:
            await self.connect()
            message = salt.payload.dumps(load)
            await self.ws.send_bytes(message)
            async for msg in self.ws:
                if msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    break
                data = salt.payload.loads(msg.data)
                break
            return data
        finally:
            self.sending = False

    async def _close(self):
        if self.ws is not None:
            await self.ws.close()
            self.ws = None
        if self.session is not None:
            await self.session.close()
            self.session = None
        self._closed = True

    def close(self):
        if self._closing:
            return
        self._closing = True
        self.close_task = asyncio.create_task(self._close())

    def get_master_uri(self, opts):
        if "master_uri" in opts:
            if self.opts.get("ssl", None):
                return opts["master_uri"].replace("tcp:", "https:", 1)
            return opts["master_uri"].replace("tcp:", "http:", 1)
        if self.opts.get("ssl", None):
            return f"https://{opts['master_ip']}:{opts['master_port']}/ws"
        return f"http://{opts['master_ip']}:{opts['master_port']}/ws"

    # pylint: disable=W1701
    def __del__(self):
        if not self._closing:
            warnings.warn(
                "Unclosed publish client {self!r}", ResourceWarning, source=self
            )

    # pylint: enable=W1701
