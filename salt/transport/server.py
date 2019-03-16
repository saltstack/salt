# -*- coding: utf-8 -*-
'''
Encapsulate the different transports available to Salt.

This includes server side transport, for the ReqServer and the Publisher
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals


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
        elif ttype == 'tcp':
            import salt.transport.tcp
            return salt.transport.tcp.TCPReqServerChannel(opts)
        elif ttype == 'local':
            import salt.transport.local
            return salt.transport.local.LocalServerChannel(opts)
        else:
            raise Exception('Channels are only defined for ZeroMQ and TCP')
            # return NewKindOfChannel(opts, **kwargs)

    def pre_fork(self, process_manager):
        '''
        Do anything necessary pre-fork. Since this is on the master side this will
        primarily be bind and listen (or the equivalent for your network library)
        '''
        pass

    def post_fork(self, payload_handler, io_loop):
        '''
        Do anything you need post-fork. This should handle all incoming payloads
        and call payload_handler. You will also be passed io_loop, for all of your
        asynchronous needs
        '''
        pass


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
            return salt.transport.zeromq.ZeroMQPubServerChannel(opts, **kwargs)
        elif ttype == 'tcp':
            import salt.transport.tcp
            return salt.transport.tcp.TCPPubServerChannel(opts)
        elif ttype == 'local':  # TODO:
            import salt.transport.local
            return salt.transport.local.LocalPubServerChannel(opts, **kwargs)
        else:
            raise Exception('Channels are only defined for ZeroMQ and TCP')
            # return NewKindOfChannel(opts, **kwargs)

    def pre_fork(self, process_manager, kwargs=None):
        '''
        Do anything necessary pre-fork. Since this is on the master side this will
        primarily be used to create IPC channels and create our daemon process to
        do the actual publishing
        '''
        pass

    def publish(self, load):
        '''
        Publish "load" to minions
        '''
        raise NotImplementedError()

# EOF
