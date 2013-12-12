# -*- coding: utf-8 -*-
'''
Encapsulate the different transports available to Salt.  Currently this is only ZeroMQ.
'''

import salt.payload
import salt.auth


class Channel(object):

    @staticmethod
    def factory(opts, **kwargs):
        if ('transport_type' in opts and opts['transport_type'] == 'zeromq') \
            or ('transport_type' in opts['pillar']['master']
                and opts['pillar']['master']['transport_type'] == 'zeromq'):
            return ZeroMQChannel(opts, **kwargs)
        else:
            raise Exception("Channels are only defined for ZeroMQ")
            # return NewKindOfChannel(opts, **kwargs)


class ZeroMQChannel(Channel):

    '''
    Encapsulate sending routines to ZeroMQ.

    ZMQ Channels default to 'crypt=True'
    '''

    def __init__(self, opts, **kwargs):
        self.opts = opts

        # crypt defaults to True
        self.crypt = kwargs['crypt'] if 'crypt' in kwargs else True

        self.auth = salt.crypt.SAuth(opts)
        self.serial = salt.payload.Serial(opts)
        if self.crypt:
            self.auth = salt.crypt.SAuth(opts)
        self.sreq = salt.payload.SREQ(opts['master_uri'])

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

    def send(self, load, tries=3, timeout=60):

        if self.crypt:
            return self._crypted_transfer(load, tries, timeout)
        # Do we ever do non-crypted transfers?
