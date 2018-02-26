# -*- coding: utf-8 -*-
'''
Grains for Cisco NX OS Switches Proxy minions

.. versionadded: 2016.11.0

For documentation on setting up the nxos proxy minion look in the documentation
for :mod:`salt.proxy.nxos<salt.proxy.nxos>`.
'''
# Import Python Libs
from __future__ import absolute_import

# Import Salt Libs
import salt.utils
import salt.modules.nxos

import logging
log = logging.getLogger(__name__)

__proxyenabled__ = ['nxos']
__virtualname__ = 'nxos'


def __virtual__():
    try:
        if salt.utils.is_proxy() and __opts__['proxy']['proxytype'] == 'nxos':
            return __virtualname__
    except KeyError:
        pass

    return False


def proxy_functions(proxy=None):
    if proxy is None:
        return {}
    if proxy['nxos.initialized']() is False:
        return {}
    return {'nxos': proxy['nxos.grains']()}
