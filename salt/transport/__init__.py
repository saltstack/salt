# -*- coding: utf-8 -*-
'''
Encapsulate the different transports available to Salt.  Currently this is only ZeroMQ.
'''

# Import Salt Libs
import salt.payload
import salt.auth
try:
    from salt.transport.road.raet import stacking
    from salt.transport.road.raet import yarding
except ImportError:
    # Don't die on missing transport libs since only one transport is required
    pass


class Channel(object):
    @staticmethod
    def factory(opts, **kwargs):
        # Default to ZeroMQ for now
        ttype = 'zeromq'

        if 'transport' in opts:
            ttype = opts['transport']
        elif 'transport' in opts.get('pillar', {}).get('master', {}):
            ttype = opts['pillar']['master']['transport']

        if ttype == 'zeromq':
            return ZeroMQChannel(opts, **kwargs)
        if ttype == 'raet':
            return RAETChannel(opts, **kwargs)
        else:
            raise Exception('Channels are only defined for ZeroMQ')
            # return NewKindOfChannel(opts, **kwargs)


class RAETChannel(Channel):
    '''
    Build the communication framework to communicate over the local process
    uxd socket and send messages forwarded to the master. then wait for the
    relative return message.
    '''
    def __init__(self, opts, **kwargs):
        self.opts = opts

    def __prep_stack(self):
        '''
        Prepare the stack objects
        '''
        self.stack = stacking.StackUxd(
                name='ex{0}'.format(self.opts['__ex_id']),
                lanename=self.opts['id'],
                yid=self.opts['__ex_id'],
                dirpath=self.opts['sock_dir'])
        self.router_yard = yarding.Yard(
                yid=0,
                prefix=self.opts['id'],
                dirpath=self.opts['sock_dir'])
        self.stack.addRemoteYard(self.router_yard)
        src = (self.opts['id'], self.stack.yard.name, None)
        dst = (self.opts['id'], 'router', None)
        self.route = {'src': src, 'dst': dst}

    def send(self, load, tries, timeout):
        '''
        Send a message load and wait for a relative reply
        '''
        msg = {'route': self.route, 'load': load}
        self.stack.transmit(msg=msg)
        while True:
            self.stack.serviceAll()
            if self.stack.rxMsgs:
                for msg in self.stack.rxMsgs:
                    return msg['load']


class ZeroMQChannel(Channel):
    '''
    Encapsulate sending routines to ZeroMQ.

    ZMQ Channels default to 'crypt=aes'
    '''
    def __init__(self, opts, **kwargs):
        self.opts = opts
        self.ttype = 'zeromq'

        # crypt defaults to 'aes'
        self.crypt = kwargs['crypt'] if 'crypt' in kwargs else 'aes'

        self.serial = salt.payload.Serial(opts)
        if self.crypt != 'clear':
            if 'auth' in kwargs:
                self.auth = kwargs['auth']
            else:
                self.auth = salt.crypt.SAuth(opts)
        if 'master_uri' in kwargs:
            master_uri = kwargs['master_uri']
        else:
            master_uri = opts['master_uri']

        self.sreq = salt.payload.SREQ(master_uri)

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
