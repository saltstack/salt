"""
NAPALM Route
============

Retrieves route details from network devices.

:codeauthor: Mircea Ulinic <ping@mirceaulinic.net>
:maturity:   new
:depends:    napalm
:platform:   unix

Dependencies
------------
- :mod:`NAPALM proxy minion <salt.proxy.napalm>`

.. versionadded:: 2016.11.0
"""

import logging

# import NAPALM utils
import salt.utils.napalm
from salt.utils.napalm import proxy_napalm_wrap

log = logging.getLogger(__file__)


# ----------------------------------------------------------------------------------------------------------------------
# module properties
# ----------------------------------------------------------------------------------------------------------------------

__virtualname__ = "route"
__proxyenabled__ = ["napalm"]
# uses NAPALM-based proxy to interact with network devices
__virtual_aliases__ = ("napalm_route",)

# ----------------------------------------------------------------------------------------------------------------------
# property functions
# ----------------------------------------------------------------------------------------------------------------------


def __virtual__():
    """
    NAPALM library must be installed for this module to work and run in a (proxy) minion.
    """
    return salt.utils.napalm.virtual(__opts__, __virtualname__, __file__)


# ----------------------------------------------------------------------------------------------------------------------
# helper functions -- will not be exported
# ----------------------------------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------------------------------
# callable functions
# ----------------------------------------------------------------------------------------------------------------------


@proxy_napalm_wrap
def show(destination, protocol=None, **kwargs):  # pylint: disable=unused-argument
    """
    Displays all details for a certain route learned via a specific protocol.
    If the protocol is not specified, will return all possible routes.

    .. note::

        This function return the routes from the RIB.
        In case the destination prefix is too short,
        there may be too many routes matched.
        Therefore in cases of devices having a very high number of routes
        it may be necessary to adjust the prefix length and request
        using a longer prefix.

    destination
        destination prefix.

    protocol (optional)
        protocol used to learn the routes to the destination.

    .. versionchanged:: 2017.7.0

    CLI Example:

    .. code-block:: bash

        salt 'my_router' route.show 172.16.0.0/25
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
    """

    return salt.utils.napalm.call(
        napalm_device,  # pylint: disable=undefined-variable
        "get_route_to",
        **{"destination": destination, "protocol": protocol}
    )
