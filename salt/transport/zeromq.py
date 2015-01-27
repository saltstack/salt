'''
Zeromq transport classes
'''

import os
import threading
import errno
import hashlib

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


class ZeroMQPubChannel(salt.transport.client.PubChannel):
    def __init__(self,
                 opts,
                 **kwargs):
        self.opts = opts
        self.ttype = 'zeromq'

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
        self._socket.connect(self.master_pub)

    @property
    def master_pub(self):
        '''
        Return the master publish port
        '''
        return 'tcp://{ip}:{port}'.format(ip=self.opts['master_ip'],
                                          port=self.publish_port)

    def _verify_master_signature(self, payload):
        if payload.get('sig') and self.opts.get('sign_pub_messages'):
            # Verify that the signature is valid
            master_pubkey_path = os.path.join(self.opts['pki_dir'], 'minion_master.pub')
            if not salt.crypt.verify_signature(master_pubkey_path, load, payload.get('sig')):
                raise salt.crypt.AuthenticationError('Message signature failed to validate.')

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

        # we need to decrypt it
        if payload['enc'] == 'aes':
            self._verify_master_signature(payload)
            try:
                payload['load'] = self.auth.crypticle.loads(payload['load'])
            except salt.crypt.AuthenticationError:
                self.auth.authenticate()
                payload['load'] = self.auth.crypticle.loads(payload['load'])

        return payload

    def recv(self, timeout=0):
        '''
        Get a pub job, with an optional timeout (0==forever)
        '''
        if timeout == 0 or self._socket.poll(timeout):
            messages = self._socket.recv_multipart()
            return self._decode_messages(messages)
        else:
            return None

    def recv_noblock(self):
        '''
        Get a pub job in a non-blocking manner.
        Return pub or None
        '''
        try:
            messages = self._socket.recv_multipart(zmq.NOBLOCK)
            return self._decode_messages(messages)
        except zmq.ZMQError as e:
            # Swallow errors for bad wakeups or signals needing processing
            if e.errno != errno.EAGAIN and e.errno != errno.EINTR:
                raise
            return None

    @property
    def socket(self):
        return self._socket


class ZeroMQReqServerChannel(salt.transport.server.ReqServerChannel):
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
        try:
            self.clients.setsockopt(zmq.HWM, self.opts['rep_hwm'])
        # in zmq >= 3.0, there are separate send and receive HWM settings
        except AttributeError:
            self.clients.setsockopt(zmq.SNDHWM, self.opts['rep_hwm'])
            self.clients.setsockopt(zmq.RCVHWM, self.opts['rep_hwm'])

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

    def pre_fork(self, process_manager):
        '''
        Pre-fork we need to create the zmq router device
        '''
        process_manager.add_process(self.zmq_device)

    def post_fork(self):
        '''
        After forking we need to create all of the local sockets to listen to the
        router
        '''
        self.context = zmq.Context(1)
        self._socket = self.context.socket(zmq.REP)
        self.w_uri = 'ipc://{0}'.format(
            os.path.join(self.opts['sock_dir'], 'workers.ipc')
            )
        log.info('Worker binding to socket {0}'.format(self.w_uri))
        self._socket.connect(self.w_uri)

        self.serial = salt.payload.Serial(self.opts)
        self.crypticle = salt.crypt.Crypticle(self.opts, self.opts['aes'].value)

        # other things needed for _auth
        # Create the event manager
        self.event = salt.utils.event.get_master_event(self.opts, self.opts['sock_dir'])
        # Make an minion checker object
        self.ckminions = salt.utils.minions.CkMinions(self.opts)
        self.auto_key = salt.daemons.masterapi.AutoKey(self.opts)

        # only create a con_cache-client if the con_cache is active
        if self.opts['con_cache']:
            self.cache_cli = CacheCli(self.opts)
        else:
            self.cache_cli = False

        self.master_key = salt.crypt.MasterKeys(self.opts)

    def _update_aes(self):
        '''
        Check to see if a fresh AES key is available and update the components
        of the worker
        '''
        if self.opts['aes'].value != self.crypticle.key_string:
            self.crypticle = salt.crypt.Crypticle(self.opts, self.opts['aes'].value)
            return True
        return False

    def _decode_payload(self, payload):
        # we need to decrypt it
        if payload['enc'] == 'aes':
            try:
                try:
                    payload['load'] = self.crypticle.loads(payload['load'])
                except salt.crypt.AuthenticationError:
                    if not self._update_aes():
                        raise
                    payload['load'] = self.crypticle.loads(payload['load'])
            except Exception:
                # send something back to the client so the client so they know
                # their load was malformed
                self.send('bad load')
                raise

        # intercept the "_auth" commands, since the main daemon shouldn't know
        # anything about our key auth
        if payload['enc'] == 'clear' and payload['load']['cmd'] == '_auth':
            self.send_clear(self._auth(payload['load']))
            return None
        return payload

    def recv(self, timeout=0):
        '''
        Get a req job, with an optional timeout (0==forever)
        '''
        if timeout == 0 or self._socket.poll(timeout):
            package = self._socket.recv()
            payload = self.serial.loads(package)
            payload = self._decode_payload(payload)
            if payload is None and timeout == 0:
                return self.recv(timeout=timeout)
            return payload
        else:
            return None

    def recv_noblock(self):
        '''
        Get a req job in a non-blocking manner.
        Return load or None
        '''
        try:
            package = self._socket.recv()
            payload = self.serial.loads(package)
            payload = self._decode_payload(payload)
            return payload
        except zmq.ZMQError as e:
            # Swallow errors for bad wakeups or signals needing processing
            if e.errno != errno.EAGAIN and e.errno != errno.EINTR:
                raise
            return None

    def _send(self, payload):
        '''
        Helper function to serialize and send payload
        '''
        self._socket.send(self.serial.dumps(payload))

    # TODO? maybe have recv() return this function, so this class isn't tied to
    # a send/recv order
    def send_clear(self, payload):
        '''
        Send a response to a recv()'d payload
        '''
        payload['enc'] = 'clear'  # make sure we set enc
        self._send(payload)

    def send(self, payload):
        '''
        Send a response to a recv()'d payload
        '''
        self._send(self.crypticle.dumps(payload))


    def send_private(self, payload, dictkey, target):
        '''
        Send a response to a recv()'d payload encrypted privately for target
        '''
        self._send(self._encrypt_private(payload, dictkey, target))

    def _encrypt_private(self, ret, dictkey, target):
        '''
        The server equivalent of ReqChannel.crypted_transfer_decode_dictentry
        '''
        # encrypt with a specific AES key
        pubfn = os.path.join(self.opts['pki_dir'],
                             'minions',
                             target)
        key = salt.crypt.Crypticle.generate_key_string()
        pcrypt = salt.crypt.Crypticle(
            self.opts,
            key)
        try:
            pub = RSA.load_pub_key(pubfn)
        except RSA.RSAError:
            return self.crypticle.dumps({})

        pret = {}
        pret['key'] = pub.public_encrypt(key, 4)
        pret[dictkey] = pcrypt.dumps(
            ret if ret is not False else {}
        )
        return pret

    @property
    def socket(self):
        '''
        Return a socket (or fd) which can be used for poll mechanisms
        '''
        self._socket

    def _auth(self, load):
        '''
        Authenticate the client, use the sent public key to encrypt the AES key
        which was generated at start up.

        This method fires an event over the master event manager. The event is
        tagged "auth" and returns a dict with information about the auth
        event

        # Verify that the key we are receiving matches the stored key
        # Store the key if it is not there
        # Make an RSA key with the pub key
        # Encrypt the AES key as an encrypted salt.payload
        # Package the return and return it
        '''

        if not salt.utils.verify.valid_id(self.opts, load['id']):
            log.info(
                'Authentication request from invalid id {id}'.format(**load)
                )
            return {'enc': 'clear',
                    'load': {'ret': False}}
        log.info('Authentication request from {id}'.format(**load))

        # 0 is default which should be 'unlimited'
        if self.opts['max_minions'] > 0:
            # use the ConCache if enabled, else use the minion utils
            if self.cache_cli:
                minions = self.cache_cli.get_cached()
            else:
                minions = self.ckminions.connected_ids()
                if len(minions) > 1000:
                    log.info('With large numbers of minions it is advised '
                             'to enable the ConCache with \'con_cache: True\' '
                             'in the masters configuration file.')

            if not len(minions) <= self.opts['max_minions']:
                # we reject new minions, minions that are already
                # connected must be allowed for the mine, highstate, etc.
                if load['id'] not in minions:
                    msg = ('Too many minions connected (max_minions={0}). '
                           'Rejecting connection from id '
                           '{1}'.format(self.opts['max_minions'],
                                        load['id']))
                    log.info(msg)
                    eload = {'result': False,
                             'act': 'full',
                             'id': load['id'],
                             'pub': load['pub']}

                    self.event.fire_event(eload, salt.utils.event.tagify(prefix='auth'))
                    return {'enc': 'clear',
                            'load': {'ret': 'full'}}

        # Check if key is configured to be auto-rejected/signed
        auto_reject = self.auto_key.check_autoreject(load['id'])
        auto_sign = self.auto_key.check_autosign(load['id'])

        pubfn = os.path.join(self.opts['pki_dir'],
                             'minions',
                             load['id'])
        pubfn_pend = os.path.join(self.opts['pki_dir'],
                                  'minions_pre',
                                  load['id'])
        pubfn_rejected = os.path.join(self.opts['pki_dir'],
                                      'minions_rejected',
                                      load['id'])
        pubfn_denied = os.path.join(self.opts['pki_dir'],
                                    'minions_denied',
                                    load['id'])
        if self.opts['open_mode']:
            # open mode is turned on, nuts to checks and overwrite whatever
            # is there
            pass
        elif os.path.isfile(pubfn_rejected):
            # The key has been rejected, don't place it in pending
            log.info('Public key rejected for {0}. Key is present in '
                     'rejection key dir.'.format(load['id']))
            eload = {'result': False,
                     'id': load['id'],
                     'pub': load['pub']}
            self.event.fire_event(eload, salt.utils.event.tagify(prefix='auth'))
            return {'enc': 'clear',
                    'load': {'ret': False}}

        elif os.path.isfile(pubfn):
            # The key has been accepted, check it
            if salt.utils.fopen(pubfn, 'r').read() != load['pub']:
                log.error(
                    'Authentication attempt from {id} failed, the public '
                    'keys did not match. This may be an attempt to compromise '
                    'the Salt cluster.'.format(**load)
                )
                # put denied minion key into minions_denied
                with salt.utils.fopen(pubfn_denied, 'w+') as fp_:
                    fp_.write(load['pub'])
                eload = {'result': False,
                         'id': load['id'],
                         'pub': load['pub']}
                self.event.fire_event(eload, salt.utils.event.tagify(prefix='auth'))
                return {'enc': 'clear',
                        'load': {'ret': False}}

        elif not os.path.isfile(pubfn_pend):
            # The key has not been accepted, this is a new minion
            if os.path.isdir(pubfn_pend):
                # The key path is a directory, error out
                log.info(
                    'New public key {id} is a directory'.format(**load)
                )
                eload = {'result': False,
                         'id': load['id'],
                         'pub': load['pub']}
                self.event.fire_event(eload, salt.utils.event.tagify(prefix='auth'))
                return {'enc': 'clear',
                        'load': {'ret': False}}

            if auto_reject:
                key_path = pubfn_rejected
                log.info('New public key for {id} rejected via autoreject_file'
                         .format(**load))
                key_act = 'reject'
                key_result = False
            elif not auto_sign:
                key_path = pubfn_pend
                log.info('New public key for {id} placed in pending'
                         .format(**load))
                key_act = 'pend'
                key_result = True
            else:
                # The key is being automatically accepted, don't do anything
                # here and let the auto accept logic below handle it.
                key_path = None

            if key_path is not None:
                # Write the key to the appropriate location
                with salt.utils.fopen(key_path, 'w+') as fp_:
                    fp_.write(load['pub'])
                ret = {'enc': 'clear',
                       'load': {'ret': key_result}}
                eload = {'result': key_result,
                         'act': key_act,
                         'id': load['id'],
                         'pub': load['pub']}
                self.event.fire_event(eload, salt.utils.event.tagify(prefix='auth'))
                return ret

        elif os.path.isfile(pubfn_pend):
            # This key is in the pending dir and is awaiting acceptance
            if auto_reject:
                # We don't care if the keys match, this minion is being
                # auto-rejected. Move the key file from the pending dir to the
                # rejected dir.
                try:
                    shutil.move(pubfn_pend, pubfn_rejected)
                except (IOError, OSError):
                    pass
                log.info('Pending public key for {id} rejected via '
                         'autoreject_file'.format(**load))
                ret = {'enc': 'clear',
                       'load': {'ret': False}}
                eload = {'result': False,
                         'act': 'reject',
                         'id': load['id'],
                         'pub': load['pub']}
                self.event.fire_event(eload, salt.utils.event.tagify(prefix='auth'))
                return ret

            elif not auto_sign:
                # This key is in the pending dir and is not being auto-signed.
                # Check if the keys are the same and error out if this is the
                # case. Otherwise log the fact that the minion is still
                # pending.
                if salt.utils.fopen(pubfn_pend, 'r').read() != load['pub']:
                    log.error(
                        'Authentication attempt from {id} failed, the public '
                        'key in pending did not match. This may be an '
                        'attempt to compromise the Salt cluster.'
                        .format(**load)
                    )
                    # put denied minion key into minions_denied
                    with salt.utils.fopen(pubfn_denied, 'w+') as fp_:
                        fp_.write(load['pub'])
                    eload = {'result': False,
                             'id': load['id'],
                             'pub': load['pub']}
                    self.event.fire_event(eload, salt.utils.event.tagify(prefix='auth'))
                    return {'enc': 'clear',
                            'load': {'ret': False}}
                else:
                    log.info(
                        'Authentication failed from host {id}, the key is in '
                        'pending and needs to be accepted with salt-key '
                        '-a {id}'.format(**load)
                    )
                    eload = {'result': True,
                             'act': 'pend',
                             'id': load['id'],
                             'pub': load['pub']}
                    self.event.fire_event(eload, salt.utils.event.tagify(prefix='auth'))
                    return {'enc': 'clear',
                            'load': {'ret': True}}
            else:
                # This key is in pending and has been configured to be
                # auto-signed. Check to see if it is the same key, and if
                # so, pass on doing anything here, and let it get automatically
                # accepted below.
                if salt.utils.fopen(pubfn_pend, 'r').read() != load['pub']:
                    log.error(
                        'Authentication attempt from {id} failed, the public '
                        'keys in pending did not match. This may be an '
                        'attempt to compromise the Salt cluster.'
                        .format(**load)
                    )
                    # put denied minion key into minions_denied
                    with salt.utils.fopen(pubfn_denied, 'w+') as fp_:
                        fp_.write(load['pub'])
                    eload = {'result': False,
                             'id': load['id'],
                             'pub': load['pub']}
                    self.event.fire_event(eload, salt.utils.event.tagify(prefix='auth'))
                    return {'enc': 'clear',
                            'load': {'ret': False}}
                else:
                    pass

        else:
            # Something happened that I have not accounted for, FAIL!
            log.warn('Unaccounted for authentication failure')
            eload = {'result': False,
                     'id': load['id'],
                     'pub': load['pub']}
            self.event.fire_event(eload, salt.utils.event.tagify(prefix='auth'))
            return {'enc': 'clear',
                    'load': {'ret': False}}

        log.info('Authentication accepted from {id}'.format(**load))
        # only write to disk if you are adding the file, and in open mode,
        # which implies we accept any key from a minion.
        if not os.path.isfile(pubfn) and not self.opts['open_mode']:
            with salt.utils.fopen(pubfn, 'w+') as fp_:
                fp_.write(load['pub'])
        elif self.opts['open_mode']:
            disk_key = ''
            if os.path.isfile(pubfn):
                with salt.utils.fopen(pubfn, 'r') as fp_:
                    disk_key = fp_.read()
            if load['pub'] and load['pub'] != disk_key:
                log.debug('Host key change detected in open mode.')
                with salt.utils.fopen(pubfn, 'w+') as fp_:
                    fp_.write(load['pub'])

        pub = None

        # the con_cache is enabled, send the minion id to the cache
        if self.cache_cli:
            self.cache_cli.put_cache([load['id']])

        # The key payload may sometimes be corrupt when using auto-accept
        # and an empty request comes in
        try:
            pub = RSA.load_pub_key(pubfn)
        except RSA.RSAError as err:
            log.error('Corrupt public key "{0}": {1}'.format(pubfn, err))
            return {'enc': 'clear',
                    'load': {'ret': False}}

        ret = {'enc': 'pub',
               'pub_key': self.master_key.get_pub_str(),
               'publish_port': self.opts['publish_port']}

        # sign the masters pubkey (if enabled) before it is
        # send to the minion that was just authenticated
        if self.opts['master_sign_pubkey']:
            # append the pre-computed signature to the auth-reply
            if self.master_key.pubkey_signature():
                log.debug('Adding pubkey signature to auth-reply')
                log.debug(self.master_key.pubkey_signature())
                ret.update({'pub_sig': self.master_key.pubkey_signature()})
            else:
                # the master has its own signing-keypair, compute the master.pub's
                # signature and append that to the auth-reply
                log.debug("Signing master public key before sending")
                pub_sign = salt.crypt.sign_message(self.master_key.get_sign_paths()[1],
                                                   ret['pub_key'])
                ret.update({'pub_sig': binascii.b2a_base64(pub_sign)})

        if self.opts['auth_mode'] >= 2:
            if 'token' in load:
                try:
                    mtoken = self.master_key.key.private_decrypt(load['token'], 4)
                    aes = '{0}_|-{1}'.format(self.opts['aes'].value, mtoken)
                except Exception:
                    # Token failed to decrypt, send back the salty bacon to
                    # support older minions
                    pass
            else:
                aes = self.opts['aes'].value

            ret['aes'] = pub.public_encrypt(aes, 4)
        else:
            if 'token' in load:
                try:
                    mtoken = self.master_key.key.private_decrypt(
                        load['token'], 4
                    )
                    ret['token'] = pub.public_encrypt(mtoken, 4)
                except Exception:
                    # Token failed to decrypt, send back the salty bacon to
                    # support older minions
                    pass

            aes = self.opts['aes'].value
            ret['aes'] = pub.public_encrypt(self.opts['aes'].value, 4)
        # Be aggressive about the signature
        digest = hashlib.sha256(aes).hexdigest()
        ret['sig'] = self.master_key.key.private_encrypt(digest, 5)
        eload = {'result': True,
                 'act': 'accept',
                 'id': load['id'],
                 'pub': load['pub']}
        self.event.fire_event(eload, salt.utils.event.tagify(prefix='auth'))
        return ret


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

        crypticle = salt.crypt.Crypticle(self.opts, self.opts['aes'].value)
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
