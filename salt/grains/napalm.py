# -*- coding: utf-8 -*-
'''
NAPALM Grains
=============

:codeauthor: Mircea Ulinic <mircea@cloudflare.com>
:maturity:   new
:depends:    napalm
:platform:   unix

Dependencies
------------

- :doc:`NAPALM proxy module (salt.proxies.napalm) </ref/proxies/all/salt.proxies.napalm>`

.. versionadded: Carbon
'''

from __future__ import absolute_import

import logging
log = logging.getLogger(__name__)

# Salt lib
import salt.utils

# ----------------------------------------------------------------------------------------------------------------------
# grains properties
# ----------------------------------------------------------------------------------------------------------------------

__virtualname__ = 'napalm'
__proxyenabled__ = ['napalm']

# ----------------------------------------------------------------------------------------------------------------------
# global variables
# ----------------------------------------------------------------------------------------------------------------------

GRAINS_CACHE = {}

# ----------------------------------------------------------------------------------------------------------------------
# property functions
# ----------------------------------------------------------------------------------------------------------------------


def __virtual__():
    try:
        if salt.utils.is_proxy() and __opts__['proxy']['proxytype'] == 'napalm':
            return __virtualname__
    except KeyError:
        pass

    return False

# ----------------------------------------------------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------------------------------------------------


def _retrieve_grains(proxy):
    '''
    Retrieves the grains from the network device if not cached already.
    '''

    global GRAINS_CACHE

    if not GRAINS_CACHE:
        GRAINS_CACHE = proxy['napalm.grains']()

    return GRAINS_CACHE


def _get_grain(proxy, name):
    '''
    Retrieves the grain value from the cached dictionary.
    '''
    grains = _retrieve_grains(proxy)
    if grains.get('result', False) and grains.get('out', {}):
        return grains.get('out').get(name)

# ----------------------------------------------------------------------------------------------------------------------
# actual grains
# ----------------------------------------------------------------------------------------------------------------------


def getos():
    '''
    Returns the Operating System name running on the network device.

    Example: Junos
    '''
    # we have this in the pillar
    return {'os': __pillar__.get('proxy', {}).get('driver', '')}


def version(proxy):
    '''
    Returns the OS version.

    Example: 13.3R6.5
    '''
    if proxy:
        return {'version': _get_grain(proxy, 'os_version')}


def model(proxy):
    '''
    Returns the network device chassis model.

    Example: MX480
    '''
    if proxy:
        return {'model': _get_grain(proxy, 'model')}


def serial(proxy):
    '''
    Returns the chassis serial number.

    Example: FOX1234W00F
    '''
    if proxy:
        return {'serial': _get_grain(proxy, 'serial_number')}


def vendor(proxy):
    '''
    Returns the network device vendor.

    Example: Cisco
    '''
    if proxy:
        return {'vendor': _get_grain(proxy, 'vendor')}


def uptime(proxy):
    '''
    Returns the uptime in seconds.

    Example: 1234
    '''
    if proxy:
        return {'uptime': _get_grain(proxy, 'uptime')}


def interfaces(proxy):
    '''
    Returns the complete list of interfaces of the network device.

    Example: ['lc-0/0/0', 'pfe-0/0/0', 'xe-1/3/0', 'lo0', 'irb', 'demux0', 'fxp0']
    '''
    if proxy:
        return {'interfaces': _get_grain(proxy, 'interface_list')}
