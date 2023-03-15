"""
TCP transport classes

Wire protocol: "len(payload) msgpack({'head': SOMEHEADER, 'body': SOMEBODY})"


"""


import errno
import logging
import multiprocessing
import os
import queue
import socket
import threading
import urllib

import salt.ext.tornado
import salt.ext.tornado.concurrent
import salt.ext.tornado.gen
import salt.ext.tornado.iostream
import salt.ext.tornado.netutil
import salt.ext.tornado.tcpclient
import salt.ext.tornado.tcpserver
import salt.master
import salt.payload
import salt.transport.client
import salt.transport.frame
import salt.transport.ipc
import salt.transport.server
import salt.utils.asynchronous
import salt.utils.files
import salt.utils.msgpack
import salt.utils.platform
import salt.utils.versions
from salt.exceptions import SaltClientError, SaltReqTimeoutError
from salt.utils.network import ip_bracket

if salt.utils.platform.is_windows():
    USE_LOAD_BALANCER = True
else:
    USE_LOAD_BALANCER = False

if USE_LOAD_BALANCER:
    import salt.ext.tornado.util
    from salt.utils.process import SignalHandlingProcess

log = logging.getLogger(__name__)


class ClosingError(Exception):
    """ """


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


if USE_LOAD_BALANCER:

    class LoadBalancerServer(SignalHandlingProcess):
        """
        Raw TCP server which runs in its own process and will listen
        for incoming connections. Each incoming connection will be
        sent via multiprocessing queue to the workers.
        Since the queue is shared amongst workers, only one worker will
        handle a given connection.
        """

        # TODO: opts!
        # Based on default used in salt.ext.tornado.netutil.bind_sockets()
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
                    if (
                        salt.ext.tornado.util.errno_from_exception(e)
                        == errno.ECONNABORTED
                    ):
                        continue
                    raise


class Resolver:

    _resolver_configured = False

    @classmethod
    def _config_resolver(cls, num_threads=10):
        salt.ext.tornado.netutil.Resolver.configure(
            "salt.ext.tornado.netutil.ThreadedResolver", num_threads=num_threads
        )
        cls._resolver_configured = True

    def __init__(self, *args, **kwargs):
        if not self._resolver_configured:
            # TODO: add opt to specify number of resolver threads
            self._config_resolver()


class TCPPubClient(salt.transport.base.PublishClient):
    """
    Tornado based TCP Pub Client
    """

    ttype = "tcp"

    def __init__(self, opts, io_loop, **kwargs):  # pylint: disable=W0231
        self.opts = opts
        self.io_loop = io_loop
        self.message_client = None
        self.connected = False
        self._closing = False
        self.resolver = Resolver()

    def close(self):
        if self._closing:
            return
        self._closing = True
        if self.message_client is not None:
            self.message_client.close()
            self.message_client = None

    # pylint: disable=W1701
    def __del__(self):
        self.close()

    # pylint: enable=W1701

    @salt.ext.tornado.gen.coroutine
    def connect(self, publish_port, connect_callback=None, disconnect_callback=None):
        self.publish_port = publish_port
        self.message_client = MessageClient(
            self.opts,
            self.opts["master_ip"],
            int(self.publish_port),
            io_loop=self.io_loop,
            connect_callback=connect_callback,
            disconnect_callback=disconnect_callback,
            source_ip=self.opts.get("source_ip"),
            source_port=self.opts.get("source_publish_port"),
        )
        yield self.message_client.connect()  # wait for the client to be connected
        self.connected = True

    @salt.ext.tornado.gen.coroutine
    def _decode_messages(self, messages):
        if not isinstance(messages, dict):
            # TODO: For some reason we need to decode here for things
            #       to work. Fix this.
            body = salt.utils.msgpack.loads(messages)
            body = salt.transport.frame.decode_embedded_strs(body)
        else:
            body = messages
        raise salt.ext.tornado.gen.Return(body)

    @salt.ext.tornado.gen.coroutine
    def send(self, msg):
        yield self.message_client._stream.write(msg)

    def on_recv(self, callback):
        """
        Register an on_recv callback
        """
        return self.message_client.on_recv(callback)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class TCPReqServer(salt.transport.base.DaemonizedRequestServer):
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
                    "TCPReqServerChannel close generated an exception: %s", str(exc)
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

        with salt.utils.asynchronous.current_ioloop(io_loop):
            if USE_LOAD_BALANCER:
                self.req_server = LoadBalancerWorker(
                    self.socket_queue,
                    self.handle_message,
                    ssl_options=self.opts.get("ssl"),
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
                    ssl_options=self.opts.get("ssl"),
                    io_loop=io_loop,
                )
                self.req_server.add_socket(self._socket)
                self._socket.listen(self.backlog)

    @salt.ext.tornado.gen.coroutine
    def handle_message(self, stream, payload, header=None):
        payload = self.decode_payload(payload)
        reply = yield self.message_handler(payload)
        stream.write(salt.transport.frame.frame_msg(reply, header=header))

    def decode_payload(self, payload):
        return payload


class SaltMessageServer(salt.ext.tornado.tcpserver.TCPServer):
    """
    Raw TCP server which will receive all of the TCP streams and re-assemble
    messages that are sent through to us
    """

    def __init__(self, message_handler, *args, **kwargs):
        io_loop = (
            kwargs.pop("io_loop", None) or salt.ext.tornado.ioloop.IOLoop.current()
        )
        self._closing = False
        super().__init__(*args, **kwargs)
        self.io_loop = io_loop
        self.clients = []
        self.message_handler = message_handler

    @salt.ext.tornado.gen.coroutine
    def handle_stream(  # pylint: disable=arguments-differ
        self,
        stream,
        address,
        _StreamClosedError=salt.ext.tornado.iostream.StreamClosedError,
    ):
        """
        Handle incoming streams and add messages to the incoming queue
        """
        log.trace("Req client %s connected", address)
        self.clients.append((stream, address))
        unpacker = salt.utils.msgpack.Unpacker()
        try:
            while True:
                wire_bytes = yield stream.read_bytes(4096, partial=True)
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


if USE_LOAD_BALANCER:

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


class TCPClientKeepAlive(salt.ext.tornado.tcpclient.TCPClient):
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
        stream = salt.ext.tornado.iostream.IOStream(
            sock, max_buffer_size=max_buffer_size
        )
        if salt.ext.tornado.version_info < (5,):
            return stream.connect(addr)
        return stream, stream.connect(addr)


# TODO consolidate with IPCClient
# TODO: limit in-flight messages.
# TODO: singleton? Something to not re-create the tcp connection so much
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
        self.opts = opts
        self.host = host
        self.port = port
        self.source_ip = source_ip
        self.source_port = source_port
        self.connect_callback = connect_callback
        self.disconnect_callback = disconnect_callback
        self.io_loop = io_loop or salt.ext.tornado.ioloop.IOLoop.current()
        with salt.utils.asynchronous.current_ioloop(self.io_loop):
            self._tcp_client = TCPClientKeepAlive(opts, resolver=resolver)
        self._mid = 1
        self._max_messages = int((1 << 31) - 2)  # number of IDs before we wrap
        # TODO: max queue size
        self.send_queue = []  # queue of messages to be sent
        self.send_future_map = {}  # mapping of request_id -> Future

        self._read_until_future = None
        self._on_recv = None
        self._closing = False
        self._closed = False
        self._connecting_future = salt.ext.tornado.concurrent.Future()
        self._stream_return_running = False
        self._stream = None

        self.backoff = opts.get("tcp_reconnect_backoff", 1)

    def _stop_io_loop(self):
        if self.io_loop is not None:
            self.io_loop.stop()

    # TODO: timeout inflight sessions
    def close(self):
        if self._closing:
            return
        self._closing = True
        self.io_loop.add_timeout(1, self.check_close)

    @salt.ext.tornado.gen.coroutine
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

    @salt.ext.tornado.gen.coroutine
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
                    **kwargs
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
                yield salt.ext.tornado.gen.sleep(self.backoff)
        raise salt.ext.tornado.gen.Return(stream)

    @salt.ext.tornado.gen.coroutine
    def connect(self):
        if self._stream is None:
            self._stream = yield self.getstream()
            if self._stream:
                if not self._stream_return_running:
                    self.io_loop.spawn_callback(self._stream_return)
                if self.connect_callback:
                    self.connect_callback(True)

    @salt.ext.tornado.gen.coroutine
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
            except salt.ext.tornado.iostream.StreamClosedError as e:
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

    @salt.ext.tornado.gen.coroutine
    def send(self, msg, timeout=None, callback=None, raw=False):
        if self._closing:
            raise ClosingError()
        message_id = self._message_id()
        header = {"mid": message_id}

        future = salt.ext.tornado.concurrent.Future()

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

        @salt.ext.tornado.gen.coroutine
        def _do_send():
            yield self.connect()
            # If the _stream is None, we failed to connect.
            if self._stream:
                yield self._stream.write(item)

        # Run send in a callback so we can wait on the future, in case we time
        # out before we are able to connect.
        self.io_loop.add_callback(_do_send)
        recv = yield future
        raise salt.ext.tornado.gen.Return(recv)


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
        self.close()

    # pylint: enable=W1701


class PubServer(salt.ext.tornado.tcpserver.TCPServer):
    """
    TCP publisher
    """

    def __init__(
        self, opts, io_loop=None, presence_callback=None, remove_presence_callback=None
    ):
        super().__init__(ssl_options=opts.get("ssl"))
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

    def close(self):
        if self._closing:
            return
        self._closing = True
        for client in self.clients:
            client.stream.disconnect()

    # pylint: disable=W1701
    def __del__(self):
        self.close()

    # pylint: enable=W1701

    @salt.ext.tornado.gen.coroutine
    def _stream_read(self, client):
        unpacker = salt.utils.msgpack.Unpacker()
        while not self._closing:
            try:
                client._read_until_future = client.stream.read_bytes(4096, partial=True)
                wire_bytes = yield client._read_until_future
                unpacker.feed(wire_bytes)
                for framed_msg in unpacker:
                    framed_msg = salt.transport.frame.decode_embedded_strs(framed_msg)
                    body = framed_msg["body"]
                    if self.presence_callback:
                        self.presence_callback(client, body)
            except salt.ext.tornado.iostream.StreamClosedError as e:
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
        log.debug("Subscriber at %s connected", address)
        client = Subscriber(stream, address)
        self.clients.add(client)
        self.io_loop.spawn_callback(self._stream_read, client)

    # TODO: ACK the publish through IPC
    @salt.ext.tornado.gen.coroutine
    def publish_payload(self, package, topic_list=None):
        log.trace("TCP PubServer sending payload: %s \n\n %r", package, topic_list)
        payload = salt.transport.frame.frame_msg(package)
        to_remove = []
        if topic_list:
            for topic in topic_list:
                sent = False
                for client in self.clients:
                    if topic == client.id_:
                        try:
                            # Write the packed str
                            yield client.stream.write(payload)
                            sent = True
                            # self.io_loop.add_future(f, lambda f: True)
                        except salt.ext.tornado.iostream.StreamClosedError:
                            to_remove.append(client)
                if not sent:
                    log.debug("Publish target %s not connected %r", topic, self.clients)
        else:
            for client in self.clients:
                try:
                    # Write the packed str
                    yield client.stream.write(payload)
                except salt.ext.tornado.iostream.StreamClosedError:
                    to_remove.append(client)
        for client in to_remove:
            log.debug(
                "Subscriber at %s has disconnected from publisher", client.address
            )
            client.close()
            self.remove_presence_callback(client)
            self.clients.discard(client)
        log.trace("TCP PubServer finished publishing payload")


class TCPPublishServer(salt.transport.base.DaemonizedPublishServer):
    """
    Tornado based TCP PublishServer
    """

    # TODO: opts!
    # Based on default used in salt.ext.tornado.netutil.bind_sockets()
    backlog = 128

    def __init__(self, opts):
        self.opts = opts
        self.pub_sock = None

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
        io_loop = salt.ext.tornado.ioloop.IOLoop()
        io_loop.make_current()

        # Spin up the publisher
        self.pub_server = pub_server = PubServer(
            self.opts,
            io_loop=io_loop,
            presence_callback=presence_callback,
            remove_presence_callback=remove_presence_callback,
        )
        sock = _get_socket(self.opts)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        _set_tcp_keepalive(sock, self.opts)
        sock.setblocking(0)
        sock.bind(_get_bind_addr(self.opts, "publish_port"))
        sock.listen(self.backlog)
        # pub_server will take ownership of the socket
        pub_server.add_socket(sock)

        # Set up Salt IPC server
        if self.opts.get("ipc_mode", "") == "tcp":
            pull_uri = int(self.opts.get("tcp_master_publish_pull", 4514))
        else:
            pull_uri = os.path.join(self.opts["sock_dir"], "publish_pull.ipc")
        self.pub_server = pub_server
        pull_sock = salt.transport.ipc.IPCMessageServer(
            pull_uri,
            io_loop=io_loop,
            payload_handler=publish_payload,
        )

        # Securely create socket
        log.warning("Starting the Salt Puller on %s", pull_uri)
        with salt.utils.files.set_umask(0o177):
            pull_sock.start()

        # run forever
        try:
            io_loop.start()
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            pull_sock.close()

    def pre_fork(self, process_manager):
        """
        Do anything necessary pre-fork. Since this is on the master side this will
        primarily be used to create IPC channels and create our daemon process to
        do the actual publishing
        """
        process_manager.add_process(self.publish_daemon, name=self.__class__.__name__)

    @salt.ext.tornado.gen.coroutine
    def publish_payload(self, payload, *args):
        ret = yield self.pub_server.publish_payload(payload, *args)
        raise salt.ext.tornado.gen.Return(ret)

    def publish(self, payload, **kwargs):
        """
        Publish "load" to minions
        """
        if self.opts.get("ipc_mode", "") == "tcp":
            pull_uri = int(self.opts.get("tcp_master_publish_pull", 4514))
        else:
            pull_uri = os.path.join(self.opts["sock_dir"], "publish_pull.ipc")
        if not self.pub_sock:
            self.pub_sock = salt.utils.asynchronous.SyncWrapper(
                salt.transport.ipc.IPCMessageClient,
                (pull_uri,),
                loop_kwarg="io_loop",
            )
            self.pub_sock.connect()
        self.pub_sock.send(payload)

    def close(self):
        if self.pub_sock:
            self.pub_sock.close()
            self.pub_sock = None


class TCPReqClient(salt.transport.base.RequestClient):
    """
    Tornado based TCP RequestClient
    """

    ttype = "tcp"

    def __init__(self, opts, io_loop, **kwargs):  # pylint: disable=W0231
        self.opts = opts
        self.io_loop = io_loop
        parse = urllib.parse.urlparse(self.opts["master_uri"])
        master_host, master_port = parse.netloc.rsplit(":", 1)
        master_addr = (master_host, int(master_port))
        # self.resolver = Resolver()
        resolver = kwargs.get("resolver")
        self.message_client = salt.transport.tcp.MessageClient(
            opts,
            master_host,
            int(master_port),
            io_loop=io_loop,
            resolver=resolver,
            source_ip=opts.get("source_ip"),
            source_port=opts.get("source_ret_port"),
        )

    @salt.ext.tornado.gen.coroutine
    def connect(self):
        yield self.message_client.connect()

    @salt.ext.tornado.gen.coroutine
    def send(self, load, timeout=60):
        ret = yield self.message_client.send(load, timeout=timeout)
        raise salt.ext.tornado.gen.Return(ret)

    def close(self):
        self.message_client.close()
