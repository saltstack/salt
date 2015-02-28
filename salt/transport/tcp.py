'''
Zeromq transport classes
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

import zmq

log = logging.getLogger(__name__)


class TCPReqChannel(salt.transport.client.ReqChannel):
    '''
    Encapsulate sending routines to tcp.

    TODO:
        - add crypto-- clear for starters
        - add timeouts
        - keepalive?
    '''
    recv_size = 16384
    def __init__(self, opts, **kwargs):
        self.opts = dict(opts)

        self.serial = salt.payload.Serial(self.opts)

    @property
    def master_addr(self):
        # TODO: opts...
        return ('127.0.0.1',
                4506)

    def crypted_transfer_decode_dictentry(self, load, dictkey=None, tries=3, timeout=60):
        return self.send(load, tries=tries, timeout=timeout)

    def send(self, load, tries=3, timeout=60):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # connect
        s.connect(self.master_addr)
        # send msg
        s.send(self.serial.dumps(load))
        # wait for response
        data = s.recv(self.recv_size)
        s.close()
        print self.master_addr, len(self.serial.dumps(load))
        return self.serial.loads(data)


class TCPPubChannel(salt.transport.client.PubChannel):
    recv_size = 16384

    def __init__(self,
                 opts,
                 **kwargs):
        self.opts = opts

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

    def _verify_master_signature(self, payload):
        if payload.get('sig') and self.opts.get('sign_pub_messages'):
            # Verify that the signature is valid
            master_pubkey_path = os.path.join(self.opts['pki_dir'], 'minion_master.pub')
            if not salt.crypt.verify_signature(master_pubkey_path, load, payload.get('sig')):
                raise salt.crypt.AuthenticationError('Message signature failed to validate.')

    def recv(self, timeout=0):
        '''
        Get a pub job, with an optional timeout (0==forever)
        '''
        if timeout == 0:
            timeout = None
        socks = select.select([self.socket], [], [], timeout)
        if self.socket in socks[0]:
            data = self.socket.recv(self.recv_size)
            return self.serial.loads(data)
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
            data = self.socket.recv(self.recv_size)
            return self.serial.loads(data)
        else:
            return None


class TCPReqServerChannel(salt.transport.server.ReqServerChannel):
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
        # other things needed for _auth
        # Create the event manager
        self.event = salt.utils.event.get_master_event(self.opts, self.opts['sock_dir'])
        self.auto_key = salt.daemons.masterapi.AutoKey(self.opts)

        self.master_key = salt.crypt.MasterKeys(self.opts)

    def payload_wrap(self, load):
        return {'enc': 'aes',
                'load': load}

    def recv(self, timeout=0):
        '''
        Get a req job, with an optional timeout (0==forever)
        '''
        if timeout == 0:
            timeout = None
        log.error('recv')
        socks = select.select([self.socket], [], [], timeout)
        if self.socket in socks[0]:
            self.client, address = self.socket.accept()
            print (address)
            data = self.client.recv(self.size)
            return self.payload_wrap(self.serial.loads(data))
        else:
            return None

    def recv_noblock(self):
        '''
        Get a req job in a non-blocking manner.
        Return load or None
        '''
        log.error('recv_noblock')
        socks = select.select([self.socket], [], [], 0)
        if self.socket in socks[0]:
            self.client, address = self.socket.accept()
            data = self.client.recv(self.size)
            return self.payload_wrap(self.serial.loads(data))
        else:
            return None

    def _send(self, payload):
        '''
        Helper function to serialize and send payload
        '''
        self.client.send(self.serial.dumps(payload))
        self.client.close()
        self.client = None

    def send_clear(self, payload):
        '''
        Send a response to a recv()'d payload
        '''
        self._send(payload)

    def send(self, payload):
        '''
        Send a response to a recv()'d payload
        '''
        self._send(payload)

    def send_private(self, payload, dictkey, target):
        '''
        Send a response to a recv()'d payload encrypted privately for target
        '''
        self._send(payload)


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
                        payload = salt.payload.unpackage(package)['payload']
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


        # TODO: re-enable
        #crypticle = salt.crypt.Crypticle(self.opts, salt.master.SMaster.secrets['aes']['secret'].value)
        #payload['load'] = crypticle.dumps(load)
        payload['load'] = load
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
