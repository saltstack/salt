"""
Encapsulate the different transports available to Salt.

This includes server side transport, for the ReqServer and the Publisher


NOTE: This module has been deprecated and will be removed in Argon. Please use
salt.channel.server instead.
"""

import logging

from salt.utils.versions import warn_until

log = logging.getLogger(__name__)


class ReqServerChannel:
    """
    ReqServerChannel handles request/reply messages from ReqChannels. The
    server listens on the master's ret_port (default: 4506) option.
    """

    @classmethod
    def factory(cls, opts, **kwargs):
        import salt.channel.server

        warn_until(
            "Argon",
            "This module is deprecated. Please use salt.channel.server instead.",
        )
        return salt.channel.server.ReqServerChannel.factory(opts, **kwargs)


class PubServerChannel:
    """
    Factory class to create subscription channels to the master's Publisher
    """

    @classmethod
    def factory(cls, opts, **kwargs):
        import salt.channel.server

        warn_until(
            "Argon",
            "This module is deprecated. Please use salt.channel.server instead.",
        )
        return salt.channel.server.PubServerChannel.factory(opts, **kwargs)
