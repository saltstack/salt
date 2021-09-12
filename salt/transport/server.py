"""
Encapsulate the different transports available to Salt.

This includes server side transport, for the ReqServer and the Publisher
"""
import logging

log = logging.getLogger(__name__)


class ReqServerChannel:
    """
    ReqServerChannel handles request/reply messages from ReqChannels. The
    server listens on the master's ret_port (default: 4506) option.
    """

    @classmethod
    def factory(cls, opts, **kwargs):
        import salt.channel.server

        return salt.channel.server.ReqServerChannel.factory(opts, **kwargs)


class PubServerChannel:
    """
    Factory class to create subscription channels to the master's Publisher
    """

    @classmethod
    def factory(cls, opts, **kwargs):
        import salt.channel.server

        return salt.channel.server.PubServerChannel.factory(opts, **kwargs)
