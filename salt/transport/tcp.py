'''
TCP transport classes



Wire protocol:

    #### msg
    # == len of msg

'''

import socket
import select



import os
import threading
import errno
import hashlib
import ctypes
import multiprocessing

from M2Crypto import RSA

from random import randint

# Import Salt Libs
import salt.payload
import salt.auth
import salt.crypt
import salt.utils
import salt.utils.verify
import salt.utils.event
import salt.payload
import logging
from collections import defaultdict


import salt.transport.client
import salt.transport.server
import salt.transport.mixins.auth

# for IPC (for now)
import zmq

log = logging.getLogger(__name__)


# TODO: put in some lib?
def frame_msg(msg):
    return '{0} {1}'.format(len(msg), msg)

def unframe_msg(frame):
    '''
    Return a tuple of (remaining_bits, msg)
    '''
    msg_len, msg = frame.split(' ', 1)

    return (int(msg_len) - len(msg), msg)

def socket_frame_recv(socket, recv_size=4096):
    '''
    Retrieve a frame from socket
    '''
    ret_frame = socket.recv(recv_size)
    remain, ret_msg = unframe_msg(ret_frame)
    while remain > 0:
        data = socket.recv(recv_size)
        ret_msg += data
        remain -= len(data)
    return ret_msg

class TCPReqChannel(salt.transport.client.ReqChannel):
    '''
    Encapsulate sending routines to tcp.

    TODO:
        - add timeouts
        - keepalive?
    '''
    recv_size = 16384
    def __init__(self, opts, **kwargs):
        self.opts = dict(opts)

        self.serial = salt.payload.Serial(self.opts)

        # crypt defaults to 'aes'
        self.crypt = kwargs.get('crypt', 'aes')

        if self.crypt != 'clear':
            # we don't need to worry about auth as a kwarg, since its a singleton
            self.auth = salt.crypt.SAuth(self.opts)

    @property
    def master_addr(self):
        # TODO: opts...
        return ('127.0.0.1',
                4506)

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
    recv_size = 16384

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
                4505)

    def recv(self, timeout=0):
        '''
        Get a pub job, with an optional timeout (0==forever)
        '''
        if timeout == 0:
            timeout = None
        socks = select.select([self.socket], [], [], timeout)
        if self.socket in socks[0]:
            data = socket_frame_recv(self.socket)
            return self._decode_payload(self.serial.loads(data))
        else:
            return None

    def recv_noblock(self):
        '''
        Get a pub job in a non-blocking manner.
        Return pub or None
        '''
        print ('noblock get??')
        socks = select.select([self.socket], [], [], 0)  #nonblocking select
        if self.socket in socks[0]:
            data = socket_frame_recv(self.socket)
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

    def recv(self, timeout=0):
        '''
        Get a req job, with an optional timeout (0==forever)
        '''
        if timeout == 0:
            timeout = None
        socks = select.select([self.socket], [], [], timeout)
        if self.socket in socks[0]:
            self.client, address = self.socket.accept()
            print (address)

            payload = socket_frame_recv(self.client)
            payload = self.serial.loads(payload)
            payload = self._decode_payload(payload)
            # if timeout was 0 and we got a None, we intercepted the job,
            # so just queue up another recv()
            if payload is None and timeout == None:
                return self.recv(timeout=timeout)
            return payload
        else:
            return None

    def recv_noblock(self):
        '''
        Get a req job in a non-blocking manner.
        Return load or None
        '''
        socks = select.select([self.socket], [], [], 0)
        if self.socket in socks[0]:
            self.client, address = self.socket.accept()
            package = socket_frame_recv(self.client)
            payload = self.serial.loads(package)
            payload = self._decode_payload(payload)
            return payload
        else:
            return None

    def _send(self, payload):
        '''
        Helper function to serialize and send payload
        '''
        self.client.send(frame_msg(self.serial.dumps(payload)))
        self.client.close()
        self.client = None


class TCPPubServerChannel(salt.transport.server.PubServerChannel):
    # TODO: opts!
    backlog = 5
    size = 16384
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
                        print ('Added minion', address, client, os.getpid())
                        clients.append(client)
                    # is it a publish job?
                    elif pull_sock in socks and socks[pull_sock] == zmq.POLLIN:
                        package = pull_sock.recv()
                        payload = frame_msg(salt.payload.unpackage(package)['payload'])
                        print ('clients', clients)
                        for s in clients:
                            s.send(payload)
                        print ('sends done')
                except zmq.ZMQError as exc:
                    if exc.errno == errno.EINTR:
                        continue
                    raise exc

        except KeyboardInterrupt:
            if pub_sock.closed is False:
                pub_sock.setsockopt(zmq.LINGER, 1)
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









# EOF
