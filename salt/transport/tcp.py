'''
TCP transport classes



Wire protocol: "len(header) header msg"
header is a msgpack'd dict which includes (at least) msgLen

'''

import socket
import select


import os
import errno
import ctypes
import multiprocessing
import urlparse  # TODO: remove


# Import Salt Libs
import salt.auth
import salt.crypt
import salt.utils
import salt.utils.verify
import salt.utils.event
import salt.payload
import salt.exceptions

import logging

import salt.transport.client
import salt.transport.server
import salt.transport.mixins.auth

# for IPC (for now)
import zmq
import zmq.eventloop.ioloop
import zmq.eventloop.zmqstream

# tornado imports
import tornado
import tornado.tcpserver
import tornado.gen
import tornado.concurrent
import tornado.tcpclient

log = logging.getLogger(__name__)

import msgpack

# TODO: put in some lib?
def frame_msg(msg, header=None):
    if header is None:
        header = {}

    header['msgLen'] = len(msg)
    header_packed = msgpack.dumps(header)
    return '{0} {1}{2}'.format(len(header_packed), header_packed, msg)


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


class TCPReqChannel(salt.transport.client.ReqChannel):
    '''
    Encapsulate sending routines to tcp.

    TODO:
        - add timeouts
    '''
    def __init__(self, opts, **kwargs):
        self.opts = dict(opts)

        self.serial = salt.payload.Serial(self.opts)

        # crypt defaults to 'aes'
        self.crypt = kwargs.get('crypt', 'aes')

        if self.crypt != 'clear':
            self.auth = salt.crypt.SAuth(self.opts)

        parse = urlparse.urlparse(self.opts['master_uri'])
        host, port = parse.netloc.rsplit(':', 1)
        self.master_addr = (host, int(port))

        self.io_loop = tornado.ioloop.IOLoop()
        self.message_client = SaltMessageClient(host, int(port), io_loop=self.io_loop)

    def _package_load(self, load):
        return self.serial.dumps({
            'enc': self.crypt,
            'load': load,
        })

    @property
    def socket(self):
        if not hasattr(self, '_socket'):
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.connect(self.master_addr)
        return self._socket

    def _send_recv(self, msg):
        '''
        Do a blocking send/recv combo
        '''
        self.socket.send(frame_msg(msg))
        return socket_frame_recv(self.socket)

    def crypted_transfer_decode_dictentry(self, load, dictkey=None, tries=3, timeout=60):
        # send msg
        ret = self._send_recv(self._package_load(self.auth.crypticle.dumps(load)))
        # wait for response
        ret = self.serial.loads(ret)
        key = self.auth.get_keys()
        aes = key.private_decrypt(ret['key'], 4)
        pcrypt = salt.crypt.Crypticle(self.opts, aes)
        return pcrypt.loads(ret[dictkey])

    def _crypted_transfer(self, load, tries=3, timeout=60):
        '''
        In case of authentication errors, try to renegotiate authentication
        and retry the method.
        Indeed, we can fail too early in case of a master restart during a
        minion state execution call
        '''
        def _do_transfer():
            data = self._send_recv(self._package_load(self.auth.crypticle.dumps(load)))
            data = self.serial.loads(data)
            # we may not have always data
            # as for example for saltcall ret submission, this is a blind
            # communication, we do not subscribe to return events, we just
            # upload the results to the master
            if data:
                data = self.auth.crypticle.loads(data)
            return data
        try:
            return _do_transfer()
        except salt.crypt.AuthenticationError:
            self.auth.authenticate()
            return _do_transfer()

    def _uncrypted_transfer(self, load, tries=3, timeout=60):
        ret = self._send_recv(self._package_load(load))
        return self.serial.loads(ret)

    def send(self, load, tries=3, timeout=60):
        if self.crypt == 'clear':  # for sign-in requests
            return self._uncrypted_transfer(load, tries, timeout)
        else:  # for just about everything else
            return self._crypted_transfer(load, tries, timeout)


class TCPPubChannel(salt.transport.mixins.auth.AESPubClientMixin, salt.transport.client.PubChannel):
    def __init__(self,
                 opts,
                 **kwargs):
        self.opts = opts

        self.auth = salt.crypt.SAuth(self.opts)
        self.serial = salt.payload.Serial(self.opts)

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # connect
        self._socket.connect(self.master_pub)
        self._socket.send('connect')

    @property
    def socket(self):
        return self._socket

    @property
    def poll_key(self):
        return self._socket.fileno()

    @property
    def master_pub(self):
        '''
        Return the master publish port
        '''
        return (self.opts['master_ip'],
                int(self.auth.creds['publish_port']))

    def recv(self, timeout=0):
        '''
        Get a pub job, with an optional timeout
            0: nonblocking
            None: forever
        '''
        socks = select.select([self.socket], [], [], timeout)
        if self.socket in socks[0]:
            try:
                data = socket_frame_recv(self.socket)
            except socket.error as e:
                raise salt.exceptions.SaltClientError(e)
            return self._decode_payload(self.serial.loads(data))
        else:
            return None


class TCPReqServerChannel(salt.transport.mixins.auth.AESReqServerMixin, salt.transport.server.ReqServerChannel):
    # TODO: opts!
    backlog = 5

    @property
    def socket(self):
        return self._socket

    def pre_fork(self, process_manager):
        '''
        Pre-fork we need to create the zmq router device
        '''
        salt.transport.mixins.auth.AESReqServerMixin.pre_fork(self, process_manager)
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind((self.opts['interface'], int(self.opts['ret_port'])))

    def post_fork(self, payload_handler, io_loop):
        '''
        After forking we need to create all of the local sockets to listen to the
        router

        payload_handler: function to call with your payloads
        '''
        self.payload_handler = payload_handler
        self.io_loop = io_loop
        self.req_server = SaltMessageServer(self.handle_message, io_loop=io_loop)
        self.req_server.add_socket(self.socket)
        self.socket.listen(self.backlog)

        self.serial = salt.payload.Serial(self.opts)
        salt.transport.mixins.auth.AESReqServerMixin.post_fork(self)

    @tornado.gen.coroutine
    def handle_message(self, stream, header, payload):
        '''
        Handle incoming messages from underylying tcp streams
        '''
        try:
            payload = self._decode_payload(payload)
        except Exception:
            stream.write(frame_msg(self.serial.dumps('bad load'), header=header))
            raise tornado.gen.Return()

        # intercept the "_auth" commands, since the main daemon shouldn't know
        # anything about our key auth
        if payload['enc'] == 'clear' and payload['load']['cmd'] == '_auth':
            yield stream.write(frame_msg(self.serial.dumps(self._auth(payload['load'])), header=header))
            raise tornado.gen.Return()


        # TODO: handle exceptions
        try:
            ret, req_opts = self.payload_handler(payload)  # TODO: check if a future
        except Exception as e:
            log.error('Some exception handling a payload from minion', exc_info=True)
            stream.close()
            raise tornado.gen.Return()

        req_fun = req_opts.get('fun', 'send')
        if req_fun == 'send_clear':
            ret['enc'] = 'clear'
            stream.write(frame_msg(self.serial.dumps(ret), header=header))
        elif req_fun == 'send':
            stream.write(frame_msg(self.serial.dumps(self.crypticle.dumps(ret)), header=header))
        elif req_fun == 'send_private':
            stream.write(frame_msg(self.serial.dumps(self._encrypt_private(ret,
                                                                           req_opts['key'],
                                                                           req_opts['tgt'],
                                                                           )),header=header))
        else:
            log.error('Unknown req_fun {0}'.format(req_fun))
            stream.close()


class SaltMessageServer(tornado.tcpserver.TCPServer):
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
        print ('req client connected {0}'.format(address))
        log.trace('Req client {0} connected'.format(address))
        self.clients.append((stream, address))
        try:
            while True:
                header_len = yield stream.read_until(' ')
                header_raw = yield stream.read_bytes(int(header_len.strip()))
                header = msgpack.loads(header_raw)
                body_raw = yield stream.read_bytes(int(header['msgLen']))
                body = msgpack.loads(body_raw)
                self.message_handler(stream, header, body)

        except tornado.iostream.StreamClosedError:
            print ('req client disconnected {0}'.format(address))
            self.clients.remove((stream, address))
        except Exception as e:
            print ('other master-side exception??', e, e.__module__, e.extra)
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


# TODO: test and use, cleanup send/recv queue stuff
class SaltMessageClient(object):
    '''
    Low-level message sending client
    '''
    def __init__(self, host, port, io_loop):
        self.host = host
        self.port = port
        self.io_loop = io_loop

        self._tcp_client = tornado.tcpclient.TCPClient(io_loop=self.io_loop)

        self._mid = 1

        self.send_queue = []  # queue of messages to be sent

        self.future_map = {}  # mapping of request_id -> Future
        self._stream = None

    @tornado.gen.coroutine
    def _stream_return(self):
        while True:
            try:
                header_len = yield self._stream.read_until(' ')
                header_raw = yield stream.read_bytes(int(header_len.strip()))
                header = msgpack.loads(header_raw)
                body = yield self._stream.read_bytes(int(header['msgLen']))
                message_id = header['mid']

                if message_id in self.future_map:
                    self.future_map[message_id].set_result(body)
                    del self.future_map[message_id]
                else:
                    log.error('Got response for message_id {0} that we are not tracking'.format(message_id))
            # TODO: if we know what message_id it is, we can save the stream
            except Exception as e:
                log.error('Exception parsing response', exc_info=True)
                raise
                for future in self.future_map.itervalues():
                    future.set_exception(e)
                self.future_map = {}
            raise tornado.gen.Return()

    @tornado.gen.coroutine
    def _stream_send(self):
        if not self._stream:
            self._stream = yield self._tcp_client.connect(self.host, self.port)
        while True:
            try:
                item = self.send_queue.pop(0)
                yield self._stream.write(item)
                self.io_loop.add_callback(self._stream_return)
                raise tornado.gen.Return()
            except IndexError:
                yield tornado.gen.sleep(1)  # TODO: remove...

    # TODO: wrap? or use UUID?
    def _message_id(self):
        ret = self._mid
        self._mid += 1
        return ret

    def send(self, msg, callback=None):
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
        self.future_map[message_id] = future

        self.send_queue.append(frame_msg(msg, header=header))
        self.io_loop.add_callback(self._stream_send)

        return future


class PubServer(tornado.tcpserver.TCPServer):
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
        package = package[0]  # ZMQ ism :/
        payload = frame_msg(salt.payload.unpackage(package)['payload'])
        to_remove = []
        for item in self.clients:
            client, address = item
            try:
                yield client.write(payload)  # TODO: don't wait
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
        pub_uri = 'tcp://{interface}:{publish_port}'.format(**self.opts)
        # Prepare minion pull socket
        pull_sock = context.socket(zmq.PULL)
        pull_uri = 'ipc://{0}'.format(
            os.path.join(self.opts['sock_dir'], 'publish_pull.ipc')
        )
        salt.utils.zeromq.check_ipc_path_max_len(pull_uri)

        # Start the minion command publisher
        log.info('Starting the Salt Publisher on {0}'.format(pub_uri))

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
        pub_server = PubServer()
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
            os.path.join(self.opts['sock_dir'], 'publish_pull.ipc')
            )
        pub_sock.connect(pull_uri)
        int_payload = {'payload': self.serial.dumps(payload)}

        # add some targeting stuff for lists only (for now)
        if load['tgt_type'] == 'list':
            int_payload['topic_lst'] = load['tgt']

        pub_sock.send(self.serial.dumps(int_payload))
