# -*- coding: utf-8 -*-
'''
IPC transport classes
'''

# Import Python libs
from __future__ import absolute_import
import logging
import socket
import msgpack
import weakref

# Import Tornado libs
import tornado
import tornado.gen
import tornado.netutil
import tornado.concurrent
from tornado.ioloop import IOLoop
from tornado.iostream import IOStream

# Import Salt libs
import salt.transport.client
import salt.transport.frame

log = logging.getLogger(__name__)


class IPCServer(object):
    '''
    A Tornado IPC server very similar to Tornado's TCPServer class
    but using either UNIX domain sockets or TCP sockets
    '''
    def __init__(self, socket_path, io_loop=None, payload_handler=None):
        '''
        Create a new Tornado IPC server

        :param IOLoop io_loop: A Tornado ioloop to handle scheduling
        :param func stream_handler: A function to customize handling of an
                                    incoming stream.
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

        :param str socket_path: Path on the filesystem for the socket to bind to.
                                This socket does not need to exist prior to calling
                                this method, but parent directories should.
        '''
        # Start up the ioloop
        log.trace('IPCServer: binding to socket: {0}'.format(self.socket_path))
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

        See http://tornado.readthedocs.org/en/latest/iostream.html#tornado.iostream.IOStream
        for additional details.
        '''
        @tornado.gen.coroutine
        def _null(msg):
            raise tornado.gen.Return(None)

        def write_callback(stream, header):
            if header.get('mid'):
                @tornado.gen.coroutine
                def return_message(msg):
                    pack = salt.transport.frame.frame_msg(
                        msg,
                        header={'mid': header['mid']},
                        raw_body=True,
                    )
                    yield stream.write(pack)
                return return_message
            else:
                return _null
        while not stream.closed():
            try:
                framed_msg_len = yield stream.read_until(' ')
                framed_msg_raw = yield stream.read_bytes(int(framed_msg_len.strip()))
                framed_msg = msgpack.loads(framed_msg_raw)
                body = framed_msg['body']
                self.io_loop.spawn_callback(self.payload_handler, body, write_callback(stream, framed_msg['head']))
            except tornado.iostream.StreamClosedError:
                log.trace('Client disconnected from IPC {0}'.format(self.socket_path))
                break
            except Exception as exc:
                log.error('Exception occurred while handling stream: {0}'.format(exc))

    def handle_connection(self, connection, address):
        log.trace('IPCServer: Handling connection to address: {0}'.format(address))
        try:
            stream = IOStream(
                connection,
                io_loop=self.io_loop,
            )
            self.io_loop.spawn_callback(self.handle_stream, stream)
        except Exception as exc:
            log.error('IPC streaming error: {0}'.format(exc))

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
    :param str socket_path: A path on the filesystem where a socket
                            belonging to a running IPCServer can be
                            found.
    '''

    # Create singleton map between two sockets
    instance_map = weakref.WeakKeyDictionary()

    def __new__(cls, socket_path, io_loop=None):
        io_loop = io_loop or tornado.ioloop.IOLoop.current()
        if io_loop not in IPCClient.instance_map:
            IPCClient.instance_map[io_loop] = weakref.WeakValueDictionary()
        loop_instance_map = IPCClient.instance_map[io_loop]

        # FIXME
        key = socket_path

        if key not in loop_instance_map:
            log.debug('Initializing new IPCClient for path: {0}'.format(key))
            new_client = object.__new__(cls)
            # FIXME
            new_client.__singleton_init__(io_loop=io_loop, socket_path=socket_path)
            loop_instance_map[key] = new_client
        else:
            log.debug('Re-using IPCClient for {0}'.format(key))
        return loop_instance_map[key]

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

    def __init__(self, socket_path, io_loop=None):
        # Handled by singleton __new__
        pass

    def connected(self):
        return hasattr(self, 'stream')

    def connect(self, callback=None):
        '''
        Connect to the IPC socket
        '''
        if hasattr(self, '_connecting_future') and not self._connecting_future.done():  # pylint: disable=E0203
            future = self._connecting_future  # pylint: disable=E0203
        else:
            future = tornado.concurrent.Future()
            self._connecting_future = future
            self.io_loop.add_callback(self._connect)

        if callback is not None:
            def handle_future(future):
                response = future.result()
                self.io_loop.add_callback(callback, response)
            future.add_done_callback(handle_future)
        return future

    @tornado.gen.coroutine
    def _connect(self):
        '''
        Connect to a running IPCServer
        '''
        self.stream = IOStream(
            socket.socket(socket.AF_UNIX, socket.SOCK_STREAM),
            io_loop=self.io_loop,
        )
        while True:
            if self._closing:
                break
            try:
                log.trace('IPCClient: Connecting to socket: {0}'.format(self.socket_path))
                yield self.stream.connect(self.socket_path)
                self._connecting_future.set_result(True)
                break
            except Exception as e:
                yield tornado.gen.sleep(1)  # TODO: backoff
                #self._connecting_future.set_exception(e)

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
        if hasattr(self, 'stream'):
            self.stream.close()


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
        pack = salt.transport.frame.frame_msg(msg, raw_body=True)
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
