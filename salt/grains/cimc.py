# -*- coding: utf-8 -*-
'''
Generate baseline proxy minion grains for cimc hosts.

'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

# Import Salt Libs
import salt.utils.platform
import salt.proxy.cimc

__proxyenabled__ = ['cimc']
__virtualname__ = 'cimc'

log = logging.getLogger(__file__)

GRAINS_CACHE = {'os_family': 'Cisco UCS'}


def __virtual__():
    try:
        if salt.utils.platform.is_proxy() and __opts__['proxy']['proxytype'] == 'cimc':
            return __virtualname__
    except KeyError:
        pass

    return False


def cimc(proxy=None):
    if not proxy:
        return {}
    if proxy['cimc.initialized']() is False:
        return {}
    return {'cimc': proxy['cimc.grains']()}
