# -*- coding: utf-8 -*-
'''
Grains for Cisco NX OS Switches Proxy minions

.. versionadded: Carbon

For documentation on setting up the nxos proxy minion look in the documentation
for :doc:`salt.proxy.nxos</ref/proxy/all/salt.proxy.nxos>`.
'''
# Import Python Libs
from __future__ import absolute_import
import logging

# Import Salt Libs
import salt.utils
import salt.modules.nxos

__proxyenabled__ = ['nxos']
__virtualname__ = 'nxos'

__salt__ = {'nxos.cmd': salt.modules.nxos.cmd}


def __virtual__():
    try:
        if salt.utils.is_proxy() and __opts__['proxy']['proxytype'] == 'nxos':
            return __virtualname__
    except KeyError:
        pass

    return False


def nxos():
    return {'nxos': salt.modules.nxos.system_info(__opts__)}
