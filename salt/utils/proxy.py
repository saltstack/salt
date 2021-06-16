# -*- coding: utf-8 -*-
"""
Utils for proxy.
"""

from __future__ import absolute_import, print_function, unicode_literals

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
