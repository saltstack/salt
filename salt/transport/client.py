# -*- coding: utf-8 -*-
'''
Encapsulate the different transports available to Salt.

This includes client side transport, for the ReqServer and the Publisher
'''


class ReqChannel(object):
    '''
    Factory class to create a Sync communication channels to the ReqServer
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
            return salt.transport.zeromq.ZeroMQReqChannel(opts, **kwargs)
        elif ttype == 'raet':
            import salt.transport.raet
            return salt.transport.raet.RAETReqChannel(opts, **kwargs)
        elif ttype == 'tcp':
            import salt.transport.tcp
            return salt.transport.tcp.TCPReqChannel(opts, **kwargs)
        elif ttype == 'local':
            import salt.transport.local
            return salt.transport.local.LocalChannel(opts, **kwargs)
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

# TODO: better doc strings
class AsyncReqChannel(object):
    '''
    Factory class to create a Async communication channels to the ReqServer
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
            return salt.transport.zeromq.AsyncZeroMQReqChannel(opts, **kwargs)
        elif ttype == 'raet':
            import salt.transport.raet
            return salt.transport.raet.AsyncRAETReqChannel(opts, **kwargs)
        elif ttype == 'tcp':
            import salt.transport.tcp
            return salt.transport.tcp.AsyncTCPReqChannel(opts, **kwargs)
        elif ttype == 'local':
            import salt.transport.local
            return salt.transport.local.AsyncLocalChannel(opts, **kwargs)
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


class AsyncPubChannel(object):
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
            return salt.transport.zeromq.AsyncZeroMQPubChannel(opts, **kwargs)
        elif ttype == 'raet':  # TODO:
            import salt.transport.raet
            return salt.transport.raet.AsyncRAETPubChannel(opts, **kwargs)
        elif ttype == 'tcp':
            import salt.transport.tcp
            return salt.transport.tcp.AsyncTCPPubChannel(opts, **kwargs)
        elif ttype == 'local':  # TODO:
            import salt.transport.local
            return salt.transport.local.AsyncLocalPubChannel(opts, **kwargs)
        else:
            raise Exception('Channels are only defined for ZeroMQ and raet')
            # return NewKindOfChannel(opts, **kwargs)

    def connect(self):
        '''
        Return a future which completes when connected to the remote publisher
        '''
        raise NotImplementedError()

    def on_recv(self, callback):
        '''
        When jobs are recieved pass them (decoded) to callback
        '''
        raise NotImplementedError()

# EOF
