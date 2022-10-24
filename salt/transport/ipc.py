"""
IPC transport classes
"""


import errno
import logging
import socket
import time

import salt.ext.tornado
import salt.ext.tornado.concurrent
import salt.ext.tornado.gen
import salt.ext.tornado.ioloop
import salt.ext.tornado.netutil
import salt.transport.client
import salt.transport.frame
import salt.utils.msgpack
from salt.ext.tornado.ioloop import IOLoop
from salt.ext.tornado.ioloop import TimeoutError as TornadoTimeoutError
from salt.ext.tornado.iostream import IOStream, StreamClosedError
from salt.ext.tornado.locks import Lock

log = logging.getLogger(__name__)


# 'tornado.concurrent.Future' doesn't support
# remove_done_callback() which we would have called
# in the timeout case. Due to this, we have this
# callback function outside of FutureWithTimeout.
def future_with_timeout_callback(future):
    if future._future_with_timeout is not None:
        future._future_with_timeout._done_callback(future)


class FutureWithTimeout(salt.ext.tornado.concurrent.Future):
    def __init__(self, io_loop, future, timeout):
        super().__init__()
        self.io_loop = io_loop
        self._future = future
        if timeout is not None:
            if timeout < 0.1:
                timeout = 0.1
            self._timeout_handle = self.io_loop.add_timeout(
                self.io_loop.time() + timeout, self._timeout_callback
            )
        else:
            self._timeout_handle = None

        if hasattr(self._future, "_future_with_timeout"):
            # Reusing a future that has previously been used.
            # Due to this, no need to call add_done_callback()
            # because we did that before.
            self._future._future_with_timeout = self
            if self._future.done():
                future_with_timeout_callback(self._future)
        else:
            self._future._future_with_timeout = self
            self._future.add_done_callback(future_with_timeout_callback)

    def _timeout_callback(self):
        self._timeout_handle = None
        # 'tornado.concurrent.Future' doesn't support
        # remove_done_callback(). So we set an attribute
        # inside the future itself to track what happens
        # when it completes.
        self._future._future_with_timeout = None
        self.set_exception(TornadoTimeoutError())

    def _done_callback(self, future):
        try:
            if self._timeout_handle is not None:
                self.io_loop.remove_timeout(self._timeout_handle)
                self._timeout_handle = None

            self.set_result(future.result())
        except Exception as exc:  # pylint: disable=broad-except
            self.set_exception(exc)


class IPCServer:
    """
    A Tornado IPC server very similar to Tornado's TCPServer class
    but using either UNIX domain sockets or TCP sockets
    """

    async_methods = [
        "handle_stream",
    ]
    close_methods = [
        "close",
    ]

    def __init__(self, socket_path, io_loop=None, payload_handler=None):
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
        self.socket_path = socket_path
        self._started = False
        self.payload_handler = payload_handler

        # Placeholders for attributes to be populated by method calls
        self.sock = None
        self.io_loop = io_loop or salt.ext.tornado.ioloop.IOLoop.current()
        self._closing = False

    def start(self):
        """
        Perform the work necessary to start up a Tornado IPC server

        Blocks until socket is established
        """
        # Start up the ioloop
        log.trace("IPCServer: binding to socket: %s", self.socket_path)
        if isinstance(self.socket_path, int):
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.setblocking(0)
            self.sock.bind(("127.0.0.1", self.socket_path))
            # Based on default used in tornado.netutil.bind_sockets()
            self.sock.listen(128)
        else:
            self.sock = salt.ext.tornado.netutil.bind_unix_socket(self.socket_path)

        with salt.utils.asynchronous.current_ioloop(self.io_loop):
            salt.ext.tornado.netutil.add_accept_handler(
                self.sock,
                self.handle_connection,
            )
        self._started = True

    @salt.ext.tornado.gen.coroutine
    def handle_stream(self, stream):
        """
        Override this to handle the streams as they arrive

        :param IOStream stream: An IOStream for processing

        See https://tornado.readthedocs.io/en/latest/iostream.html#tornado.iostream.IOStream
        for additional details.
        """

        @salt.ext.tornado.gen.coroutine
        def _null(msg):
            raise salt.ext.tornado.gen.Return(None)

        def write_callback(stream, header):
            if header.get("mid"):

                @salt.ext.tornado.gen.coroutine
                def return_message(msg):
                    pack = salt.transport.frame.frame_msg_ipc(
                        msg,
                        header={"mid": header["mid"]},
                        raw_body=True,
                    )
                    yield stream.write(pack)

                return return_message
            else:
                return _null

        # msgpack deprecated `encoding` starting with version 0.5.2
        if salt.utils.msgpack.version >= (0, 5, 2):
            # Under Py2 we still want raw to be set to True
            msgpack_kwargs = {"raw": False}
        else:
            msgpack_kwargs = {"encoding": "utf-8"}
        unpacker = salt.utils.msgpack.Unpacker(**msgpack_kwargs)
        while not stream.closed():
            try:
                wire_bytes = yield stream.read_bytes(4096, partial=True)
                unpacker.feed(wire_bytes)
                for framed_msg in unpacker:
                    body = framed_msg["body"]
                    self.io_loop.spawn_callback(
                        self.payload_handler,
                        body,
                        write_callback(stream, framed_msg["head"]),
                    )
            except StreamClosedError:
                log.trace("Client disconnected from IPC %s", self.socket_path)
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
            with salt.utils.asynchronous.current_ioloop(self.io_loop):
                stream = IOStream(
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
        try:
            self.close()
        except TypeError:
            # This is raised when Python's GC has collected objects which
            # would be needed when calling self.close()
            pass

    # pylint: enable=W1701

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class IPCClient:
    """
    A Tornado IPC client very similar to Tornado's TCPClient class
    but using either UNIX domain sockets or TCP sockets

    This was written because Tornado does not have its own IPC
    server/client implementation.

    :param IOLoop io_loop: A Tornado ioloop to handle scheduling
    :param str/int socket_path: A path on the filesystem where a socket
                                belonging to a running IPCServer can be
                                found.
                                It may also be of type 'int', in which
                                case it is used as the port for a tcp
                                localhost connection.
    """

    def __init__(self, socket_path, io_loop=None):
        """
        Create a new IPC client

        IPC clients cannot bind to ports, but must connect to
        existing IPC servers. Clients can then send messages
        to the server.

        """
        self.io_loop = io_loop or salt.ext.tornado.ioloop.IOLoop.current()
        self.socket_path = socket_path
        self._closing = False
        self.stream = None
        # msgpack deprecated `encoding` starting with version 0.5.2
        if salt.utils.msgpack.version >= (0, 5, 2):
            # Under Py2 we still want raw to be set to True
            msgpack_kwargs = {"raw": False}
        else:
            msgpack_kwargs = {"encoding": "utf-8"}
        self.unpacker = salt.utils.msgpack.Unpacker(**msgpack_kwargs)
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
            future = salt.ext.tornado.concurrent.Future()
            self._connecting_future = future
            self._connect(timeout)

        if callback is not None:

            def handle_future(future):
                response = future.result()
                self.io_loop.add_callback(callback, response)

            future.add_done_callback(handle_future)

        return future

    @salt.ext.tornado.gen.coroutine
    def _connect(self, timeout=None):
        """
        Connect to a running IPCServer
        """
        if isinstance(self.socket_path, int):
            sock_type = socket.AF_INET
            sock_addr = ("127.0.0.1", self.socket_path)
        else:
            sock_type = socket.AF_UNIX
            sock_addr = self.socket_path

        self.stream = None
        if timeout is not None:
            timeout_at = time.time() + timeout

        while True:
            if self._closing:
                break

            if self.stream is None:
                with salt.utils.asynchronous.current_ioloop(self.io_loop):
                    self.stream = IOStream(socket.socket(sock_type, socket.SOCK_STREAM))
            try:
                log.trace("IPCClient: Connecting to socket: %s", self.socket_path)
                yield self.stream.connect(sock_addr)
                self._connecting_future.set_result(True)
                break
            except Exception as e:  # pylint: disable=broad-except
                if self.stream.closed():
                    self.stream = None

                if timeout is None or time.time() > timeout_at:
                    if self.stream is not None:
                        self.stream.close()
                        self.stream = None
                    self._connecting_future.set_exception(e)
                    break

                yield salt.ext.tornado.gen.sleep(1)

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
        try:
            self.close()
        except TypeError:
            # This is raised when Python's GC has collected objects which
            # would be needed when calling self.close()
            pass

    # pylint: enable=W1701

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class IPCMessageClient(IPCClient):
    """
    Salt IPC message client

    Create an IPC client to send messages to an IPC server

    An example of a very simple IPCMessageClient connecting to an IPCServer. This
    example assumes an already running IPCMessage server.

    IMPORTANT: The below example also assumes a running IOLoop process.

    # Import Tornado libs
    import salt.ext.tornado.ioloop

    # Import Salt libs
    import salt.config
    import salt.transport.ipc

    io_loop = salt.ext.tornado.ioloop.IOLoop.current()

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

    # FIXME timeout unimplemented
    # FIXME tries unimplemented
    @salt.ext.tornado.gen.coroutine
    def send(self, msg, timeout=None, tries=None):
        """
        Send a message to an IPC socket

        If the socket is not currently connected, a connection will be established.

        :param dict msg: The message to be sent
        :param int timeout: Timeout when sending message (Currently unimplemented)
        """
        if not self.connected():
            yield self.connect()
        pack = salt.transport.frame.frame_msg_ipc(msg, raw_body=True)
        yield self.stream.write(pack)


class IPCMessageServer(IPCServer):
    """
    Salt IPC message server

    Creates a message server which can create and bind to a socket on a given
    path and then respond to messages asynchronously.

    An example of a very simple IPCServer which prints received messages to
    a console:

        # Import Tornado libs
        import salt.ext.tornado.ioloop

        # Import Salt libs
        import salt.transport.ipc

        io_loop = salt.ext.tornado.ioloop.IOLoop.current()
        ipc_server_socket_path = '/var/run/ipc_server.ipc'
        ipc_server = salt.transport.ipc.IPCMessageServer(ipc_server_socket_path, io_loop=io_loop,
                                                         payload_handler=print_to_console)
        # Bind to the socket and prepare to run
        ipc_server.start()

        # Start the server
        io_loop.start()

        # This callback is run whenever a message is received
        def print_to_console(payload):
            print(payload)

    See IPCMessageClient() for an example of sending messages to an IPCMessageServer instance
    """


class IPCMessagePublisher:
    """
    A Tornado IPC Publisher similar to Tornado's TCPServer class
    but using either UNIX domain sockets or TCP sockets
    """

    def __init__(self, opts, socket_path, io_loop=None):
        """
        Create a new Tornado IPC server
        :param dict opts: Salt options
        :param str/int socket_path: Path on the filesystem for the
                                    socket to bind to. This socket does
                                    not need to exist prior to calling
                                    this method, but parent directories
                                    should.
                                    It may also be of type 'int', in
                                    which case it is used as the port
                                    for a tcp localhost connection.
        :param IOLoop io_loop: A Tornado ioloop to handle scheduling
        """
        self.opts = opts
        self.socket_path = socket_path
        self._started = False

        # Placeholders for attributes to be populated by method calls
        self.sock = None
        self.io_loop = io_loop or IOLoop.current()
        self._closing = False
        self.streams = set()

    def start(self):
        """
        Perform the work necessary to start up a Tornado IPC server

        Blocks until socket is established
        """
        # Start up the ioloop
        log.trace("IPCMessagePublisher: binding to socket: %s", self.socket_path)
        if isinstance(self.socket_path, int):
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.setblocking(0)
            self.sock.bind(("127.0.0.1", self.socket_path))
            # Based on default used in salt.ext.tornado.netutil.bind_sockets()
            self.sock.listen(128)
        else:
            self.sock = salt.ext.tornado.netutil.bind_unix_socket(self.socket_path)

        with salt.utils.asynchronous.current_ioloop(self.io_loop):
            salt.ext.tornado.netutil.add_accept_handler(
                self.sock,
                self.handle_connection,
            )
        self._started = True

    @salt.ext.tornado.gen.coroutine
    def _write(self, stream, pack):
        try:
            yield stream.write(pack)
        except StreamClosedError:
            log.trace("Client disconnected from IPC %s", self.socket_path)
            self.streams.discard(stream)
        except Exception as exc:  # pylint: disable=broad-except
            log.error("Exception occurred while handling stream: %s", exc)
            if not stream.closed():
                stream.close()
            self.streams.discard(stream)

    def publish(self, msg):
        """
        Send message to all connected sockets
        """
        if not self.streams:
            return

        pack = salt.transport.frame.frame_msg_ipc(msg, raw_body=True)
        for stream in self.streams:
            self.io_loop.spawn_callback(self._write, stream, pack)

    def handle_connection(self, connection, address):
        log.trace("IPCServer: Handling connection to address: %s", address)
        try:
            kwargs = {}
            if self.opts["ipc_write_buffer"] > 0:
                kwargs["max_write_buffer_size"] = self.opts["ipc_write_buffer"]
                log.trace(
                    "Setting IPC connection write buffer: %s",
                    (self.opts["ipc_write_buffer"]),
                )
            with salt.utils.asynchronous.current_ioloop(self.io_loop):
                stream = IOStream(connection, **kwargs)
            self.streams.add(stream)

            def discard_after_closed():
                self.streams.discard(stream)

            stream.set_close_callback(discard_after_closed)
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
        for stream in self.streams:
            stream.close()
        self.streams.clear()
        if hasattr(self.sock, "close"):
            self.sock.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class IPCMessageSubscriber(IPCClient):
    """
    Salt IPC message subscriber

    Create an IPC client to receive messages from IPC publisher

    An example of a very simple IPCMessageSubscriber connecting to an IPCMessagePublisher.
    This example assumes an already running IPCMessagePublisher.

    IMPORTANT: The below example also assumes the IOLoop is NOT running.

    # Import Tornado libs
    import salt.ext.tornado.ioloop

    # Import Salt libs
    import salt.config
    import salt.transport.ipc

    # Create a new IO Loop.
    # We know that this new IO Loop is not currently running.
    io_loop = salt.ext.tornado.ioloop.IOLoop()

    ipc_publisher_socket_path = '/var/run/ipc_publisher.ipc'

    ipc_subscriber = salt.transport.ipc.IPCMessageSubscriber(ipc_server_socket_path, io_loop=io_loop)

    # Connect to the server
    # Use the associated IO Loop that isn't running.
    io_loop.run_sync(ipc_subscriber.connect)

    # Wait for some data
    package = ipc_subscriber.read_sync()
    """

    async_methods = [
        "read",
        "connect",
    ]
    close_methods = [
        "close",
    ]

    def __init__(self, socket_path, io_loop=None):
        super().__init__(socket_path, io_loop=io_loop)
        self._read_stream_future = None
        self._saved_data = []
        self._read_in_progress = Lock()

    @salt.ext.tornado.gen.coroutine
    def _read(self, timeout, callback=None):
        try:
            try:
                yield self._read_in_progress.acquire(timeout=0.00000001)
            except salt.ext.tornado.gen.TimeoutError:
                raise salt.ext.tornado.gen.Return(None)

            exc_to_raise = None
            ret = None
            try:
                while True:
                    if self._read_stream_future is None:
                        self._read_stream_future = self.stream.read_bytes(
                            4096, partial=True
                        )

                    if timeout is None:
                        wire_bytes = yield self._read_stream_future
                    else:
                        wire_bytes = yield FutureWithTimeout(
                            self.io_loop, self._read_stream_future, timeout
                        )
                    self._read_stream_future = None

                    # Remove the timeout once we get some data or an exception
                    # occurs. We will assume that the rest of the data is already
                    # there or is coming soon if an exception doesn't occur.
                    timeout = None

                    self.unpacker.feed(wire_bytes)
                    first_sync_msg = True
                    for framed_msg in self.unpacker:
                        if callback:
                            self.io_loop.spawn_callback(callback, framed_msg["body"])
                        elif first_sync_msg:
                            ret = framed_msg["body"]
                            first_sync_msg = False
                        else:
                            self._saved_data.append(framed_msg["body"])
                    if not first_sync_msg:
                        # We read at least one piece of data and we're on sync run
                        break
            except TornadoTimeoutError:
                # In the timeout case, just return None.
                # Keep 'self._read_stream_future' alive.
                ret = None
            except StreamClosedError as exc:
                log.trace("Subscriber disconnected from IPC %s", self.socket_path)
                self._read_stream_future = None
            except Exception as exc:  # pylint: disable=broad-except
                log.error(
                    "Exception occurred in Subscriber while handling stream: %s", exc
                )
                self._read_stream_future = None
                exc_to_raise = exc

            self._read_in_progress.release()

            if exc_to_raise is not None:
                raise exc_to_raise  # pylint: disable=E0702
            raise salt.ext.tornado.gen.Return(ret)
        # Handle ctrl+c gracefully
        except TypeError:
            pass

    @salt.ext.tornado.gen.coroutine
    def read(self, timeout):
        """
        Asynchronously read messages and invoke a callback when they are ready.
        :param callback: A callback with the received data
        """
        if self._saved_data:
            res = self._saved_data.pop(0)
            raise salt.ext.tornado.gen.Return(res)
        while not self.connected():
            try:
                yield self.connect(timeout=5)
            except StreamClosedError:
                log.trace(
                    "Subscriber closed stream on IPC %s before connect",
                    self.socket_path,
                )
                yield salt.ext.tornado.gen.sleep(1)
            except Exception as exc:  # pylint: disable=broad-except
                log.error("Exception occurred while Subscriber connecting: %s", exc)
                yield salt.ext.tornado.gen.sleep(1)
        res = yield self._read(timeout)
        raise salt.ext.tornado.gen.Return(res)

    def read_sync(self, timeout=None):
        """
        Read a message from an IPC socket

        The socket must already be connected.
        The associated IO Loop must NOT be running.
        :param int timeout: Timeout when receiving message
        :return: message data if successful. None if timed out. Will raise an
                 exception for all other error conditions.
        """
        if self._saved_data:
            return self._saved_data.pop(0)
        return self.io_loop.run_sync(lambda: self._read(timeout))

    @salt.ext.tornado.gen.coroutine
    def read_async(self, callback):
        """
        Asynchronously read messages and invoke a callback when they are ready.

        :param callback: A callback with the received data
        """
        while not self.connected():
            try:
                yield self.connect(timeout=5)
            except StreamClosedError:
                log.trace(
                    "Subscriber closed stream on IPC %s before connect",
                    self.socket_path,
                )
                yield salt.ext.tornado.gen.sleep(1)
            except Exception as exc:  # pylint: disable=broad-except
                log.error("Exception occurred while Subscriber connecting: %s", exc)
                yield salt.ext.tornado.gen.sleep(1)
        yield self._read(None, callback)

    def close(self):
        """
        Routines to handle any cleanup before the instance shuts down.
        Sockets and filehandles should be closed explicitly, to prevent
        leaks.
        """
        if self._closing:
            return
        super().close()
        # This will prevent this message from showing up:
        # '[ERROR   ] Future exception was never retrieved:
        # StreamClosedError'
        if self._read_stream_future is not None and self._read_stream_future.done():
            exc = self._read_stream_future.exception()
            if exc and not isinstance(exc, StreamClosedError):
                log.error("Read future returned exception %r", exc)
