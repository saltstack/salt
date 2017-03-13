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
import salt.utils.napalm

# ----------------------------------------------------------------------------------------------------------------------
# grains properties
# ----------------------------------------------------------------------------------------------------------------------

__virtualname__ = 'napalm'
__proxyenabled__ = ['napalm']

# ----------------------------------------------------------------------------------------------------------------------
# global variables
# ----------------------------------------------------------------------------------------------------------------------

GRAINS_CACHE = {}
DEVICE_CACHE = {}

_FORBIDDEN_OPT_ARGS = [
    'secret',  # used by IOS to enter in enable mode
    'enable_password'  # used by EOS
]

# ----------------------------------------------------------------------------------------------------------------------
# property functions
# ----------------------------------------------------------------------------------------------------------------------


def __virtual__():
    '''
    NAPALM library must be installed for this module to work and run in a (proxy) minion.
    '''
    return salt.utils.napalm.virtual(__opts__, __virtualname__, __file__)

# ----------------------------------------------------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------------------------------------------------


def _retrieve_grains_cache(proxy=None):
    '''
    Retrieves the grains from the network device if not cached already.
    '''
    global GRAINS_CACHE
    if not GRAINS_CACHE:
        if proxy and salt.utils.napalm.is_proxy(__opts__):
            # if proxy var passed and is NAPALM-type proxy minion
            GRAINS_CACHE = proxy['napalm.get_grains']()
        elif not proxy and salt.utils.napalm.is_minion(__opts__):
            # if proxy var not passed and is running in a straight minion
            GRAINS_CACHE = salt.utils.napalm.call(
                DEVICE_CACHE,
                'get_facts',
                **{}
            )
    return GRAINS_CACHE


def _retrieve_device_cache(proxy=None):
    '''
    Loads the network device details if not cached already.
    '''
    global DEVICE_CACHE
    if not DEVICE_CACHE:
        if proxy and salt.utils.napalm.is_proxy(__opts__):
            # if proxy var passed and is NAPALM-type proxy minion
            if 'napalm.get_device' in proxy:
                DEVICE_CACHE = proxy['napalm.get_device']()
        elif not proxy and salt.utils.napalm.is_minion(__opts__):
            # if proxy var not passed and is running in a straight minion
            DEVICE_CACHE = salt.utils.napalm.get_device(__opts__)
    return DEVICE_CACHE


def _get_grain(name, proxy=None):
    '''
    Retrieves the grain value from the cached dictionary.
    '''
    grains = _retrieve_grains_cache(proxy=proxy)
    if grains.get('result', False) and grains.get('out', {}):
        return grains.get('out').get(name)


def _get_device_grain(name, proxy=None):
    '''
    Retrieves device-specific grains.
    '''
    device = _retrieve_device_cache(proxy=proxy)
    return device.get(name.upper())

# ----------------------------------------------------------------------------------------------------------------------
# actual grains
# ----------------------------------------------------------------------------------------------------------------------


def getos(proxy=None):
    '''
    Returns the Operating System name running on the network device.

    Example: junos, iosxr, eos, ios etc.

    CLI Example - select all network devices running JunOS:

    .. code-block:: bash

        salt -G 'os:junos' test.ping
    '''
    return {'os': _get_device_grain('driver_name', proxy=proxy)}


def version(proxy=None):
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
    return {'version': _get_grain('os_version', proxy=proxy)}


def model(proxy=None):
    '''
    Returns the network device chassis model.

    Example: MX480, ASR-9904-AC etc.

    CLI Example - select all Juniper MX480 routers and execute traceroute to 8.8.8.8:

    .. code-block:: bash

        salt -G 'model:MX480' net.traceroute 8.8.8.8
    '''
    return {'model': _get_grain('model', proxy=proxy)}


def serial(proxy=None):
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
    return {'serial': _get_grain('serial_number', proxy=proxy)}


def vendor(proxy=None):
    '''
    Returns the network device vendor.

    Example: juniper, cisco, arista etc.

    CLI Example - select all devices produced by Cisco and shutdown:

    .. code-block:: bash

        salt -G 'vendor:cisco' net.cli "shut"
    '''
    return {'vendor': _get_grain('vendor', proxy=proxy)}


def uptime(proxy=None):
    '''
    Returns the uptime in seconds.

    CLI Example - select all devices started/restarted within the last hour:

    .. code-block: bash

        salt -G 'uptime<3600' test.ping
    '''
    return {'uptime': _get_grain('uptime', proxy=proxy)}


def interfaces(proxy=None):
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
    return {'interfaces': _get_grain('interface_list', proxy=proxy)}


def username(proxy=None):
    '''
    Return the username.

    .. versionadded:: Nitrogen

    CLI Example - select all devices using `foobar` as username for connection:

    .. code-block:: bash

        salt -G 'username:foobar' test.ping

    Output:

    .. code-block::yaml

        device1:
            True
        device2:
            True
    '''
    if proxy and salt.utils.napalm.is_proxy(__opts__):
        # only if proxy will override the username
        # otherwise will use the default Salt grains
        return {'username': _get_device_grain('username', proxy=proxy)}


def hostname(proxy=None):
    '''
    Return the hostname as configured on the network device.

    CLI Example:

    .. code-block:: bash

        salt 'device*' grains.get hostname

    Output:

    .. code-block:: yaml

        device1:
            edge01.yyz01
        device2:
            edge01.bjm01
        device3:
            edge01.flw01
    '''
    return {'hostname': _get_grain('hostname', proxy=proxy)}


def host(proxy=None):
    '''
    This grain is set by the NAPALM grain module
    only when running in a proxy minion.
    When Salt is installed directly on the network device,
    thus running a regular minion, the ``host`` grain
    provides the physical hostname of the network device,
    as it would be on an ordinary minion server.
    When running in a proxy minion, ``host`` points to the
    value configured in the pillar: :mod:`NAPALM proxy module <salt.proxies.napalm>`.

    .. note::

        The diference betwen ``host`` and ``hostname`` is that
        ``host`` provides the physical location - either domain name or IP address,
        while ``hostname`` provides the hostname as configured on the device.
        They are not necessarily the same.

    .. versionadded:: Nitrogen

    CLI Example:

    .. code-block:: bash

        salt 'device*' grains.get host

    Output:

    .. code-block:: yaml

        device1:
            ip-172-31-13-136.us-east-2.compute.internal
        device2:
            ip-172-31-11-193.us-east-2.compute.internal
        device3:
            ip-172-31-2-181.us-east-2.compute.internal
    '''
    if proxy and salt.utils.napalm.is_proxy(__opts__):
        # this grain is set only when running in a proxy minion
        # otherwise will use the default Salt grains
        return {'host': _get_device_grain('hostname', proxy=proxy)}


def optional_args(proxy=None):
    '''
    Return the connection optional args.

    .. note::

        Sensible data will not be returned.

    .. versionadded:: Nitrogen

    CLI Example - select all devices connecting via port 1234:

    .. code-block:: bash

        salt -G 'optional_args:port:1234' test.ping

    Output:

    .. code-block:: yaml

        device1:
            True
        device2:
            True
    '''
    opt_args = _get_device_grain('optional_args', proxy=proxy)
    if _FORBIDDEN_OPT_ARGS:
        for arg in _FORBIDDEN_OPT_ARGS:
            opt_args.pop(arg, None)
    return {'optional_args': opt_args}
