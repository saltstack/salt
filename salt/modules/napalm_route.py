# -*- coding: utf-8 -*-
'''
NAPALM Route
============

Retrieves route details from network devices.

:codeauthor: Mircea Ulinic <mircea@cloudflare.com>
:maturity:   new
:depends:    napalm
:platform:   unix

Dependencies
------------
- :mod:`NAPALM proxy minion <salt.proxy.napalm>`

.. versionadded:: 2016.11.0
'''

from __future__ import absolute_import

import logging
log = logging.getLogger(__file__)


try:
    # will try to import NAPALM
    # https://github.com/napalm-automation/napalm
    # pylint: disable=W0611
    from napalm_base import get_network_driver
    # pylint: enable=W0611
    HAS_NAPALM = True
except ImportError:
    HAS_NAPALM = False

# ----------------------------------------------------------------------------------------------------------------------
# module properties
# ----------------------------------------------------------------------------------------------------------------------

__virtualname__ = 'route'
__proxyenabled__ = ['napalm']
# uses NAPALM-based proxy to interact with network devices

# ----------------------------------------------------------------------------------------------------------------------
# property functions
# ----------------------------------------------------------------------------------------------------------------------


def __virtual__():

    '''
    NAPALM library must be installed for this module to work.
    Also, the key proxymodule must be set in the __opts___ dictionary.
    '''

    if HAS_NAPALM and 'proxy' in __opts__:
        return __virtualname__
    else:
        return (False, 'The module napalm_route cannot be loaded: \
                napalm or proxy could not be loaded.')

# ----------------------------------------------------------------------------------------------------------------------
# helper functions -- will not be exported
# ----------------------------------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------------------------------
# callable functions
# ----------------------------------------------------------------------------------------------------------------------


def show(destination, protocol=None):

    '''
    Displays all details for a certain route learned via a specific protocol.

    :param destination: destination prefix.
    :param protocol: protocol used to learn the routes to the destination.

    CLI Example:

    .. code-block:: bash

        salt 'my_router' route.show 172.16.0.0/25 bgp

    Output example:

    .. code-block:: python

        {
            '172.16.0.0/25': [
                {
                    'protocol': 'BGP',
                    'last_active': True,
                    'current_active': True,
                    'age': 1178693,
                    'routing_table': 'inet.0',
                    'next_hop': '192.168.0.11',
                    'outgoing_interface': 'xe-1/1/1.100',
                    'preference': 170,
                    'selected_next_hop': False,
                    'protocol_attributes': {
                        'remote_as': 65001,
                        'metric': 5,
                        'local_as': 13335,
                        'as_path': '',
                        'remote_address': '192.168.0.11',
                        'metric2': 0,
                        'local_preference': 0,
                        'communities': [
                            '0:2',
                            'no-export'
                        ],
                        'preference2': -1
                    },
                    'inactive_reason': ''
                },
                {
                    'protocol': 'BGP',
                    'last_active': False,
                    'current_active': False,
                    'age': 2359429,
                    'routing_table': 'inet.0',
                    'next_hop': '192.168.0.17',
                    'outgoing_interface': 'xe-1/1/1.100',
                    'preference': 170,
                    'selected_next_hop': True,
                    'protocol_attributes': {
                        'remote_as': 65001,
                        'metric': 5,
                        'local_as': 13335,
                        'as_path': '',
                        'remote_address': '192.168.0.17',
                        'metric2': 0,
                        'local_preference': 0,
                        'communities': [
                            '0:3',
                            'no-export'
                        ],
                        'preference2': -1
                    },
                    'inactive_reason': 'Not Best in its group - Router ID'
                }
            ]
        }
    '''

    return __proxy__['napalm.call'](
        'get_route_to',
        **{
            'destination': destination,
            'protocol': protocol
        }
    )
