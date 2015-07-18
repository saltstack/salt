# -*- coding: utf-8 -*-
'''
IPC transport classes
'''

# Import Python libs
from __future__ import absolute_import
import logging
import socket
import sys
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
import salt.utils.async
from salt.exceptions import SaltReqTimeoutError

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
        self.stream = None
        self.sock = None
        self.io_loop = io_loop or IOLoop.current()

        self.clients = []  # clients connected to the server

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

    def publish(self, msg):
        '''
        Publish a `msg` to all connected clients
        '''
        payload = salt.transport.frame.frame_msg(msg, raw_body=True)
        to_remove = []
        for client in self.clients:
            try:
                # Don't wait on the future, best effort only
                f = client.write(payload)
                self.io_loop.add_future(f, lambda f: True)
            except tornado.iostream.StreamClosedError:
                to_remove.append(client)
        for client in to_remove:
            client.close()
            self.clients.remove(client)
        log.trace('IPCServer finished publishing msg')

    @tornado.gen.coroutine
    def handle_stream(self, stream):
        '''
        Override this to handle the streams as they arrive

        :param IOStream stream: An IOStream for processing

        See http://tornado.readthedocs.org/en/latest/iostream.html#tornado.iostream.IOStream
        for additional details.
        '''
        self.clients.append(stream)

        while not stream.closed():
            try:
                framed_msg_len = yield stream.read_until(' ')
                framed_msg_raw = yield stream.read_bytes(int(framed_msg_len.strip()))
                framed_msg = msgpack.loads(framed_msg_raw)
                body = framed_msg['body']
                self.io_loop.spawn_callback(self.payload_handler, body, write_callback(stream, framed_msg['head']))
            except Exception as exc:
                log.error('Exception occurred while handling stream: {0}'.format(exc))

        self.clients.remove(stream)

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
        Sockets and filehandles should be closed explicitely, to prevent
        leaks.
        '''
        if hasattr(self.stream, 'close'):
            self.stream.close()
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

        self.subscribe_handlers = []
        self._mid = 1
        # TODO: move to config
        self._max_messages = sys.maxint - 1  # number of IDs before we wrap

        # Maximum number of inflight messages
        self.maxflight = 5  # TODO: config

        # queue of messages to send
        self.send_queue = []

        # mapping of message_id -> future
        self.inflight_messages = {}

        # mapping of message_future -> timeout
        self.timeout_map = {}

    def _alloc_mid(self):
        '''
        Return an available MID
        '''
        wrap = False
        while self._mid in self.inflight_messages:
            if self._mid >= self._max_messages:
                if wrap:
                    # this shouldn't ever happen, but just in case
                    raise Exception('Unable to find available messageid')
                self._mid = 1
                wrap = True
            else:
                self._mid += 2

        return self._mid

    def __init__(self, socket_path, io_loop=None):
        # Handled by singleton __new__
        pass

    def connected(self):
        return hasattr(self, 'stream') and hasattr(self, '_connecting_future') and self._connecting_future.done()

    def connect(self, callback=None):
        '''
        Connect to the IPC socket
        '''
        if hasattr(self, '_connecting_future') and (self.connected() or not self._connecting_future.done()):  # pylint: disable=E0203
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
                self.io_loop.spawn_callback(self._handle_incoming)
                self._connecting_future.set_result(True)
                break
            except Exception as e:
                yield tornado.gen.sleep(1)  # TODO: backoff
                #self._connecting_future.set_exception(e)

    @tornado.gen.coroutine
    def _handle_incoming(self):
        '''
        Coroutine responsible for handling all incoming data and disbatching it
        appropriately

        - msg incoming with no message_id -- subscribe
        - msg incoming with message_id
            client odd: meaning we are getting a return
            server even: meaning we are getting a request which we must respond to

        '''

        if not self.connected():
            yield self.connect()

        while not self._closing:
            try:
                framed_msg_len = yield self.stream.read_until(' ')
                framed_msg_raw = yield self.stream.read_bytes(int(framed_msg_len.strip()))
                framed_msg = msgpack.loads(framed_msg_raw)
                header = framed_msg['head']
                message_id = header.get('mid')
                body = framed_msg['body']

                if message_id is None:
                    log.trace('Recieved subcribed message on {0}'.format(self.socket_path))
                    for handler in self.subscribe_handlers:
                        self.io_loop.spawn_callback(handler, body)
                # otherwise we have a message ID, lets handle it
                else:
                    # if its odd, then we are getting a return for something we requested
                    if message_id % 2 == 1:
                        log.trace('Recieved return for message_id {0} on {1}'.format(message_id, self.socket_path))
                        message_future = self.inflight_messages.pop(message_id)
                        self.remove_message_timeout(message_future)
                        message_future.set_result(body)

                    # if its even, we are getting a request to respond to
                    else:
                        # TODO: implement if we need it
                        #ret_func = write_callback(self.stream, header)
                        pass

            except tornado.iostream.StreamClosedError as e:
                log.debug('IPC stream to {0} closed, unable to recv'.format(self.socket_path))
                yield self.connect()
            except Exception as e:
                log.error('Exception parsing response', exc_info=True)
                self.disconnect()
                raise tornado.gen.Return()

    @tornado.gen.coroutine
    def _handle_outgoing(self):
        '''
        Handle all sending of messages
        '''
        while len(self.send_queue) > 0 and not self._closing:
            # if there are too many outgoing, lets wait until one finishes
            if len(self.inflight_messages) >= self.maxflight:
                log.trace('IPC socket {0} has too many messages inflight, waiting...'.format(self.socket_path))
                yield salt.utils.async.Any(self.inflight_messages.itervalues())
            if not self.connected():
                yield self.connect()
            message_future = self.send_queue.pop(0)
            message_id = self._alloc_mid()
            message_future._msg_id = message_id
            msg = salt.transport.frame.frame_msg(
                message_future._msg,
                header={'mid': message_id},
                raw_body=True
            )
            try:
                yield self.stream.write(msg)
                self.inflight_messages[message_id] = message_future
            # if the connection is dead, lets fail this send, and make sure we
            # attempt to reconnect
            except tornado.iostream.StreamClosedError as e:
                self.inflight_messages.pop(message_id).set_exception(Exception())
                self.remove_message_timeout(message_future)
                # if the last connect finished, then we need to make a new one
                self.disconnect()

    def timeout_message(self, message_future):
        '''
        timeout a given message_id
        '''
        log.trace('Timing out message_id {0} on {1}'.format(message_id, self.socket_path))
        del self.timeout_map[message_future]
        if message_future in self.send_queue:
            log.trace('Timing out future from send queue')
            self.send_queue.remove(message_future)
        else:
            log.trace('Timing out inflight future from send queue')
            self.inflight_messages.pop(message_future._msg_id).set_exception(SaltReqTimeoutError('Message timed out'))

    def remove_message_timeout(self, message_future):
        if message_future not in self.timeout_map:
            return
        timeout = self.timeout_map.pop(message_future)
        self.io_loop.remove_timeout(timeout)

    def send(self, msg, timeout=None, callback=None):
        '''
        Send given message, and return a future with the result of the message
        '''
        future = tornado.concurrent.Future()
        future._msg = msg
        if callback is not None:
            def handle_future(future):
                response = future.result()
                self.io_loop.add_callback(callback, response)
            future.add_done_callback(handle_future)

        if timeout is not None:
            send_timeout = self.io_loop.call_later(timeout, self.timeout_message, future)
            self.timeout_map[future] = send_timeout

        # if we don't have a send queue, we need to spawn the callback to do the sending
        if len(self.send_queue) == 0:
            self.io_loop.spawn_callback(self._handle_outgoing)
        self.send_queue.append(future)
        return future

    # TODO: implement if we need it?
    def publish(self, msg, timeout=None, callback=None):
        '''
        Publish a message (send without expecting a response. Return a future
        which will complete when the message has been sent
        '''
        raise NotImplementedError()

    def subscribe(self, handler):
        '''
        Subscribe to all incoming publishes messages. `handler` will be called
        with the message
        '''
        self.subscribe_handlers.append(handler)

    def unsubscribe(self, handler):
        '''
        Unsubscribe `handler` from incoming messages
        '''
        self.subscribe_handlers.remove(handler)

    def __del__(self):
        self.close()

    def close(self):
        '''
        Routines to handle any cleanup before the instance shuts down.
        Sockets and filehandles should be closed explicitely, to prevent
        leaks.
        '''
        self._closing = True
        if hasattr(self, 'stream'):
            self.stream.close()
            del self.stream

        # close out all inflight messages and remove all timeouts
        for message_id, future in self.inflight_messages.iteritems():
            future.set_exception(SaltReqTimeoutError('IPC Channel closed'))
            self.remove_message_timeout(message_id)

    def disconnect(self):
        '''
        Foribly disconnect the current stream, this will cause a reconnect unlike
        close() which will just close and shutdown
        '''
        if hasattr(self, 'stream'):
            self.stream.close()
            del self.stream


# TODO: move to a library?
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
        @tornado.gen.coroutine
        def _null(msg):
            raise tornado.gen.Return(None)
        return _null


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
