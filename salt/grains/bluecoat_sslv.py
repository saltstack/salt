# -*- coding: utf-8 -*-
'''
Generate baseline proxy minion grains for bluecoat_sslv hosts.
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

# Import Salt Libs
import salt.utils.platform
import salt.proxy.bluecoat_sslv

__proxyenabled__ = ['bluecoat_sslv']
__virtualname__ = 'bluecoat_sslv'

log = logging.getLogger(__file__)

GRAINS_CACHE = {'os_family': 'bluecoat_sslv'}


def __virtual__():
    try:
        if salt.utils.platform.is_proxy() and __opts__['proxy']['proxytype'] == 'bluecoat_sslv':
            return __virtualname__
    except KeyError:
        pass

    return False


def bluecoat_sslv(proxy=None):
    if not proxy:
        return {}
    if proxy['bluecoat_sslv.initialized']() is False:
        return {}
    return {'bluecoat_sslv': proxy['bluecoat_sslv.grains']()}
