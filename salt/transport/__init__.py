# -*- coding: utf-8 -*-
'''
Encapsulate the different transports available to Salt.  Currently this is only ZeroMQ.
'''
from __future__ import absolute_import

# for backwards compatibility
from salt.transport.channel import ReqChannel

class Channel(ReqChannel):
    @staticmethod
    def factory(opts, **kwargs):
        # TODO: deprecation warning, should use
        # salt.transport.channel.Channel.factory()
        return ReqChannel.factory(opts, **kwargs)
