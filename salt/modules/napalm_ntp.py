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

.. versionadded: 2016.3
'''

from __future__ import absolute_import

import logging
log = logging.getLogger(__file__)

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
    return True

# ----------------------------------------------------------------------------------------------------------------------
# helper functions -- will not be exported
# ----------------------------------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------------------------------
# callable functions
# ----------------------------------------------------------------------------------------------------------------------


def peers(peer=''):

    """
    Returns a dictionary containing all NTP peers and synchronization details.
    :param peer: Returns only the details of a specific NTP peer.
    :return: a dictionary of NTP peers, each peer having the following details:

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

        salt '*' ntp.peers

    Example output:

    .. code-block:: python

        {
            u'188.114.101.4': {
                'referenceid'   : u'188.114.100.1',
                'stratum'       : 4,
                'type'          : u'-',
                'when'          : u'107',
                'hostpoll'      : 256,
                'reachability'  : 377,
                'delay'         : 164.228,
                'offset'        : -13.866,
                'jitter'        : 2.695
            }
        }
    """

    proxy_output = __proxy__['napalm.call'](
        'get_ntp_peers',
        **{
        }
    )

    if not proxy_output.get('result'):
        return proxy_output

    ntp_peers = proxy_output.get('out')

    if peer:
        ntp_peers = {peer: ntp_peers.get(peer)}

    proxy_output.update({
        'out': ntp_peers
    })

    return proxy_output


def set_peers(peers):

    """
    Configures a list of NTP peers on the device.
    :param peers: list of IP Addresses/Domain Names

    CLI Example:

    .. code-block:: bash

        salt '*' ntp.set_peers 192.168.0.1 172.17.17.1 time.apple.com
    """

    return __proxy__['napalm.call'](
        'load_template',
        **{
            'template_name': 'set_ntp_peers',
            'peers': peers
        }
    )


def delete_peers(peers):

    """
    Removes NTP peers configured on the device.
    :param peers: list of IP Addresses/Domain Names to be removed as NTP peers

    CLI Example:

    .. code-block:: bash

        salt '*' ntp.delete_peers 8.8.8.8 time.apple.com
    """

    return __proxy__['napalm.call'](
        'load_template',
        **{
            'template_name': 'delete_ntp_peers',
            'peers': peers
        }
    )
