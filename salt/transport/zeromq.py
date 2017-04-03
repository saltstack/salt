# -*- coding: utf-8 -*-
'''
Zeromq transport classes
'''

# Import Python Libs
from __future__ import absolute_import
import os
import sys
import copy
import errno
import signal
import hashlib
import logging
import weakref
from random import randint

# Import Salt Libs
import salt.auth
import salt.crypt
import salt.utils
import salt.utils.verify
import salt.utils.event
import salt.payload
import salt.transport.client
import salt.transport.server
import salt.transport.mixins.auth
from salt.exceptions import SaltReqTimeoutError

import zmq
import zmq.error
import zmq.eventloop.ioloop
# support pyzmq 13.0.x, TODO: remove once we force people to 14.0.x
if not hasattr(zmq.eventloop.ioloop, 'ZMQIOLoop'):
    zmq.eventloop.ioloop.ZMQIOLoop = zmq.eventloop.ioloop.IOLoop
import zmq.eventloop.zmqstream
try:
    import zmq.utils.monitor
    HAS_ZMQ_MONITOR = True
except ImportError:
    HAS_ZMQ_MONITOR = False

# Import Tornado Libs
import tornado
import tornado.gen
import tornado.concurrent

# Import third party libs
import salt.ext.six as six
try:
    from Cryptodome.Cipher import PKCS1_OAEP
except ImportError:
    from Crypto.Cipher import PKCS1_OAEP

log = logging.getLogger(__name__)


class AsyncZeroMQReqChannel(salt.transport.client.ReqChannel):
    '''
    Encapsulate sending routines to ZeroMQ.

    ZMQ Channels default to 'crypt=aes'
    '''
    # This class is only a singleton per minion/master pair
    # mapping of io_loop -> {key -> channel}
    instance_map = weakref.WeakKeyDictionary()

    def __new__(cls, opts, **kwargs):
        '''
        Only create one instance of channel per __key()
        '''

        # do we have any mapping for this io_loop
        io_loop = kwargs.get('io_loop')
        if io_loop is None:
            zmq.eventloop.ioloop.install()
            io_loop = tornado.ioloop.IOLoop.current()
        if io_loop not in cls.instance_map:
            cls.instance_map[io_loop] = weakref.WeakValueDictionary()
        loop_instance_map = cls.instance_map[io_loop]

        key = cls.__key(opts, **kwargs)
        if key not in loop_instance_map:
            log.debug('Initializing new AsyncZeroMQReqChannel for {0}'.format(key))
            # we need to make a local variable for this, as we are going to store
            # it in a WeakValueDictionary-- which will remove the item if no one
            # references it-- this forces a reference while we return to the caller
            new_obj = object.__new__(cls)
            new_obj.__singleton_init__(opts, **kwargs)
            loop_instance_map[key] = new_obj
            log.trace('Inserted key into loop_instance_map id {0} for key {1} and process {2}'.format(id(loop_instance_map), key, os.getpid()))
        else:
            log.debug('Re-using AsyncZeroMQReqChannel for {0}'.format(key))
        try:
            return loop_instance_map[key]
        except KeyError:
            # In iterating over the loop_instance_map, we may have triggered
            # garbage collection. Therefore, the key is no longer present in
            # the map. Re-gen and add to map.
            log.debug('Initializing new AsyncZeroMQReqChannel due to GC for {0}'.format(key))
            new_obj = object.__new__(cls)
            new_obj.__singleton_init__(opts, **kwargs)
            loop_instance_map[key] = new_obj
            return loop_instance_map[key]

    def __deepcopy__(self, memo):
        cls = self.__class__
        result = cls.__new__(cls, copy.deepcopy(self.opts, memo))  # pylint: disable=too-many-function-args
        memo[id(self)] = result
        for key in self.__dict__:
            if key in ('_io_loop',):
                continue
                # The _io_loop has a thread Lock which will fail to be deep
                # copied. Skip it because it will just be recreated on the
                # new copy.
            if key == 'message_client':
                # Recreate the message client because it will fail to be deep
                # copied. The reason is the same as the io_loop skip above.
                setattr(result, key,
                        AsyncReqMessageClientPool(result.opts,
                                              self.master_uri,
                                              io_loop=result._io_loop))
                continue
            setattr(result, key, copy.deepcopy(self.__dict__[key], memo))
        return result

    @classmethod
    def __key(cls, opts, **kwargs):
        return (opts['pki_dir'],     # where the keys are stored
                opts['id'],          # minion ID
                kwargs.get('master_uri', opts.get('master_uri')),  # master ID
                kwargs.get('crypt', 'aes'),  # TODO: use the same channel for crypt
                )

    # has to remain empty for singletons, since __init__ will *always* be called
    def __init__(self, opts, **kwargs):
        pass

    # an init for the singleton instance to call
    def __singleton_init__(self, opts, **kwargs):
        self.opts = dict(opts)
        self.ttype = 'zeromq'

        # crypt defaults to 'aes'
        self.crypt = kwargs.get('crypt', 'aes')

        if 'master_uri' in kwargs:
            self.opts['master_uri'] = kwargs['master_uri']

        self._io_loop = kwargs.get('io_loop')
        if self._io_loop is None:
            zmq.eventloop.ioloop.install()
            self._io_loop = tornado.ioloop.IOLoop.current()

        if self.crypt != 'clear':
            # we don't need to worry about auth as a kwarg, since its a singleton
            self.auth = salt.crypt.AsyncAuth(self.opts, io_loop=self._io_loop)
        self.message_client = AsyncReqMessageClientPool(self.opts,
                                                    self.master_uri,
                                                    io_loop=self._io_loop,
                                                    )

    def __del__(self):
        '''
        Since the message_client creates sockets and assigns them to the IOLoop we have to
        specifically destroy them, since we aren't the only ones with references to the FDs
        '''
        if hasattr(self, 'message_client'):
            self.message_client.destroy()
        else:
            log.debug('No message_client attr for AsyncZeroMQReqChannel found. Not destroying sockets.')

    @property
    def master_uri(self):
        return self.opts['master_uri']

    def _package_load(self, load):
        return {
            'enc': self.crypt,
            'load': load,
        }

    @tornado.gen.coroutine
    def crypted_transfer_decode_dictentry(self, load, dictkey=None, tries=3, timeout=60):
        if not self.auth.authenticated:
            # Return controle back to the caller, continue when authentication succeeds
            yield self.auth.authenticate()
        # Return control to the caller. When send() completes, resume by populating ret with the Future.result
        ret = yield self.message_client.send(
            self._package_load(self.auth.crypticle.dumps(load)),
            timeout=timeout,
            tries=tries,
        )
        key = self.auth.get_keys()
        cipher = PKCS1_OAEP.new(key)
        if 'key' not in ret:
            # Reauth in the case our key is deleted on the master side.
            yield self.auth.authenticate()
            ret = yield self.message_client.send(
                self._package_load(self.auth.crypticle.dumps(load)),
                timeout=timeout,
                tries=tries,
            )
        aes = cipher.decrypt(ret['key'])
        pcrypt = salt.crypt.Crypticle(self.opts, aes)
        data = pcrypt.loads(ret[dictkey])
        if six.PY3:
            data = salt.transport.frame.decode_embedded_strs(data)
        raise tornado.gen.Return(data)

    @tornado.gen.coroutine
    def _crypted_transfer(self, load, tries=3, timeout=60, raw=False):
        '''
        Send a load across the wire, with encryption

        In case of authentication errors, try to renegotiate authentication
        and retry the method.

        Indeed, we can fail too early in case of a master restart during a
        minion state execution call

        :param dict load: A load to send across the wire
        :param int tries: The number of times to make before failure
        :param int timeout: The number of seconds on a response before failing
        '''
        @tornado.gen.coroutine
        def _do_transfer():
            # Yield control to the caller. When send() completes, resume by populating data with the Future.result
            data = yield self.message_client.send(
                self._package_load(self.auth.crypticle.dumps(load)),
                timeout=timeout,
                tries=tries,
            )
            # we may not have always data
            # as for example for saltcall ret submission, this is a blind
            # communication, we do not subscribe to return events, we just
            # upload the results to the master
            if data:
                data = self.auth.crypticle.loads(data, raw)
            if six.PY3 and not raw:
                data = salt.transport.frame.decode_embedded_strs(data)
            raise tornado.gen.Return(data)
        if not self.auth.authenticated:
            # Return control back to the caller, resume when authentication succeeds
            yield self.auth.authenticate()
        try:
            # We did not get data back the first time. Retry.
            ret = yield _do_transfer()
        except salt.crypt.AuthenticationError:
            # If auth error, return control back to the caller, continue when authentication succeeds
            yield self.auth.authenticate()
            ret = yield _do_transfer()
        raise tornado.gen.Return(ret)

    @tornado.gen.coroutine
    def _uncrypted_transfer(self, load, tries=3, timeout=60):
        '''
        Send a load across the wire in cleartext

        :param dict load: A load to send across the wire
        :param int tries: The number of times to make before failure
        :param int timeout: The number of seconds on a response before failing
        '''
        ret = yield self.message_client.send(
            self._package_load(load),
            timeout=timeout,
            tries=tries,
        )

        raise tornado.gen.Return(ret)

    @tornado.gen.coroutine
    def send(self, load, tries=3, timeout=60, raw=False):
        '''
        Send a request, return a future which will complete when we send the message
        '''
        if self.crypt == 'clear':
            ret = yield self._uncrypted_transfer(load, tries=tries, timeout=timeout)
        else:
            ret = yield self._crypted_transfer(load, tries=tries, timeout=timeout, raw=raw)
        raise tornado.gen.Return(ret)


class AsyncZeroMQPubChannel(salt.transport.mixins.auth.AESPubClientMixin, salt.transport.client.AsyncPubChannel):
    '''
    A transport channel backed by ZeroMQ for a Salt Publisher to use to
    publish commands to connected minions
    '''
    def __init__(self,
                 opts,
                 **kwargs):
        self.opts = opts
        self.ttype = 'zeromq'

        self.io_loop = kwargs.get('io_loop')
        if self.io_loop is None:
            zmq.eventloop.ioloop.install()
            self.io_loop = tornado.ioloop.IOLoop.current()

        self.hexid = hashlib.sha1(six.b(self.opts['id'])).hexdigest()

        self.auth = salt.crypt.AsyncAuth(self.opts, io_loop=self.io_loop)

        self.serial = salt.payload.Serial(self.opts)

        self.context = zmq.Context()
        self._socket = self.context.socket(zmq.SUB)

        if self.opts['zmq_filtering']:
            # TODO: constants file for "broadcast"
            self._socket.setsockopt(zmq.SUBSCRIBE, b'broadcast')
            self._socket.setsockopt(zmq.SUBSCRIBE, self.hexid)
        else:
            self._socket.setsockopt(zmq.SUBSCRIBE, b'')

        self._socket.setsockopt(zmq.IDENTITY, salt.utils.to_bytes(self.opts['id']))

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

        if (self.opts['ipv6'] is True or ':' in self.opts['master_ip']) and hasattr(zmq, 'IPV4ONLY'):
            # IPv6 sockets work for both IPv6 and IPv4 addresses
            self._socket.setsockopt(zmq.IPV4ONLY, 0)

        if HAS_ZMQ_MONITOR and self.opts['zmq_monitor']:
            self._monitor = ZeroMQSocketMonitor(self._socket)
            self._monitor.start_io_loop(self.io_loop)

    def destroy(self):
        if hasattr(self, '_monitor') and self._monitor is not None:
            self._monitor.stop()
            self._monitor = None
        if hasattr(self, '_stream'):
            # TODO: Optionally call stream.close() on newer pyzmq? Its broken on some
            self._stream.io_loop.remove_handler(self._stream.socket)
            self._stream.socket.close(0)
        elif hasattr(self, '_socket'):
            self._socket.close(0)
        if hasattr(self, 'context') and self.context.closed is False:
            self.context.term()

    def __del__(self):
        self.destroy()

    # TODO: this is the time to see if we are connected, maybe use the req channel to guess?
    @tornado.gen.coroutine
    def connect(self):
        if not self.auth.authenticated:
            yield self.auth.authenticate()
        self.publish_port = self.auth.creds['publish_port']
        self._socket.connect(self.master_pub)

    @property
    def master_pub(self):
        '''
        Return the master publish port
        '''
        return 'tcp://{ip}:{port}'.format(ip=self.opts['master_ip'],
                                          port=self.publish_port)

    @tornado.gen.coroutine
    def _decode_messages(self, messages):
        '''
        Take the zmq messages, decrypt/decode them into a payload

        :param list messages: A list of messages to be decoded
        '''
        messages_len = len(messages)
        # if it was one message, then its old style
        if messages_len == 1:
            payload = self.serial.loads(messages[0])
        # 2 includes a header which says who should do it
        elif messages_len == 2:
            if messages[0] not in ('broadcast', self.hexid):
                log.debug('Publish received for not this minion: {0}'.format(messages[0]))
                raise tornado.gen.Return(None)
            payload = self.serial.loads(messages[1])
        else:
            raise Exception(('Invalid number of messages ({0}) in zeromq pub'
                             'message from master').format(len(messages_len)))
        # Yield control back to the caller. When the payload has been decoded, assign
        # the decoded payload to 'ret' and resume operation
        ret = yield self._decode_payload(payload)
        raise tornado.gen.Return(ret)

    @property
    def stream(self):
        '''
        Return the current zmqstream, creating one if necessary
        '''
        if not hasattr(self, '_stream'):
            self._stream = zmq.eventloop.zmqstream.ZMQStream(self._socket, io_loop=self.io_loop)
        return self._stream

    def on_recv(self, callback):
        '''
        Register a callback for received messages (that we didn't initiate)

        :param func callback: A function which should be called when data is received
        '''
        if callback is None:
            return self.stream.on_recv(None)

        @tornado.gen.coroutine
        def wrap_callback(messages):
            payload = yield self._decode_messages(messages)
            if payload is not None:
                callback(payload)
        return self.stream.on_recv(wrap_callback)


class ZeroMQReqServerChannel(salt.transport.mixins.auth.AESReqServerMixin, salt.transport.server.ReqServerChannel):

    def __init__(self, opts):
        salt.transport.server.ReqServerChannel.__init__(self, opts)
        self._closing = False

    def zmq_device(self):
        '''
        Multiprocessing target for the zmq queue device
        '''
        self.__setup_signals()
        salt.utils.appendproctitle('MWorkerQueue')
        self.context = zmq.Context(self.opts['worker_threads'])
        # Prepare the zeromq sockets
        self.uri = 'tcp://{interface}:{ret_port}'.format(**self.opts)
        self.clients = self.context.socket(zmq.ROUTER)
        if self.opts['ipv6'] is True and hasattr(zmq, 'IPV4ONLY'):
            # IPv6 sockets work for both IPv6 and IPv4 addresses
            self.clients.setsockopt(zmq.IPV4ONLY, 0)
        self.clients.setsockopt(zmq.BACKLOG, self.opts.get('zmq_backlog', 1000))
        if HAS_ZMQ_MONITOR and self.opts['zmq_monitor']:
            # Socket monitor shall be used the only for debug  purposes so using threading doesn't look too bad here
            import threading
            self._monitor = ZeroMQSocketMonitor(self.clients)
            t = threading.Thread(target=self._monitor.start_poll)
            t.start()

        self.workers = self.context.socket(zmq.DEALER)

        if self.opts.get('ipc_mode', '') == 'tcp':
            self.w_uri = 'tcp://127.0.0.1:{0}'.format(
                self.opts.get('tcp_master_workers', 4515)
                )
        else:
            self.w_uri = 'ipc://{0}'.format(
                os.path.join(self.opts['sock_dir'], 'workers.ipc')
                )

        log.info('Setting up the master communication server')
        self.clients.bind(self.uri)

        self.workers.bind(self.w_uri)

        while True:
            if self.clients.closed or self.workers.closed:
                break
            try:
                zmq.device(zmq.QUEUE, self.clients, self.workers)
            except zmq.ZMQError as exc:
                if exc.errno == errno.EINTR:
                    continue
                raise exc
            except (KeyboardInterrupt, SystemExit):
                break

    def close(self):
        '''
        Cleanly shutdown the router socket
        '''
        if self._closing:
            return
        log.info('MWorkerQueue under PID %s is closing', os.getpid())
        self._closing = True
        if hasattr(self, '_monitor') and self._monitor is not None:
            self._monitor.stop()
            self._monitor = None
        if hasattr(self, '_w_monitor') and self._w_monitor is not None:
            self._w_monitor.stop()
            self._w_monitor = None
        if hasattr(self, 'clients') and self.clients.closed is False:
            self.clients.close()
        if hasattr(self, 'workers') and self.workers.closed is False:
            self.workers.close()
        if hasattr(self, 'stream'):
            self.stream.close()
        if hasattr(self, '_socket') and self._socket.closed is False:
            self._socket.close()
        if hasattr(self, 'context') and self.context.closed is False:
            self.context.term()

    def pre_fork(self, process_manager):
        '''
        Pre-fork we need to create the zmq router device

        :param func process_manager: An instance of salt.utils.process.ProcessManager
        '''
        salt.transport.mixins.auth.AESReqServerMixin.pre_fork(self, process_manager)
        process_manager.add_process(self.zmq_device)

    def post_fork(self, payload_handler, io_loop):
        '''
        After forking we need to create all of the local sockets to listen to the
        router

        :param func payload_handler: A function to called to handle incoming payloads as
                                     they are picked up off the wire
        :param IOLoop io_loop: An instance of a Tornado IOLoop, to handle event scheduling
        '''
        self.payload_handler = payload_handler
        self.io_loop = io_loop

        self.context = zmq.Context(1)
        self._socket = self.context.socket(zmq.REP)
        if HAS_ZMQ_MONITOR and self.opts['zmq_monitor']:
            # Socket monitor shall be used the only for debug  purposes so using threading doesn't look too bad here
            import threading
            self._w_monitor = ZeroMQSocketMonitor(self._socket)
            t = threading.Thread(target=self._w_monitor.start_poll)
            t.start()

        if self.opts.get('ipc_mode', '') == 'tcp':
            self.w_uri = 'tcp://127.0.0.1:{0}'.format(
                self.opts.get('tcp_master_workers', 4515)
                )
        else:
            self.w_uri = 'ipc://{0}'.format(
                os.path.join(self.opts['sock_dir'], 'workers.ipc')
                )
        log.info('Worker binding to socket {0}'.format(self.w_uri))
        self._socket.connect(self.w_uri)

        salt.transport.mixins.auth.AESReqServerMixin.post_fork(self, payload_handler, io_loop)

        self.stream = zmq.eventloop.zmqstream.ZMQStream(self._socket, io_loop=self.io_loop)
        self.stream.on_recv_stream(self.handle_message)

    @tornado.gen.coroutine
    def handle_message(self, stream, payload):
        '''
        Handle incoming messages from underylying TCP streams

        :stream ZMQStream stream: A ZeroMQ stream.
        See http://zeromq.github.io/pyzmq/api/generated/zmq.eventloop.zmqstream.html

        :param dict payload: A payload to process
        '''
        try:
            payload = self.serial.loads(payload[0])
            payload = self._decode_payload(payload)
        except Exception as exc:
            exc_type = type(exc).__name__
            if exc_type == 'AuthenticationError':
                log.debug(
                    'Minion failed to auth to master. Since the payload is '
                    'encrypted, it is not known which minion failed to '
                    'authenticate. It is likely that this is a transient '
                    'failure due to the master rotating its public key.'
                )
            else:
                log.error('Bad load from minion: %s: %s', exc_type, exc)
            stream.send(self.serial.dumps('bad load'))
            raise tornado.gen.Return()

        # TODO helper functions to normalize payload?
        if not isinstance(payload, dict) or not isinstance(payload.get('load'), dict):
            log.error('payload and load must be a dict. Payload was: {0} and load was {1}'.format(payload, payload.get('load')))
            stream.send(self.serial.dumps('payload and load must be a dict'))
            raise tornado.gen.Return()

        # intercept the "_auth" commands, since the main daemon shouldn't know
        # anything about our key auth
        if payload['enc'] == 'clear' and payload.get('load', {}).get('cmd') == '_auth':
            stream.send(self.serial.dumps(self._auth(payload['load'])))
            raise tornado.gen.Return()

        # TODO: test
        try:
            # Take the payload_handler function that was registered when we created the channel
            # and call it, returning control to the caller until it completes
            ret, req_opts = yield self.payload_handler(payload)
        except Exception as e:
            # always attempt to return an error to the minion
            stream.send('Some exception handling minion payload')
            log.error('Some exception handling a payload from minion', exc_info=True)
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
            # always attempt to return an error to the minion
            stream.send('Server-side exception handling payload')
        raise tornado.gen.Return()

    def __setup_signals(self):
        signal.signal(signal.SIGINT, self._handle_signals)
        signal.signal(signal.SIGTERM, self._handle_signals)

    def _handle_signals(self, signum, sigframe):
        msg = '{0} received a '.format(self.__class__.__name__)
        if signum == signal.SIGINT:
            msg += 'SIGINT'
        elif signum == signal.SIGTERM:
            msg += 'SIGTERM'
        msg += '. Exiting'
        log.debug(msg)
        self.close()
        sys.exit(salt.defaults.exitcodes.EX_OK)


class ZeroMQPubServerChannel(salt.transport.server.PubServerChannel):
    '''
    Encapsulate synchronous operations for a publisher channel
    '''
    def __init__(self, opts):
        self.opts = opts
        self.serial = salt.payload.Serial(self.opts)  # TODO: in init?
        self.ckminions = salt.utils.minions.CkMinions(self.opts)

    def connect(self):
        return tornado.gen.sleep(5)

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
            # Set the High Water Marks. For more information on HWM, see:
            # http://api.zeromq.org/4-1:zmq-setsockopt
            pub_sock.setsockopt(zmq.SNDHWM, self.opts.get('pub_hwm', 1000))
            pub_sock.setsockopt(zmq.RCVHWM, self.opts.get('pub_hwm', 1000))
        if self.opts['ipv6'] is True and hasattr(zmq, 'IPV4ONLY'):
            # IPv6 sockets work for both IPv6 and IPv4 addresses
            pub_sock.setsockopt(zmq.IPV4ONLY, 0)
        pub_sock.setsockopt(zmq.BACKLOG, self.opts.get('zmq_backlog', 1000))
        pub_uri = 'tcp://{interface}:{publish_port}'.format(**self.opts)
        # Prepare minion pull socket
        pull_sock = context.socket(zmq.PULL)

        if self.opts.get('ipc_mode', '') == 'tcp':
            pull_uri = 'tcp://127.0.0.1:{0}'.format(
                self.opts.get('tcp_master_publish_pull', 4514)
                )
        else:
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
                    if six.PY3:
                        unpacked_package = salt.transport.frame.decode_embedded_strs(unpacked_package)
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
            # Cleanly close the sockets if we're shutting down
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

        :param func process_manager: A ProcessManager, from salt.utils.process.ProcessManager
        '''
        process_manager.add_process(self._publish_daemon)

    def publish(self, load):
        '''
        Publish "load" to minions

        :param dict load: A load to be sent across the wire to minions
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
        if self.opts.get('ipc_mode', '') == 'tcp':
            pull_uri = 'tcp://127.0.0.1:{0}'.format(
                self.opts.get('tcp_master_publish_pull', 4514)
                )
        else:
            pull_uri = 'ipc://{0}'.format(
                os.path.join(self.opts['sock_dir'], 'publish_pull.ipc')
                )
        pub_sock.connect(pull_uri)
        int_payload = {'payload': self.serial.dumps(payload)}

        # add some targeting stuff for lists only (for now)
        if load['tgt_type'] == 'list':
            int_payload['topic_lst'] = load['tgt']

        # If zmq_filtering is enabled, target matching has to happen master side
        match_targets = ["pcre", "glob", "list"]
        if self.opts['zmq_filtering'] and load['tgt_type'] in match_targets:
            # Fetch a list of minions that match
            match_ids = self.ckminions.check_minions(load['tgt'],
                                                     expr_form=load['tgt_type']
                                                     )

            log.debug("Publish Side Match: {0}".format(match_ids))
            # Send list of miions thru so zmq can target them
            int_payload['topic_lst'] = match_ids

        pub_sock.send(self.serial.dumps(int_payload))
        pub_sock.close()
        context.term()


# TODO: unit tests!
class AsyncReqMessageClientPool(object):
    def __init__(self, opts, addr, linger=0, io_loop=None, socket_pool=1):
        self.opts = opts
        self.addr = addr
        self.linger = linger
        self.io_loop = io_loop
        self.socket_pool = socket_pool
        self.message_clients = []

    def destroy(self):
        for message_client in self.message_clients:
            message_client.destroy()
        self.message_clients = []

    def __del__(self):
        self.destroy()

    def send(self, message, timeout=None, tries=3, future=None, callback=None, raw=False):
        if len(self.message_clients) < self.socket_pool:
            message_client = AsyncReqMessageClient(self.opts, self.addr, self.linger, self.io_loop)
            self.message_clients.append(message_client)
            return message_client.send(message, timeout, tries, future, callback, raw)
        else:
            available_clients = sorted(self.message_clients, key=lambda x: len(x.send_queue))
            return available_clients[0].send(message, timeout, tries, future, callback, raw)


# TODO: unit tests!
class AsyncReqMessageClient(object):
    '''
    This class wraps the underylying zeromq REQ socket and gives a future-based
    interface to sending and recieving messages. This works around the primary
    limitation of serialized send/recv on the underlying socket by queueing the
    message sends in this class. In the future if we decide to attempt to multiplex
    we can manage a pool of REQ/REP sockets-- but for now we'll just do them in serial
    '''
    def __init__(self, opts, addr, linger=0, io_loop=None):
        '''
        Create an asynchronous message client

        :param dict opts: The salt opts dictionary
        :param str addr: The interface IP address to bind to
        :param int linger: The number of seconds to linger on a ZMQ socket. See
                           http://api.zeromq.org/2-1:zmq-setsockopt [ZMQ_LINGER]
        :param IOLoop io_loop: A Tornado IOLoop event scheduler [tornado.ioloop.IOLoop]
        '''
        self.opts = opts
        self.addr = addr
        self.linger = linger
        if io_loop is None:
            zmq.eventloop.ioloop.install()
            tornado.ioloop.IOLoop.current()
        else:
            self.io_loop = io_loop

        self.serial = salt.payload.Serial(self.opts)

        self.context = zmq.Context()

        # wire up sockets
        self._init_socket()

        self.send_queue = []
        # mapping of message -> future
        self.send_future_map = {}

        self.send_timeout_map = {}  # message -> timeout

    # TODO: timeout all in-flight sessions, or error
    def destroy(self):
        if hasattr(self, 'stream') and self.stream is not None:
            # TODO: Optionally call stream.close() on newer pyzmq? It is broken on some.
            if self.stream.socket:
                self.stream.socket.close()
            self.stream.io_loop.remove_handler(self.stream.socket)
            # set this to None, more hacks for messed up pyzmq
            self.stream.socket = None
            self.stream = None
            self.socket.close()
        if self.context.closed is False:
            self.context.term()

    def __del__(self):
        self.destroy()

    def _init_socket(self):
        if hasattr(self, 'stream'):
            self.stream.close()  # pylint: disable=E0203
            self.socket.close()  # pylint: disable=E0203
            del self.stream
            del self.socket

        self.socket = self.context.socket(zmq.REQ)

        # socket options
        if hasattr(zmq, 'RECONNECT_IVL_MAX'):
            self.socket.setsockopt(
                zmq.RECONNECT_IVL_MAX, 5000
            )

        self._set_tcp_keepalive()
        if self.addr.startswith('tcp://['):
            # Hint PF type if bracket enclosed IPv6 address
            if hasattr(zmq, 'IPV6'):
                self.socket.setsockopt(zmq.IPV6, 1)
            elif hasattr(zmq, 'IPV4ONLY'):
                self.socket.setsockopt(zmq.IPV4ONLY, 0)
        self.socket.linger = self.linger
        self.socket.connect(self.addr)
        self.stream = zmq.eventloop.zmqstream.ZMQStream(self.socket, io_loop=self.io_loop)

    def _set_tcp_keepalive(self):
        '''
        Ensure that TCP keepalives are set for the ReqServer.

        Warning: Failure to set TCP keepalives can result in frequent or unexpected
        disconnects!
        '''
        if hasattr(zmq, 'TCP_KEEPALIVE') and self.opts:
            if 'tcp_keepalive' in self.opts:
                self.socket.setsockopt(
                    zmq.TCP_KEEPALIVE, self.opts['tcp_keepalive']
                )
            if 'tcp_keepalive_idle' in self.opts:
                self.socket.setsockopt(
                    zmq.TCP_KEEPALIVE_IDLE, self.opts['tcp_keepalive_idle']
                )
            if 'tcp_keepalive_cnt' in self.opts:
                self.socket.setsockopt(
                    zmq.TCP_KEEPALIVE_CNT, self.opts['tcp_keepalive_cnt']
                )
            if 'tcp_keepalive_intvl' in self.opts:
                self.socket.setsockopt(
                    zmq.TCP_KEEPALIVE_INTVL, self.opts['tcp_keepalive_intvl']
                )

    @tornado.gen.coroutine
    def _internal_send_recv(self):
        while len(self.send_queue) > 0:
            message = self.send_queue[0]
            future = self.send_future_map.get(message, None)
            if future is None:
                # Timedout
                del self.send_queue[0]
                continue

            # send
            def mark_future(msg):
                if not future.done():
                    data = self.serial.loads(msg[0])
                    future.set_result(data)
            self.stream.on_recv(mark_future)
            self.stream.send(message)

            try:
                ret = yield future
            except:  # pylint: disable=W0702
                self._init_socket()  # re-init the zmq socket (no other way in zmq)
                del self.send_queue[0]
                continue
            del self.send_queue[0]
            self.send_future_map.pop(message, None)
            self.remove_message_timeout(message)

    def remove_message_timeout(self, message):
        if message not in self.send_timeout_map:
            return
        timeout = self.send_timeout_map.pop(message, None)
        if timeout is not None:
            # Hasn't been already timedout
            self.io_loop.remove_timeout(timeout)

    def timeout_message(self, message):
        '''
        Handle a message timeout by removing it from the sending queue
        and informing the caller

        :raises: SaltReqTimeoutError
        '''
        future = self.send_future_map.pop(message, None)
        # In a race condition the message might have been sent by the time
        # we're timing it out. Make sure the future is not None
        if future is not None:
            del self.send_timeout_map[message]
            if future.attempts < future.tries:
                future.attempts += 1
                log.debug('SaltReqTimeoutError, retrying. ({0}/{1})'.format(future.attempts, future.tries))
                self.send(
                    message,
                    timeout=future.timeout,
                    tries=future.tries,
                    future=future,
                )

            else:
                future.set_exception(SaltReqTimeoutError('Message timed out'))

    def send(self, message, timeout=None, tries=3, future=None, callback=None, raw=False):
        '''
        Return a future which will be completed when the message has a response
        '''
        if future is None:
            future = tornado.concurrent.Future()
            future.tries = tries
            future.attempts = 0
            future.timeout = timeout
            # if a future wasn't passed in, we need to serialize the message
            message = self.serial.dumps(message)
        if callback is not None:
            def handle_future(future):
                response = future.result()
                self.io_loop.add_callback(callback, response)
            future.add_done_callback(handle_future)
        # Add this future to the mapping
        self.send_future_map[message] = future

        if self.opts.get('detect_mode') is True:
            timeout = 1

        if timeout is not None:
            send_timeout = self.io_loop.call_later(timeout, self.timeout_message, message)
            self.send_timeout_map[message] = send_timeout

        if len(self.send_queue) == 0:
            self.io_loop.spawn_callback(self._internal_send_recv)

        self.send_queue.append(message)

        return future


class ZeroMQSocketMonitor(object):
    __EVENT_MAP = None

    def __init__(self, socket):
        '''
        Create ZMQ monitor sockets

        More information:
            http://api.zeromq.org/4-0:zmq-socket-monitor
        '''
        self._socket = socket
        self._monitor_socket = self._socket.get_monitor_socket()
        self._monitor_stream = None

    def start_io_loop(self, io_loop):
        log.trace("Event monitor start!")
        self._monitor_stream = zmq.eventloop.zmqstream.ZMQStream(self._monitor_socket, io_loop=io_loop)
        self._monitor_stream.on_recv(self.monitor_callback)

    def start_poll(self):
        log.trace("Event monitor start!")
        try:
            while self._monitor_socket is not None and self._monitor_socket.poll():
                msg = self._monitor_socket.recv_multipart()
                self.monitor_callback(msg)
        except (AttributeError, zmq.error.ContextTerminated):
            # We cannot log here because we'll get an interrupted system call in trying
            # to flush the logging buffer as we terminate
            pass

    @property
    def event_map(self):
        if ZeroMQSocketMonitor.__EVENT_MAP is None:
            event_map = {}
            for name in dir(zmq):
                if name.startswith('EVENT_'):
                    value = getattr(zmq, name)
                    event_map[value] = name
            ZeroMQSocketMonitor.__EVENT_MAP = event_map
        return ZeroMQSocketMonitor.__EVENT_MAP

    def monitor_callback(self, msg):
        evt = zmq.utils.monitor.parse_monitor_message(msg)
        evt['description'] = self.event_map[evt['event']]
        log.debug("ZeroMQ event: {0}".format(evt))
        if evt['event'] == zmq.EVENT_MONITOR_STOPPED:
            self.stop()

    def stop(self):
        if self._socket is None:
            return
        self._socket.disable_monitor()
        self._socket = None
        self._monitor_socket = None
        if self._monitor_stream is not None:
            self._monitor_stream.close()
            self._monitor_stream = None
        log.trace("Event monitor done!")
