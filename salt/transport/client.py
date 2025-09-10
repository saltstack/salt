"""
Encapsulate the different transports available to Salt.

This includes client side transport, for the ReqServer and the Publisher


NOTE: This module has been deprecated and will be removed in Argon. Please use
salt.channel.server instead.
"""

import logging

from salt.utils.versions import warn_until

log = logging.getLogger(__name__)


class ReqChannel:
    """
    Factory class to create a sychronous communication channels to the master's
    ReqServer.
    """

    @staticmethod
    def factory(opts, **kwargs):
        import salt.channel.client

        warn_until(
            3008,
            "This module is deprecated. Please use salt.channel.client instead.",
        )
        return salt.channel.client.ReqChannel.factory(opts, **kwargs)


class PushChannel:
    """
    Factory class to create Sync channel for push side of push/pull IPC
    """

    @staticmethod
    def factory(opts, **kwargs):
        import salt.channel.client

        warn_until(
            3008,
            "This module is deprecated. Please use salt.channel.client instead.",
        )
        return salt.channel.client.PushChannel.factory(opts, **kwargs)


class PullChannel:
    """
    Factory class to create Sync channel for pull side of push/pull IPC
    """

    @staticmethod
    def factory(opts, **kwargs):
        import salt.channel.client

        warn_until(
            3008,
            "This module is deprecated. Please use salt.channel.client instead.",
        )
        return salt.channel.client.PullChannel.factory(opts, **kwargs)


class AsyncReqChannel:
    """
    Factory class to create a asynchronous communication channels to the
    master's ReqServer. ReqChannels connect to the master's ReqServerChannel on
    the minion's master_port (default: 4506) option.
    """

    @classmethod
    def factory(cls, opts, **kwargs):
        import salt.channel.client

        warn_until(
            3008,
            "This module is deprecated. Please use salt.channel.client instead.",
        )
        return salt.channel.client.AsyncReqChannel.factory(opts, **kwargs)


class AsyncPubChannel:
    """
    Factory class to create subscription channels to the master's Publisher
    """

    @classmethod
    def factory(cls, opts, **kwargs):
        import salt.channel.client

        warn_until(
            3008,
            "This module is deprecated. Please use salt.channel.client instead.",
        )
        return salt.channel.client.AsyncPubChannel.factory(opts, **kwargs)


class AsyncPushChannel:
    """
    Factory class to create IPC Push channels
    """

    @staticmethod
    def factory(opts, **kwargs):
        """
        If we have additional IPC transports other than UxD and TCP, add them here
        """
        import salt.channel.client

        warn_until(
            3008,
            "This module is deprecated. Please use salt.channel.client instead.",
        )
        return salt.channel.client.AsyncPushChannel.factory(opts, **kwargs)


class AsyncPullChannel:
    """
    Factory class to create IPC pull channels
    """

    @staticmethod
    def factory(opts, **kwargs):
        """
        If we have additional IPC transports other than UXD and TCP, add them here
        """
        import salt.channel.client

        warn_until(
            3008,
            "This module is deprecated. Please use salt.channel.client instead.",
        )
        return salt.channel.client.AsyncPullChannel.factory(opts, **kwargs)
