# -*- coding: utf-8 -*-

"""
THis module allows Salt interact with network devices via NAPALM library
(https://github.com/napalm-automation/napalm)
"""

from __future__ import absolute_import

import logging
log = logging.getLogger(__file__)

from napalm import get_network_driver

# ------------------------------------------------------------------------
# proxy properties
# ------------------------------------------------------------------------

__proxyenabled__ = ['napalm']
# proxy name

# ------------------------------------------------------------------------
# global variables
# ------------------------------------------------------------------------

NETWORK_DEVICE = {}

# ------------------------------------------------------------------------
# property functions
# ------------------------------------------------------------------------


def __virtual__():
    return True

# ------------------------------------------------------------------------
# helper functions -- will not be exported
# ------------------------------------------------------------------------

# ------------------------------------------------------------------------
# Salt specific proxy functions
# ------------------------------------------------------------------------


def init(opts):
    '''
    Perform any needed setup.
    '''
    NETWORK_DEVICE['HOSTNAME'] = opts.get('proxy', {}).get('host')
    NETWORK_DEVICE['USERNAME'] = opts.get('proxy', {}).get('username')
    NETWORK_DEVICE['PASSWORD'] = opts.get('proxy', {}).get('passwd')
    NETWORK_DEVICE['DRIVER_NAME'] = opts.get('proxy', {}).get('driver')

    NETWORK_DEVICE['UP'] = False

    _driver_ = get_network_driver(NETWORK_DEVICE.get('DRIVER_NAME'))
    # get driver object form NAPALM

    optional_args = {
        'config_lock': False  # to avoid locking config DB
    }

    try:
        NETWORK_DEVICE['DRIVER'] = _driver_(
            NETWORK_DEVICE.get('HOSTNAME', ''),
            NETWORK_DEVICE.get('USERNAME', ''),
            NETWORK_DEVICE.get('PASSWORD', ''),
            optional_args=optional_args
        )
        NETWORK_DEVICE.get('DRIVER').open()
        # no exception raised here, means connection established
        NETWORK_DEVICE['UP'] = True
    except Exception as error:
        log.error(
            "Cannot connect to {hostname} as {username}. Please check error: {error}".format(
                hostname=NETWORK_DEVICE.get('HOSTNAME', ''),
                username=NETWORK_DEVICE.get('USERNAME', ''),
                error=error
            )
        )

    return True


def ping():
    '''
    is the device responding ?
    '''
    return NETWORK_DEVICE['UP']


def shutdown(opts):
    '''
    use napalm close()
    '''
    try:
        if not NETWORK_DEVICE.get('UP', False):
            raise Exception('not connected!')
        NETWORK_DEVICE.get('DRIVER').close()
    except Exception as error:
        log.error(
            'Cannot close connection with {hostname}! Please check error: {error}'.format(
                hostname=NETWORK_DEVICE.get('HOSTNAME', '[unknown hostname]'),
                error=error
            )
        )

    return True

# ------------------------------------------------------------------------
# Callable functions
# ------------------------------------------------------------------------


def call(method, **params):

    """
    This function calls methods from the NAPALM driver object.
    Available methods:

    ============================== =====  =====   ======  =======  ======  ======  =====  =========
    _                               EOS   JunOS   IOS-XR  FortiOS  IBM     NXOS    IOS    Pluribus
    ============================== =====  =====   ======  =======  ======  ======  =====  =========
    **cli**                        |yes|  |yes|   |yes|   |no|     |no|    |yes|   |yes|  |yes|
    **get_facts**                  |yes|  |yes|   |yes|   |yes|    |no|    |yes|   |yes|  |yes|
    **get_interfaces**             |yes|  |yes|   |yes|   |yes|    |no|    |yes|   |yes|  |yes|
    **get_lldp_neighbors**         |yes|  |yes|   |yes|   |yes|    |no|    |no|    |yes|  |yes|
    **get_lldp_neighbors_detail**  |yes|  |yes|   |yes|   |no|     |no|    |yes|   |no|   |yes|
    **get_bgp_neighbors**          |yes|  |yes|   |yes|   |yes|    |no|    |no|    |yes|  |no|
    **get_bgp_neighbors_detail**   |yes|  |yes|   |no|    |no|     |no|    |no|    |no|   |no|
    **get_bgp_config**             |yes|  |yes|   |yes|   |no|     |no|    |no|    |no|   |no|
    **get_environment**            |yes|  |yes|   |yes|   |yes|    |no|    |no|    |yes|  |no|
    **get_mac_address_table**      |yes|  |yes|   |yes|   |no|     |no|    |yes|   |no|   |yes|
    **get_arp_table**              |yes|  |yes|   |yes|   |no|     |no|    |yes|   |no|   |no|
    **get_snmp_information**       |no|   |no|    |no|    |no|     |no|    |no|    |no|   |yes|
    **get_ntp_peers**              |yes|  |yes|   |yes|   |no|     |no|    |yes|   |no|   |yes|
    **get_interfaces_ip**          |yes|  |yes|   |yes|   |no|     |no|    |yes|   |yes|  |no|
    ============================== =====  =====   ======  =======  ======  ======  =====  =========

    For example::

    call('cli', **{
        'commands': [
            "show version",
            "show chassis fan"
        ]
    })

    """

    try:
        if not NETWORK_DEVICE.get('UP', False):
            raise Exception('not connected')
        # if connected will try to execute desired command
        return {
            'out': getattr(NETWORK_DEVICE.get('DRIVER'), method)(**params),
            'result': True,
            'comment': ''
        }
    except Exception as error:
        # either not connected
        # either unable to execute the command
        return {
            'out': {},
            'result': False,
            'comment': 'Cannot execute "{method}" on {device}. Reason: {error}!'.format(
                device=NETWORK_DEVICE.get('HOSTNAME', '[unspecified hostname]'),
                method=method,
                error=error
            )
        }
