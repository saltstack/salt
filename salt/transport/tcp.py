# -*- coding: utf-8 -*-
'''
TCP transport classes

Wire protocol: "len(payload) msgpack({'head': SOMEHEADER, 'body': SOMEBODY})"

'''

# Import Python Libs
from __future__ import absolute_import
import logging
import msgpack
import socket
import sys
import os
import urlparse  # TODO: remove


# Import Salt Libs
import salt.crypt
import salt.utils
import salt.utils.verify
import salt.utils.event
import salt.payload
import salt.exceptions
import salt.transport.client
import salt.transport.server
import salt.transport.mixins.auth
from salt.exceptions import SaltReqTimeoutError, SaltClientError

# for IPC (for now)
import zmq
import zmq.eventloop.ioloop
# support pyzmq 13.0.x, TODO: remove once we force people to 14.0.x
if not hasattr(zmq.eventloop.ioloop, 'ZMQIOLoop'):
    zmq.eventloop.ioloop.ZMQIOLoop = zmq.eventloop.ioloop.IOLoop
import zmq.eventloop.zmqstream

# Import Tornado Libs
import tornado
import tornado.tcpserver
import tornado.gen
import tornado.concurrent
import tornado.tcpclient
import tornado.netutil

log = logging.getLogger(__name__)


def frame_msg(body, header=None, raw_body=False):
    '''
    Frame the given message with our wire protocol
    '''
    framed_msg = {}
    if header is None:
        header = {}

    # if the body wasn't already msgpacked-- lets do that.
    if not raw_body:
        body = msgpack.dumps(body)

    framed_msg['head'] = header
    framed_msg['body'] = body
    framed_msg_packed = msgpack.dumps(framed_msg)
    return '{0} {1}'.format(len(framed_msg_packed), framed_msg_packed)


def socket_frame_recv(s, recv_size=4096):
    '''
    Retrieve a frame from socket
    '''
    # get the header size
    recv_buf = ''
    while ' ' not in recv_buf:
        data = s.recv(recv_size)
        if data == '':
            raise socket.error('Empty response!')
        else:
            recv_buf += data
    # once we have a space, we know how long the rest is
    header_len, buf = recv_buf.split(' ', 1)
    header_len = int(header_len)
    while len(buf) < header_len:
        data = s.recv(recv_size)
        if data == '':
            raise socket.error('msg stopped, we are missing some data!')
        else:
            buf += data

    header = msgpack.loads(buf[:header_len])
    msg_len = int(header['msgLen'])
    buf = buf[header_len:]
    while len(buf) < msg_len:
        data = s.recv(recv_size)
        if data == '':
            raise socket.error('msg stopped, we are missing some data!')
        else:
            buf += data

    return buf


# TODO: make singleton
# TODO: move serial down into message library
class AsyncTCPReqChannel(salt.transport.client.ReqChannel):
    '''
    Encapsulate sending routines to tcp.
    '''
    def __init__(self, opts, **kwargs):
        self.opts = dict(opts)

        self.serial = salt.payload.Serial(self.opts)

        # crypt defaults to 'aes'
        self.crypt = kwargs.get('crypt', 'aes')

        self.io_loop = kwargs.get('io_loop') or tornado.ioloop.IOLoop.current()

        if self.crypt != 'clear':
            self.auth = salt.crypt.AsyncAuth(self.opts, io_loop=self.io_loop)

        parse = urlparse.urlparse(self.opts['master_uri'])
        host, port = parse.netloc.rsplit(':', 1)
        self.master_addr = (host, int(port))

        self.message_client = SaltMessageClient(host, int(port), io_loop=self.io_loop)

    def __del__(self):
        self.message_client.destroy()

    def _package_load(self, load):
        return {
            'enc': self.crypt,
            'load': load,
        }

    @tornado.gen.coroutine
    def crypted_transfer_decode_dictentry(self, load, dictkey=None, tries=3, timeout=60):
        if not self.auth.authenticated:
            yield self.auth.authenticate()
        ret = yield self.message_client.send(self._package_load(self.auth.crypticle.dumps(load)), timeout=timeout)
        key = self.auth.get_keys()
        aes = key.private_decrypt(ret['key'], 4)
        pcrypt = salt.crypt.Crypticle(self.opts, aes)
        raise tornado.gen.Return(pcrypt.loads(ret[dictkey]))

    @tornado.gen.coroutine
    def _crypted_transfer(self, load, tries=3, timeout=60):
        '''
        In case of authentication errors, try to renegotiate authentication
        and retry the method.
        Indeed, we can fail too early in case of a master restart during a
        minion state execution call
        '''
        @tornado.gen.coroutine
        def _do_transfer():
            data = yield self.message_client.send(self._package_load(self.auth.crypticle.dumps(load)),
                                                  timeout=timeout,
                                                  )
            # we may not have always data
            # as for example for saltcall ret submission, this is a blind
            # communication, we do not subscribe to return events, we just
            # upload the results to the master
            if data:
                data = self.auth.crypticle.loads(data)
            raise tornado.gen.Return(data)

        if not self.auth.authenticated:
            yield self.auth.authenticate()
        try:
            ret = yield _do_transfer()
            raise tornado.gen.Return(ret)
        except salt.crypt.AuthenticationError:
            yield self.auth.authenticate()
            ret = yield _do_transfer()
            raise tornado.gen.Return(ret)

    @tornado.gen.coroutine
    def _uncrypted_transfer(self, load, tries=3, timeout=60):
        ret = yield self.message_client.send(self._package_load(load), timeout=timeout)
        raise tornado.gen.Return(ret)

    @tornado.gen.coroutine
    def send(self, load, tries=3, timeout=60):
        '''
        Send a request, return a future which will complete when we send the message
        '''
        if self.crypt == 'clear':
            ret = yield self._uncrypted_transfer(load, tries=tries, timeout=timeout)
        else:
            ret = yield self._crypted_transfer(load, tries=tries, timeout=timeout)
        raise tornado.gen.Return(ret)


class AsyncTCPPubChannel(salt.transport.mixins.auth.AESPubClientMixin, salt.transport.client.AsyncPubChannel):
    def __init__(self,
                 opts,
                 **kwargs):
        self.opts = opts

        self.serial = salt.payload.Serial(self.opts)

        self.io_loop = kwargs['io_loop'] or tornado.ioloop.IOLoop.current()
        self.connected = False

    def __del__(self):
        if hasattr(self, 'message_client'):
            self.message_client.destroy()

    @tornado.gen.coroutine
    def connect(self):
        try:
            self.auth = salt.crypt.AsyncAuth(self.opts)
            if not self.auth.authenticated:
                yield self.auth.authenticate()
            self.message_client = SaltMessageClient(self.opts['master_ip'],
                                                    int(self.auth.creds['publish_port']),
                                                    io_loop=self.io_loop)
            yield self.message_client.connect()  # wait for the client to be connected
            self.connected = True
        # TODO: better exception handling...
        except KeyboardInterrupt:
            raise
        except:
            raise SaltClientError('Unable to sign_in to master')  # TODO: better error message

    def on_recv(self, callback):
        '''
        Register an on_recv callback
        '''
        if callback is None:
            return self.message_client.on_recv(callback)

        @tornado.gen.coroutine
        def wrap_callback(body):
            ret = yield self._decode_payload(body)
            callback(ret)
        return self.message_client.on_recv(wrap_callback)


class TCPReqServerChannel(salt.transport.mixins.auth.AESReqServerMixin, salt.transport.server.ReqServerChannel):
    # TODO: opts!
    backlog = 5

    @property
    def socket(self):
        return self._socket

    def close(self):
        self.socket.shutdown(socket.SHUT_RDWR)
        self.socket.close()

    def __del__(self):
        self.close()

    def pre_fork(self, process_manager):
        '''
        Pre-fork we need to create the zmq router device
        '''
        salt.transport.mixins.auth.AESReqServerMixin.pre_fork(self, process_manager)
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.setblocking(0)
        self._socket.bind((self.opts['interface'], int(self.opts['ret_port'])))

    def post_fork(self, payload_handler, io_loop):
        '''
        After forking we need to create all of the local sockets to listen to the
        router

        payload_handler: function to call with your payloads
        '''
        self.payload_handler = payload_handler
        self.io_loop = io_loop
        self.req_server = SaltMessageServer(self.handle_message, io_loop=self.io_loop)
        self.req_server.add_socket(self.socket)
        self.socket.listen(self.backlog)

        self.serial = salt.payload.Serial(self.opts)
        salt.transport.mixins.auth.AESReqServerMixin.post_fork(self, payload_handler, io_loop)

    @tornado.gen.coroutine
    def handle_message(self, stream, header, payload):
        '''
        Handle incoming messages from underylying tcp streams
        '''
        try:
            payload = self._decode_payload(payload)
        except Exception:
            stream.write(frame_msg('bad load', header=header))
            raise tornado.gen.Return()

        # TODO helper functions to normalize payload?
        if not isinstance(payload, dict) or not isinstance(payload.get('load'), dict):
            yield stream.write(frame_msg('payload and load must be a dict', header=header))
            raise tornado.gen.Return()

        # intercept the "_auth" commands, since the main daemon shouldn't know
        # anything about our key auth
        if payload['enc'] == 'clear' and payload.get('load', {}).get('cmd') == '_auth':
            yield stream.write(frame_msg(self._auth(payload['load']), header=header))
            raise tornado.gen.Return()

        # TODO: test
        try:
            ret, req_opts = yield self.payload_handler(payload)
        except Exception as e:
            # always attempt to return an error to the minion
            stream.write('Some exception handling minion payload')
            log.error('Some exception handling a payload from minion', exc_info=True)
            stream.close()
            raise tornado.gen.Return()

        req_fun = req_opts.get('fun', 'send')
        if req_fun == 'send_clear':
            stream.write(frame_msg(ret, header=header))
        elif req_fun == 'send':
            stream.write(frame_msg(self.crypticle.dumps(ret), header=header))
        elif req_fun == 'send_private':
            stream.write(frame_msg(self._encrypt_private(ret,
                                                         req_opts['key'],
                                                         req_opts['tgt'],
                                                         ), header=header))
        else:
            log.error('Unknown req_fun {0}'.format(req_fun))
            # always attempt to return an error to the minion
            stream.write('Server-side exception handling payload')
            stream.close()
        raise tornado.gen.Return()


class SaltMessageServer(tornado.tcpserver.TCPServer, object):
    '''
    Raw TCP server which will recieve all of the TCP streams and re-assemble
    messages that are sent through to us
    '''
    def __init__(self, message_handler, *args, **kwargs):
        super(SaltMessageServer, self).__init__(*args, **kwargs)

        self.clients = []
        self.message_handler = message_handler

    @tornado.gen.coroutine
    def handle_stream(self, stream, address):
        '''
        Handle incoming streams and add messages to the incoming queue
        '''
        log.trace('Req client {0} connected'.format(address))
        self.clients.append((stream, address))
        try:
            while True:
                framed_msg_len = yield stream.read_until(' ')
                framed_msg_raw = yield stream.read_bytes(int(framed_msg_len.strip()))
                framed_msg = msgpack.loads(framed_msg_raw)
                header = framed_msg['head']
                body = msgpack.loads(framed_msg['body'])
                self.io_loop.spawn_callback(self.message_handler, stream, header, body)

        except tornado.iostream.StreamClosedError:
            log.trace('req client disconnected {0}'.format(address))
            self.clients.remove((stream, address))
        except Exception as e:
            log.trace('other master-side exception??', e, e.__module__, e.extra)
            self.clients.remove((stream, address))
            stream.close()

    def shutdown(self):
        '''
        Shutdown the whole server
        '''
        for item in self.clients:
            client, address = item
            client.close()
            self.clients.remove(item)


# TODO: singleton? Something to not re-create the tcp connection so much
class SaltMessageClient(object):
    '''
    Low-level message sending client
    '''
    def __init__(self, host, port, io_loop=None):
        self.host = host
        self.port = port

        self.io_loop = io_loop or tornado.ioloop.IOLoop.current()

        # Configure the resolver to use a non-blocking one
        # Not Threaded since we need to work on python2
        tornado.netutil.Resolver.configure('tornado.netutil.ExecutorResolver')

        self._tcp_client = tornado.tcpclient.TCPClient(io_loop=self.io_loop)

        self._mid = 1
        self._max_messages = sys.maxint - 1  # number of IDs before we wrap

        # TODO: max queue size
        self.send_queue = []  # queue of messages to be sent
        self.send_future_map = {}  # mapping of request_id -> Future
        self.send_timeout_map = {}  # request_id -> timeout_callback

        self._connecting_future = self.connect()
        self.io_loop.spawn_callback(self._stream_return)

        self._on_recv = None
        self._closing = False

    # TODO: timeout inflight sessions
    def destroy(self):
        self._closing = True
        if hasattr(self, '_stream') and not self._stream.closed():
            self._stream.close()

    def __del__(self):
        self.destroy()

    def connect(self, callback=None):
        '''
        Ask for this client to reconnect to the origin
        '''
        if hasattr(self, '_connecting_future') and not self._connecting_future.done():
            future = self._connecting_future
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

    # TODO: tcp backoff opts
    @tornado.gen.coroutine
    def _connect(self):
        '''
        Try to connect for the rest of time!
        '''
        while True:
            if self._closing:
                break
            try:
                self._stream = yield self._tcp_client.connect(self.host, self.port)
                self._connecting_future.set_result(True)
                break
            except Exception as e:
                yield tornado.gen.sleep(1)  # TODO: backoff
                #self._connecting_future.set_exception(e)

    @tornado.gen.coroutine
    def _stream_return(self):
        while not self._connecting_future.done() or self._connecting_future.result() is not True:
            yield self._connecting_future
        while True:
            try:
                framed_msg_len = yield self._stream.read_until(' ')
                framed_msg_raw = yield self._stream.read_bytes(int(framed_msg_len.strip()))
                framed_msg = msgpack.loads(framed_msg_raw)
                header = framed_msg['head']
                message_id = header.get('mid')
                body = msgpack.loads(framed_msg['body'])

                if message_id in self.send_future_map:
                    self.send_future_map.pop(message_id).set_result(body)
                    self.remove_message_timeout(message_id)
                else:
                    if self._on_recv is not None:
                        self.io_loop.spawn_callback(self._on_recv, header, body)
                    else:
                        log.error('Got response for message_id {0} that we are not tracking'.format(message_id))
            except tornado.iostream.StreamClosedError as e:
                log.debug('tcp stream to {0}:{1} closed, unable to recv'.format(self.host, self.port))
                for future in self.send_future_map.itervalues():
                    future.set_exception(e)
                self.send_future_map = {}
                # if the last connect finished, then we need to make a new one
                if self._connecting_future.done():
                    self._connecting_future = self.connect()
                yield self._connecting_future
            except Exception as e:
                log.error('Exception parsing response', exc_info=True)
                for future in self.send_future_map.itervalues():
                    future.set_exception(e)
                self.send_future_map = {}
                # if the last connect finished, then we need to make a new one
                if self._connecting_future.done():
                    self._connecting_future = self.connect()

    @tornado.gen.coroutine
    def _stream_send(self):
        while not self._connecting_future.done() or self._connecting_future.result() is not True:
            yield self._connecting_future
        while len(self.send_queue) > 0:
            message_id, item = self.send_queue.pop(0)
            try:
                yield self._stream.write(item)
            # if the connection is dead, lets fail this send, and make sure we
            # attempt to reconnect
            except tornado.iostream.StreamClosedError as e:
                self.send_future_map.pop(message_id).set_exception(Exception())
                self.remove_message_timeout(message_id)
                # if the last connect finished, then we need to make a new one
                if self._connecting_future.done():
                    self._connecting_future = self.connect()

    def _message_id(self):
        wrap = False
        while self._mid in self.send_future_map:
            if self._mid >= self._max_messages:
                if wrap:
                    # this shouldn't ever happen, but just in case
                    raise Exception('Unable to find available messageid')
                self._mid = 1
                wrap = True
            else:
                self._mid += 1

        return self._mid

    # TODO: return a message object which takes care of multiplexing?
    def on_recv(self, callback):
        '''
        Register a callback for recieved messages (that we didn't initiate)
        '''
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

    def timeout_message(self, message_id):
        del self.send_timeout_map[message_id]
        self.send_future_map.pop(message_id).set_exception(SaltReqTimeoutError('Message timed out'))

    def send(self, msg, timeout=None, callback=None):
        '''
        Send given message, and return a future
        '''
        message_id = self._message_id()
        header = {'mid': message_id}

        future = tornado.concurrent.Future()
        if callback is not None:
            def handle_future(future):
                response = future.result()
                self.io_loop.add_callback(callback, response)
            future.add_done_callback(handle_future)
        # Add this future to the mapping
        self.send_future_map[message_id] = future

        if timeout is not None:
            send_timeout = self.io_loop.call_later(timeout, self.timeout_message, message_id)
            self.send_timeout_map[message_id] = send_timeout

        # if we don't have a send queue, we need to spawn the callback to do the sending
        if len(self.send_queue) == 0:
            self.io_loop.spawn_callback(self._stream_send)
        self.send_queue.append((message_id, frame_msg(msg, header=header)))
        return future


class PubServer(tornado.tcpserver.TCPServer, object):
    '''
    TCP publisher
    '''
    def __init__(self, *args, **kwargs):
        super(PubServer, self).__init__(*args, **kwargs)
        self.clients = []

    def handle_stream(self, stream, address):
        log.trace('Subscriber at {0} connected'.format(address))
        self.clients.append((stream, address))

    @tornado.gen.coroutine
    def publish_payload(self, package):
        log.trace('TCP PubServer starting to publish payload')
        package = package[0]  # ZMQ (The IPC calling us) ism :/
        payload = frame_msg(salt.payload.unpackage(package)['payload'], raw_body=True)
        to_remove = []
        for item in self.clients:
            client, address = item
            try:
                f = client.write(payload)
                self.io_loop.add_future(f, lambda f: True)
            except tornado.iostream.StreamClosedError:
                to_remove.append(item)
        for item in to_remove:
            client, address = item
            log.debug('Subscriber at {0} has disconnected from publisher'.format(address))
            client.close()
            self.clients.remove(item)
        log.trace('TCP PubServer finished publishing payload')


class TCPPubServerChannel(salt.transport.server.PubServerChannel):
    def __init__(self, opts):
        self.opts = opts
        self.serial = salt.payload.Serial(self.opts)  # TODO: in init?

    def _publish_daemon(self):
        '''
        Bind to the interface specified in the configuration file
        '''
        salt.utils.appendproctitle(self.__class__.__name__)

        # Set up the context
        context = zmq.Context(1)
        # Prepare minion pull socket
        pull_sock = context.socket(zmq.PULL)
        pull_uri = 'ipc://{0}'.format(
            os.path.join(self.opts['sock_dir'], 'publish_pull_tcp.ipc')
        )
        salt.utils.zeromq.check_ipc_path_max_len(pull_uri)

        # Securely create socket
        log.info('Starting the Salt Puller on {0}'.format(pull_uri))
        old_umask = os.umask(0o177)
        try:
            pull_sock.bind(pull_uri)
        finally:
            os.umask(old_umask)

        # load up the IOLoop
        io_loop = zmq.eventloop.ioloop.ZMQIOLoop()
        # add the publisher
        pub_server = PubServer(io_loop=io_loop)
        pub_server.listen(int(self.opts['publish_port']), address=self.opts['interface'])

        # add our IPC
        stream = zmq.eventloop.zmqstream.ZMQStream(pull_sock, io_loop=io_loop)
        stream.on_recv(pub_server.publish_payload)

        # run forever
        io_loop.start()

    def pre_fork(self, process_manager):
        '''
        Do anything necessary pre-fork. Since this is on the master side this will
        primarily be used to create IPC channels and create our daemon process to
        do the actual publishing
        '''
        process_manager.add_process(self._publish_daemon)

    def publish(self, load):
        '''
        Publish "load" to minions
        '''
        payload = {'enc': 'aes'}

        crypticle = salt.crypt.Crypticle(self.opts, salt.master.SMaster.secrets['aes']['secret'].value)
        payload['load'] = crypticle.dumps(load)
        if self.opts['sign_pub_messages']:
            master_pem_path = os.path.join(self.opts['pki_dir'], 'master.pem')
            log.debug("Signing data packet")
            payload['sig'] = salt.crypt.sign_message(master_pem_path, payload['load'])
        # Send 0MQ to the publisher
        context = zmq.Context(1)
        pub_sock = context.socket(zmq.PUSH)
        pull_uri = 'ipc://{0}'.format(
            os.path.join(self.opts['sock_dir'], 'publish_pull_tcp.ipc')
            )
        pub_sock.connect(pull_uri)
        int_payload = {'payload': self.serial.dumps(payload)}

        # add some targeting stuff for lists only (for now)
        if load['tgt_type'] == 'list':
            int_payload['topic_lst'] = load['tgt']

        pub_sock.send(self.serial.dumps(int_payload))
