# -*- coding: utf-8 -*-
'''
Encapsulate the different transports available to Salt.  Currently this is only ZeroMQ.
'''
import time
import os
import threading

from collections import defaultdict

# Import Salt Libs
import salt.payload
import salt.auth
import salt.utils
import logging

log = logging.getLogger(__name__)

try:
    from raet import raeting, nacling
    from raet.lane.stacking import LaneStack
    from raet.lane import yarding

except ImportError:
    # Don't die on missing transport libs since only one transport is required
    pass


class Channel(object):
    '''
    Factory class to create communication-channels for different transport
    '''
    @staticmethod
    def factory(opts, **kwargs):
        # Default to ZeroMQ for now
        ttype = 'zeromq'

        # determine the ttype
        if 'transport' in opts:
            ttype = opts['transport']
        elif 'transport' in opts.get('pillar', {}).get('master', {}):
            ttype = opts['pillar']['master']['transport']

        # switch on available ttypes
        if ttype == 'zeromq':
            return ZeroMQChannel(opts, **kwargs)
        elif ttype == 'raet':
            return RAETChannel(opts, **kwargs)
        else:
            raise Exception('Channels are only defined for ZeroMQ and raet')
            # return NewKindOfChannel(opts, **kwargs)


class RAETChannel(Channel):
    '''
    Build the communication framework to communicate over the local process
    uxd socket and send messages forwarded to the master. then wait for the
    relative return message.
    '''
    def __init__(self, opts, **kwargs):
        self.opts = opts
        self.ttype = 'raet'
        self.__prep_stack()

    def __prep_stack(self):
        '''
        Prepare the stack objects
        '''
        mid = self.opts.get('id', 'master')
        yid = nacling.uuid(size=18)
        stackname = 'raet' + yid
        self.stack = LaneStack(
                name=stackname,
                lanename=mid,
                yid=yid,
                sockdirpath=self.opts['sock_dir'])
        self.stack.Pk = raeting.packKinds.pack
        self.router_yard = yarding.RemoteYard(
                stack=self.stack,
                yid=0,
                name='manor',
                lanename=mid,
                dirpath=self.opts['sock_dir'])
        self.stack.addRemote(self.router_yard)
        src = (mid, self.stack.local.name, None)
        dst = ('master', None, 'remote_cmd')
        self.route = {'src': src, 'dst': dst}

    def crypted_transfer_decode_dictentry(self, load, dictkey=None, tries=3, timeout=60):
        '''
        We don't need to do the crypted_transfer_decode_dictentry routine for
        raet, just wrap send.
        '''
        return self.send(load, tries, timeout)

    def send(self, load, tries=3, timeout=60):
        '''
        Send a message load and wait for a relative reply
        '''
        msg = {'route': self.route, 'load': load}
        self.stack.transmit(msg, self.stack.uids['manor'])
        tried = 1
        start = time.time()
        while True:
            time.sleep(0.01)
            self.stack.serviceAll()
            while self.stack.rxMsgs:
                msg, sender = self.stack.rxMsgs.popleft()
                return msg.get('return', {})
            if time.time() - start > timeout:
                if tried >= tries:
                    raise ValueError
                self.stack.transmit(msg, self.stack.uids['manor'])
                tried += 1

    def __del__(self):
        '''
        Clean up the stack when finished
        '''
        self.stack.server.close()


class ZeroMQChannel(Channel):
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
        key = self.sreq_key

        if key not in ZeroMQChannel.sreq_cache:
            master_type = self.opts.get('master_type', None)
            if master_type == 'failover':
                # remove all cached sreqs to the old master to prevent
                # zeromq from reconnecting to old masters automagically
                for check_key in self.sreq_cache.keys():
                    if self.opts['master_uri'] != check_key[0]:
                        del self.sreq_cache[check_key]
                        log.debug('Removed obsolete sreq-object from '
                                  'sreq_cache for master {0}'.format(check_key[0]))

            ZeroMQChannel.sreq_cache[key] = salt.payload.SREQ(self.master_uri)

        return ZeroMQChannel.sreq_cache[key]

    def __init__(self, opts, **kwargs):
        self.opts = opts
        self.ttype = 'zeromq'

        # crypt defaults to 'aes'
        self.crypt = kwargs.get('crypt', 'aes')

        self.serial = salt.payload.Serial(opts)
        if self.crypt != 'clear':
            if 'auth' in kwargs:
                self.auth = kwargs['auth']
            else:
                self.auth = salt.crypt.SAuth(opts)
        if 'master_uri' in kwargs:
            self.master_uri = kwargs['master_uri']
        else:
            self.master_uri = opts['master_uri']

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
            self.auth = salt.crypt.SAuth(self.opts)
            return _do_transfer()

    def _uncrypted_transfer(self, load, tries=3, timeout=60):
        return self.sreq.send(self.crypt, load, tries, timeout)

    def send(self, load, tries=3, timeout=60):

        if self.crypt != 'clear':
            return self._crypted_transfer(load, tries, timeout)
        else:
            return self._uncrypted_transfer(load, tries, timeout)
        # Do we ever do non-crypted transfers?
