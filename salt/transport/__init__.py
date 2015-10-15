# -*- coding: utf-8 -*-
'''
Encapsulate the different transports available to Salt.
'''
from __future__ import absolute_import


# for backwards compatibility
class Channel(object):
    @staticmethod
    def factory(opts, **kwargs):
        # Default to ZeroMQ for now
        ttype = 'zeromq'

        # determine the ttype
        if 'transport' in opts:
            ttype = opts['transport']
        elif 'transport' in opts.get('pillar', {}).get('master', {}):
            ttype = opts['pillar']['master']['transport']

        # the raet ioflo implementation still uses this channel, we need
        # this as compatibility
        if ttype == 'raet':
            import salt.transport.raet
            return salt.transport.raet.RAETReqChannel(opts, **kwargs)
        # TODO: deprecation warning, should use
        # salt.transport.channel.Channel.factory()
        from salt.transport.client import ReqChannel
        return ReqChannel.factory(opts, **kwargs)
