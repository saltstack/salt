import asyncio
import logging
import socket

import aiohttp
import aiohttp.web
import tornado.ioloop
from tornado.locks import Lock

import salt.payload
import salt.transport.base
from salt.transport.tcp import (
    USE_LOAD_BALANCER,
    LoadBalancer,
    TCPPuller,
    _get_bind_addr,
    _get_socket,
    _set_tcp_keepalive,
    _TCPPubServerPublisher,
)
from salt.utils.network import ip_bracket

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
        self.message_client = None
        self.unpacker = salt.utils.msgpack.Unpacker()
        self.connected = False
        self._closing = False
        self._stream = None
        self._closing = False
        self._closed = False
        self.backoff = opts.get("tcp_reconnect_backoff", 1)
        self.resolver = kwargs.get("resolver")
        self._read_in_progress = Lock()
        self.poller = None

        self.host = kwargs.get("host", None)
        self.port = kwargs.get("port", None)
        self.path = kwargs.get("path", None)
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
        self._closed = False

    async def _close(self):
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
        if self._session is not None:
            await self._session.close()
            self._session = None
        self._closed = True

    def close(self):
        if self._closing:
            return
        self._closing = True
        self.io_loop.spawn_callback(self._close)

    # pylint: disable=W1701
    def __del__(self):
        self.close()

    # pylint: enable=W1701

    async def getstream(self, **kwargs):
        if self.source_ip or self.source_port:
            kwargs = {
                "source_ip": self.source_ip,
                "source_port": self.source_port,
            }
        ws = None
        while ws is None and (not self._closed and not self._closing):
            try:
                if self.host and self.port:
                    conn = aiohttp.TCPConnector()
                    session = aiohttp.ClientSession(connector=conn)
                    url = f"http://{self.host}:{self.port}"
                else:
                    conn = aiohttp.UnixConnector(path=self.path)
                    session = aiohttp.ClientSession(connector=conn)
                    url = f"http://ipc.saltproject.io/ws"
                ws = await session.ws_connect(url)
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
                await asyncio.sleep(self.backoff)
        return ws, session

    async def _connect(self):
        if self._ws is None:
            self._ws, self._session = await self.getstream()
            # if not self._stream_return_running:
            #    self.io_loop.spawn_callback(self._stream_return)
            if self.connect_callback:
                self.connect_callback(True)
            self.connected = True

    async def connect(
        self,
        port=None,
        connect_callback=None,
        disconnect_callback=None,
        background=False,
    ):
        if port is not None:
            self.port = port
        if connect_callback:
            self.connect_callback = None
        if disconnect_callback:
            self.disconnect_callback = None
        if background:
            self.io_loop.spawn_callback(self._connect)
        else:
            await self._connect()

    def _decode_messages(self, messages):
        if not isinstance(messages, dict):
            # TODO: For some reason we need to decode here for things
            #       to work. Fix this.
            body = salt.utils.msgpack.loads(messages)
            body = salt.transport.frame.decode_embedded_strs(body)
        else:
            body = messages
        return body

    async def send(self, msg):
        await self.message_client.send(msg, reply=False)

    async def recv(self, timeout=None):
        try:
            await self._read_in_progress.acquire(timeout=0.001)
        except tornado.gen.TimeoutError:
            log.error("Timeout Error")
            return
        try:
            if timeout == 0:
                if not self._ws:
                    await asyncio.sleep(0.001)
                    return
                for msg in self.unpacker:
                    framed_msg = salt.transport.frame.decode_embedded_strs(msg)
                    return framed_msg["body"]
                try:
                    raw_msg = await asyncio.wait_for(self._ws.receive(), 0.0001)
                except TimeoutError:
                    return
                if raw_msg.type == aiohttp.WSMsgType.TEXT:
                    if raw_msg.data == "close":
                        await self._ws.close()
                if raw_msg.type == aiohttp.WSMsgType.BINARY:
                    self.unpacker.feed(raw_msg.data)
                    for msg in self.unpacker:
                        framed_msg = salt.transport.frame.decode_embedded_strs(msg)
                        return framed_msg["body"]
                elif raw_msg.type == aiohttp.WSMsgType.ERROR:
                    log.error("ws connection closed with exception %s", ws.exception())
            elif timeout:
                return await asyncio.wait_for(self.recv(), timeout=timeout)
            else:
                for msg in self.unpacker:
                    framed_msg = salt.transport.frame.decode_embedded_strs(msg)
                    return framed_msg["body"]
                while True:
                    for msg in self.unpacker:
                        framed_msg = salt.transport.frame.decode_embedded_strs(msg)
                        return framed_msg["body"]
                    raw_msg = await self._ws.receive()
                    if raw_msg.type == aiohttp.WSMsgType.TEXT:
                        if raw_msg.data == "close":
                            await self._ws.close()
                    if raw_msg.type == aiohttp.WSMsgType.BINARY:
                        log.error("ORIG MSG IS %r", raw_msg.data)
                        self.unpacker.feed(raw_msg.data)
                        for msg in self.unpacker:
                            log.error("MSG IS %r", msg)
                            framed_msg = salt.transport.frame.decode_embedded_strs(msg)
                            return framed_msg["body"]
                    elif raw_msg.type == aiohttp.WSMsgType.ERROR:
                        log.error(
                            "ws connection closed with exception %s", ws.exception()
                        )
        finally:
            self._read_in_progress.release()

    async def handle_on_recv(self, callback):
        while not self._ws:
            await asyncio.sleep(0.003)
        while True:
            try:
                msg = await self.recv()
            except Exception:
                log.error("Other exception", exc_info=True)
            else:
                log.error("on recv got msg %r", msg)
                callback(msg)

    def on_recv(self, callback):
        """
        Register a callback for received messages (that we didn't initiate)
        """
        self.io_loop.spawn_callback(self.handle_on_recv, callback)

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

    def __init__(self, opts, **kwargs):
        self.opts = opts
        self.pub_sock = None
        self.pub_host = kwargs.get("pub_host", None)
        self.pub_port = kwargs.get("pub_port", None)
        self.pub_path = kwargs.get("pub_path", None)
        self.pull_host = kwargs.get("pull_host", None)
        self.pull_port = kwargs.get("pull_port", None)
        self.pull_path = kwargs.get("pull_path", None)
        self.clients = set()
        self._run = None

    @property
    def topic_support(self):
        return not self.opts.get("order_masters", False)

    def __setstate__(self, state):
        self.__init__(state["opts"])

    def __getstate__(self):
        return {"opts": self.opts}

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

        if self.pub_path:
            server = aiohttp.web.Server(self.handle_request)
            runner = aiohttp.web.ServerRunner(server)
            await runner.setup()
            site = aiohttp.web.UnixSite(runner, self.pub_path)
            log.info("Publisher binding to path %s", self.pub_path)
            await site.start()
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
            site = aiohttp.web.SockSite(runner, sock)
            log.info("Publisher binding to socket %s", (self.pub_host, self.pub_port))
            await site.start()

        if self.pull_path:
            pull_uri = self.pull_path
        else:
            pull_uri = self.pull_port

        self.pull_sock = TCPPuller(
            pull_uri,
            io_loop=io_loop,
            payload_handler=publish_payload,
        )
        # Securely create socket
        log.warning("Starting the Salt Puller on %s", pull_uri)
        with salt.utils.files.set_umask(0o177):
            self.pull_sock.start()
        while self._run.is_set():
            await asyncio.sleep(0.3)
        await server.stop()

    def pre_fork(self, process_manager):
        """
        Do anything necessary pre-fork. Since this is on the master side this will
        primarily be used to create IPC channels and create our daemon process to
        do the actual publishing
        """
        process_manager.add_process(self.publish_daemon, name=self.__class__.__name__)

    async def handle_request(self, request):
        ws = aiohttp.web.WebSocketResponse()
        log.error("perpare request")
        await ws.prepare(request)
        log.error("request prepared")
        self.clients.add(ws)
        while True:
            await asyncio.sleep(1)

    def connect(self):
        log.debug("Connect pusher %s", self.pull_path)
        self.pub_sock = salt.utils.asynchronous.SyncWrapper(
            _TCPPubServerPublisher,
            (self.pull_path,),
            loop_kwarg="io_loop",
        )
        self.pub_sock.connect()

    async def publish(self, payload, **kwargs):
        """
        Publish "load" to minions
        """
        if not self.pub_sock:
            self.connect()
        self.pub_sock.send(payload)

    async def publish_payload(self, package, *args):
        payload = salt.transport.frame.frame_msg(package)
        for ws in list(self.clients):
            try:
                log.error("Publish package %r %r", ws, payload)
                await ws.send_bytes(payload)
            except ConnectionResetError:
                self.clients.discard(ws)

    def close(self):
        if self.pub_sock:
            self.pub_sock.close()
            self.pub_sock = None
        if self._run is not None:
            self._run.clear()


class RequestServer(salt.transport.base.DaemonizedRequestServer):
    def __init__(self, opts):
        self.opts = opts
        self.site = None

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
            self.site = aiohttp.web.SockSite(runner, self._socket)
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
            ws = aiohttp.web.WebSocketResponse()
            await ws.prepare(request)
            async for msg in ws:
                log.error("got msg %r", msg)
                if msg.type == aiohttp.WSMsgType.TEXT:
                    if msg.data == "close":
                        await ws.close()
                if msg.type == aiohttp.WSMsgType.BINARY:
                    payload = salt.payload.loads(msg.data)
                    log.error("Handle message got %r", payload)
                    reply = await self.message_handler(payload)
                    log.error("Handle message reply %r", reply)
                    await ws.send_bytes(salt.payload.dumps(reply))
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    log.error("ws connection closed with exception %s", ws.exception())
        except Exception:
            log.error("Message handler", exc_info=True)

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

    async def connect(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()
            URL = self.get_master_uri(self.opts)
            self.ws = await self.session.ws_connect(URL)

    async def send(self, load, timeout=60):
        if self.sending:
            await asyncio.sleep(0.03)
        self.sending = True
        try:
            await self.connect()
            message = salt.payload.dumps(load)
            await self.ws.send_bytes(message)
            async for msg in self.ws:
                log.error("Got MSG %r", msg)
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
        if self.session is not None:
            await self.session.close()
        self._closed = True

    def close(self):
        if self._closing:
            return
        self._closing = True
        self.io_loop.spawn_callback(self._close)

    @staticmethod
    def get_master_uri(opts):
        if "master_uri" in opts:
            return opts["master_uri"]
        return f"http://{opts['master_ip']}:{opts['master_port']}/ws"

    # pylint: disable=W1701
    def __del__(self):
        if not self._closing:
            warnings.warn(
                "unclosed publish client {self!r}", ResourceWarning, source=self
            )

    # pylint: enable=W1701
