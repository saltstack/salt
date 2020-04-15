# -*- coding: utf-8 -*-
"""
Encapsulate the different transports available to Salt.
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import Salt libs
import salt.utils.versions

# Import third party libs
from salt.ext import six
from salt.ext.six.moves import range

log = logging.getLogger(__name__)


def iter_transport_opts(opts):
    """
    Yield transport, opts for all master configured transports
    """
    transports = set()

    for transport, opts_overrides in six.iteritems(opts.get("transport_opts", {})):
        t_opts = dict(opts)
        t_opts.update(opts_overrides)
        t_opts["transport"] = transport
        transports.add(transport)
        yield transport, t_opts

    if opts["transport"] not in transports:
        yield opts["transport"], opts


# for backwards compatibility
class Channel(object):
    @staticmethod
    def factory(opts, **kwargs):
        salt.utils.versions.warn_until(
            "Sodium",
            "Stop using salt.transport.Channel and instead use salt.transport.client.ReqChannel",
            stacklevel=3,
        )
        from salt.transport.client import ReqChannel

        return ReqChannel.factory(opts, **kwargs)


class MessageClientPool(object):
    def __init__(self, tgt, opts, args=None, kwargs=None):
        sock_pool_size = opts["sock_pool_size"] if "sock_pool_size" in opts else 1
        if sock_pool_size < 1:
            log.warning(
                "sock_pool_size is not correctly set, the option should be "
                "greater than 0 but is instead %s",
                sock_pool_size,
            )
            sock_pool_size = 1

        if args is None:
            args = ()
        if kwargs is None:
            kwargs = {}

        self.message_clients = [tgt(*args, **kwargs) for _ in range(sock_pool_size)]
