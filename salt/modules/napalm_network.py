# -*- coding: utf-8 -*-
'''
Basic functions from Napalm library
'''

from __future__ import absolute_import

import logging
log = logging.getLogger(__name__)

# ------------------------------------------------------------------------
# module properties
# ------------------------------------------------------------------------

__virtualname__ = 'net'
__proxyenabled__ = ['napalm']
# uses NAPALM-based proxy to interact with network devices

# ------------------------------------------------------------------------
# property functions
# ------------------------------------------------------------------------


def __virtual__():
    return True

# ------------------------------------------------------------------------
# helper functions -- will not be exported
# ------------------------------------------------------------------------


def _filter_list(input_list, search_key, search_value):

    output_list = list()

    for dictionary in input_list:
        if dictionary.get(search_key) == search_value:
            output_list.append(dictionary)

    return output_list


def _filter_dict(input_dict, search_key, search_value):

    output_dict = dict()

    for key, key_list in input_dict.iteritems():
        key_list_filtered = _filter_list(key_list, search_key, search_value)
        if key_list_filtered:
            output_dict[key] = key_list_filtered

    return output_dict

# ------------------------------------------------------------------------
# callable functions
# ------------------------------------------------------------------------


def ping():
    '''
    is the device alive ?

    CLI example:

    .. code-block:: bash

        salt myminion net.ping
    '''

    return {
        'out': __proxy__['napalm.ping']()
    }


def cli(*commands):

    """
    NAPALM returns a dictionary with the output of all commands passed as arguments:

    CLI example:

    .. code-block:: bash

        salt myminion net.cli "show version" "show route 8.8.8.8"

    :param commands: list of raw commands to execute on device

    Example:
        {
            u'show version and haiku'  :  u'''Hostname: re0.edge01.arn01
                                              Model: mx480
                                              Junos: 13.3R6.5
                                                   Help me, Obi-Wan
                                                   I just saw Episode Two
                                                   You're my only hope
                                           ''',
            u'show chassis fan'        :   u'''Item                      Status   RPM     Measurement
                                               Top Rear Fan              OK       3840    Spinning at intermediate-speed
                                               Bottom Rear Fan           OK       3840    Spinning at intermediate-speed
                                               Top Middle Fan            OK       3900    Spinning at intermediate-speed
                                               Bottom Middle Fan         OK       3840    Spinning at intermediate-speed
                                               Top Front Fan             OK       3810    Spinning at intermediate-speed
                                               Bottom Front Fan          OK       3840    Spinning at intermediate-speed
                                           '''
        }
    """

    return __proxy__['napalm.call'](
        'cli',
        **{
            'commands': list(commands)
        }
    )
    # thus we can display the output as is
    # in case of errors, they'll be catched in the proxy


def arp(interface='', ipaddr='', macaddr=''):

    """
    NAPALM returns a list of dictionaries with details of the ARP entries:
    [{INTERFACE, MAC, IP, AGE}]

    CLI example:

    .. code-block:: bash

        salt myminion net.arp
        salt myminion net.arp macaddr='5c:5e:ab:da:3c:f0'

    :param interface: interface name to filter on
    :param ipaddr: IP address to filter on
    :param macaddr: MAC address to filter on

    Example output:
        [
            {
                'interface' : 'MgmtEth0/RSP0/CPU0/0',
                'mac'       : '5c:5e:ab:da:3c:f0',
                'ip'        : '172.17.17.1',
                'age'       : 1454496274.84
            },
            {
                'interface': 'MgmtEth0/RSP0/CPU0/0',
                'mac'       : '66:0e:94:96:e0:ff',
                'ip'        : '172.17.17.2',
                'age'       : 1435641582.49
            }
        ]
    """

    proxy_output = __proxy__['napalm.call'](
        'get_arp_table',
        **{
        }
    )

    if not proxy_output.get('result'):
        return proxy_output

    arp_table = proxy_output.get('out')

    if interface:
        arp_table = _filter_list(arp_table, 'interface', interface)

    if ipaddr:
        arp_table = _filter_list(arp_table, 'ip', ipaddr)

    if macaddr:
        arp_table = _filter_list(arp_table, 'mac', macaddr)

    proxy_output.update({
        'out': arp_table
    })

    return proxy_output


def ipaddrs():
    '''
    Returns IP addresses on the device

    CLI example:

    .. code-block:: bash

        salt myminion net.ipaddrs
    '''
    return __proxy__['napalm.call'](
        'get_interfaces_ip',
        **{
        }
    )


def lldp(interface=''):

    """
    returns LLDP neighbors

    CLI example:

    .. code-block:: bash

        salt myminion net.lldp
        salt myminion net.lldp interface='TenGigE0/0/0/8'

    :param interface: interface name to filter on

    Example output:
        {
            'TenGigE0/0/0/8': [
                {
                    'parent_interface': u'Bundle-Ether8',
                    'interface_description': u'TenGigE0/0/0/8',
                    'remote_chassis_id': u'8c60.4f69.e96c',
                    'remote_system_name': u'switch',
                    'remote_port': u'Eth2/2/1',
                    'remote_port_description': u'Ethernet2/2/1',
                    'remote_system_description': u'''Cisco Nexus Operating System (NX-OS) Software 7.1(0)N1(1a)
                          TAC support: http://www.cisco.com/tac
                          Copyright (c) 2002-2015, Cisco Systems, Inc. All rights reserved.''',
                    'remote_system_capab': u'B, R',
                    'remote_system_enable_capab': u'B'
                }
            ]
        }
    """

    proxy_output = __proxy__['napalm.call'](
        'get_lldp_neighbors_detail',
        **{
        }
    )

    if not proxy_output.get('result'):
        return proxy_output

    lldp_neighbors = proxy_output.get('out')

    if interface:
        lldp_neighbors = {interface: lldp_neighbors.get(interface)}

    proxy_output.update({
        'out': lldp_neighbors
    })

    return proxy_output


def mac(address='', interface='', vlan=0):

    """
    returns device MAC address table

    CLI example:

    .. code-block:: bash

        salt myminion net.mac
        salt myminion net.mac vlan=10

    :param address: MAC address to filter on
    :param interface: interface name to filter on
    :param vlan: vlan identifier

    Example output:
            [
                {
                    'mac'       : '00:1c:58:29:4a:71',
                    'interface' : 'xe-3/0/2',
                    'static'    : False,
                    'active'    : True,
                    'moves'     : 1,
                    'vlan'      : 10,
                    'last_move' : 1454417742.58
                },
                {
                    'mac'       : '8c:60:4f:58:e1:c1',
                    'interface' : 'xe-1/0/1',
                    'static'    : False,
                    'active'    : True,
                    'moves'     : 2,
                    'vlan'      : 42,
                    'last_move' : 1453191948.11
                }
            ]

    """

    proxy_output = __proxy__['napalm.call'](
        'get_mac_address_table',
        **{
        }
    )

    if not proxy_output.get('result'):
        # if negative, leave the output unchanged
        return proxy_output

    mac_address_table = proxy_output.get('out')

    if vlan and isinstance(int, vlan):
        mac_address_table = {vlan: mac_address_table.get(vlan)}

    if address:
        mac_address_table = _filter_dict(mac_address_table, 'mac', address)

    if interface:
        mac_address_table = _filter_dict(mac_address_table, 'interface', interface)

    proxy_output.update({
        'out': mac_address_table
    })

    return proxy_output
