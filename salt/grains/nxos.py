# -*- coding: utf-8 -*-
'''
Grains for Cisco NX-OS minions

.. versionadded: 2016.11.0

For documentation on setting up the nxos proxy minion look in the documentation
for :mod:`salt.proxy.nxos<salt.proxy.nxos>`.
'''
# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.utils.platform
import salt.modules.nxos

import logging
log = logging.getLogger(__name__)

__proxyenabled__ = ['nxos']
__virtualname__ = 'nxos'


def __virtual__():
    return __virtualname__


def proxy_functions(proxy=None):
    '''
    The loader will execute functions with one argument and pass
    a reference to the proxymodules LazyLoader object.  However,
    grains sometimes get called before the LazyLoader object is setup
    so `proxy` might be None.
    '''
    try:
        return {'nxos': salt.modules.nxos.grains()}
    except NameError:
        return {}
