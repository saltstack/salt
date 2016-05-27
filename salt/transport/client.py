# -*- coding: utf-8 -*-
'''
Encapsulate the different transports available to Salt.

This includes client side transport, for the ReqServer and the Publisher
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Libs
from salt.utils.async import SyncWrapper


class ReqChannel(object):
    '''
    Factory class to create a Sync communication channels to the ReqServer
    '''
    @staticmethod
    def factory(opts, **kwargs):
        # All Sync interfaces are just wrappers around the Async ones
        sync = SyncWrapper(AsyncReqChannel.factory, (opts,), kwargs)
        return sync

    def send(self, load, tries=3, timeout=60, raw=False):
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


class PushChannel(object):
    '''
    Factory class to create Sync channel for push side of push/pull IPC
    '''
    @staticmethod
    def factory(opts, **kwargs):
        sync = SyncWrapper(AsyncPushChannel.factory, (opts,), kwargs)
        return sync

    def send(self, load, tries=3, timeout=60):
        '''
        Send load across IPC push
        '''
        raise NotImplementedError()


class PullChannel(object):
    '''
    Factory class to create Sync channel for pull side of push/pull IPC
    '''
    @staticmethod
    def factory(opts, **kwargs):
        sync = SyncWrapper(AsyncPullChannel.factory, (opts,), kwargs)
        return sync


# TODO: better doc strings
class AsyncChannel(object):
    '''
    Parent class for Async communication channels
    '''
    # Resolver is used by Tornado TCPClient.
    # This static field is shared between
    # AsyncReqChannel and AsyncPubChannel.
    # This will check to make sure the Resolver
    # is configured before first use.
    _resolver_configured = False

    @classmethod
    def _config_resolver(cls, num_threads=10):
        from tornado.netutil import Resolver
        Resolver.configure(
                'tornado.netutil.ThreadedResolver',
                num_threads=num_threads)
        cls._resolver_configured = True


# TODO: better doc strings
class AsyncReqChannel(AsyncChannel):
    '''
    Factory class to create a Async communication channels to the ReqServer
    '''
    @classmethod
    def factory(cls, opts, **kwargs):
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
            if not cls._resolver_configured:
                # TODO: add opt to specify number of resolver threads
                AsyncChannel._config_resolver()
            import salt.transport.tcp
            return salt.transport.tcp.AsyncTCPReqChannel(opts, **kwargs)
        elif ttype == 'local':
            import salt.transport.local
            return salt.transport.local.AsyncLocalChannel(opts, **kwargs)
        else:
            raise Exception('Channels are only defined for ZeroMQ and raet')
            # return NewKindOfChannel(opts, **kwargs)

    def send(self, load, tries=3, timeout=60, raw=False):
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


class AsyncPubChannel(AsyncChannel):
    '''
    Factory class to create subscription channels to the master's Publisher
    '''
    @classmethod
    def factory(cls, opts, **kwargs):
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
            if not cls._resolver_configured:
                # TODO: add opt to specify number of resolver threads
                AsyncChannel._config_resolver()
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
        When jobs are received pass them (decoded) to callback
        '''
        raise NotImplementedError()


class AsyncPushChannel(object):
    '''
    Factory class to create IPC Push channels
    '''
    @staticmethod
    def factory(opts, **kwargs):
        '''
        If we have additional IPC transports other than UxD and TCP, add them here
        '''
        # FIXME for now, just UXD
        # Obviously, this makes the factory approach pointless, but we'll extend later
        import salt.transport.ipc
        return salt.transport.ipc.IPCMessageClient(opts, **kwargs)


class AsyncPullChannel(object):
    '''
    Factory class to create IPC pull channels
    '''
    @staticmethod
    def factory(opts, **kwargs):
        '''
        If we have additional IPC transports other than UXD and TCP, add them here
        '''
        import salt.transport.ipc
        return salt.transport.ipc.IPCMessageServer(opts, **kwargs)

## Additional IPC messaging patterns should provide interfaces here, ala router/dealer, pub/sub, etc

# EOF
