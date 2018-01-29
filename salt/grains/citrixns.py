# -*- coding: utf-8 -*-
'''
Generate baseline proxy minion grains for citrixns hosts.

'''

# Import Python Libs
from __future__ import absolute_import
import logging

# Import Salt Libs
import salt.utils.platform
import salt.proxy.citrixns

__proxyenabled__ = ['citrixns']
__virtualname__ = 'citrixns'

log = logging.getLogger(__file__)

GRAINS_CACHE = {'os_family': 'netscaler'}


def __virtual__():
    try:
        if salt.utils.platform.is_proxy() and __opts__['proxy']['proxytype'] == 'citrixns':
            return __virtualname__
    except KeyError:
        pass

    return False


def citrixns(proxy=None):
    if not proxy:
        return {}
    if proxy['citrixns.initialized']() is False:
        return {}
    return {'citrixns': proxy['citrixns.grains']()}
