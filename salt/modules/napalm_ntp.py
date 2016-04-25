# -*- coding: utf-8 -*-
'''
NAPALM NTP
===============

Manages NTP peers of a network device.

:codeauthor: Mircea Ulinic <mircea@cloudflare.com> & Jerome Fleury <jf@cloudflare.com>
:maturity:   new
:depends:    napalm
:platform:   linux

Dependencies
------------

- :doc:`napalm proxy minion (salt.proxy.napalm) </ref/proxy/all/salt.proxy.napalm>`

See also
--------

- :doc:`NTP peers management state (salt.states.netntp) </ref/states/all/salt.states.netntp>`

.. versionadded: Carbon
'''

from __future__ import absolute_import

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

__virtualname__ = 'ntp'
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
        return (False, 'The module NTP cannot be loaded: \
                napalm or proxy could not be loaded.')

# ----------------------------------------------------------------------------------------------------------------------
# helper functions -- will not be exported
# ----------------------------------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------------------------------
# callable functions
# ----------------------------------------------------------------------------------------------------------------------


def peers():

    '''
    Returns a list the NTP peers configured on the network device.

    :return: configured NTP peers as list.

    CLI Example:

    .. code-block:: bash

        salt '*' ntp.peers

    Example output:

    .. code-block:: python

        [
            '192.168.0.1',
            '172.17.17.1',
            '172.17.17.2',
            '2400:cb00:6:1024::c71b:840a'
        ]

    '''

    return __proxy__['napalm.call'](
        'get_ntp_peers',
        **{
        }
    )


def stats(peer=''):

    '''
    Returns a dictionary containing synchronization details of the NTP peers.

    :param peer: Returns only the details of a specific NTP peer.
    :return: a list of dictionaries, with the following keys:

        * referenceid
        * stratum
        * type
        * when
        * hostpoll
        * reachability
        * delay
        * offset
        * jitter

    CLI Example:

    .. code-block:: bash

        salt '*' ntp.stats

    Example output:

    .. code-block:: python

        [
            {
                'remote'        : u'188.114.101.4',
                'referenceid'   : u'188.114.100.1',
                'synchronized'  : True,
                'stratum'       : 4,
                'type'          : u'-',
                'when'          : u'107',
                'hostpoll'      : 256,
                'reachability'  : 377,
                'delay'         : 164.228,
                'offset'        : -13.866,
                'jitter'        : 2.695
            }
        ]
    '''

    proxy_output = __proxy__['napalm.call'](
        'get_ntp_stats',
        **{
        }
    )

    if not proxy_output.get('result'):
        return proxy_output

    ntp_peers = proxy_output.get('out')

    if peer:
        ntp_peers = [ntp_peer for ntp_peer in ntp_peers if ntp_peer.get('remote', '') == peer]

    proxy_output.update({
        'out': ntp_peers
    })

    return proxy_output


def set_peers(*peers):

    '''
    Configures a list of NTP peers on the device.

    :param peers: list of IP Addresses/Domain Names

    CLI Example:

    .. code-block:: bash

        salt '*' ntp.set_peers 192.168.0.1 172.17.17.1 time.apple.com
    '''

    return __proxy__['napalm.call'](
        'load_template',
        **{
            'template_name': 'set_ntp_peers',
            'peers': peers
        }
    )


def delete_peers(*peers):

    '''
    Removes NTP peers configured on the device.

    :param peers: list of IP Addresses/Domain Names to be removed as NTP peers

    CLI Example:

    .. code-block:: bash

        salt '*' ntp.delete_peers 8.8.8.8 time.apple.com
    '''

    return __proxy__['napalm.call'](
        'load_template',
        **{
            'template_name': 'delete_ntp_peers',
            'peers': peers
        }
    )
