# -*- coding: utf-8 -*-
'''
Encapsulate the different transports available to Salt.  Currently this is only ZeroMQ.
'''
import time
import os
import threading

# Import Salt Libs
import salt.payload
import salt.auth
import salt.utils
import logging
from collections import defaultdict

log = logging.getLogger(__name__)

try:
    from raet import raeting, nacling
    from raet.lane.stacking import LaneStack
    from raet.lane.yarding import RemoteYard

except ImportError:
    # Don't die on missing transport libs since only one transport is required
    pass

jobber_stack = None  # global that holds raet jobber LaneStack
jobber_rxMsgs = {}  # dict of deques one for each RaetChannel


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
        self.dst = ('master', None, 'remote_cmd')
        self.stack = None

    def _setup_stack(self):
        '''
        Setup and return the LaneStack and Yard used by by channel when global
        not already setup such as in salt-call to communicate to-from the minion

        '''
        mid = self.opts.get('id', 'master')
        yid = nacling.uuid(size=18)
        name = 'channel' + yid
        stack = LaneStack(name=name,
                          lanename=mid,
                          sockdirpath=self.opts['sock_dir'])

        stack.Pk = raeting.packKinds.pack
        stack.addRemote(RemoteYard(stack=stack,
                                   name='manor',
                                   lanename=mid,
                                   dirpath=self.opts['sock_dir']))
        log.debug("Created Channel Jobber Stack {0}\n".format(stack.name))
        return stack

    def __prep_stack(self):
        '''
        Prepare the stack objects
        '''
        global jobber_stack
        if not self.stack:
            if jobber_stack:
                self.stack = jobber_stack
            else:
                self.stack = jobber_stack = self._setup_stack()
        log.debug("Using Jobber Stack at = {0}\n".format(self.stack.local.ha))

    def crypted_transfer_decode_dictentry(self, load, dictkey=None, tries=3, timeout=60):
        '''
        We don't need to do the crypted_transfer_decode_dictentry routine for
        raet, just wrap send.
        '''
        return self.send(load, tries, timeout)

    def send(self, load, tries=3, timeout=60):
        '''
        Send a message load and wait for a relative reply
        One shot wonder
        '''
        self.__prep_stack()
        tried = 1
        start = time.time()
        mid = self.opts.get('id', None)
        track = nacling.uuid(18)
        src = (mid, self.stack.local.name, track)
        self.route = {'src': src, 'dst': self.dst}
        msg = {'route': self.route, 'load': load}
        self.stack.transmit(msg, self.stack.nameRemotes['manor'].uid)
        while track not in jobber_rxMsgs:
            self.stack.serviceAll()
            while self.stack.rxMsgs:
                msg, sender = self.stack.rxMsgs.popleft()
                jobber_rxMsgs[msg['route']['dst'][2]] = msg
                continue
            if track in jobber_rxMsgs:
                break
            if time.time() - start > timeout:
                if tried >= tries:
                    raise ValueError
                self.stack.transmit(msg, self.stack.nameRemotes['manor'].uid)
                tried += 1
            time.sleep(0.01)
        return jobber_rxMsgs.pop(track).get('return', {})


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
