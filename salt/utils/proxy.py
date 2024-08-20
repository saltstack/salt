"""
Utils for proxy.
"""

import logging

import salt.utils.platform

log = logging.getLogger(__file__)


def is_proxytype(opts, proxytype):
    """
    Is this a proxy minion of type proxytype
    """
    return (
        salt.utils.platform.is_proxy()
        and opts.get("proxy", {}).get("proxytype", None) == proxytype
    )
