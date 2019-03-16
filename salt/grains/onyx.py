# -*- coding: utf-8 -*-
'''
Grains for Onyx OS Switches Proxy minions

.. versionadded: Neon

For documentation on setting up the onyx proxy minion look in the documentation
for :mod:`salt.proxy.onyx<salt.proxy.onyx>`.
'''
# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import logging
import salt.utils.platform
import salt.modules.onyx

log = logging.getLogger(__name__)

__proxyenabled__ = ['onyx']
__virtualname__ = 'onyx'


def __virtual__():
    try:
        if salt.utils.platform.is_proxy() and __opts__['proxy']['proxytype'] == 'onyx':
            return __virtualname__
    except KeyError:
        pass

    return False


def proxy_functions(proxy=None):
    '''
        Proxy Initialization
    '''
    if proxy is None:
        return {}
    if proxy['onyx.initialized']() is False:
        return {}
    return {'onyx': proxy['onyx.grains']()}
