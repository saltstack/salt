# -*- coding: utf-8 -*-
'''
NAPALM BGP
==========

Manages BGP configuration on network devices and provides statistics.

:codeauthor: Mircea Ulinic <mircea@cloudflare.com> & Jerome Fleury <jf@cloudflare.com>
:maturity:   new
:depends:    napalm
:platform:   linux

Dependencies
------------

- :doc:`napalm proxy minion (salt.proxy.napalm) </ref/proxy/all/salt.proxy.napalm>`

.. versionadded: Carbon
'''

from __future__ import absolute_import

# Import python lib
import logging
log = logging.getLogger(__file__)


try:
    # will try to import NAPALM
    # https://github.com/napalm-automation/napalm
    # pylint: disable=W0611
    from napalm import get_network_driver
    # pylint: enable=W0611
    HAS_NAPALM = True
except ImportError:
    HAS_NAPALM = False

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
    NAPALM library must be installed for this module to work.
    Also, the key proxymodule must be set in the __opts___ dictionary.
    '''

    if HAS_NAPALM and 'proxy' in __opts__:
        return __virtualname__
    else:
        return (False, 'The module napalm_bgp (BGP) cannot be loaded: \
                napalm lib or proxy could not be loaded.')

# ----------------------------------------------------------------------------------------------------------------------
# helper functions -- will not be exported
# ----------------------------------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------------------------------
# callable functions
# ----------------------------------------------------------------------------------------------------------------------


def config(group='', neighbor=''):

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
                'type'          : u'external',
                'description'   : u'Here we should have a nice description',
                'apply_groups'  : [u'BGP-PREFIX-LIMIT'],
                'import_policy' : u'PUBLIC-PEER-IN',
                'export_policy' : u'PUBLIC-PEER-OUT',
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

    return __proxy__['napalm.call'](
        'get_bgp_config',
        **{
            'group': group,
            'neighbor': neighbor
        }
    )


def neighbors(neighbor=''):

    '''
    Provides details regarding the BGP sessions configured on the network device.

    :param neighbor: IP Address of a specific neighbor.
    :return: A dictionary with the statistics of the selected BGP neighbors.
    Keys of this dictionary represent the AS numbers, while the values are lists of dictionaries,
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

        salt '*' bgp.neighbors # all neighbors
        salt '*' bgp.neighbors 172.17.17.1 # only session with BGP neighbor(s) 172.17.17.1

    Output Example:

    .. code-block:: python

        {
            8121: [
                {
                    'up'                        : True,
                    'local_as'                  : 13335,
                    'remote_as'                 : 8121,
                    'local_address'             : u'172.101.76.1',
                    'local_address_configured'  : True,
                    'local_port'                : 179,
                    'remote_address'            : u'192.247.78.0',
                    'remote_port'               : 58380,
                    'multihop'                  : False,
                    'import_policy'             : u'4-NTT-TRANSIT-IN',
                    'export_policy'             : u'4-NTT-TRANSIT-OUT',
                    'input_messages'            : 123,
                    'output_messages'           : 13,
                    'input_updates'             : 123,
                    'output_updates'            : 5,
                    'messages_queued_out'       : 23,
                    'connection_state'          : u'Established',
                    'previous_connection_state' : u'EstabSync',
                    'last_event'                : u'RecvKeepAlive',
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
    '''

    return __proxy__['napalm.call'](
        'get_bgp_neighbors_detail',
        **{
            'neighbor_address': neighbor
        }
    )
