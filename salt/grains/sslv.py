# -*- coding: utf-8 -*-
"""
Generate baseline proxy minion grains for sslv hosts.

"""

# Import Python Libs
from __future__ import absolute_import

import logging

import salt.proxy.sslv

# Import Salt Libs
import salt.utils.platform

__proxyenabled__ = ["sslv"]
__virtualname__ = "sslv"

log = logging.getLogger(__file__)

GRAINS_CACHE = {"os_family": "sslv"}


def __virtual__():
    try:
        if salt.utils.platform.is_proxy() and __opts__["proxy"]["proxytype"] == "sslv":
            return __virtualname__
    except KeyError:
        pass

    return False


def sslv(proxy=None):
    if not proxy:
        return {}
    if proxy["sslv.initialized"]() is False:
        return {}
    return {"sslv": proxy["sslv.grains"]()}
