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

- :mod:`NAPALM proxy module <salt.proxies.napalm>`

.. versionadded:: 2016.11.0
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

    Example: junos, iosxr, eos, ios etc.

    CLI Example - select all network devices running JunOS:

    .. code-block:: bash

        salt -G 'os:junos' test.ping
    '''
    # we have this in the pillar
    return {'os': __pillar__.get('proxy', {}).get('driver', '')}


def version(proxy):
    '''
    Returns the OS version.

    Example: 13.3R6.5, 6.0.2 etc.

    CLI Example - select all network devices running JunOS 13.3R6.5 and return the model:

    .. code-block:: bash

        salt -G 'os:junos and version:13.3R6.5' grains.get model

    Output:

    .. code-block:: yaml

        edge01.bjm01:
            MX2000
        edge01.sjc01:
            MX960
        edge01.mrs01:
            MX480
        edge01.muc01:
            MX240
    '''
    if proxy:
        return {'version': _get_grain(proxy, 'os_version')}


def model(proxy):
    '''
    Returns the network device chassis model.

    Example: MX480, ASR-9904-AC etc.

    CLI Example - select all Juniper MX480 routers and execute traceroute to 8.8.8.8:

    .. code-block:: bash

        salt -G 'model:MX480' net.traceroute 8.8.8.8
    '''
    if proxy:
        return {'model': _get_grain(proxy, 'model')}


def serial(proxy):
    '''
    Returns the chassis serial number.

    Example: FOX1234W00F

    CLI Example - select all devices whose serial number begins with `FOX` and display the serial number value:

    .. code-block:: bash

        salt -G 'serial:FOX*' grains.get serial

    Output:

    .. code-block:: yaml

        edge01.icn01:
            FOXW00F001
        edge01.del01:
            FOXW00F002
        edge01.yyz01:
            FOXW00F003
        edge01.mrs01:
            FOXW00F004
    '''
    if proxy:
        return {'serial': _get_grain(proxy, 'serial_number')}


def vendor(proxy):
    '''
    Returns the network device vendor.

    Example: juniper, cisco, arista etc.

    CLI Example - select all devices produced by Cisco and shutdown:

    .. code-block:: bash

        salt -G 'vendor:cisco' net.cli "shut"
    '''
    if proxy:
        return {'vendor': _get_grain(proxy, 'vendor')}


def uptime(proxy):
    '''
    Returns the uptime in seconds.

    CLI Example - select all devices started/restarted within the last hour:

    .. code-block: bash

        salt -G 'uptime<3600' test.ping
    '''
    if proxy:
        return {'uptime': _get_grain(proxy, 'uptime')}


def interfaces(proxy):
    '''
    Returns the complete interfaces list of the network device.

    Example: ['lc-0/0/0', 'pfe-0/0/0', 'xe-1/3/0', 'lo0', 'irb', 'demux0', 'fxp0']

    CLI Example - select all devices that have a certain interface, e.g.: xe-1/1/1:

    .. code-block:: bash

        salt -G 'interfaces:xe-1/1/1' test.ping

    Output:

    .. code-block:: yaml

        edge01.yyz01:
            True
        edge01.maa01:
            True
        edge01.syd01:
            True
        edge01.del01:
            True
        edge01.dus01:
            True
        edge01.kix01:
            True
    '''
    if proxy:
        return {'interfaces': _get_grain(proxy, 'interface_list')}
