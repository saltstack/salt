"""
Encapsulate the different transports available to Salt.
"""


import logging
import warnings

log = logging.getLogger(__name__)

# Supress warnings when running with a very old pyzmq. This can be removed
# after we drop support for Ubuntu 16.04 and Debian 9
warnings.filterwarnings(
    "ignore", message="IOLoop.current expected instance.*", category=RuntimeWarning
)


def iter_transport_opts(opts):
    """
    Yield transport, opts for all master configured transports
    """
    transports = set()

    for transport, opts_overrides in opts.get("transport_opts", {}).items():
        t_opts = dict(opts)
        t_opts.update(opts_overrides)
        t_opts["transport"] = transport
        transports.add(transport)
        yield transport, t_opts

    if opts["transport"] not in transports:
        yield opts["transport"], opts


class MessageClientPool:
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
