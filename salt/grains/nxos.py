# -*- coding: utf-8 -*-
'''
Generate baseline proxy minion grains for NXOS hosts.
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
