'''
Zeromq transport classes
'''

import os
import threading
import errno
import hashlib

from random import randint

# Import Salt Libs
import salt.payload
import salt.auth
import salt.crypt
import salt.utils
import salt.payload
import logging
from collections import defaultdict

import salt.transport.client

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
