# -*- coding: utf-8 -*-
'''
Encapsulate the different transports available to Salt.  Currently this is only ZeroMQ.
'''

import salt.payload
import salt.auth


class Channel(object):

    @staticmethod
    def factory(opts, **kwargs):

        # Default to ZeroMQ for now
        ttype = 'zeromq'

        if 'transport_type' in opts:
            ttype = opts['transport_type']
        elif 'transport_type' in opts.get('pillar', {}).get('master', {}):
            ttype = opts['pillar']['master']['transport_type']

        if ttype == 'zeromq':
            return ZeroMQChannel(opts, **kwargs)
        else:
            raise Exception("Channels are only defined for ZeroMQ")
            # return NewKindOfChannel(opts, **kwargs)


class ZeroMQChannel(Channel):

    '''
    Encapsulate sending routines to ZeroMQ.

    ZMQ Channels default to 'crypt=aes'
    '''

    def __init__(self, opts, **kwargs):
        self.opts = opts

        # crypt defaults to 'aes'
        self.crypt = kwargs['crypt'] if 'crypt' in kwargs else 'aes'

        self.serial = salt.payload.Serial(opts)
        if self.crypt != 'clear':
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
            return self.auth.crypticle.loads(
                self.sreq.send(self.crypt,
                               self.auth.crypticle.dumps(load),
                               tries,
                               timeout)
            )
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
