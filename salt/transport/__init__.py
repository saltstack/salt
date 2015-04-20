# -*- coding: utf-8 -*-
'''
Encapsulate the different transports available to Salt.  Currently this is only ZeroMQ.
'''
from __future__ import absolute_import
import time
import os
import threading

# Import Salt Libs
import salt.payload
import salt.auth
import salt.crypt
import salt.utils
import logging
from collections import defaultdict

from salt.utils import kinds

log = logging.getLogger(__name__)

try:
    from raet import raeting, nacling
    from raet.lane.stacking import LaneStack
    from raet.lane.yarding import RemoteYard
except (ImportError, OSError):
    # Don't die on missing transport libs since only one transport is required
    pass

# Module globals for default LaneStack. Because RaetChannels are created on demand
# they do not have access to the master estate that motivated their creation
# Also in Raet a LaneStack can be shared shared by all channels in a given jobber
# For these reasons module globals are used to setup a shared jobber_stack as
# well has routing information for the master that motivated the jobber
# when a channel is not used in a jobber context then a LaneStack is created
# on demand.

jobber_stack = None  # module global that holds raet jobber LaneStack
jobber_rxMsgs = {}  # dict of deques one for each RaetChannel for the jobber
jobber_estate_name = None  # module global of motivating master estate name
jobber_yard_name = None  # module global of motivating master yard name


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

    def send(self, load, tries=3, timeout=60):
        '''
        Send "load" to the master.
        '''
        raise NotImplementedError()

    def crypted_transfer_decode_dictentry(self, load, dictkey=None, tries=3, timeout=60):
        '''
        Send "load" to the master in a way that the load is only readable by
        the minion and the master (not other minions etc.)
        '''
        raise NotImplementedError()


class RAETChannel(Channel):
    '''
    Build the communication framework to communicate over the local process
    uxd socket and send messages forwarded to the master. then wait for the
    relative return message.

    Two use cases:
        mininion to master communication, normal use case
           Minion is communicating via yard through minion Road to master
           The destination route needs the estate name of the associated master
        master call via runner, special use case
           In the special case the master call external process is communicating
           via a yard with the master manor yard
           The destination route estate is None to indicate local estate

        The difference between the two is how the destination route
        is assigned.
    '''
    def __init__(self, opts, usage=None, **kwargs):
        self.opts = opts
        self.ttype = 'raet'
        if usage == 'master_call':  # runner.py master_call
            self.dst = (None, None, 'local_cmd')
        else:  # everything else minion to master including salt-call
            self.dst = (jobber_estate_name or None,
                        jobber_yard_name or None,
                        'remote_cmd')
        self.stack = None
        self.ryn = 'manor'  # remote yard name

    def __prep_stack(self):
        '''
        Prepare the stack objects
        '''
        global jobber_stack
        if not self.stack:
            if jobber_stack:
                self.stack = jobber_stack
            else:
                self.stack = jobber_stack = self._setup_stack(ryn=self.ryn)
        log.debug("RAETChannel Using Jobber Stack at = {0}\n".format(self.stack.ha))

    def _setup_stack(self, ryn='manor'):
        '''
        Setup and return the LaneStack and Yard used by by channel when global
        not already setup such as in salt-call to communicate to-from the minion

        '''
        role = self.opts.get('id')
        if not role:
            emsg = ("Missing role required to setup RAETChannel.")
            log.error(emsg + "\n")
            raise ValueError(emsg)

        kind = self.opts.get('__role')  # application kind 'master', 'minion', etc
        if kind not in kinds.APPL_KINDS:
            emsg = ("Invalid application kind = '{0}' for RAETChannel.".format(kind))
            log.error(emsg + "\n")
            raise ValueError(emsg)
        if kind in [kinds.APPL_KIND_NAMES[kinds.applKinds.master],
                    kinds.APPL_KIND_NAMES[kinds.applKinds.syndic]]:
            lanename = 'master'
        elif kind == [kinds.APPL_KIND_NAMES[kinds.applKinds.minion],
                      kinds.APPL_KIND_NAMES[kinds.applKinds.caller]]:
            lanename = "{0}_{1}".format(role, kind)
        else:
            emsg = ("Unsupported application kind '{0}' for RAETChannel.".format(kind))
            log.error(emsg + '\n')
            raise ValueError(emsg)

        name = 'channel' + nacling.uuid(size=18)
        stack = LaneStack(name=name,
                          lanename=lanename,
                          sockdirpath=self.opts['sock_dir'])

        stack.Pk = raeting.PackKind.pack.value
        stack.addRemote(RemoteYard(stack=stack,
                                   name=ryn,
                                   lanename=lanename,
                                   dirpath=self.opts['sock_dir']))
        log.debug("Created Channel Jobber Stack {0}\n".format(stack.name))
        return stack

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
        track = nacling.uuid(18)
        src = (None, self.stack.local.name, track)
        self.route = {'src': src, 'dst': self.dst}
        msg = {'route': self.route, 'load': load}
        self.stack.transmit(msg, self.stack.nameRemotes[self.ryn].uid)
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
                    raise ValueError("Message send timed out after '{0} * {1}'"
                             " secs. route = {2} track = {3} load={4}".format(tries,
                                                                       timeout,
                                                                       self.route,
                                                                       track,
                                                                       load))
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
        # When using threading, like on Windows, don't cache.
        # The following block prevents thread leaks.
        if not self.opts.get('multiprocessing'):
            return salt.payload.SREQ(self.master_uri, opts=self.opts)

        key = self.sreq_key

        if not self.opts['cache_sreqs']:
            return salt.payload.SREQ(self.master_uri, opts=self.opts)
        else:
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

                ZeroMQChannel.sreq_cache[key] = salt.payload.SREQ(self.master_uri, opts=self.opts)

            return ZeroMQChannel.sreq_cache[key]

    def __init__(self, opts, **kwargs):
        self.opts = opts
        self.ttype = 'zeromq'

        # crypt defaults to 'aes'
        self.crypt = kwargs.get('crypt', 'aes')

        if 'master_uri' in kwargs:
            self.master_uri = kwargs['master_uri']
        else:
            self.master_uri = opts['master_uri']

        if self.crypt != 'clear':
            # we don't need to worry about auth as a kwarg, since its a singleton
            self.auth = salt.crypt.SAuth(self.opts)

    def crypted_transfer_decode_dictentry(self, load, dictkey=None, tries=3, timeout=60):
        ret = self.sreq.send('aes', self.auth.crypticle.dumps(load), tries, timeout)
        key = self.auth.get_keys()
        try:
            aes = key.private_decrypt(ret['key'], 4)
        except (TypeError, KeyError):
            return None
        else:
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
