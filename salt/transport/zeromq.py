'''
Zeromq transport classes
'''

import os
import threading
import errno
import hashlib
import ctypes
import multiprocessing

from random import randint

# Import Salt Libs
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


class ZeroMQReqChannel(salt.transport.client.ReqChannel):
    '''
    Encapsulate sending routines to ZeroMQ.

    ZMQ Channels default to 'crypt=aes'
    '''
    # the sreq is the zmq connection, since those are relatively expensive to
    # set up, we are going to reuse them as much as possible.
    sreq_cache = defaultdict(dict)

    @property
    def sreq_key(self):
        '''
        Return a tuple which uniquely defines this channel (for caching)
        '''
        return (self.master_uri,                  # which master you want to talk to
                os.getpid(),                      # per process
                threading.current_thread().name,  # per per-thread
                )

    @property
    def sreq(self):
        # When using threading, like on Windows, don't cache.
        # The following block prevents thread leaks.
        if not self.opts.get('multiprocessing'):
            return salt.payload.SREQ(self.master_uri)

        key = self.sreq_key

        if not self.opts['cache_sreqs']:
            return salt.payload.SREQ(self.master_uri)
        else:
            if key not in ZeroMQReqChannel.sreq_cache:
                master_type = self.opts.get('master_type', None)
                if master_type == 'failover':
                    # remove all cached sreqs to the old master to prevent
                    # zeromq from reconnecting to old masters automagically
                    for check_key in self.sreq_cache.keys():
                        if self.opts['master_uri'] != check_key[0]:
                            del self.sreq_cache[check_key]
                            log.debug('Removed obsolete sreq-object from '
                                      'sreq_cache for master {0}'.format(check_key[0]))

                ZeroMQReqChannel.sreq_cache[key] = salt.payload.SREQ(self.master_uri)

            return ZeroMQReqChannel.sreq_cache[key]

    def __init__(self, opts, **kwargs):
        self.opts = dict(opts)
        self.ttype = 'zeromq'

        # crypt defaults to 'aes'
        self.crypt = kwargs.get('crypt', 'aes')

        if 'master_uri' in kwargs:
            self.opts['master_uri'] = kwargs['master_uri']

        if self.crypt != 'clear':
            # we don't need to worry about auth as a kwarg, since its a singleton
            self.auth = salt.crypt.SAuth(self.opts)

    @property
    def master_uri(self):
        return self.opts['master_uri']

    def crypted_transfer_decode_dictentry(self, load, dictkey=None, tries=3, timeout=60):
        ret = self.sreq.send('aes', self.auth.crypticle.dumps(load), tries, timeout)
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
            data = self.sreq.send(
                self.crypt,
                self.auth.crypticle.dumps(load),
                tries,
                timeout)
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
        return self.sreq.send(self.crypt, load, tries, timeout)

    def send(self, load, tries=3, timeout=60):
        if self.crypt == 'clear':  # for sign-in requests
            return self._uncrypted_transfer(load, tries, timeout)
        else:  # for just about everything else
            return self._crypted_transfer(load, tries, timeout)


class AsyncZeroMQPubChannel(salt.transport.mixins.auth.AESPubClientMixin, salt.transport.client.PubChannel):
    def __init__(self,
                 opts,
                 **kwargs):
        self.opts = opts
        self.ttype = 'zeromq'

        if 'io_loop' in kwargs:
            self.io_loop = kwargs['io_loop']
        else:
            self.io_loop = tornado.ioloop.IOLoop()

        self.hexid = hashlib.sha1(self.opts['id']).hexdigest()

        self.auth = salt.crypt.SAuth(self.opts)

        self.serial = salt.payload.Serial(self.opts)

        self.context = zmq.Context()
        self._socket = self.context.socket(zmq.SUB)

        if self.opts['zmq_filtering']:
            # TODO: constants file for "broadcast"
            self._socket.setsockopt(zmq.SUBSCRIBE, 'broadcast')
            self._socket.setsockopt(zmq.SUBSCRIBE, self.hexid)
        else:
            self._socket.setsockopt(zmq.SUBSCRIBE, '')

        self._socket.setsockopt(zmq.SUBSCRIBE, '')
        self._socket.setsockopt(zmq.IDENTITY, self.opts['id'])

        # TODO: cleanup all the socket opts stuff
        if hasattr(zmq, 'TCP_KEEPALIVE'):
            self._socket.setsockopt(
                zmq.TCP_KEEPALIVE, self.opts['tcp_keepalive']
            )
            self._socket.setsockopt(
                zmq.TCP_KEEPALIVE_IDLE, self.opts['tcp_keepalive_idle']
            )
            self._socket.setsockopt(
                zmq.TCP_KEEPALIVE_CNT, self.opts['tcp_keepalive_cnt']
            )
            self._socket.setsockopt(
                zmq.TCP_KEEPALIVE_INTVL, self.opts['tcp_keepalive_intvl']
            )

        recon_delay = self.opts['recon_default']

        if self.opts['recon_randomize']:
            recon_delay = randint(self.opts['recon_default'],
                                  self.opts['recon_default'] + self.opts['recon_max']
                          )

            log.debug("Generated random reconnect delay between '{0}ms' and '{1}ms' ({2})".format(
                self.opts['recon_default'],
                self.opts['recon_default'] + self.opts['recon_max'],
                recon_delay)
            )

        log.debug("Setting zmq_reconnect_ivl to '{0}ms'".format(recon_delay))
        self._socket.setsockopt(zmq.RECONNECT_IVL, recon_delay)

        if hasattr(zmq, 'RECONNECT_IVL_MAX'):
            log.debug("Setting zmq_reconnect_ivl_max to '{0}ms'".format(
                self.opts['recon_default'] + self.opts['recon_max'])
            )

            self._socket.setsockopt(
                zmq.RECONNECT_IVL_MAX, self.opts['recon_max']
            )

        if self.opts['ipv6'] is True and hasattr(zmq, 'IPV4ONLY'):
            # IPv6 sockets work for both IPv6 and IPv4 addresses
            self._socket.setsockopt(zmq.IPV4ONLY, 0)

        self.publish_port = self.auth.creds['publish_port']

    # TODO: this is the time to see if we are connected, maybe use the req channel to guess?
    @tornado.gen.coroutine
    def connect(self):
        self._socket.connect(self.master_pub)

    @property
    def master_pub(self):
        '''
        Return the master publish port
        '''
        return 'tcp://{ip}:{port}'.format(ip=self.opts['master_ip'],
                                          port=self.publish_port)

    def _decode_messages(self, messages):
        '''
        Take the zmq messages, decrypt/decode them into a payload
        '''
        messages_len = len(messages)
        # if it was one message, then its old style
        if messages_len == 1:
            payload = self.serial.loads(messages[0])
        # 2 includes a header which says who should do it
        elif messages_len == 2:
            payload = self.serial.loads(messages[1])
        else:
            raise Exception(('Invalid number of messages ({0}) in zeromq pub'
                             'message from master').format(len(messages_len)))
        return self._decode_payload(payload)

    @property
    def stream(self):
        if not hasattr(self, '_stream'):
            self._stream = zmq.eventloop.zmqstream.ZMQStream(self._socket, io_loop=self.io_loop)
        return self._stream

    def on_recv(self, callback):
        '''
        Register a callback for recieved messages (that we didn't initiate)
        '''
        if callback is None:
            return self.stream.on_recv(None)

        def wrap_callback(messages):
            payload = self._decode_messages(messages)
            callback(payload)
        return self.stream.on_recv(wrap_callback)


class ZeroMQReqServerChannel(salt.transport.mixins.auth.AESReqServerMixin, salt.transport.server.ReqServerChannel):
    def zmq_device(self):
        '''
        Multiprocessing target for the zmq queue device
        '''
        salt.utils.appendproctitle('MWorkerQueue')
        self.context = zmq.Context(self.opts['worker_threads'])
        # Prepare the zeromq sockets
        self.uri = 'tcp://{interface}:{ret_port}'.format(**self.opts)
        self.clients = self.context.socket(zmq.ROUTER)
        if self.opts['ipv6'] is True and hasattr(zmq, 'IPV4ONLY'):
            # IPv6 sockets work for both IPv6 and IPv4 addresses
            self.clients.setsockopt(zmq.IPV4ONLY, 0)

        self.workers = self.context.socket(zmq.DEALER)
        self.w_uri = 'ipc://{0}'.format(
            os.path.join(self.opts['sock_dir'], 'workers.ipc')
        )

        log.info('Setting up the master communication server')
        self.clients.bind(self.uri)

        self.workers.bind(self.w_uri)

        while True:
            try:
                zmq.device(zmq.QUEUE, self.clients, self.workers)
            except zmq.ZMQError as exc:
                if exc.errno == errno.EINTR:
                    continue
                raise exc

    def close(self):
        if hasattr(self, 'clients'):
            self.clients.close()
        self.stream.close()

    def pre_fork(self, process_manager):
        '''
        Pre-fork we need to create the zmq router device
        '''
        salt.transport.mixins.auth.AESReqServerMixin.pre_fork(self, process_manager)
        process_manager.add_process(self.zmq_device)

    def post_fork(self, payload_handler, io_loop):
        '''
        After forking we need to create all of the local sockets to listen to the
        router
        '''
        self.payload_handler = payload_handler
        self.io_loop = io_loop

        self.context = zmq.Context(1)
        self._socket = self.context.socket(zmq.REP)
        self.w_uri = 'ipc://{0}'.format(
            os.path.join(self.opts['sock_dir'], 'workers.ipc')
            )
        log.info('Worker binding to socket {0}'.format(self.w_uri))
        self._socket.connect(self.w_uri)

        salt.transport.mixins.auth.AESReqServerMixin.post_fork(self)

        self.stream = zmq.eventloop.zmqstream.ZMQStream(self._socket, io_loop=self.io_loop)
        self.stream.on_recv_stream(self.handle_message)

    @tornado.gen.coroutine
    def handle_message(self, stream, payload):
        '''
        Handle incoming messages from underylying tcp streams
        '''
        payload = self.serial.loads(payload[0])
        try:
            payload = self._decode_payload(payload)
        except Exception as e:
            stream.send(self.serial.dumps('bad load'))
            raise tornado.gen.Return()

        # TODO helper functions to normalize payload?
        if not isinstance(payload, dict) or not isinstance(payload.get('load'), dict):
            stream.send(self.serial.dumps('payload and load must be a dict'))
            raise tornado.gen.Return()

        # intercept the "_auth" commands, since the main daemon shouldn't know
        # anything about our key auth
        if payload['enc'] == 'clear' and payload.get('load', {}).get('cmd') == '_auth':
            stream.send(self.serial.dumps(self._auth(payload['load'])))
            raise tornado.gen.Return()

        # TODO: handle exceptions
        try:
            ret, req_opts = self.payload_handler(payload)  # TODO: check if a future
        except Exception as e:
            log.error('Some exception handling a payload from minion', exc_info=True)
            stream.send('bad low')
            raise tornado.gen.Return()

        req_fun = req_opts.get('fun', 'send')
        if req_fun == 'send_clear':
            stream.send(self.serial.dumps(ret))
        elif req_fun == 'send':
            stream.send(self.serial.dumps(self.crypticle.dumps(ret)))
        elif req_fun == 'send_private':
            stream.send(self.serial.dumps(self._encrypt_private(ret,
                                                                req_opts['key'],
                                                                req_opts['tgt'],
                                                                )))
        else:
            log.error('Unknown req_fun {0}'.format(req_fun))
            stream.send('err')
        raise tornado.gen.Return()


class ZeroMQPubServerChannel(salt.transport.server.PubServerChannel):
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
        # Prepare minion publish socket
        pub_sock = context.socket(zmq.PUB)
        # if 2.1 >= zmq < 3.0, we only have one HWM setting
        try:
            pub_sock.setsockopt(zmq.HWM, self.opts.get('pub_hwm', 1000))
        # in zmq >= 3.0, there are separate send and receive HWM settings
        except AttributeError:
            pub_sock.setsockopt(zmq.SNDHWM, self.opts.get('pub_hwm', 1000))
            pub_sock.setsockopt(zmq.RCVHWM, self.opts.get('pub_hwm', 1000))
        if self.opts['ipv6'] is True and hasattr(zmq, 'IPV4ONLY'):
            # IPv6 sockets work for both IPv6 and IPv4 addresses
            pub_sock.setsockopt(zmq.IPV4ONLY, 0)
        pub_uri = 'tcp://{interface}:{publish_port}'.format(**self.opts)
        # Prepare minion pull socket
        pull_sock = context.socket(zmq.PULL)
        pull_uri = 'ipc://{0}'.format(
            os.path.join(self.opts['sock_dir'], 'publish_pull.ipc')
        )
        salt.utils.zeromq.check_ipc_path_max_len(pull_uri)

        # Start the minion command publisher
        log.info('Starting the Salt Publisher on {0}'.format(pub_uri))
        pub_sock.bind(pub_uri)

        # Securely create socket
        log.info('Starting the Salt Puller on {0}'.format(pull_uri))
        old_umask = os.umask(0o177)
        try:
            pull_sock.bind(pull_uri)
        finally:
            os.umask(old_umask)

        try:
            while True:
                # Catch and handle EINTR from when this process is sent
                # SIGUSR1 gracefully so we don't choke and die horribly
                try:
                    package = pull_sock.recv()
                    unpacked_package = salt.payload.unpackage(package)
                    payload = unpacked_package['payload']
                    if self.opts['zmq_filtering']:
                        # if you have a specific topic list, use that
                        if 'topic_lst' in unpacked_package:
                            for topic in unpacked_package['topic_lst']:
                                # zmq filters are substring match, hash the topic
                                # to avoid collisions
                                htopic = hashlib.sha1(topic).hexdigest()
                                pub_sock.send(htopic, flags=zmq.SNDMORE)
                                pub_sock.send(payload)
                                # otherwise its a broadcast
                        else:
                            # TODO: constants file for "broadcast"
                            pub_sock.send('broadcast', flags=zmq.SNDMORE)
                            pub_sock.send(payload)
                    else:
                        pub_sock.send(payload)
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
