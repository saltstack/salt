"""
TCP transport classes

Wire protocol: "len(payload) msgpack({'head': SOMEHEADER, 'body': SOMEBODY})"

"""

import asyncio
import asyncio.exceptions
import errno
import logging
import multiprocessing
import queue
import select
import socket
import threading
import time
import urllib
import uuid
import warnings

import tornado
import tornado.concurrent
import tornado.gen
import tornado.iostream
import tornado.netutil
import tornado.tcpclient
import tornado.tcpserver
import tornado.util

import salt.master
import salt.payload
import salt.transport.base
import salt.transport.frame
import salt.utils.asynchronous
import salt.utils.files
import salt.utils.msgpack
import salt.utils.platform
import salt.utils.process
import salt.utils.versions
from salt.exceptions import SaltClientError, SaltReqTimeoutError
from salt.utils.network import ip_bracket

if salt.utils.platform.is_windows():
    USE_LOAD_BALANCER = True
else:
    USE_LOAD_BALANCER = False


log = logging.getLogger(__name__)


class ClosingError(Exception):
    """ """


def _null_callback(*args, **kwargs):
    pass


def _get_socket(opts):
    family = socket.AF_INET
    if opts.get("ipv6", False):
        family = socket.AF_INET6
    return socket.socket(family, socket.SOCK_STREAM)


def _get_bind_addr(opts, port_type):
    return (
        ip_bracket(opts["interface"], strip=True),
        int(opts[port_type]),
    )


def _set_tcp_keepalive(sock, opts):
    """
    Ensure that TCP keepalives are set for the socket.
    """
    if hasattr(socket, "SO_KEEPALIVE"):
        if opts.get("tcp_keepalive", False):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            if hasattr(socket, "SOL_TCP"):
                if hasattr(socket, "TCP_KEEPIDLE"):
                    tcp_keepalive_idle = opts.get("tcp_keepalive_idle", -1)
                    if tcp_keepalive_idle > 0:
                        sock.setsockopt(
                            socket.SOL_TCP, socket.TCP_KEEPIDLE, int(tcp_keepalive_idle)
                        )
                if hasattr(socket, "TCP_KEEPCNT"):
                    tcp_keepalive_cnt = opts.get("tcp_keepalive_cnt", -1)
                    if tcp_keepalive_cnt > 0:
                        sock.setsockopt(
                            socket.SOL_TCP, socket.TCP_KEEPCNT, int(tcp_keepalive_cnt)
                        )
                if hasattr(socket, "TCP_KEEPINTVL"):
                    tcp_keepalive_intvl = opts.get("tcp_keepalive_intvl", -1)
                    if tcp_keepalive_intvl > 0:
                        sock.setsockopt(
                            socket.SOL_TCP,
                            socket.TCP_KEEPINTVL,
                            int(tcp_keepalive_intvl),
                        )
            if hasattr(socket, "SIO_KEEPALIVE_VALS"):
                # Windows doesn't support TCP_KEEPIDLE, TCP_KEEPCNT, nor
                # TCP_KEEPINTVL. Instead, it has its own proprietary
                # SIO_KEEPALIVE_VALS.
                tcp_keepalive_idle = opts.get("tcp_keepalive_idle", -1)
                tcp_keepalive_intvl = opts.get("tcp_keepalive_intvl", -1)
                # Windows doesn't support changing something equivalent to
                # TCP_KEEPCNT.
                if tcp_keepalive_idle > 0 or tcp_keepalive_intvl > 0:
                    # Windows defaults may be found by using the link below.
                    # Search for 'KeepAliveTime' and 'KeepAliveInterval'.
                    # https://technet.microsoft.com/en-us/library/bb726981.aspx#EDAA
                    # If one value is set and the other isn't, we still need
                    # to send both values to SIO_KEEPALIVE_VALS and they both
                    # need to be valid. So in that case, use the Windows
                    # default.
                    if tcp_keepalive_idle <= 0:
                        tcp_keepalive_idle = 7200
                    if tcp_keepalive_intvl <= 0:
                        tcp_keepalive_intvl = 1
                    # The values expected are in milliseconds, so multiply by
                    # 1000.
                    sock.ioctl(
                        socket.SIO_KEEPALIVE_VALS,
                        (
                            1,
                            int(tcp_keepalive_idle * 1000),
                            int(tcp_keepalive_intvl * 1000),
                        ),
                    )
        else:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 0)


class LoadBalancerServer(salt.utils.process.SignalHandlingProcess):
    """
    Raw TCP server which runs in its own process and will listen
    for incoming connections. Each incoming connection will be
    sent via multiprocessing queue to the workers.
    Since the queue is shared amongst workers, only one worker will
    handle a given connection.
    """

    # TODO: opts!
    # Based on default used in tornado.netutil.bind_sockets()
    backlog = 128

    def __init__(self, opts, socket_queue, **kwargs):
        super().__init__(**kwargs)
        self.opts = opts
        self.socket_queue = socket_queue
        self._socket = None

    def close(self):
        if self._socket is not None:
            self._socket.shutdown(socket.SHUT_RDWR)
            self._socket.close()
            self._socket = None

    # pylint: disable=W1701
    def __del__(self):
        self.close()

    # pylint: enable=W1701

    def run(self):
        """
        Start the load balancer
        """
        self._socket = _get_socket(self.opts)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        _set_tcp_keepalive(self._socket, self.opts)
        self._socket.setblocking(1)
        self._socket.bind(_get_bind_addr(self.opts, "ret_port"))
        self._socket.listen(self.backlog)

        while True:
            try:
                # Wait for a connection to occur since the socket is
                # blocking.
                connection, address = self._socket.accept()
                # Wait for a free slot to be available to put
                # the connection into.
                # Sockets are picklable on Windows in Python 3.
                self.socket_queue.put((connection, address), True, None)
            except OSError as e:
                # ECONNABORTED indicates that there was a connection
                # but it was closed while still in the accept queue.
                # (observed on FreeBSD).
                if tornado.util.errno_from_exception(e) == errno.ECONNABORTED:
                    continue
                raise


class Resolver(tornado.netutil.DefaultLoopResolver):
    """
    Default resolver for tornado
    """


class PublishClient(salt.transport.base.PublishClient):
    """
    Tornado based TCP Pub Client
    """

    ttype = "tcp"

    async_methods = [
        "connect",
        "connect_uri",
        "recv",
    ]
    close_methods = [
        "close",
    ]

    def __init__(self, opts, io_loop, **kwargs):  # pylint: disable=W0231
        super().__init__(opts, io_loop, **kwargs)
        self.opts = opts
        self.io_loop = io_loop
        self.unpacker = salt.utils.msgpack.Unpacker()
        self.connected = False
        self._closing = False
        self._stream = None
        self._closing = False
        self._closed = False
        self.backoff = opts.get("tcp_reconnect_backoff", 1)
        self.resolver = kwargs.get("resolver")
        self._read_in_progress = asyncio.Lock()
        self.poller = None

        self.host = kwargs.get("host", None)
        self.port = kwargs.get("port", None)
        self.path = kwargs.get("path", None)
        self.ssl = kwargs.get("ssl", None)
        self.source_ip = self.opts.get("source_ip")
        self.source_port = self.opts.get("source_publish_port")
        self.on_recv_task = None
        if self.host is None and self.port is None:
            if self.path is None:
                raise RuntimeError("A host and port or a path must be provided")
        elif self.host and self.port:
            if self.path:
                raise RuntimeError(
                    "A host and port or a path must be provided, not both"
                )
        self.connect_callback = kwargs.get("connect_callback", _null_callback)
        self.disconnect_callback = kwargs.get("disconnect_callback", _null_callback)

    def close(self):
        if self._closing:
            return
        self._closing = True
        if self.on_recv_task:
            self.on_recv_task.cancel()
            self.on_recv_task = None
        if self._stream is not None:
            self._stream.close()
        self._stream = None
        self._closed = True

    async def getstream(self, **kwargs):
        if self.source_ip or self.source_port:
            kwargs.update(source_ip=self.source_ip, source_port=self.source_port)
        stream = None
        start = time.monotonic()
        timeout = kwargs.get("timeout", None)
        while stream is None and (not self._closed and not self._closing):
            try:
                if self.host and self.port:
                    log.debug(
                        "PubClient connecting to %r %r:%r", self, self.host, self.port
                    )
                    self._tcp_client = TCPClientKeepAlive(
                        self.opts, resolver=self.resolver
                    )
                    # ctx = None
                    # if self.ssl is not None:
                    #     ctx = salt.transport.base.ssl_context(
                    #         self.ssl, server_side=False
                    #     )
                    stream = await asyncio.wait_for(
                        self._tcp_client.connect(
                            ip_bracket(self.host, strip=True),
                            self.port,
                            # ssl_options=ctx,
                            ssl_options=self.opts.get("ssl"),
                            **kwargs,
                        ),
                        1,
                    )
                    self.unpacker = salt.utils.msgpack.Unpacker()
                    log.debug(
                        "PubClient conencted to %r %r:%r", self, self.host, self.port
                    )
                else:
                    log.debug("PubClient connecting to %r %r", self, self.path)
                    sock_type = socket.AF_UNIX
                    stream = tornado.iostream.IOStream(
                        socket.socket(sock_type, socket.SOCK_STREAM)
                    )
                    await asyncio.wait_for(stream.connect(self.path), 1)
                    self.unpacker = salt.utils.msgpack.Unpacker()
                    log.debug("PubClient conencted to %r %r", self, self.path)
            except Exception as exc:  # pylint: disable=broad-except
                if self.path:
                    _connect_to = self.path
                else:
                    _connect_to = f"{self.host}:{self.port}"
                log.warning(
                    "TCP Publish Client encountered an exception while connecting to"
                    " %s: %r, will reconnect in %d seconds - %s",
                    _connect_to,
                    exc,
                    self.backoff,
                    self._trace,
                )
                if timeout and time.monotonic() - start > timeout:
                    break
                await asyncio.sleep(self.backoff)
            if timeout and time.monotonic() - start > timeout:
                break
        return stream

    async def _connect(self, timeout=None):
        if self._stream is None:
            self._connect_called = True
            self._closing = False
            self._closed = False
            self._stream = await self.getstream(timeout=timeout)
            if self._stream:
                if self.connect_callback:
                    self.connect_callback(True)
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
            self.connect_callback = connect_callback
        if disconnect_callback:
            self.disconnect_callback = disconnect_callback
        await self._connect(timeout=timeout)

    def _decode_messages(self, messages):
        if not isinstance(messages, dict):
            # TODO: For some reason we need to decode here for things
            #       to work. Fix this.
            body = salt.payload.loads(messages)
            # body = salt.utils.msgpack.loads(messages)
            # body = salt.transport.frame.decode_embedded_strs(body)
        else:
            body = messages
        return body

    async def send(self, msg):
        await self._stream.write(msg)

    async def recv(self, timeout=None):
        while self._stream is None:
            await self.connect()
            await asyncio.sleep(0.001)
        if timeout == 0:
            for msg in self.unpacker:
                return msg[b"body"]
            try:
                events, _, _ = select.select([self._stream.socket], [], [], 0)
            except TimeoutError:
                events = []
            if events:
                while not self._closing:
                    async with self._read_in_progress:
                        try:
                            byts = await self._stream.read_bytes(4096, partial=True)
                        except tornado.iostream.StreamClosedError:
                            log.trace("Stream closed, reconnecting.")
                            stream = self._stream
                            self._stream = None
                            stream.close()
                            if self.disconnect_callback:
                                self.disconnect_callback()
                            await self.connect()
                            return
                        self.unpacker.feed(byts)
                        for msg in self.unpacker:
                            return msg[b"body"]
        elif timeout:
            try:
                return await asyncio.wait_for(self.recv(), timeout=timeout)
            except (
                TimeoutError,
                asyncio.exceptions.TimeoutError,
                asyncio.exceptions.CancelledError,
            ):
                self.close()
                await self.connect()
                return
        else:
            for msg in self.unpacker:
                return msg[b"body"]
            while not self._closing:
                async with self._read_in_progress:
                    try:
                        byts = await self._stream.read_bytes(4096, partial=True)
                    except tornado.iostream.StreamClosedError:
                        log.trace("Stream closed, reconnecting.")
                        stream = self._stream
                        self._stream = None
                        stream.close()
                        if self.disconnect_callback:
                            self.disconnect_callback()
                        await self.connect()
                        log.debug("Re-connected - continue")
                        continue
                    self.unpacker.feed(byts)
                    for msg in self.unpacker:
                        return msg[b"body"]

    async def on_recv_handler(self, callback):
        while not self._stream:
            # Retry quickly, we may want to increase this if it's hogging cpu.
            await asyncio.sleep(0.003)
        while True:
            msg = await self.recv()
            if msg:
                try:
                    # XXX This is handled better in the websocket transport work
                    await callback(msg)
                except Exception as exc:  # pylint: disable=broad-except
                    log.error(
                        "Unhandled exception while running callback %r",
                        self,
                        exc_info=True,
                    )

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


class TCPPubClient(PublishClient):
    def __init__(self, *args, **kwargs):  # pylint: disable=W0231
        salt.utils.versions.warn_until(
            3009,
            "TCPPubClient has been deprecated, use PublishClient instead.",
        )
        super().__init__(*args, **kwargs)


class RequestServer(salt.transport.base.DaemonizedRequestServer):
    """
    Tornado based TCP Request/Reply Server

    :param dict opts: Salt master config options.
    """

    # TODO: opts!
    backlog = 5

    def __init__(self, opts):  # pylint: disable=W0231
        self.opts = opts
        self._socket = None
        self.req_server = None
        self.ssl = self.opts.get("ssl", None)

    @property
    def socket(self):
        return self._socket

    def close(self):
        if self._socket is not None:
            try:
                self._socket.shutdown(socket.SHUT_RDWR)
            except OSError as exc:
                if exc.errno == errno.ENOTCONN:
                    # We may try to shutdown a socket which is already disconnected.
                    # Ignore this condition and continue.
                    pass
                else:
                    raise
            if self.req_server is None:
                # We only close the socket if we don't have a req_server instance.
                # If we did, because the req_server is also handling this socket, when we call
                # req_server.stop(), tornado will give us an AssertionError because it's trying to
                # match the socket.fileno() (after close it's -1) to the fd it holds on it's _sockets cache
                # so it can remove the socket from the IOLoop handlers
                self._socket.close()
            self._socket = None
        if self.req_server is not None:
            try:
                self.req_server.close()
            except OSError as exc:
                if exc.errno != 9:
                    raise
                log.exception(
                    "RequestServer close generated an exception: %s", str(exc)
                )
            self.req_server = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

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
        log.info("RequestServer workers %s", socket)

        with salt.utils.asynchronous.current_ioloop(io_loop):
            ctx = None
            if self.ssl is not None:
                ctx = salt.transport.base.ssl_context(self.ssl, server_side=True)
            if USE_LOAD_BALANCER:
                self.req_server = LoadBalancerWorker(
                    self.socket_queue,
                    self.handle_message,
                    ssl_options=ctx,
                )
            else:
                if salt.utils.platform.is_windows():
                    self._socket = _get_socket(self.opts)
                    self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    _set_tcp_keepalive(self._socket, self.opts)
                    self._socket.setblocking(0)
                    self._socket.bind(_get_bind_addr(self.opts, "ret_port"))
                self.req_server = SaltMessageServer(
                    self.handle_message,
                    ssl_options=ctx,
                    io_loop=io_loop,
                )
                self.req_server.add_socket(self._socket)
                self._socket.listen(self.backlog)

    async def handle_message(self, stream, payload, header=None):
        try:
            cert = stream.socket.getpeercert()
        except AttributeError:
            pass
        else:
            if cert:
                name = salt.transport.base.common_name(cert)
                log.error("Request client cert %r", name)
        payload = self.decode_payload(payload)
        reply = await self.message_handler(payload)
        # XXX Handle StreamClosedError
        stream.write(salt.transport.frame.frame_msg(reply, header=header))

    def decode_payload(self, payload):
        return payload


class TCPReqServer(RequestServer):
    def __init__(self, *args, **kwargs):  # pylint: disable=W0231
        salt.utils.versions.warn_until(
            3009,
            "TCPReqServer has been deprecated, use RequestServer instead.",
        )
        super().__init__(*args, **kwargs)


class SaltMessageServer(tornado.tcpserver.TCPServer):
    """
    Raw TCP server which will receive all of the TCP streams and re-assemble
    messages that are sent through to us
    """

    def __init__(self, message_handler, *args, **kwargs):
        io_loop = kwargs.pop("io_loop", None) or tornado.ioloop.IOLoop.current()
        self._closing = False
        super().__init__(*args, **kwargs)
        self.io_loop = io_loop
        self.clients = []
        self.message_handler = message_handler

    async def handle_stream(  # pylint: disable=arguments-differ,invalid-overridden-method
        self,
        stream,
        address,
        _StreamClosedError=tornado.iostream.StreamClosedError,
    ):
        """
        Handle incoming streams and add messages to the incoming queue
        """
        log.trace("Req client %s connected", address)
        self.clients.append((stream, address))
        unpacker = salt.utils.msgpack.Unpacker()
        try:
            while True:
                wire_bytes = await stream.read_bytes(4096, partial=True)
                unpacker.feed(wire_bytes)
                for framed_msg in unpacker:
                    framed_msg = salt.transport.frame.decode_embedded_strs(framed_msg)
                    header = framed_msg["head"]
                    self.io_loop.spawn_callback(
                        self.message_handler, stream, framed_msg["body"], header
                    )
        except _StreamClosedError:
            log.trace("req client disconnected %s", address)
            self.remove_client((stream, address))
        except Exception as e:  # pylint: disable=broad-except
            log.trace("other master-side exception: %s", e, exc_info=True)
            self.remove_client((stream, address))
            stream.close()

    def remove_client(self, client):
        try:
            self.clients.remove(client)
        except ValueError:
            log.trace("Message server client was not in list to remove")

    def close(self):
        """
        Close the server
        """
        if self._closing:
            return
        self._closing = True
        for item in self.clients:
            client, address = item
            client.close()
            self.remove_client(item)
        try:
            self.stop()
        except OSError as exc:
            if exc.errno != 9:
                raise


class LoadBalancerWorker(SaltMessageServer):
    """
    This will receive TCP connections from 'LoadBalancerServer' via
    a multiprocessing queue.
    Since the queue is shared amongst workers, only one worker will handle
    a given connection.
    """

    def __init__(self, socket_queue, message_handler, *args, **kwargs):
        super().__init__(message_handler, *args, **kwargs)
        self.socket_queue = socket_queue
        self._stop = threading.Event()
        self.thread = threading.Thread(target=self.socket_queue_thread)
        self.thread.start()

    def close(self):
        self._stop.set()
        self.thread.join()
        super().close()

    def socket_queue_thread(self):
        try:
            while True:
                try:
                    client_socket, address = self.socket_queue.get(True, 1)
                except queue.Empty:
                    if self._stop.is_set():
                        break
                    continue
                # 'self.io_loop' initialized in super class
                # 'salt.ext.tornado.tcpserver.TCPServer'.
                # 'self._handle_connection' defined in same super class.
                self.io_loop.spawn_callback(
                    self._handle_connection, client_socket, address
                )
        except (KeyboardInterrupt, SystemExit):
            pass


class TCPClientKeepAlive(tornado.tcpclient.TCPClient):
    """
    Override _create_stream() in TCPClient to enable keep alive support.
    """

    def __init__(self, opts, resolver=None):
        self.opts = opts
        super().__init__(resolver=resolver)

    def _create_stream(
        self, max_buffer_size, af, addr, **kwargs
    ):  # pylint: disable=unused-argument,arguments-differ
        """
        Override _create_stream() in TCPClient.

        Tornado 4.5 added the kwargs 'source_ip' and 'source_port'.
        Due to this, use **kwargs to swallow these and any future
        kwargs to maintain compatibility.
        """
        # Always connect in plaintext; we'll convert to ssl if necessary
        # after one connection has completed.
        sock = _get_socket(self.opts)
        _set_tcp_keepalive(sock, self.opts)
        stream = tornado.iostream.IOStream(sock, max_buffer_size=max_buffer_size)
        return stream, stream.connect(addr)


class MessageClient:
    """
    Low-level message sending client
    """

    def __init__(
        self,
        opts,
        host,
        port,
        io_loop=None,
        resolver=None,
        connect_callback=None,
        disconnect_callback=None,
        source_ip=None,
        source_port=None,
    ):
        salt.utils.versions.warn_until(
            3009,
            "MessageClient has been deprecated and will be removed.",
        )
        self.opts = opts
        self.host = host
        self.port = port
        self.source_ip = source_ip
        self.source_port = source_port
        self.connect_callback = connect_callback
        self.disconnect_callback = disconnect_callback
        self.io_loop = io_loop or tornado.ioloop.IOLoop.current()
        with salt.utils.asynchronous.current_ioloop(self.io_loop):
            self._tcp_client = TCPClientKeepAlive(opts, resolver=resolver)
        # TODO: max queue size
        self.send_future_map = {}  # mapping of request_id -> Future

        self._read_until_future = None
        self._on_recv = None
        self._closing = False
        self._closed = False
        self._connecting_future = tornado.concurrent.Future()
        self._stream_return_running = False
        self._stream = None

        self.backoff = opts.get("tcp_reconnect_backoff", 1)

    # TODO: timeout inflight sessions
    def close(self):
        if self._closing or self._closed:
            return
        self._closing = True
        self.io_loop.add_timeout(1, self.check_close)

    @tornado.gen.coroutine
    def check_close(self):
        if not self.send_future_map:
            self._tcp_client.close()
            self._stream = None
            self._closing = False
            self._closed = True
        else:
            self.io_loop.add_timeout(1, self.check_close)

    # pylint: disable=W1701
    def __del__(self):
        self.close()

    # pylint: enable=W1701

    @tornado.gen.coroutine
    def getstream(self, **kwargs):
        if self.source_ip or self.source_port:
            kwargs = {
                "source_ip": self.source_ip,
                "source_port": self.source_port,
            }
        stream = None
        while stream is None and (not self._closed and not self._closing):
            try:
                stream = yield self._tcp_client.connect(
                    ip_bracket(self.host, strip=True),
                    self.port,
                    ssl_options=self.opts.get("ssl"),
                    **kwargs,
                )
            except Exception as exc:  # pylint: disable=broad-except
                log.warning(
                    "TCP Message Client encountered an exception while connecting to"
                    " %s:%s: %r, will reconnect in %d seconds",
                    self.host,
                    self.port,
                    exc,
                    self.backoff,
                )
                yield tornado.gen.sleep(self.backoff)
        raise tornado.gen.Return(stream)

    @tornado.gen.coroutine
    def connect(self):
        if self._stream is None:
            self._stream = yield self.getstream()
            if self._stream:
                if not self._stream_return_running:
                    self.io_loop.spawn_callback(self._stream_return)
                if self.connect_callback:
                    self.connect_callback(True)

    @tornado.gen.coroutine
    def _stream_return(self):
        self._stream_return_running = True
        unpacker = salt.utils.msgpack.Unpacker()
        while not self._closing:
            try:
                wire_bytes = yield self._stream.read_bytes(4096, partial=True)
                unpacker.feed(wire_bytes)
                for framed_msg in unpacker:
                    framed_msg = salt.transport.frame.decode_embedded_strs(framed_msg)
                    header = framed_msg["head"]
                    body = framed_msg["body"]
                    message_id = header.get("mid")

                    if message_id in self.send_future_map:
                        self.send_future_map.pop(message_id).set_result(body)
                        # self.remove_message_timeout(message_id)
                    else:
                        if self._on_recv is not None:
                            self.io_loop.spawn_callback(self._on_recv, header, body)
                        else:
                            log.error(
                                "Got response for message_id %s that we are not"
                                " tracking",
                                message_id,
                            )
            except tornado.iostream.StreamClosedError as e:
                log.debug(
                    "tcp stream to %s:%s closed, unable to recv",
                    self.host,
                    self.port,
                )
                for future in self.send_future_map.values():
                    future.set_exception(e)
                self.send_future_map = {}
                if self._closing or self._closed:
                    return
                if self.disconnect_callback:
                    self.disconnect_callback()
                stream = self._stream
                self._stream = None
                if stream:
                    stream.close()
                unpacker = salt.utils.msgpack.Unpacker()
                yield self.connect()
            except TypeError:
                # This is an invalid transport
                if "detect_mode" in self.opts:
                    log.info(
                        "There was an error trying to use TCP transport; "
                        "attempting to fallback to another transport"
                    )
                else:
                    raise SaltClientError
            except Exception as e:  # pylint: disable=broad-except
                log.error("Exception parsing response", exc_info=True)
                for future in self.send_future_map.values():
                    future.set_exception(e)
                self.send_future_map = {}
                if self._closing or self._closed:
                    return
                if self.disconnect_callback:
                    self.disconnect_callback()
                stream = self._stream
                self._stream = None
                if stream:
                    stream.close()
                unpacker = salt.utils.msgpack.Unpacker()
                yield self.connect()
        self._stream_return_running = False

    def _message_id(self):
        return str(uuid.uuid4())

    # TODO: return a message object which takes care of multiplexing?
    def on_recv(self, callback):
        """
        Register a callback for received messages (that we didn't initiate)
        """
        if callback is None:
            self._on_recv = callback
        else:

            def wrap_recv(header, body):
                callback(body)

            self._on_recv = wrap_recv

    def remove_message_timeout(self, message_id):
        if message_id not in self.send_timeout_map:
            return
        timeout = self.send_timeout_map.pop(message_id)
        self.io_loop.remove_timeout(timeout)

    def timeout_message(self, message_id, msg):
        if message_id not in self.send_future_map:
            return
        future = self.send_future_map.pop(message_id)
        if future is not None:
            future.set_exception(SaltReqTimeoutError("Message timed out"))

    @tornado.gen.coroutine
    def send(self, msg, timeout=None, callback=None, raw=False):
        if self._closing:
            raise ClosingError()
        message_id = self._message_id()
        header = {"mid": message_id}

        future = tornado.concurrent.Future()

        if callback is not None:

            def handle_future(future):
                response = future.result()
                self.io_loop.add_callback(callback, response)

            future.add_done_callback(handle_future)
        # Add this future to the mapping
        self.send_future_map[message_id] = future

        if self.opts.get("detect_mode") is True:
            timeout = 1

        if timeout is not None:
            self.io_loop.call_later(timeout, self.timeout_message, message_id, msg)

        item = salt.transport.frame.frame_msg(msg, header=header)

        @tornado.gen.coroutine
        def _do_send():
            yield self.connect()
            # If the _stream is None, we failed to connect.
            if self._stream:
                yield self._stream.write(item)

        # Run send in a callback so we can wait on the future, in case we time
        # out before we are able to connect.
        self.io_loop.add_callback(_do_send)
        recv = yield future
        raise tornado.gen.Return(recv)


class Subscriber:
    """
    Client object for use with the TCP publisher server
    """

    def __init__(self, stream, address):
        self.stream = stream
        self.address = address
        self._closing = False
        self._read_until_future = None
        self.id_ = None

    def close(self):
        if self._closing:
            return
        self._closing = True
        if not self.stream.closed():
            self.stream.close()
            if self._read_until_future is not None and self._read_until_future.done():
                # This will prevent this message from showing up:
                # '[ERROR   ] Future exception was never retrieved:
                # StreamClosedError'
                # This happens because the logic is always waiting to read
                # the next message and the associated read future is marked
                # 'StreamClosedError' when the stream is closed.
                self._read_until_future.exception()

    # pylint: disable=W1701
    def __del__(self):
        if not self._closing:
            warnings.warn(
                "unclosed publish subscriber {self!r}", ResourceWarning, source=self
            )

    # pylint: enable=W1701


class PubServer(tornado.tcpserver.TCPServer):
    """
    TCP publisher
    """

    def __init__(
        self,
        opts,
        io_loop=None,
        presence_callback=None,
        remove_presence_callback=None,
        ssl=None,
    ):
        super().__init__(ssl_options=ssl)
        self.io_loop = io_loop
        self.opts = opts
        self._closing = False
        self.clients = set()
        self.presence_events = False
        if presence_callback:
            self.presence_callback = presence_callback
        else:
            self.presence_callback = lambda subscriber, msg: msg
        if remove_presence_callback:
            self.remove_presence_callback = remove_presence_callback
        else:
            self.remove_presence_callback = lambda subscriber: subscriber
        self.ssl = ssl

    def close(self):
        if self._closing:
            return
        self._closing = True
        for client in self.clients:
            client.stream.close()

    # pylint: disable=W1701
    def __del__(self):
        self.close()

    # pylint: enable=W1701

    async def _stream_read(self, client):
        unpacker = salt.utils.msgpack.Unpacker()
        while not self._closing:
            try:
                client._read_until_future = client.stream.read_bytes(4096, partial=True)
                wire_bytes = await client._read_until_future
                unpacker.feed(wire_bytes)
                for framed_msg in unpacker:
                    framed_msg = salt.transport.frame.decode_embedded_strs(framed_msg)
                    body = framed_msg["body"]
                    if self.presence_callback:
                        self.presence_callback(client, body)
            except tornado.iostream.StreamClosedError as e:
                log.debug("tcp stream to %s closed, unable to recv", client.address)
                client.close()
                self.remove_presence_callback(client)
                self.clients.discard(client)
                break
            except Exception as e:  # pylint: disable=broad-except
                log.error(
                    "Exception parsing response from %s", client.address, exc_info=True
                )
                continue

    def handle_stream(self, stream, address):
        try:
            cert = stream.socket.getpeercert()
        except AttributeError:
            pass
        else:
            if cert:
                name = salt.transport.base.common_name(cert)
                log.error("Request client cert %r", name)
        log.debug("Subscriber at %s connected", address)
        client = Subscriber(stream, address)
        self.clients.add(client)
        self.io_loop.spawn_callback(self._stream_read, client)

    # TODO: ACK the publish through IPC
    async def publish_payload(self, package, topic_list=None):
        log.trace(
            "TCP PubServer sending payload: topic_list=%r %r", topic_list, package
        )
        payload = salt.transport.frame.frame_msg(package)
        to_remove = []
        if topic_list:
            for topic in topic_list:
                sent = False
                for client in list(self.clients):
                    if topic == client.id_:
                        try:
                            # Write the packed str
                            await client.stream.write(payload)
                            sent = True
                            # self.io_loop.add_future(f, lambda f: True)
                        except tornado.iostream.StreamClosedError:
                            to_remove.append(client)
                if not sent:
                    log.debug("Publish target %s not connected %r", topic, self.clients)
        else:
            for client in list(self.clients):
                try:
                    # Write the packed str
                    await client.stream.write(payload)
                except tornado.iostream.StreamClosedError:
                    to_remove.append(client)
        for client in to_remove:
            log.debug(
                "Subscriber at %s has disconnected from publisher", client.address
            )
            client.close()
            self.remove_presence_callback(client)
            self.clients.discard(client)
        log.trace("TCP PubServer finished publishing payload")


class TCPPuller:
    """
    A Tornado IPC server very similar to Tornado's TCPServer class
    but using either UNIX domain sockets or TCP sockets
    """

    def __init__(
        self, host=None, port=None, path=None, io_loop=None, payload_handler=None
    ):
        """
        Create a new Tornado IPC server

        :param str/int socket_path: Path on the filesystem for the
                                    socket to bind to. This socket does
                                    not need to exist prior to calling
                                    this method, but parent directories
                                    should.
                                    It may also be of type 'int', in
                                    which case it is used as the port
                                    for a tcp localhost connection.
        :param IOLoop io_loop: A Tornado ioloop to handle scheduling
        :param func payload_handler: A function to customize handling of
                                     incoming data.
        """
        self.host = host
        self.port = port
        self.path = path
        self._started = False
        self.payload_handler = payload_handler

        # Placeholders for attributes to be populated by method calls
        self.sock = None
        self.io_loop = io_loop or tornado.ioloop.IOLoop.current()
        self._closing = False

    def start(self):
        """
        Perform the work necessary to start up a Tornado IPC server

        Blocks until socket is established
        """
        # Start up the ioloop
        if self.path:
            log.trace("IPCServer: binding to socket: %s", self.path)
            self.sock = tornado.netutil.bind_unix_socket(self.path)
        else:
            log.trace("IPCServer: binding to socket: %s:%s", self.host, self.port)
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.setblocking(0)
            self.sock.bind((self.host, self.port))
            # Based on default used in tornado.netutil.bind_sockets()
            self.sock.listen(128)

        tornado.netutil.add_accept_handler(
            self.sock,
            self.handle_connection,
        )
        self._started = True

    async def handle_stream(self, stream):
        """
        Override this to handle the streams as they arrive

        :param IOStream stream: An IOStream for processing

        See https://tornado.readthedocs.io/en/latest/iostream.html#tornado.iostream.IOStream
        for additional details.
        """

        async def _null(msg):
            return

        def write_callback(stream, header):
            if header.get("mid"):

                async def return_message(msg):
                    pack = salt.transport.frame.frame_msg_ipc(
                        msg,
                        header={"mid": header["mid"]},
                        raw_body=True,
                    )
                    await stream.write(pack)

                return return_message
            else:
                return _null

        unpacker = salt.utils.msgpack.Unpacker(raw=False)
        while not stream.closed():
            try:
                wire_bytes = await stream.read_bytes(4096, partial=True)
                unpacker.feed(wire_bytes)
                for framed_msg in unpacker:
                    body = framed_msg["body"]
                    self.io_loop.spawn_callback(
                        self.payload_handler,
                        body,
                        write_callback(stream, framed_msg["head"]),
                    )
            except tornado.iostream.StreamClosedError:
                if self.path:
                    log.trace("Client disconnected from IPC %s", self.path)
                else:
                    log.trace(
                        "Client disconnected from IPC %s:%s", self.host, self.port
                    )
                break
            except OSError as exc:
                # On occasion an exception will occur with
                # an error code of 0, it's a spurious exception.
                if exc.errno == 0:
                    log.trace(
                        "Exception occurred with error number 0, "
                        "spurious exception: %s",
                        exc,
                    )
                else:
                    log.error("Exception occurred while handling stream: %s", exc)
            except Exception as exc:  # pylint: disable=broad-except
                log.error("Exception occurred while handling stream: %s", exc)

    def handle_connection(self, connection, address):
        log.trace(
            "IPCServer: Handling connection to address: %s",
            address if address else connection,
        )
        try:
            stream = tornado.iostream.IOStream(
                connection,
            )
            self.io_loop.spawn_callback(self.handle_stream, stream)
        except Exception as exc:  # pylint: disable=broad-except
            log.error("IPC streaming error: %s", exc)

    def close(self):
        """
        Routines to handle any cleanup before the instance shuts down.
        Sockets and filehandles should be closed explicitly, to prevent
        leaks.
        """
        if self._closing:
            return
        self._closing = True
        if hasattr(self.sock, "close"):
            self.sock.close()

    # pylint: disable=W1701
    def __del__(self):
        if not self._closing:
            warnings.warn("unclosed tcp puller {self!r}", ResourceWarning, source=self)

    # pylint: enable=W1701

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class PublishServer(salt.transport.base.DaemonizedPublishServer):
    """
    Tornado based TCP PublishServer
    """

    # TODO: opts!
    # Based on default used in tornado.netutil.bind_sockets()
    backlog = 128
    async_methods = [
        "publish",
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
        self.pub_sock = None
        self.pub_host = pub_host
        self.pub_port = pub_port
        self.pub_path = pub_path
        self.pull_host = pull_host
        self.pull_port = pull_port
        self.pull_path = pull_path
        self.ssl = ssl

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
        # Spin up the publisher
        ctx = None
        if self.ssl is not None:
            ctx = salt.transport.base.ssl_context(self.ssl, server_side=True)
        self.pub_server = pub_server = PubServer(
            self.opts,
            io_loop=io_loop,
            presence_callback=presence_callback,
            remove_presence_callback=remove_presence_callback,
            ssl=ctx,
        )
        if self.pub_path:
            log.error(
                "Publish server binding pub to %s ssl=%r", self.pub_path, self.ssl
            )
            sock = tornado.netutil.bind_unix_socket(self.pub_path)
        else:
            log.error(
                "Publish server binding pub to %s:%s ssl=%r",
                self.pub_host,
                self.pub_port,
                self.ssl,
            )
            sock = _get_socket(self.opts)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            _set_tcp_keepalive(sock, self.opts)
            sock.setblocking(0)
            sock.bind((self.pub_host, self.pub_port))
        sock.listen(self.backlog)
        # pub_server will take ownership of the socket
        pub_server.add_socket(sock)

        # Set up Salt IPC server
        self.pub_server = pub_server
        if self.pull_path:
            log.debug("Publish server binding pull to %s", self.pull_path)
            pull_path = self.pull_path
        else:
            log.debug(
                "Publish server binding pull to %s:%s", self.pull_host, self.pull_port
            )
            pull_host = self.pull_host
            pull_port = self.pull_port

        self.pull_sock = TCPPuller(
            host=self.pull_host,
            port=self.pull_port,
            path=self.pull_path,
            io_loop=io_loop,
            payload_handler=publish_payload,
        )

        # Securely create socket
        with salt.utils.files.set_umask(0o177):
            self.pull_sock.start()

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

    async def publish_payload(self, payload, *args):
        return await self.pub_server.publish_payload(payload)

    def connect(self, timeout=None):
        self.pub_sock = salt.utils.asynchronous.SyncWrapper(
            _TCPPubServerPublisher,
            (
                self.pull_host,
                self.pull_port,
                self.pull_path,
            ),
            loop_kwarg="io_loop",
        )
        self.pub_sock.connect(timeout=timeout)

    async def publish(
        self, payload, **kwargs
    ):  # pylint: disable=invalid-overridden-method
        """
        Publish "load" to minions
        """
        if not self.pub_sock:
            self.connect()
        self.pub_sock.send(payload)

    def close(self):
        if self.pub_sock:
            self.pub_sock.close()
            self.pub_sock = None


class TCPPublishServer(PublishServer):
    def __init__(self, *args, **kwargs):  # pylint: disable=W0231
        salt.utils.versions.warn_until(
            3009,
            "TCPPublishServer has been deprecated, use PublishServer instead.",
        )
        super().__init__(*args, **kwargs)


class _TCPPubServerPublisher:
    """
    Salt IPC message client

    Create an IPC client to send messages to an IPC server

    An example of a very simple IPCMessageClient connecting to an IPCServer. This
    example assumes an already running IPCMessage server.

    IMPORTANT: The below example also assumes a running IOLoop process.

    # Import Tornado libs
    import tornado.ioloop

    # Import Salt libs
    import salt.config
    import salt.transport.ipc

    io_loop = tornado.ioloop.IOLoop.current()

    ipc_server_socket_path = '/var/run/ipc_server.ipc'

    ipc_client = salt.transport.ipc.IPCMessageClient(ipc_server_socket_path, io_loop=io_loop)

    # Connect to the server
    ipc_client.connect()

    # Send some data
    ipc_client.send('Hello world')
    """

    async_methods = [
        "send",
        "connect",
        "_connect",
    ]
    close_methods = [
        "close",
    ]

    def __init__(self, host, port, path, io_loop=None):
        """
        Create a new IPC client

        IPC clients cannot bind to ports, but must connect to
        existing IPC servers. Clients can then send messages
        to the server.

        """
        self.io_loop = io_loop or tornado.ioloop.IOLoop.current()
        self.host = host
        self.port = port
        self.path = path
        self._closing = False
        self.stream = None
        self.unpacker = salt.utils.msgpack.Unpacker(raw=False)
        self._connecting_future = None

    def connected(self):
        return self.stream is not None and not self.stream.closed()

    def connect(self, callback=None, timeout=None):
        """
        Connect to the IPC socket
        """
        if self._connecting_future is not None and not self._connecting_future.done():
            future = self._connecting_future
        else:
            if self._connecting_future is not None:
                # read previous future result to prevent the "unhandled future exception" error
                self._connecting_future.exception()  # pylint: disable=E0203
            future = tornado.concurrent.Future()
            self._connecting_future = future
            # self._connect(timeout)
            self.io_loop.spawn_callback(self._connect, timeout)

        if callback is not None:

            def handle_future(future):
                response = future.result()
                self.io_loop.add_callback(callback, response)

            future.add_done_callback(handle_future)

        return future

    async def _connect(self, timeout=None):
        """
        Connect to a running IPCServer
        """
        if self.path:
            sock_type = socket.AF_UNIX
            sock_addr = self.path
            log.debug("Publisher connecting to %s", self.path)
        else:
            sock_type = socket.AF_INET
            sock_addr = (self.host, self.port)
            log.debug("Publisher connecting to %s:%s", self.host, self.port)

        self.stream = None
        if timeout is not None:
            timeout_at = time.monotonic() + timeout

        while True:
            if self._closing:
                break

            if self.stream is None:
                # with salt.utils.asynchronous.current_ioloop(self.io_loop):
                self.stream = tornado.iostream.IOStream(
                    socket.socket(sock_type, socket.SOCK_STREAM)
                )
            try:
                await self.stream.connect(sock_addr)
                self._connecting_future.set_result(True)
                break
            except Exception as e:  # pylint: disable=broad-except
                if self.stream.closed():
                    self.stream = None

                if timeout is None or time.monotonic() > timeout_at:
                    if self.stream is not None:
                        self.stream.close()
                        self.stream = None
                    self._connecting_future.set_exception(e)
                    break

    def close(self):
        """
        Routines to handle any cleanup before the instance shuts down.
        Sockets and filehandles should be closed explicitly, to prevent
        leaks.
        """
        if self._closing:
            return

        self._closing = True
        self._connecting_future = None

        log.debug("Closing %s instance", self.__class__.__name__)

        if self.stream is not None and not self.stream.closed():
            try:
                self.stream.close()
            except OSError as exc:
                if exc.errno != errno.EBADF:
                    # If its not a bad file descriptor error, raise
                    raise

    # pylint: disable=W1701
    def __del__(self):
        if not self._closing:
            warnings.warn(
                "unclosed publisher client {self!r}", ResourceWarning, source=self
            )

    # pylint: enable=W1701

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # FIXME timeout unimplemented
    # FIXME tries unimplemented
    async def send(self, msg, timeout=None, tries=None):
        """
        Send a message to an IPC socket

        If the socket is not currently connected, a connection will be established.

        :param dict msg: The message to be sent
        :param int timeout: Timeout when sending message (Currently unimplemented)
        """
        if not self.connected():
            await self.connect()
        pack = salt.transport.frame.frame_msg_ipc(msg, raw_body=True)
        await self.stream.write(pack)


class RequestClient(salt.transport.base.RequestClient):
    """
    Tornado based TCP RequestClient
    """

    ttype = "tcp"

    def __init__(self, opts, io_loop, **kwargs):  # pylint: disable=W0231
        super().__init__(opts, io_loop, **kwargs)
        self.opts = opts
        self.io_loop = io_loop

        parse = urllib.parse.urlparse(self.opts["master_uri"])
        master_host, master_port = parse.netloc.rsplit(":", 1)
        master_addr = (master_host, int(master_port))
        resolver = kwargs.get("resolver", None)
        self.host = master_host
        self.port = int(master_port)
        self._tcp_client = TCPClientKeepAlive(opts)
        self.source_ip = opts.get("source_ip")
        self.source_port = opts.get("source_ret_port")
        self._mid = 1
        self._max_messages = int((1 << 31) - 2)  # number of IDs before we wrap
        # TODO: max queue size
        self.send_queue = []  # queue of messages to be sent
        self.send_future_map = {}  # mapping of request_id -> Future

        self._read_until_future = None
        self._on_recv = None
        self._closing = False
        self._closed = False
        self._stream_return_running = False
        self._stream = None
        self.disconnect_callback = _null_callback
        self.connect_callback = _null_callback
        self.backoff = opts.get("tcp_reconnect_backoff", 1)
        self.ssl = self.opts.get("ssl", None)

    async def getstream(self, **kwargs):
        if self.source_ip or self.source_port:
            kwargs.update(source_ip=self.source_ip, source_port=self.source_port)
        stream = None
        while stream is None and (not self._closed and not self._closing):
            try:
                # XXX: Support ipc sockets too
                ctx = None
                if self.ssl is not None:
                    ctx = salt.transport.base.ssl_context(self.ssl, server_side=False)
                stream = await self._tcp_client.connect(
                    ip_bracket(self.host, strip=True),
                    self.port,
                    ssl_options=ctx,
                    **kwargs,
                )
            except Exception as exc:  # pylint: disable=broad-except
                log.warning(
                    "TCP Message Client encountered an exception while connecting to"
                    " %s:%s: %r, will reconnect in %d seconds",
                    self.host,
                    self.port,
                    exc,
                    self.backoff,
                )
                await asyncio.sleep(self.backoff)
        return stream

    async def connect(self):  # pylint: disable=invalid-overridden-method
        if self._stream is None:
            self._connect_called = True
            self._stream = await self.getstream()
            if self._stream:
                if not self._stream_return_running:
                    self.task = asyncio.create_task(self._stream_return())
                if self.connect_callback is not None:
                    self.connect_callback()

    async def _stream_return(self):
        self._stream_return_running = True
        unpacker = salt.utils.msgpack.Unpacker()
        while not self._closing:
            try:
                wire_bytes = await self._stream.read_bytes(4096, partial=True)
                unpacker.feed(wire_bytes)
                for framed_msg in unpacker:
                    framed_msg = salt.transport.frame.decode_embedded_strs(framed_msg)
                    header = framed_msg["head"]
                    body = framed_msg["body"]
                    message_id = header.get("mid")

                    if message_id in self.send_future_map:
                        self.send_future_map.pop(message_id).set_result(body)
                    else:
                        if self._on_recv is not None:
                            self.io_loop.spawn_callback(self._on_recv, header, body)
                        else:
                            log.error(
                                "Got response for message_id %s that we are not"
                                " tracking",
                                message_id,
                            )
            except tornado.iostream.StreamClosedError as e:
                log.error(
                    "tcp stream to %s:%s closed, unable to recv",
                    self.host,
                    self.port,
                )
                for future in self.send_future_map.values():
                    future.set_exception(e)
                self.send_future_map = {}
                if self._closing or self._closed:
                    return
                if self.disconnect_callback is not None:
                    self.disconnect_callback()
                stream = self._stream
                self._stream = None
                if stream:
                    stream.close()
                unpacker = salt.utils.msgpack.Unpacker()
                await self.connect()
            except TypeError:
                # This is an invalid transport
                if "detect_mode" in self.opts:
                    log.info(
                        "There was an error trying to use TCP transport; "
                        "attempting to fallback to another transport"
                    )
                else:
                    raise SaltClientError
            except Exception as e:  # pylint: disable=broad-except
                log.error("Exception parsing response", exc_info=True)
                for future in self.send_future_map.values():
                    future.set_exception(e)
                self.send_future_map = {}
                if self._closing or self._closed:
                    return
                if self.disconnect_callback is not None:
                    self.disconnect_callback()
                stream = self._stream
                self._stream = None
                if stream:
                    stream.close()
                unpacker = salt.utils.msgpack.Unpacker()
                await self.connect()
        self._stream_return_running = False

    def _message_id(self):
        wrap = False
        while self._mid in self.send_future_map:
            if self._mid >= self._max_messages:
                if wrap:
                    # this shouldn't ever happen, but just in case
                    raise Exception("Unable to find available messageid")
                self._mid = 1
                wrap = True
            else:
                self._mid += 1

        return self._mid

    def timeout_message(self, message_id, msg):
        if message_id not in self.send_future_map:
            return
        future = self.send_future_map.pop(message_id)
        if future is not None:
            future.set_exception(SaltReqTimeoutError("Message timed out"))

    async def send(self, load, timeout=60):
        await self.connect()
        if self._closing:
            raise ClosingError()
        while not self._stream:
            await asyncio.sleep(0.03)
        message_id = self._message_id()
        header = {"mid": message_id}
        future = tornado.concurrent.Future()

        # Add this future to the mapping
        self.send_future_map[message_id] = future

        if self.opts.get("detect_mode") is True:
            timeout = 1

        if timeout is not None:
            self.io_loop.call_later(timeout, self.timeout_message, message_id, load)

        item = salt.transport.frame.frame_msg(load, header=header)

        async def _do_send():
            await self.connect()
            # If the _stream is None, we failed to connect.
            if self._stream:
                await self._stream.write(item)

        # Run send in a callback so we can wait on the future, in case we time
        # out before we are able to connect.
        self.io_loop.add_callback(_do_send)
        recv = await future
        return recv

    def close(self):
        if self._closing:
            return
        if self._stream is not None:
            self._stream.close()
            self._stream = None


class TCPReqClient(RequestClient):
    def __init__(self, *args, **kwargs):  # pylint: disable=W0231
        salt.utils.versions.warn_until(
            3009,
            "TCPReqClient has been deprecated, use RequestClient instead.",
        )
        super().__init__(*args, **kwargs)
