# -*- coding: utf-8 -*-
'''
Encapsulate the different transports available to Salt.

This includes server side transport, for the ReqServer and the Publisher
'''


class ReqServerChannel(object):
    '''
    Factory class to create a communication channels to the ReqServer
    '''
    def __init__(self, opts):
        self.opts = opts

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
            import salt.transport.zeromq
            return salt.transport.zeromq.ZeroMQReqServerChannel(opts)
        elif ttype == 'raet':
            import salt.transport.raet
            return salt.transport.raet.RAETReqServerChannel(opts)
        elif ttype == 'local':
            import salt.transport.local
            return salt.transport.local.LocalServerChannel(opts)
        else:
            raise Exception('Channels are only defined for ZeroMQ and raet')
            # return NewKindOfChannel(opts, **kwargs)

    def pre_fork(self, process_manager):
        '''
        Do anything necessary pre-fork. Since this is on the master side this will
        primarily be bind and listen (or the equivalent for your network library)
        '''
        pass

    def post_fork(self):
        '''
        Do anything you need post-fork. This should be something like recv
        '''
        pass

    def recv(self, timeout=0):
        '''
        Get a req job, with an optional timeout (0==forever)
        '''
        raise NotImplementedError()

    def recv_noblock(self):
        '''
        Get a req job in a non-blocking manner.
        Return load or None
        '''
        raise NotImplementedError()

    @property
    def socket(self):
        '''
        Return a socket (or fd) which can be used for poll mechanisms
        '''
        raise NotImplementedError()

    # TODO: use a send method? or have the recv return one?
    def send(self, load, tries=3, timeout=60):
        '''
        Send "load" to the master.
        '''
        raise NotImplementedError()

    # TODO:
    def crypted_transfer_decode_dictentry(self, load, dictkey=None, tries=3, timeout=60):
        '''
        Send "load" to the master in a way that the load is only readable by
        the minion and the master (not other minions etc.)
        '''
        raise NotImplementedError()


class PubServerChannel(object):
    '''
    Factory class to create subscription channels to the master's Publisher
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
            import salt.transport.zeromq
            return salt.transport.zeromq.ZeroMQPubChannel(opts, **kwargs)
        elif ttype == 'raet':  # TODO:
            import salt.transport.raet
            return salt.transport.raet.RAETPubChannel(opts, **kwargs)
        elif ttype == 'local':  # TODO:
            import salt.transport.local
            return salt.transport.local.LocalPubChannel(opts, **kwargs)
        else:
            raise Exception('Channels are only defined for ZeroMQ and raet')
            # return NewKindOfChannel(opts, **kwargs)

    def recv(self, timeout=0):
        '''
        Get a pub job, with an optional timeout (0==forever)
        '''
        raise NotImplementedError()

    def recv_noblock(self):
        '''
        Get a pub job in a non-blocking manner.
        Return pub or None
        '''
        raise NotImplementedError()

    @property
    def socket(self):
        '''
        Return a socket (or fd) which can be used for poll mechanisms
        '''
        raise NotImplementedError()

# EOF
