"""
TCP transport classes

Wire protocol: "len(payload) msgpack({'head': SOMEHEADER, 'body': SOMEBODY})"


"""


import asyncio
import errno
import logging
import os
import queue
import socket
import threading
import traceback
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

if salt.utils.platform.is_windows():
    USE_LOAD_BALANCER = True
else:
    USE_LOAD_BALANCER = False

if USE_LOAD_BALANCER:
    import threading
    import multiprocessing
    import salt.ext.tornado.util
    from salt.utils.process import SignalHandlingProcess

log = logging.getLogger(__name__)


class ClosingError(Exception):
    """ """


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
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            _set_tcp_keepalive(self._socket, self.opts)
            self._socket.setblocking(1)
            self._socket.bind((self.opts["interface"], int(self.opts["ret_port"])))
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


class PublishClient(salt.transport.base.PublishClient):
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

    async def connect(
        self, publish_port, connect_callback=None, disconnect_callback=None
    ):
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
        await self.message_client.connect()  # wait for the client to be connected
        self.connected = True

    async def _decode_messages(self, messages):
        if not isinstance(messages, dict):
            # TODO: For some reason we need to decode here for things
            #       to work. Fix this.
            body = salt.utils.msgpack.loads(messages)
            body = salt.transport.frame.decode_embedded_strs(body)
        else:
            body = messages
        return body

    async def send(self, msg):
        self.message_client._writer.write(msg)
        await self.message_client._writer.drain()

    def on_recv(self, callback):
        """
        Register an on_recv callback
        """
        return self.message_client.on_recv(callback)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


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

    @property
    def socket(self):
        return self._socket

    def close(self):
        if self.req_server:
            self.req_server.close()
        # if self._socket is not None:
        #    try:
        #        self._socket.shutdown(socket.SHUT_RDWR)
        #    except OSError as exc:
        #        if exc.errno == errno.ENOTCONN:
        #            # We may try to shutdown a socket which is already disconnected.
        #            # Ignore this condition and continue.
        #            pass
        #        else:
        #            raise
        #    if self.req_server is None:
        #        # We only close the socket if we don't have a req_server instance.
        #        # If we did, because the req_server is also handling this socket, when we call
        #        # req_server.stop(), tornado will give us an AssertionError because it's trying to
        #        # match the socket.fileno() (after close it's -1) to the fd it holds on it's _sockets cache
        #        # so it can remove the socket from the IOLoop handlers
        #        self._socket.close()
        #    self._socket = None
        # if self.req_server is not None:
        #    try:
        #        self.req_server.close()
        #    except OSError as exc:
        #        if exc.errno != 9:
        #            raise
        #        log.exception(
        #            "TCPReqServerChannel close generated an exception: %s", str(exc)
        #        )
        #    self.req_server = None

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
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            _set_tcp_keepalive(self._socket, self.opts)
            # self._socket.setblocking(0)
            self._socket.bind((self.opts["interface"], int(self.opts["ret_port"])))

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
                    self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    #  _set_tcp_keepalive(self._socket, self.opts)
                    self._socket.setblocking(0)
                    self._socket.bind(
                        (self.opts["interface"], int(self.opts["ret_port"]))
                    )
            self.req_server = SaltMessageServer(
                self.handle_message,
                ssl_options=self.opts.get("ssl"),
                io_loop=io_loop,
            )
            #  self.req_server.add_socket(self._socket)
            self._socket.listen()  # self.backlog)
            io_loop.create_task(self.req_server.connect(self._socket))

    async def handle_message(self, writer, payload, header=None):
        payload = self.decode_payload(payload)
        reply = await self.message_handler(payload)
        writer.write(salt.transport.frame.frame_msg(reply, header=header))
        await writer.drain()

    def decode_payload(self, payload):
        return payload


class SaltMessageServer:
    """
    Raw TCP server which will receive all of the TCP streams and re-assemble
    messages that are sent through to us
    """

    def __init__(self, message_handler, *args, **kwargs):
        io_loop = kwargs.pop("io_loop", None) or asyncio.get_event_loop()
        self._closing = False
        self.io_loop = io_loop
        self.clients = []
        self.message_handler = message_handler
        self.server = None

    async def connect(self, sock):
        self.server = await asyncio.start_server(
            self.handle_stream,
            sock=sock,
            reuse_address=True,
        )

    async def handle_stream(self, reader, writer):
        """
        Handle incoming streams and add messages to the incoming queue
        """
        socket = writer.get_extra_info("socket")
        addr = socket.getpeername()
        self.clients.append(((reader, writer), addr))
        unpacker = salt.utils.msgpack.Unpacker()
        try:
            while True:
                wire_bytes = await reader.read(4096)
                if not wire_bytes:
                    log.error("%s empty read", self.__class__.__name__)
                    break
                unpacker.feed(wire_bytes)
                for framed_msg in unpacker:
                    framed_msg = salt.transport.frame.decode_embedded_strs(framed_msg)
                    header = framed_msg["head"]
                    await self.message_handler(writer, framed_msg["body"], header)
                    # self.io_loop.create_task(
                    #     self.message_handler(writer, framed_msg["body"], header)
                    # )
        # except salt.ext.tornado.iostream.StreamClosedError:
        #     log.info("req client disconnected %s", addr)
        #     self.remove_client(((reader, writer), addr))
        except Exception as exc:  # pylint: disable=broad-except
            log.info("other master-side exception: %s", exc, exc_info=True)
            self.remove_client(((reader, writer), addr))
            writer.close()

    def remove_client(self, client):
        try:
            self.clients.remove(client)
        except ValueError:
            log.trace("Message server client was not in list to remove")

    def shutdown(self):
        """
        Shutdown the whole server
        """
        salt.utils.versions.warn_until(
            "Phosphorus",
            "Please stop calling {0}.{1}.shutdown() and instead call {0}.{1}.close()".format(
                __name__, self.__class__.__name__
            ),
        )
        self.close()

    def close(self):
        """
        Close the server
        """
        if self._closing:
            return
        self._closing = True
        if self.server:
            self.server.close()
        for item in self.clients:
            (reader, writer), address = item
            writer.close()
            self.remove_client(item)
        # try:
        #    self.stop()
        # except OSError as exc:
        #    if exc.errno != 9:
        #        raise


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

        def stop(self):
            salt.utils.versions.warn_until(
                "Phosphorus",
                "Please stop calling {0}.{1}.stop() and instead call {0}.{1}.close()".format(
                    __name__, self.__class__.__name__
                ),
            )
            self.close()

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
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
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
        self.io_loop = io_loop or asyncio.get_event_loop()
        # XXX This needs to be fixed
        # with salt.utils.asynchronous.current_ioloop(self.io_loop):
        #    self._tcp_client = TCPClientKeepAlive(opts, resolver=resolver)
        self._mid = 1
        self._max_messages = int((1 << 31) - 2)  # number of IDs before we wrap
        # TODO: max queue size
        self.send_queue = []  # queue of messages to be sent
        self.send_future_map = {}  # mapping of request_id -> Future

        self._on_recv = None
        self._closing = False
        self._closed = False
        self._connecting_future = asyncio.Future()
        self.stream_return_running = False
        self._reader = None
        self._writer = None

        self.backoff = opts.get("tcp_reconnect_backoff", 1)
        self._tb = traceback.format_stack()

    def _stop_io_loop(self):
        if self.io_loop is not None:
            self.io_loop.stop()

    # TODO: timeout inflight sessions
    def close(self):
        # log.error("WTF %r", self.stream_return_running)
        if self._closing:
            return
        self._closing = True
        if self._writer:
            self._writer.close()
        # self.io_loop.call_later(1, self.check_close)

        # try:
        #     for msg_id in list(self.send_future_map):
        #         log.error("Closing before send future completed %r", msg_id)
        #         future = self.send_future_map.pop(msg_id)
        #         future.set_exception(ClosingError())
        #     self._tcp_client.close()
        #     # self._stream.close()
        # finally:
        #     self._stream = None
        #     self._closing = False
        #     self._closed = True

    def check_close(self):
        if not self.send_future_map:
            self._writer.close()
            self._stream = None
            self._closing = False
            self._closed = True
        else:
            self.io_loop.call_later(1, self.check_close)

    # pylint: disable=W1701
    def __del__(self):
        # if not self._closing:
        #     log.error("__del__ called %s", "\n".join(self._tb))
        self.close()

    # pylint: enable=W1701

    async def getstream(self, **kwargs):
        if self.source_ip or self.source_port:
            kwargs = {
                "source_ip": self.source_ip,
                "source_port": self.source_port,
            }
        reader, writer = None, None
        while writer is None and (not self._closed and not self._closing):
            try:
                reader, writer = await asyncio.open_connection(
                    host=self.host,
                    port=self.port,
                    # ssl=self.opts.get("ssl"), #**kwargs
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
        return reader, writer

    async def connect(self):
        if self._writer is None:
            self._reader, self._writer = await self.getstream()
            if self._writer:
                if not self.stream_return_running:
                    self.stream_return_running = self.io_loop.create_task(
                        self._stream_return()
                    )
                if self.connect_callback:
                    if asyncio.iscoroutinefunction(self.connect_callback):
                        self.io_loop.create_task(self.connect_callback(True))
                    else:
                        self.io_loop.call_soon(self.connect_callback, True)

    async def _stream_return(self):
        unpacker = salt.utils.msgpack.Unpacker()
        while not self._closing:
            try:
                wire_bytes = await self._reader.read(4096)
                if not wire_bytes:
                    log.error("%s empty read", self.__class__.__name__)
                    break
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
                            self.io_loop.call_soon(self._on_recv, header, body)
                        else:
                            log.error(
                                "Got response for message_id %s that we are not"
                                " tracking",
                                message_id,
                            )
            except asyncio.TimeoutError as e:
                continue
            except salt.ext.tornado.iostream.StreamClosedError as e:
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
                if self.disconnect_callback:
                    self.disconnect_callback()
                # if the last connect finished, then we need to make a new one
                # if self._connecting_future.done():
                stream = self._writer
                self._writer = None
                if stream:
                    stream.close()
                await self.connect()
                # self._connecting_future = self.connect()
                # yield self._connecting_future
            except TypeError:
                log.error("Exception parsing response", exc_info=True)
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
                stream = self._writer
                self._writer = None
                if stream:
                    stream.close()
                await self.connect()
                # if the last connect finished, then we need to make a new one
                # if self._connecting_future.done():
                #    self._connecting_future = self.connect()
                # yield self._connecting_future
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
                if asyncio.iscoroutinefunction(callback):
                    self.io_loop.create_task(callback(body))
                else:
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

    async def send(self, msg, timeout=None, callback=None, raw=False):
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

        async def _do_send():
            await self.connect()
            # If the _writer is None, we failed to connect.
            if self._writer:
                self._writer.write(item)
                await self._writer.drain()

        # Run send in a callback so we can wait on the future, in case we time
        # out before we are able to connect.
        self.io_loop.create_task(_do_send())
        recv = await future
        return recv


class Subscriber:
    """
    Client object for use with the TCP publisher server
    """

    def __init__(self, reader, writer, address):
        self.reader = reader
        self.writer = writer
        self.address = address
        self._closing = False
        self.id_ = None

    def close(self):
        if self._closing:
            return
        self._closing = True
        self.writer.close()

    # pylint: disable=W1701
    def __del__(self):
        self.close()

    # pylint: enable=W1701


class PubServer:
    """
    TCP publisher
    """

    def __init__(
        self,
        interface,
        port,
        ssl_opts=None,
        io_loop=None,
        presence_callback=None,
        remove_presence_callback=None,
    ):
        self.io_loop = io_loop
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
        self.server = None
        self.interface = interface
        self.port = port
        self.ssl_opts = ssl_opts

    async def connect(self):
        self.server = await asyncio.start_server(
            self.handle_stream,
            host=self.interface,
            port=self.port,
            reuse_address=True,
        )

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

    async def _stream_read(self, client):
        unpacker = salt.utils.msgpack.Unpacker()
        while not self._closing:
            try:
                wire_bytes = await client.reader.read(4096)
                log.error("PubServer Read from client %r", wire_bytes)
                if not wire_bytes:
                    log.error("%s empty read", self.__class__.__name__)
                    break
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

    async def handle_stream(self, reader, writer):
        socket = writer.get_extra_info("socket")
        address = socket.getpeername()
        log.error("Subscriber at %s connected", address)
        client = Subscriber(reader, writer, address)
        self.clients.add(client)
        await self._stream_read(client)
        # self.io_loop.create_task(self._stream_read(client))

    # TODO: ACK the publish through IPC
    async def publish_payload(self, package, topic_list=None):
        log.trace("TCP PubServer sending payload: %s \n\n %r", package, topic_list)
        payload = salt.transport.frame.frame_msg(package)
        to_remove = []
        if topic_list:
            for topic in topic_list:
                sent = False
                for client in self.clients:
                    if topic == client.id_:
                        try:
                            client.writer.write(payload)
                            await client.writer.drain()
                            sent = True
                            # self.io_loop.add_future(f, lambda f: True)
                        except Exception as exc:  # pylint: disable=broad-except
                            log.error(
                                "Exception while writting to client: %r",
                                exc,
                                exc_info=True,
                            )
                            to_remove.append(client)
                if not sent:
                    log.debug(
                        "Publish target %s not connected %r",
                        topic,
                        [c.id_ for c in self.clients],
                    )
        else:
            for client in self.clients:
                try:
                    client.stream.write(payload)
                    await client.writer.drain()
                except salt.ext.tornado.iostream.StreamClosedError:
                    to_remove.append(client)
                except Exception as exc:  # pylint: disable=broad-except
                    log.error(
                        "Exception while writting to client: %r", exc, exc_info=True
                    )
        for client in to_remove:
            log.debug(
                "Subscriber at %s has disconnected from publisher", client.address
            )
            client.close()
            self._remove_client_present(client)
            self.clients.discard(client)
        log.trace("TCP PubServer finished publishing payload")


class PublishServer(salt.transport.base.DaemonizedPublishServer):
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
        io_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(io_loop)
        io_loop.set_debug(True)

        # Spin up the publisher
        self.pub_server = pub_server = PubServer(
            self.opts["interface"],
            self.opts["publish_port"],
            ssl_opts=self.opts.get("ssl"),
            io_loop=io_loop,
            presence_callback=presence_callback,
            remove_presence_callback=remove_presence_callback,
        )

        # sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # _set_tcp_keepalive(sock, self.opts)
        # sock.setblocking(0)
        # sock.bind((self.opts["interface"], int(self.opts["publish_port"])))
        # sock.listen(self.backlog)
        # pub_server will take ownership of the socket
        # pub_server.add_socket(sock)

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
        log.warn("Starting the Salt Puller on %s", pull_uri)
        # with salt.utils.files.set_umask(0o177):
        io_loop.create_task(pull_sock.start())
        io_loop.create_task(self.pub_server.connect())

        # run forever
        try:
            io_loop.run_forever()
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

    async def publish_payload(self, payload, *args):
        ret = await self.pub_server.publish_payload(payload, *args)
        return ret

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


class RequestClient(salt.transport.base.RequestClient):
    """
    Tornado based TCP RequestClient
    """

    ttype = "tcp"

    def __init__(self, opts, io_loop, **kwargs):  # pylint: disable=W0231
        self.opts = opts
        self.io_loop = io_loop
        parse = urllib.parse.urlparse(self.opts["master_uri"])
        master_host, master_port = parse.netloc.rsplit(":", 1)
        # master_addr = (master_host, int(master_port))
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

    async def connect(self):
        await self.message_client.connect()

    async def send(self, load, timeout=60):
        return await self.message_client.send(load, timeout=60)

    def close(self):
        return self.message_client.close()
