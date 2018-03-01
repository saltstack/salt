# -*- coding: utf-8 -*-
'''
NAPALM BGP
==========

Manages BGP configuration on network devices and provides statistics.

:codeauthor: Mircea Ulinic <mircea@cloudflare.com> & Jerome Fleury <jf@cloudflare.com>
:maturity:   new
:depends:    napalm
:platform:   unix

Dependencies
------------

- :mod:`napalm proxy minion <salt.proxy.napalm>`

.. versionadded:: 2016.11.0
'''

from __future__ import absolute_import, unicode_literals, print_function

# Import python lib
import logging
log = logging.getLogger(__file__)

# import NAPALM utils
import salt.utils.napalm
from salt.utils.napalm import proxy_napalm_wrap

# ----------------------------------------------------------------------------------------------------------------------
# module properties
# ----------------------------------------------------------------------------------------------------------------------

__virtualname__ = 'bgp'
__proxyenabled__ = ['napalm']
# uses NAPALM-based proxy to interact with network devices

# ----------------------------------------------------------------------------------------------------------------------
# property functions
# ----------------------------------------------------------------------------------------------------------------------


def __virtual__():
    '''
    NAPALM library must be installed for this module to work and run in a (proxy) minion.
    '''
    return salt.utils.napalm.virtual(__opts__, __virtualname__, __file__)

# ----------------------------------------------------------------------------------------------------------------------
# helper functions -- will not be exported
# ----------------------------------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------------------------------
# callable functions
# ----------------------------------------------------------------------------------------------------------------------


@proxy_napalm_wrap
def config(group=None, neighbor=None, **kwargs):

    '''
    Provides the BGP configuration on the device.

    :param group: Name of the group selected to display the configuration.
    :param neighbor: IP Address of the neighbor to display the configuration.
    If the group parameter is not specified, the neighbor setting will be ignored.
    :return: A dictionary containing the BGP configuration from the network device.
    The keys of the main dictionary are the group names.

    Each group has the following properties:

        * type (string)
        * description (string)
        * apply_groups (string list)
        * multihop_ttl (int)
        * multipath (True/False)
        * local_address (string)
        * local_as (int)
        * remote_as (int)
        * import_policy (string)
        * export_policy (string)
        * remove_private_as (True/False)
        * prefix_limit (dictionary)
        * neighbors (dictionary)

    Each neighbor in the dictionary of neighbors provides:

        * description (string)
        * import_policy (string)
        * export_policy (string)
        * local_address (string)
        * local_as (int)
        * remote_as (int)
        * authentication_key (string)
        * prefix_limit (dictionary)
        * route_reflector_client (True/False)
        * nhs (True/False)

    CLI Example:

    .. code-block:: bash

        salt '*' bgp.config # entire BGP config
        salt '*' bgp.config PEERS-GROUP-NAME # provides detail only about BGP group PEERS-GROUP-NAME
        salt '*' bgp.config PEERS-GROUP-NAME 172.17.17.1 # provides details only about BGP neighbor 172.17.17.1,
        # configured in the group PEERS-GROUP-NAME

    Output Example:

    .. code-block:: python

        {
            'PEERS-GROUP-NAME':{
                'type'          : 'external',
                'description'   : 'Here we should have a nice description',
                'apply_groups'  : ['BGP-PREFIX-LIMIT'],
                'import_policy' : 'PUBLIC-PEER-IN',
                'export_policy' : 'PUBLIC-PEER-OUT',
                'remove_private': True,
                'multipath'     : True,
                'multihop_ttl'  : 30,
                'neighbors'     : {
                    '192.168.0.1': {
                        'description'   : 'Facebook [CDN]',
                        'prefix_limit'  : {
                            'inet': {
                                'unicast': {
                                    'limit': 100,
                                    'teardown': {
                                        'threshold' : 95,
                                        'timeout'   : 5
                                    }
                                }
                            }
                        }
                        'peer-as'        : 32934,
                        'route_reflector': False,
                        'nhs'            : True
                    },
                    '172.17.17.1': {
                        'description'   : 'Twitter [CDN]',
                        'prefix_limit'  : {
                            'inet': {
                                'unicast': {
                                    'limit': 500,
                                    'no-validate': 'IMPORT-FLOW-ROUTES'
                                }
                            }
                        }
                        'peer_as'        : 13414
                        'route_reflector': False,
                        'nhs'            : False
                    }
                }
            }
        }
    '''

    return salt.utils.napalm.call(
        napalm_device,  # pylint: disable=undefined-variable
        'get_bgp_config',
        **{
            'group': group,
            'neighbor': neighbor
        }
    )


@proxy_napalm_wrap
def neighbors(neighbor=None, **kwargs):

    '''
    Provides details regarding the BGP sessions configured on the network device.

    :param neighbor: IP Address of a specific neighbor.
    :return: A dictionary with the statistics of the all/selected BGP neighbors.
    Outer dictionary keys represent the VRF name.
    Keys of inner dictionary represent the AS numbers, while the values are lists of dictionaries,
    having the following keys:

        * up (True/False)
        * local_as (int)
        * remote_as (int)
        * local_address (string)
        * routing_table (string)
        * local_address_configured (True/False)
        * local_port (int)
        * remote_address (string)
        * remote_port (int)
        * multihop (True/False)
        * multipath (True/False)
        * remove_private_as (True/False)
        * import_policy (string)
        * export_policy (string)
        * input_messages (int)
        * output_messages (int)
        * input_updates (int)
        * output_updates (int)
        * messages_queued_out (int)
        * connection_state (string)
        * previous_connection_state (string)
        * last_event (string)
        * suppress_4byte_as (True/False)
        * local_as_prepend (True/False)
        * holdtime (int)
        * configured_holdtime (int)
        * keepalive (int)
        * configured_keepalive (int)
        * active_prefix_count (int)
        * received_prefix_count (int)
        * accepted_prefix_count (int)
        * suppressed_prefix_count (int)
        * advertised_prefix_count (int)
        * flap_count (int)

    CLI Example:

    .. code-block:: bash

        salt '*' bgp.neighbors  # all neighbors
        salt '*' bgp.neighbors 172.17.17.1  # only session with BGP neighbor(s) 172.17.17.1

    Output Example:

    .. code-block:: python

        {
            'default': {
                8121: [
                    {
                        'up'                        : True,
                        'local_as'                  : 13335,
                        'remote_as'                 : 8121,
                        'local_address'             : '172.101.76.1',
                        'local_address_configured'  : True,
                        'local_port'                : 179,
                        'remote_address'            : '192.247.78.0',
                        'router_id'                 : '192.168.0.1',
                        'remote_port'               : 58380,
                        'multihop'                  : False,
                        'import_policy'             : '4-NTT-TRANSIT-IN',
                        'export_policy'             : '4-NTT-TRANSIT-OUT',
                        'input_messages'            : 123,
                        'output_messages'           : 13,
                        'input_updates'             : 123,
                        'output_updates'            : 5,
                        'messages_queued_out'       : 23,
                        'connection_state'          : 'Established',
                        'previous_connection_state' : 'EstabSync',
                        'last_event'                : 'RecvKeepAlive',
                        'suppress_4byte_as'         : False,
                        'local_as_prepend'          : False,
                        'holdtime'                  : 90,
                        'configured_holdtime'       : 90,
                        'keepalive'                 : 30,
                        'configured_keepalive'      : 30,
                        'active_prefix_count'       : 132808,
                        'received_prefix_count'     : 566739,
                        'accepted_prefix_count'     : 566479,
                        'suppressed_prefix_count'   : 0,
                        'advertise_prefix_count'    : 0,
                        'flap_count'                : 27
                    }
                ]
            }
        }
    '''

    return salt.utils.napalm.call(
        napalm_device,  # pylint: disable=undefined-variable
        'get_bgp_neighbors_detail',
        **{
            'neighbor_address': neighbor
        }
    )
