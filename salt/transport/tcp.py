'''
TCP transport classes



Wire protocol: "len(msg) msg"

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

log = logging.getLogger(__name__)


# TODO: put in some lib?
def frame_msg(msg):
    return '{0} {1}'.format(len(msg), msg)


def socket_frame_recv(s, recv_size=4096):
    '''
    Retrieve a frame from socket
    '''
    recv_buf = ''
    while ' ' not in recv_buf:
        data = s.recv(recv_size)
        if data == '':
            raise socket.error('Empty response!')
        else:
            recv_buf += data
    # once we have a space, we know how long the rest is
    msg_len, msg = recv_buf.split(' ', 1)
    msg_len = int(msg_len)
    while len(msg) != msg_len:
        data = s.recv(recv_size)
        if data == '':
           raise socket.error('msg stopped, we are missing some data!')
        else:
            msg += data
    return msg


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
    size = 16384

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

    def post_fork(self):
        '''
        After forking we need to create all of the local sockets to listen to the
        router
        '''
        self.socket.listen(self.backlog)
        self.client = None  # The client we are currently talking with


        self.serial = salt.payload.Serial(self.opts)
        salt.transport.mixins.auth.AESReqServerMixin.post_fork(self)

        self.epoll = select.epoll()
        self.epoll.register(self.socket.fileno(), select.EPOLLIN)
        # map of fd -> (socket, address)
        self.sock_map = {}

    def recv(self, timeout=0.001):
        '''
        Get a req job, with an optional timeout
            0: nonblocking
            None: forever

        This is the main event loop of the TCP server. Since we aren't using an
        event driven mechanism-- we'll allow the caller to determine when we should
        listen next-- by controlling the timeout with which we are called
        '''
        if timeout:
            timeout = timeout * 1000  # epoll takes milliseconds
            socks = self.epoll.poll(timeout)
        else:
            socks = self.epoll.poll()
        for fd, event in socks:
            # do we have a new client?
            if fd == self.socket.fileno():
                client, address = self.socket.accept()
                self.epoll.register(client.fileno(), select.EPOLLIN)
                self.sock_map[client.fileno()] = (client, address)
                log.trace('New client at {0} connected to reqserver'.format(address))
            if fd in self.sock_map:
                client, address = self.sock_map[fd]
                try:
                    payload = socket_frame_recv(client)
                # if the client bombed out on us, we just soldier on
                except socket.error as e:
                    log.trace('Socket error {0} communicating with {1}, closing connection'.format(e, address))
                    client.close()
                    self.epoll.unregister(fd)
                    del self.sock_map[fd]
                    continue
                self.client = client
                payload = self.serial.loads(payload)
                payload = self._decode_payload(payload)
                # if timeout was 0 and we got a None, we intercepted the job,
                # so just queue up another recv()
                if payload is None and timeout == None:
                    return self.recv(timeout=timeout)
                return payload
        if timeout is None:
            return self.recv(timeout=timeout)
        return None

    def _send(self, payload):
        '''
        Helper function to serialize and send payload
        '''
        try:
            self.client.send(frame_msg(self.serial.dumps(payload)))
        # if there was an error, close the socket out
        except socket.error as e:
            self.client.close()
            epoll.unregister(self.client.fileno())
            del self.sock_map[self.client.fileno()]
            raise salt.exceptions.SaltClientError(e)
        # always reset self.client
        finally:
            self.client = None


class TCPPubServerChannel(salt.transport.server.PubServerChannel):
    # TODO: opts!
    backlog = 5
    def __init__(self, opts):
        self.opts = opts
        self.serial = salt.payload.Serial(self.opts)  # TODO: in init?

    def _publish_daemon(self):
        '''
        Bind to the interface specified in the configuration file
        '''
        salt.utils.appendproctitle(self.__class__.__name__)

        pub_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        pub_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        pub_sock.bind((self.opts['interface'], int(self.opts['publish_port'])))
        pub_sock.listen(self.backlog)
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

        poller = zmq.Poller()
        poller.register(pub_sock, zmq.POLLIN)
        poller.register(pull_sock, zmq.POLLIN)
        clients = []

        try:
            while True:
                try:
                    socks = dict(poller.poll())
                    # is it a new client?
                    if pub_sock.fileno() in socks and socks[pub_sock.fileno()] == zmq.POLLIN:
                        client, address = pub_sock.accept()
                        clients.append((client, address))
                    # TODO: non-blocking sends
                    # is it a publish job?
                    elif pull_sock in socks and socks[pull_sock] == zmq.POLLIN:
                        package = pull_sock.recv()
                        payload = frame_msg(salt.payload.unpackage(package)['payload'])
                        to_remove = []
                        for item in clients:
                            client, address = item
                            try:
                                client.send(payload)
                            except socket.error as e:
                                to_remove.append(item)
                        for item in to_remove:
                            client, address = item
                            log.debug('Client at {0} has disconnected from publisher'.format(address))
                            client.close()
                            clients.remove(item)

                except zmq.ZMQError as exc:
                    if exc.errno == errno.EINTR:
                        continue
                    raise exc

        except KeyboardInterrupt:
            # TODO: try/except?
            for client, address in clients:
                client.shutdown(socket.SHUT_RDWR)
                client.close()
            pub_sock.shutdown(socket.SHUT_RDWR)
            pub_sock.close()
            if pull_sock.closed is False:
                pull_sock.setsockopt(zmq.LINGER, 1)
                pull_sock.close()
            if context.closed is False:
                context.term()

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
