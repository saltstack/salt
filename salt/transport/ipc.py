# -*- coding: utf-8 -*-
'''
IPC transport classes
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import socket
import weakref
import time

# Import 3rd-party libs
import msgpack

# Import Tornado libs
import tornado
import tornado.gen
import tornado.netutil
import tornado.concurrent
from tornado.locks import Semaphore
from tornado.ioloop import IOLoop, TimeoutError as TornadoTimeoutError
from tornado.iostream import IOStream
# Import Salt libs
import salt.transport.client
import salt.transport.frame
from salt.ext import six

log = logging.getLogger(__name__)


# 'tornado.concurrent.Future' doesn't support
# remove_done_callback() which we would have called
# in the timeout case. Due to this, we have this
# callback function outside of FutureWithTimeout.
def future_with_timeout_callback(future):
    if future._future_with_timeout is not None:
        future._future_with_timeout._done_callback(future)


class FutureWithTimeout(tornado.concurrent.Future):
    def __init__(self, io_loop, future, timeout):
        super(FutureWithTimeout, self).__init__()
        self.io_loop = io_loop
        self._future = future
        if timeout is not None:
            if timeout < 0.1:
                timeout = 0.1
            self._timeout_handle = self.io_loop.add_timeout(
                self.io_loop.time() + timeout, self._timeout_callback)
        else:
            self._timeout_handle = None

        if hasattr(self._future, '_future_with_timeout'):
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
        except Exception as exc:
            self.set_exception(exc)


class IPCServer(object):
    '''
    A Tornado IPC server very similar to Tornado's TCPServer class
    but using either UNIX domain sockets or TCP sockets
    '''
    def __init__(self, socket_path, io_loop=None, payload_handler=None):
        '''
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
        '''
        self.socket_path = socket_path
        self._started = False
        self.payload_handler = payload_handler

        # Placeholders for attributes to be populated by method calls
        self.sock = None
        self.io_loop = io_loop or IOLoop.current()
        self._closing = False

    def start(self):
        '''
        Perform the work necessary to start up a Tornado IPC server

        Blocks until socket is established
        '''
        # Start up the ioloop
        log.trace('IPCServer: binding to socket: %s', self.socket_path)
        if isinstance(self.socket_path, int):
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.setblocking(0)
            self.sock.bind(('127.0.0.1', self.socket_path))
            # Based on default used in tornado.netutil.bind_sockets()
            self.sock.listen(128)
        else:
            self.sock = tornado.netutil.bind_unix_socket(self.socket_path)

        tornado.netutil.add_accept_handler(
            self.sock,
            self.handle_connection,
            io_loop=self.io_loop,
        )
        self._started = True

    @tornado.gen.coroutine
    def handle_stream(self, stream):
        '''
        Override this to handle the streams as they arrive

        :param IOStream stream: An IOStream for processing

        See https://tornado.readthedocs.io/en/latest/iostream.html#tornado.iostream.IOStream
        for additional details.
        '''
        @tornado.gen.coroutine
        def _null(msg):
            raise tornado.gen.Return(None)

        def write_callback(stream, header):
            if header.get('mid'):
                @tornado.gen.coroutine
                def return_message(msg):
                    pack = salt.transport.frame.frame_msg_ipc(
                        msg,
                        header={'mid': header['mid']},
                        raw_body=True,
                    )
                    yield stream.write(pack)
                return return_message
            else:
                return _null
        if six.PY2:
            encoding = None
        else:
            encoding = 'utf-8'
        unpacker = msgpack.Unpacker(encoding=encoding)
        while not stream.closed():
            try:
                wire_bytes = yield stream.read_bytes(4096, partial=True)
                unpacker.feed(wire_bytes)
                for framed_msg in unpacker:
                    body = framed_msg['body']
                    self.io_loop.spawn_callback(self.payload_handler, body, write_callback(stream, framed_msg['head']))
            except tornado.iostream.StreamClosedError:
                log.trace('Client disconnected from IPC %s', self.socket_path)
                break
            except socket.error as exc:
                # On occasion an exception will occur with
                # an error code of 0, it's a spurious exception.
                if exc.errno == 0:
                    log.trace('Exception occured with error number 0, '
                              'spurious exception: %s', exc)
                else:
                    log.error('Exception occurred while '
                              'handling stream: %s', exc)
            except Exception as exc:
                log.error('Exception occurred while '
                          'handling stream: %s', exc)

    def handle_connection(self, connection, address):
        log.trace('IPCServer: Handling connection '
                  'to address: %s', address)
        try:
            stream = IOStream(
                connection,
                io_loop=self.io_loop,
            )
            self.io_loop.spawn_callback(self.handle_stream, stream)
        except Exception as exc:
            log.error('IPC streaming error: %s', exc)

    def close(self):
        '''
        Routines to handle any cleanup before the instance shuts down.
        Sockets and filehandles should be closed explicitly, to prevent
        leaks.
        '''
        if self._closing:
            return
        self._closing = True
        if hasattr(self.sock, 'close'):
            self.sock.close()

    def __del__(self):
        self.close()


class IPCClient(object):
    '''
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
    '''

    # Create singleton map between two sockets
    instance_map = weakref.WeakKeyDictionary()

    def __new__(cls, socket_path, io_loop=None):
        io_loop = io_loop or tornado.ioloop.IOLoop.current()
        if io_loop not in IPCClient.instance_map:
            IPCClient.instance_map[io_loop] = weakref.WeakValueDictionary()
        loop_instance_map = IPCClient.instance_map[io_loop]

        # FIXME
        key = six.text_type(socket_path)

        client = loop_instance_map.get(key)
        if client is None:
            log.debug('Initializing new IPCClient for path: %s', key)
            client = object.__new__(cls)
            # FIXME
            client.__singleton_init__(io_loop=io_loop, socket_path=socket_path)
            loop_instance_map[key] = client
        else:
            log.debug('Re-using IPCClient for %s', key)
        return client

    def __singleton_init__(self, socket_path, io_loop=None):
        '''
        Create a new IPC client

        IPC clients cannot bind to ports, but must connect to
        existing IPC servers. Clients can then send messages
        to the server.

        '''
        self.io_loop = io_loop or tornado.ioloop.IOLoop.current()
        self.socket_path = socket_path
        self._closing = False
        self.stream = None
        if six.PY2:
            encoding = None
        else:
            encoding = 'utf-8'
        self.unpacker = msgpack.Unpacker(encoding=encoding)

    def __init__(self, socket_path, io_loop=None):
        # Handled by singleton __new__
        pass

    def connected(self):
        return self.stream is not None and not self.stream.closed()

    def connect(self, callback=None, timeout=None):
        '''
        Connect to the IPC socket
        '''
        if hasattr(self, '_connecting_future') and not self._connecting_future.done():  # pylint: disable=E0203
            future = self._connecting_future  # pylint: disable=E0203
        else:
            if hasattr(self, '_connecting_future'):
                # read previous future result to prevent the "unhandled future exception" error
                self._connecting_future.exc_info()  # pylint: disable=E0203
            future = tornado.concurrent.Future()
            self._connecting_future = future
            self._connect(timeout=timeout)

        if callback is not None:
            def handle_future(future):
                response = future.result()
                self.io_loop.add_callback(callback, response)
            future.add_done_callback(handle_future)

        return future

    @tornado.gen.coroutine
    def _connect(self, timeout=None):
        '''
        Connect to a running IPCServer
        '''
        if isinstance(self.socket_path, int):
            sock_type = socket.AF_INET
            sock_addr = ('127.0.0.1', self.socket_path)
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
                self.stream = IOStream(
                    socket.socket(sock_type, socket.SOCK_STREAM),
                    io_loop=self.io_loop,
                )

            try:
                log.trace('IPCClient: Connecting to socket: %s', self.socket_path)
                yield self.stream.connect(sock_addr)
                self._connecting_future.set_result(True)
                break
            except Exception as e:
                if self.stream.closed():
                    self.stream = None

                if timeout is None or time.time() > timeout_at:
                    if self.stream is not None:
                        self.stream.close()
                        self.stream = None
                    self._connecting_future.set_exception(e)
                    break

                yield tornado.gen.sleep(1)

    def __del__(self):
        self.close()

    def close(self):
        '''
        Routines to handle any cleanup before the instance shuts down.
        Sockets and filehandles should be closed explicitly, to prevent
        leaks.
        '''
        if self._closing:
            return
        self._closing = True
        if self.stream is not None and not self.stream.closed():
            self.stream.close()

        # Remove the entry from the instance map so
        # that a closed entry may not be reused.
        # This forces this operation even if the reference
        # count of the entry has not yet gone to zero.
        if self.io_loop in IPCClient.instance_map:
            loop_instance_map = IPCClient.instance_map[self.io_loop]
            key = six.text_type(self.socket_path)
            if key in loop_instance_map:
                del loop_instance_map[key]


class IPCMessageClient(IPCClient):
    '''
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
    '''
    # FIXME timeout unimplemented
    # FIXME tries unimplemented
    @tornado.gen.coroutine
    def send(self, msg, timeout=None, tries=None):
        '''
        Send a message to an IPC socket

        If the socket is not currently connected, a connection will be established.

        :param dict msg: The message to be sent
        :param int timeout: Timeout when sending message (Currently unimplemented)
        '''
        if not self.connected():
            yield self.connect()
        pack = salt.transport.frame.frame_msg_ipc(msg, raw_body=True)
        yield self.stream.write(pack)


class IPCMessageServer(IPCServer):
    '''
    Salt IPC message server

    Creates a message server which can create and bind to a socket on a given
    path and then respond to messages asynchronously.

    An example of a very simple IPCServer which prints received messages to
    a console:

        # Import Tornado libs
        import tornado.ioloop

        # Import Salt libs
        import salt.transport.ipc
        import salt.config

        opts = salt.config.master_opts()

        io_loop = tornado.ioloop.IOLoop.current()
        ipc_server_socket_path = '/var/run/ipc_server.ipc'
        ipc_server = salt.transport.ipc.IPCMessageServer(opts, io_loop=io_loop
                                                         stream_handler=print_to_console)
        # Bind to the socket and prepare to run
        ipc_server.start(ipc_server_socket_path)

        # Start the server
        io_loop.start()

        # This callback is run whenever a message is received
        def print_to_console(payload):
            print(payload)

    See IPCMessageClient() for an example of sending messages to an IPCMessageServer instance
    '''


class IPCMessagePublisher(object):
    '''
    A Tornado IPC Publisher similar to Tornado's TCPServer class
    but using either UNIX domain sockets or TCP sockets
    '''
    def __init__(self, opts, socket_path, io_loop=None):
        '''
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
        '''
        self.opts = opts
        self.socket_path = socket_path
        self._started = False

        # Placeholders for attributes to be populated by method calls
        self.sock = None
        self.io_loop = io_loop or IOLoop.current()
        self._closing = False
        self.streams = set()

    def start(self):
        '''
        Perform the work necessary to start up a Tornado IPC server

        Blocks until socket is established
        '''
        # Start up the ioloop
        log.trace('IPCMessagePublisher: binding to socket: %s', self.socket_path)
        if isinstance(self.socket_path, int):
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.setblocking(0)
            self.sock.bind(('127.0.0.1', self.socket_path))
            # Based on default used in tornado.netutil.bind_sockets()
            self.sock.listen(128)
        else:
            self.sock = tornado.netutil.bind_unix_socket(self.socket_path)

        tornado.netutil.add_accept_handler(
            self.sock,
            self.handle_connection,
            io_loop=self.io_loop,
        )
        self._started = True

    @tornado.gen.coroutine
    def _write(self, stream, pack):
        try:
            yield stream.write(pack)
        except tornado.iostream.StreamClosedError:
            log.trace('Client disconnected from IPC %s', self.socket_path)
            self.streams.discard(stream)
        except Exception as exc:
            log.error('Exception occurred while handling stream: %s', exc)
            if not stream.closed():
                stream.close()
            self.streams.discard(stream)

    def publish(self, msg):
        '''
        Send message to all connected sockets
        '''
        if not len(self.streams):
            return

        pack = salt.transport.frame.frame_msg_ipc(msg, raw_body=True)

        for stream in self.streams:
            self.io_loop.spawn_callback(self._write, stream, pack)

    def handle_connection(self, connection, address):
        log.trace('IPCServer: Handling connection to address: %s', address)
        try:
            if self.opts['ipc_write_buffer'] > 0:
                log.trace('Setting IPC connection write buffer: %s', (self.opts['ipc_write_buffer']))
                stream = IOStream(
                    connection,
                    io_loop=self.io_loop,
                    max_write_buffer_size=self.opts['ipc_write_buffer']
                )
            else:
                stream = IOStream(
                    connection,
                    io_loop=self.io_loop
                )
            self.streams.add(stream)

            def discard_after_closed():
                self.streams.discard(stream)

            stream.set_close_callback(discard_after_closed)
        except Exception as exc:
            log.error('IPC streaming error: %s', exc)

    def close(self):
        '''
        Routines to handle any cleanup before the instance shuts down.
        Sockets and filehandles should be closed explicitly, to prevent
        leaks.
        '''
        if self._closing:
            return
        self._closing = True
        for stream in self.streams:
            stream.close()
        self.streams.clear()
        if hasattr(self.sock, 'close'):
            self.sock.close()

    def __del__(self):
        self.close()


class IPCMessageSubscriber(IPCClient):
    '''
    Salt IPC message subscriber

    Create an IPC client to receive messages from IPC publisher

    An example of a very simple IPCMessageSubscriber connecting to an IPCMessagePublisher.
    This example assumes an already running IPCMessagePublisher.

    IMPORTANT: The below example also assumes the IOLoop is NOT running.

    # Import Tornado libs
    import tornado.ioloop

    # Import Salt libs
    import salt.config
    import salt.transport.ipc

    # Create a new IO Loop.
    # We know that this new IO Loop is not currently running.
    io_loop = tornado.ioloop.IOLoop()

    ipc_publisher_socket_path = '/var/run/ipc_publisher.ipc'

    ipc_subscriber = salt.transport.ipc.IPCMessageSubscriber(ipc_server_socket_path, io_loop=io_loop)

    # Connect to the server
    # Use the associated IO Loop that isn't running.
    io_loop.run_sync(ipc_subscriber.connect)

    # Wait for some data
    package = ipc_subscriber.read_sync()
    '''
    def __singleton_init__(self, socket_path, io_loop=None):
        super(IPCMessageSubscriber, self).__singleton_init__(
            socket_path, io_loop=io_loop)
        self._read_sync_future = None
        self._read_stream_future = None
        self._sync_ioloop_running = False
        self.saved_data = []
        self._sync_read_in_progress = Semaphore()

    @tornado.gen.coroutine
    def _read_sync(self, timeout):
        yield self._sync_read_in_progress.acquire()
        exc_to_raise = None
        ret = None

        try:
            while True:
                if self._read_stream_future is None:
                    self._read_stream_future = self.stream.read_bytes(4096, partial=True)

                if timeout is None:
                    wire_bytes = yield self._read_stream_future
                else:
                    future_with_timeout = FutureWithTimeout(
                        self.io_loop, self._read_stream_future, timeout)
                    wire_bytes = yield future_with_timeout

                self._read_stream_future = None

                # Remove the timeout once we get some data or an exception
                # occurs. We will assume that the rest of the data is already
                # there or is coming soon if an exception doesn't occur.
                timeout = None

                self.unpacker.feed(wire_bytes)
                first = True
                for framed_msg in self.unpacker:
                    if first:
                        ret = framed_msg['body']
                        first = False
                    else:
                        self.saved_data.append(framed_msg['body'])
                if not first:
                    # We read at least one piece of data
                    break
        except TornadoTimeoutError:
            # In the timeout case, just return None.
            # Keep 'self._read_stream_future' alive.
            ret = None
        except tornado.iostream.StreamClosedError as exc:
            log.trace('Subscriber disconnected from IPC %s', self.socket_path)
            self._read_stream_future = None
            exc_to_raise = exc
        except Exception as exc:
            log.error('Exception occurred in Subscriber while handling stream: %s', exc)
            self._read_stream_future = None
            exc_to_raise = exc

        if self._sync_ioloop_running:
            # Stop the IO Loop so that self.io_loop.start() will return in
            # read_sync().
            self.io_loop.spawn_callback(self.io_loop.stop)

        if exc_to_raise is not None:
            raise exc_to_raise  # pylint: disable=E0702
        self._sync_read_in_progress.release()
        raise tornado.gen.Return(ret)

    def read_sync(self, timeout=None):
        '''
        Read a message from an IPC socket

        The socket must already be connected.
        The associated IO Loop must NOT be running.
        :param int timeout: Timeout when receiving message
        :return: message data if successful. None if timed out. Will raise an
                 exception for all other error conditions.
        '''
        if self.saved_data:
            return self.saved_data.pop(0)

        self._sync_ioloop_running = True
        self._read_sync_future = self._read_sync(timeout)
        self.io_loop.start()
        self._sync_ioloop_running = False

        ret_future = self._read_sync_future
        self._read_sync_future = None
        return ret_future.result()

    @tornado.gen.coroutine
    def _read_async(self, callback):
        while not self.stream.closed():
            try:
                self._read_stream_future = self.stream.read_bytes(4096, partial=True)
                wire_bytes = yield self._read_stream_future
                self._read_stream_future = None
                self.unpacker.feed(wire_bytes)
                for framed_msg in self.unpacker:
                    body = framed_msg['body']
                    self.io_loop.spawn_callback(callback, body)
            except tornado.iostream.StreamClosedError:
                log.trace('Subscriber disconnected from IPC %s', self.socket_path)
                break
            except Exception as exc:
                log.error('Exception occurred while Subscriber handling stream: %s', exc)

    @tornado.gen.coroutine
    def read_async(self, callback):
        '''
        Asynchronously read messages and invoke a callback when they are ready.

        :param callback: A callback with the received data
        '''
        while not self.connected():
            try:
                yield self.connect(timeout=5)
            except tornado.iostream.StreamClosedError:
                log.trace('Subscriber closed stream on IPC %s before connect', self.socket_path)
                yield tornado.gen.sleep(1)
            except Exception as exc:
                log.error('Exception occurred while Subscriber connecting: %s', exc)
                yield tornado.gen.sleep(1)
        yield self._read_async(callback)

    def close(self):
        '''
        Routines to handle any cleanup before the instance shuts down.
        Sockets and filehandles should be closed explicitly, to prevent
        leaks.
        '''
        if not self._closing:
            IPCClient.close(self)
            # This will prevent this message from showing up:
            # '[ERROR   ] Future exception was never retrieved:
            # StreamClosedError'
            if self._read_sync_future is not None:
                self._read_sync_future.exc_info()
            if self._read_stream_future is not None:
                self._read_stream_future.exc_info()

    def __del__(self):
        if IPCMessageSubscriber in globals():
            self.close()
