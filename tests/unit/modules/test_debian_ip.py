# -*- coding: utf-8 -*-
"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import tempfile
from collections import OrderedDict as odict

# Import third party libs
import jinja2.exceptions

# Import Salt Libs
import salt.modules.debian_ip as debian_ip
import salt.utils

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase, skipIf

# Big pile of interface data for unit tests
#   To skip, search for 'DebianIpTestCase'
# fmt: off
test_interfaces = [
        # Structure
        #{'iface_name': 'ethX', 'iface_type': 'eth', 'enabled': True,
        #    'skip_test': bool(),        # True to disable this test
        #    'build_interface': dict(),  # data read from sls
        #    'get_interface(): OrderedDict(),   # data read from interfaces file
        #    'return': list()},          # jinja-rendered data

        # IPv4-only interface; single address
        {'iface_name': 'eth1', 'iface_type': 'eth', 'enabled': True,
            'build_interface': {
                'proto': 'static',
                'ipaddr': '192.168.4.9',
                'netmask': '255.255.255.0',
                'gateway': '192.168.4.1',
                'enable_ipv6': False,
                'noifupdown': True,
                },
            'get_interface': odict([('eth1', odict([('enabled', True), ('data', odict([
                ('inet', odict([
                    ('addrfam', 'inet'),
                    ('proto', 'static'),
                    ('filename', None),
                    ('address', '192.168.4.9'),
                    ('netmask', '255.255.255.0'),
                    ('gateway', '192.168.4.1'),
                    ])),
                ]))]))]),
            'return': [
                'auto eth1\n',
                'iface eth1 inet static\n',
                '    address 192.168.4.9\n',
                '    netmask 255.255.255.0\n',
                '    gateway 192.168.4.1\n',
                '\n']},

        # IPv6-only; single address
        {'iface_name': 'eth2', 'iface_type': 'eth', 'enabled': True,
            'build_interface': {
                'ipv6proto': 'static',
                'ipv6ipaddr': '2001:db8:dead:beef::3',
                'ipv6netmask': '64',
                'ipv6gateway': '2001:db8:dead:beef::1',
                'enable_ipv6': True,
                'noifupdown': True,
                },
            'get_interface': odict([('eth2', odict([('enabled', True), ('data', odict([
                ('inet6', odict([
                    ('addrfam', 'inet6'),
                    ('proto', 'static'),
                    ('filename', None),
                    ('address', '2001:db8:dead:beef::3'),
                    ('netmask', 64),
                    ('gateway', '2001:db8:dead:beef::1'),
                    ])),
                ]))]))]),
            'return': [
                'auto eth2\n',
                'iface eth2 inet6 static\n',
                '    address 2001:db8:dead:beef::3\n',
                '    netmask 64\n',
                '    gateway 2001:db8:dead:beef::1\n',
                '\n']},

        # IPv6-only; multiple addrs; no gw; first addr from ipv6addr
        {'iface_name': 'eth3', 'iface_type': 'eth', 'enabled': True,
            'build_interface': {
                'ipv6proto': 'static',
                'ipv6ipaddr': '2001:db8:dead:beef::5/64',
                'ipv6ipaddrs': [
                    '2001:db8:dead:beef::7/64',
                    '2001:db8:dead:beef::8/64',
                    '2001:db8:dead:beef::9/64'],
                'enable_ipv6': True,
                'noifupdown': True,
                },
            'get_interface': odict([('eth3', odict([('enabled', True), ('data', odict([
                ('inet6', odict([
                    ('addrfam', 'inet6'),
                    ('proto', 'static'),
                    ('filename', None),
                    ('address', '2001:db8:dead:beef::5/64'),
                    ('addresses', [
                        '2001:db8:dead:beef::7/64',
                        '2001:db8:dead:beef::8/64',
                        '2001:db8:dead:beef::9/64',
                        ]),
                    ])),
                ]))]))]),
            'return': [
                'auto eth3\n',
                'iface eth3 inet6 static\n',
                '    address 2001:db8:dead:beef::5/64\n',
                '    address 2001:db8:dead:beef::7/64\n',
                '    address 2001:db8:dead:beef::8/64\n',
                '    address 2001:db8:dead:beef::9/64\n',
                '\n']},

        # IPv6-only; multiple addresses
        {'iface_name': 'eth4', 'iface_type': 'eth', 'enabled': True,
            'build_interface': {
                'ipv6proto': 'static',
                'ipv6ipaddrs': [
                    '2001:db8:dead:beef::5/64',
                    '2001:db8:dead:beef::7/64',
                    '2001:db8:dead:beef::8/64',
                    '2001:db8:dead:beef::9/64'],
                'ipv6gateway': '2001:db8:dead:beef::1',
                'enable_ipv6': True,
                'noifupdown': True,
                },
            'get_interface': odict([('eth4', odict([('enabled', True), ('data', odict([
                ('inet6', odict([
                    ('addrfam', 'inet6'),
                    ('proto', 'static'),
                    ('filename', None),
                    ('address', '2001:db8:dead:beef::5/64'),
                    ('addresses', [
                        '2001:db8:dead:beef::7/64',
                        '2001:db8:dead:beef::8/64',
                        '2001:db8:dead:beef::9/64',
                        ]),
                    ('gateway', '2001:db8:dead:beef::1'),
                    ])),
                ]))]))]),
            'return': [
                'auto eth4\n',
                'iface eth4 inet6 static\n',
                '    address 2001:db8:dead:beef::5/64\n',
                '    address 2001:db8:dead:beef::7/64\n',
                '    address 2001:db8:dead:beef::8/64\n',
                '    address 2001:db8:dead:beef::9/64\n',
                '    gateway 2001:db8:dead:beef::1\n',
                '\n']},

        # IPv4 and IPv6 settings with v4 disabled
        {'iface_name': 'eth5', 'iface_type': 'eth', 'enabled': True,
            'build_interface': {
                'proto': 'static',
                'ipaddr': '192.168.4.9',
                'netmask': '255.255.255.0',
                'gateway': '192.168.4.1',
                'ipv6proto': 'static',
                'ipv6ipaddr': '2001:db8:dead:beef::3',
                'ipv6netmask': '64',
                'ipv6gateway': '2001:db8:dead:beef::1',
                'enable_ipv4': False,
                'noifupdown': True,
                },
            'get_interface': odict([('eth5', odict([('enabled', True), ('data', odict([
                ('inet6', odict([
                    ('addrfam', 'inet6'),
                    ('proto', 'static'),
                    ('filename', None),
                    ('address', '2001:db8:dead:beef::3'),
                    ('netmask', 64),
                    ('gateway', '2001:db8:dead:beef::1'),
                    ])),
                ]))]))]),
            'return': [
                'auto eth5\n',
                'iface eth5 inet6 static\n',
                '    address 2001:db8:dead:beef::3\n',
                '    netmask 64\n',
                '    gateway 2001:db8:dead:beef::1\n',
                '\n']},

        # IPv4 and IPv6 settings with v6 disabled
        {'iface_name': 'eth6', 'iface_type': 'eth', 'enabled': True,
            'build_interface': {
                'proto': 'static',
                'ipaddr': '192.168.4.9',
                'netmask': '255.255.255.0',
                'gateway': '192.168.4.1',
                'ipv6proto': 'static',
                'ipv6ipaddr': '2001:db8:dead:beef::3',
                'ipv6netmask': '64',
                'ipv6gateway': '2001:db8:dead:beef::1',
                'enable_ipv6': False,
                'noifupdown': True,
                },
            'get_interface': odict([('eth6', odict([('enabled', True), ('data', odict([
                ('inet', odict([
                    ('addrfam', 'inet'),
                    ('proto', 'static'),
                    ('filename', None),
                    ('address', '192.168.4.9'),
                    ('netmask', '255.255.255.0'),
                    ('gateway', '192.168.4.1'),
                    ])),
                ]))]))]),
            'return': [
                'auto eth6\n',
                'iface eth6 inet static\n',
                '    address 192.168.4.9\n',
                '    netmask 255.255.255.0\n',
                '    gateway 192.168.4.1\n',
                '\n']},

        # IPv4 and IPv6; shared/overridden settings
        {'iface_name': 'eth7', 'iface_type': 'eth', 'enabled': True,
            'build_interface': {
                'proto': 'static',
                'ipaddr': '192.168.4.9',
                'netmask': '255.255.255.0',
                'gateway': '192.168.4.1',
                'ipv6proto': 'static',
                'ipv6ipaddr': '2001:db8:dead:beef::3',
                'ipv6netmask': '64',
                'ipv6gateway': '2001:db8:dead:beef::1',
                'ttl': '18',  # shared
                'ipv6ttl': '15',  # overriden for v6
                'mtu': '1480',  # shared
                'enable_ipv6': True,
                'noifupdown': True,
                },
            'get_interface': odict([('eth7', odict([('enabled', True), ('data', odict([
                ('inet', odict([
                    ('addrfam', 'inet'),
                    ('proto', 'static'),
                    ('filename', None),
                    ('address', '192.168.4.9'),
                    ('netmask', '255.255.255.0'),
                    ('gateway', '192.168.4.1'),
                    ('ttl', 18),
                    ('mtu', 1480),
                    ])),
                ('inet6', odict([
                    ('addrfam', 'inet6'),
                    ('proto', 'static'),
                    ('filename', None),
                    ('address', '2001:db8:dead:beef::3'),
                    ('netmask', 64),
                    ('gateway', '2001:db8:dead:beef::1'),
                    ('ttl', 15),
                    ('mtu', 1480),
                    ])),
                ]))]))]),
            'return': [
                'auto eth7\n',
                'iface eth7 inet static\n',
                '    address 192.168.4.9\n',
                '    netmask 255.255.255.0\n',
                '    gateway 192.168.4.1\n',
                '    ttl 18\n',
                '    mtu 1480\n',
                'iface eth7 inet6 static\n',
                '    address 2001:db8:dead:beef::3\n',
                '    netmask 64\n',
                '    gateway 2001:db8:dead:beef::1\n',
                '    ttl 15\n',
                '    mtu 1480\n',
                '\n']},

        # Slave iface
        {'iface_name': 'eth8', 'iface_type': 'slave', 'enabled': True,
            'build_interface': {
                'master': 'bond0',
                'noifupdown': True,
                },
            'get_interface': odict([('eth8', odict([('enabled', True), ('data', odict([
                ('inet', odict([
                    ('addrfam', 'inet'),
                    ('proto', 'manual'),
                    ('filename', None),
                    ('bonding', odict([
                        ('master', 'bond0'),
                        ])),
                    ('bonding_keys', ['master']),
                    ])),
                ]))]))]),
            'return': [
                'auto eth8\n',
                'iface eth8 inet manual\n',
                '    bond-master bond0\n',
                '\n']},

        # Bond; with address IPv4 and IPv6 address; slaves as string
        {'iface_name': 'bond9', 'iface_type': 'bond', 'enabled': True,
            'build_interface': {
                'proto': 'static',
                'ipaddr': '10.1.0.14',
                'netmask': '255.255.255.0',
                'gateway': '10.1.0.1',
                'ipv6proto': 'static',
                'ipv6ipaddr': '2001:db8:dead:c0::3',
                'ipv6netmask': '64',
                'ipv6gateway': '2001:db8:dead:c0::1',
                'mode': '802.3ad',
                'slaves': 'eth4 eth5',
                'enable_ipv6': True,
                'noifupdown': True,
                },
            'get_interface': odict([('bond9', odict([('enabled', True), ('data', odict([
                ('inet', odict([
                    ('addrfam', 'inet'),
                    ('proto', 'static'),
                    ('filename', None),
                    ('address', '10.1.0.14'),
                    ('netmask', '255.255.255.0'),
                    ('gateway', '10.1.0.1'),
                    ('bonding', odict([
                        ('ad_select', '0'),
                        ('downdelay', '200'),
                        ('lacp_rate', '0'),
                        ('miimon', '100'),
                        ('mode', '4'),
                        ('slaves', 'eth4 eth5'),
                        ('updelay', '0'),
                        ('use_carrier', 'on'),
                        ])),
                    ('bonding_keys', [
                        'ad_select',
                        'downdelay',
                        'lacp_rate',
                        'miimon',
                        'mode',
                        'slaves',
                        'updelay',
                        'use_carrier',
                        ]),
                    ])),
                ('inet6', odict([
                    ('addrfam', 'inet6'),
                    ('proto', 'static'),
                    ('filename', None),
                    ('address', '2001:db8:dead:c0::3'),
                    ('netmask', 64),
                    ('gateway', '2001:db8:dead:c0::1'),
                    ('bonding', odict([
                        ('ad_select', '0'),
                        ('downdelay', '200'),
                        ('lacp_rate', '0'),
                        ('miimon', '100'),
                        ('mode', '4'),
                        ('slaves', 'eth4 eth5'),
                        ('updelay', '0'),
                        ('use_carrier', 'on'),
                        ])),
                    ('bonding_keys', [
                        'ad_select',
                        'downdelay',
                        'lacp_rate',
                        'miimon',
                        'mode',
                        'slaves',
                        'updelay',
                        'use_carrier',
                        ]),
                    ])),
                ]))]))]),
            'return': [
                'auto bond9\n',
                'iface bond9 inet static\n',
                '    address 10.1.0.14\n',
                '    netmask 255.255.255.0\n',
                '    gateway 10.1.0.1\n',
                '    bond-ad_select 0\n',
                '    bond-downdelay 200\n',
                '    bond-lacp_rate 0\n',
                '    bond-miimon 100\n',
                '    bond-mode 4\n',
                '    bond-slaves eth4 eth5\n',
                '    bond-updelay 0\n',
                '    bond-use_carrier on\n',
                'iface bond9 inet6 static\n',
                '    address 2001:db8:dead:c0::3\n',
                '    netmask 64\n',
                '    gateway 2001:db8:dead:c0::1\n',
                '    bond-ad_select 0\n',
                '    bond-downdelay 200\n',
                '    bond-lacp_rate 0\n',
                '    bond-miimon 100\n',
                '    bond-mode 4\n',
                '    bond-slaves eth4 eth5\n',
                '    bond-updelay 0\n',
                '    bond-use_carrier on\n',
                '\n']},

        # Bond; with address IPv4 and IPv6 address; slaves as list
        {'iface_name': 'bond10', 'iface_type': 'bond', 'enabled': True,
            'build_interface': {
                'proto': 'static',
                'ipaddr': '10.1.0.14',
                'netmask': '255.255.255.0',
                'gateway': '10.1.0.1',
                'ipv6proto': 'static',
                'ipv6ipaddr': '2001:db8:dead:c0::3',
                'ipv6netmask': '64',
                'ipv6gateway': '2001:db8:dead:c0::1',
                'mode': '802.3ad',
                'slaves': ['eth4', 'eth5'],
                'enable_ipv6': True,
                'noifupdown': True,
                },
            'get_interface': odict([('bond10', odict([('enabled', True), ('data', odict([
                ('inet', odict([
                    ('addrfam', 'inet'),
                    ('proto', 'static'),
                    ('filename', None),
                    ('address', '10.1.0.14'),
                    ('netmask', '255.255.255.0'),
                    ('gateway', '10.1.0.1'),
                    ('bonding', odict([
                        ('ad_select', '0'),
                        ('downdelay', '200'),
                        ('lacp_rate', '0'),
                        ('miimon', '100'),
                        ('mode', '4'),
                        ('slaves', 'eth4 eth5'),
                        ('updelay', '0'),
                        ('use_carrier', 'on'),
                        ])),
                    ('bonding_keys', [
                        'ad_select',
                        'downdelay',
                        'lacp_rate',
                        'miimon',
                        'mode',
                        'slaves',
                        'updelay',
                        'use_carrier',
                        ]),
                    ])),
                ('inet6', odict([
                    ('addrfam', 'inet6'),
                    ('proto', 'static'),
                    ('filename', None),
                    ('address', '2001:db8:dead:c0::3'),
                    ('netmask', 64),
                    ('gateway', '2001:db8:dead:c0::1'),
                    ('bonding', odict([
                        ('ad_select', '0'),
                        ('downdelay', '200'),
                        ('lacp_rate', '0'),
                        ('miimon', '100'),
                        ('mode', '4'),
                        ('slaves', 'eth4 eth5'),
                        ('updelay', '0'),
                        ('use_carrier', 'on'),
                        ])),
                    ('bonding_keys', [
                        'ad_select',
                        'downdelay',
                        'lacp_rate',
                        'miimon',
                        'mode',
                        'slaves',
                        'updelay',
                        'use_carrier',
                        ]),
                    ])),
                ]))]))]),
            'return': [
                'auto bond10\n',
                'iface bond10 inet static\n',
                '    address 10.1.0.14\n',
                '    netmask 255.255.255.0\n',
                '    gateway 10.1.0.1\n',
                '    bond-ad_select 0\n',
                '    bond-downdelay 200\n',
                '    bond-lacp_rate 0\n',
                '    bond-miimon 100\n',
                '    bond-mode 4\n',
                '    bond-slaves eth4 eth5\n',
                '    bond-updelay 0\n',
                '    bond-use_carrier on\n',
                'iface bond10 inet6 static\n',
                '    address 2001:db8:dead:c0::3\n',
                '    netmask 64\n',
                '    gateway 2001:db8:dead:c0::1\n',
                '    bond-ad_select 0\n',
                '    bond-downdelay 200\n',
                '    bond-lacp_rate 0\n',
                '    bond-miimon 100\n',
                '    bond-mode 4\n',
                '    bond-slaves eth4 eth5\n',
                '    bond-updelay 0\n',
                '    bond-use_carrier on\n',
                '\n']},

        # Bond VLAN; with IPv4 address
        {'iface_name': 'bond0.11', 'iface_type': 'vlan', 'enabled': True,
            'build_interface': {
                'proto': 'static',
                'ipaddr': '10.7.0.8',
                'netmask': '255.255.255.0',
                'gateway': '10.7.0.1',
                'slaves': 'eth6 eth7',
                'mode': '802.3ad',
                'enable_ipv6': False,
                'noifupdown': True,
                },
            'get_interface': odict([('bond0.11', odict([('enabled', True), ('data', odict([
                ('inet', odict([
                    ('addrfam', 'inet'),
                    ('proto', 'static'),
                    ('filename', None),
                    ('vlan_raw_device', 'bond1'),
                    ('address', '10.7.0.8'),
                    ('netmask', '255.255.255.0'),
                    ('gateway', '10.7.0.1'),
                    ('mode', '802.3ad'),
                    ])),
                ]))]))]),
            'return': [
                'auto bond0.11\n',
                'iface bond0.11 inet static\n',
                '    vlan-raw-device bond1\n',
                '    address 10.7.0.8\n',
                '    netmask 255.255.255.0\n',
                '    gateway 10.7.0.1\n',
                '    mode 802.3ad\n',
                '\n']},

        # Bond; without address
        {'iface_name': 'bond0.12', 'iface_type': 'vlan', 'enabled': True,
            'build_interface': {
                'proto': 'static',
                'slaves': 'eth6 eth7',
                'mode': '802.3ad',
                'enable_ipv6': False,
                'noifupdown': True,
                },
            'get_interface': odict([('bond0.12', odict([('enabled', True), ('data', odict([
                ('inet', odict([
                    ('addrfam', 'inet'),
                    ('proto', 'static'),
                    ('filename', None),
                    ('vlan_raw_device', 'bond1'),
                    ('mode', '802.3ad'),
                    ])),
                ]))]))]),
            'return': [
                'auto bond0.12\n',
                'iface bond0.12 inet static\n',
                '    vlan-raw-device bond1\n',
                '    mode 802.3ad\n',
                '\n']},

        # DNS NS as list
        {'iface_name': 'eth13', 'iface_type': 'eth', 'enabled': True,
            'build_interface': {
                'proto': 'static',
                'ipaddr': '192.168.4.9',
                'netmask': '255.255.255.0',
                'gateway': '192.168.4.1',
                'enable_ipv6': False,
                'noifupdown': True,
                'dns': ['8.8.8.8', '8.8.4.4'],
                },
            'get_interface': odict([('eth13', odict([('enabled', True), ('data', odict([
                ('inet', odict([
                    ('addrfam', 'inet'),
                    ('proto', 'static'),
                    ('filename', None),
                    ('address', '192.168.4.9'),
                    ('netmask', '255.255.255.0'),
                    ('gateway', '192.168.4.1'),
                    ('dns_nameservers', ['8.8.8.8', '8.8.4.4']),
                    ])),
                ]))]))]),
            'return': [
                'auto eth13\n',
                'iface eth13 inet static\n',
                '    address 192.168.4.9\n',
                '    netmask 255.255.255.0\n',
                '    gateway 192.168.4.1\n',
                '    dns-nameservers 8.8.8.8 8.8.4.4\n',
                '\n']},

        # DNS NS as string
        {'iface_name': 'eth14', 'iface_type': 'eth', 'enabled': True,
            'build_interface': {
                'proto': 'static',
                'ipaddr': '192.168.4.9',
                'netmask': '255.255.255.0',
                'gateway': '192.168.4.1',
                'enable_ipv6': False,
                'noifupdown': True,
                'dns': '8.8.8.8 8.8.4.4',
                },
            'get_interface': odict([('eth14', odict([('enabled', True), ('data', odict([
                ('inet', odict([
                    ('addrfam', 'inet'),
                    ('proto', 'static'),
                    ('filename', None),
                    ('address', '192.168.4.9'),
                    ('netmask', '255.255.255.0'),
                    ('gateway', '192.168.4.1'),
                    ('dns_nameservers', ['8.8.8.8', '8.8.4.4']),
                    ])),
                ]))]))]),
            'return': [
                'auto eth14\n',
                'iface eth14 inet static\n',
                '    address 192.168.4.9\n',
                '    netmask 255.255.255.0\n',
                '    gateway 192.168.4.1\n',
                '    dns-nameservers 8.8.8.8 8.8.4.4\n',
                '\n']},

        # Loopback; with IPv4 and IPv6 address
        {'iface_name': 'lo15', 'iface_type': 'eth', 'enabled': True,
            'build_interface': {
                'proto': 'loopback',
                'ipaddr': '192.168.4.9',
                'netmask': '255.255.255.0',
                'gateway': '192.168.4.1',
                'enable_ipv6': True,
                'ipv6proto': 'loopback',
                'ipv6ipaddr': 'fc00::1',
                'ipv6netmask': '128',
                'ipv6_autoconf': False,
                'noifupdown': True,
                },
            'get_interface': odict([('lo15', odict([('enabled', True), ('data', odict([
                ('inet', odict([
                    ('addrfam', 'inet'),
                    ('proto', 'loopback'),
                    ('filename', None),
                    ('address', '192.168.4.9'),
                    ('netmask', '255.255.255.0'),
                    ('gateway', '192.168.4.1'),
                    ])),
                ('inet6', odict([
                    ('addrfam', 'inet6'),
                    ('proto', 'loopback'),
                    ('filename', None),
                    ('address', 'fc00::1'),
                    ('netmask', 128),
                    ])),
                ]))]))]),
            'return': [
                'auto lo15\n',
                'iface lo15 inet loopback\n',
                '    address 192.168.4.9\n',
                '    netmask 255.255.255.0\n',
                '    gateway 192.168.4.1\n',
                'iface lo15 inet6 loopback\n',
                '    address fc00::1\n',
                '    netmask 128\n',
                '\n']},

        # Loopback; with only IPv6 address; enabled=False
        {'iface_name': 'lo16', 'iface_type': 'eth', 'enabled': False,
            'build_interface': {
                'enable_ipv6': True,
                'ipv6proto': 'loopback',
                'ipv6ipaddr': 'fc00::1',
                'ipv6netmask': '128',
                'ipv6_autoconf': False,
                'noifupdown': True,
                },
            'get_interface': odict([('lo16', odict([('data', odict([
                ('inet6', odict([
                    ('addrfam', 'inet6'),
                    ('proto', 'loopback'),
                    ('filename', None),
                    ('address', 'fc00::1'),
                    ('netmask', 128),
                    ])),
                ]))]))]),
            'return': [
                'iface lo16 inet6 loopback\n',
                '    address fc00::1\n',
                '    netmask 128\n',
                '\n']},

        # Loopback; without address
        {'iface_name': 'lo17', 'iface_type': 'eth', 'enabled': True,
            'build_interface': {
                'proto': 'loopback',
                'enable_ipv6': False,
                'noifupdown': True,
                },
            'get_interface': odict([('lo17', odict([('enabled', True), ('data', odict([
                ('inet', odict([
                    ('addrfam', 'inet'),
                    ('proto', 'loopback'),
                    ('filename', None),
                    ])),
                ]))]))]),
            'return': [
                'auto lo17\n',
                'iface lo17 inet loopback\n',
                '\n']},

        # IPv4=DHCP; IPv6=Static; with IPv6 netmask
        {'iface_name': 'eth18', 'iface_type': 'eth', 'enabled': True,
            'build_interface': {
                'proto': 'dhcp',
                'enable_ipv6': True,
                'ipv6proto': 'static',
                'ipv6ipaddr': '2001:db8:dead:c0::3',
                'ipv6netmask': '64',
                'ipv6gateway': '2001:db8:dead:c0::1',
                'noifupdown': True,
                },
            'get_interface': odict([('eth18', odict([('enabled', True), ('data', odict([
                ('inet', odict([
                    ('addrfam', 'inet'),
                    ('proto', 'dhcp'),
                    ('filename', None),
                    ])),
                ('inet6', odict([
                    ('addrfam', 'inet6'),
                    ('proto', 'static'),
                    ('filename', None),
                    ('address', '2001:db8:dead:c0::3'),
                    ('netmask', 64),
                    ('gateway', '2001:db8:dead:c0::1'),
                    ])),
                ]))]))]),
            'return': [
                'auto eth18\n',
                'iface eth18 inet dhcp\n',
                'iface eth18 inet6 static\n',
                '    address 2001:db8:dead:c0::3\n',
                '    netmask 64\n',
                '    gateway 2001:db8:dead:c0::1\n',
                '\n']},

        # IPv4=DHCP; IPv6=Static; without IPv6 netmask
        {'iface_name': 'eth19', 'iface_type': 'eth', 'enabled': True,
            'build_interface': {
                'proto': 'dhcp',
                'enable_ipv6': True,
                'ipv6proto': 'static',
                'ipv6ipaddr': '2001:db8:dead:c0::3/64',
                'ipv6gateway': '2001:db8:dead:c0::1',
                'noifupdown': True,
                },
            'get_interface': odict([('eth19', odict([('enabled', True), ('data', odict([
                ('inet', odict([
                    ('addrfam', 'inet'),
                    ('proto', 'dhcp'),
                    ('filename', None),
                    ])),
                ('inet6', odict([
                    ('addrfam', 'inet6'),
                    ('proto', 'static'),
                    ('filename', None),
                    ('address', '2001:db8:dead:c0::3/64'),
                    ('gateway', '2001:db8:dead:c0::1'),
                    ])),
                ]))]))]),
            'return': [
                'auto eth19\n',
                'iface eth19 inet dhcp\n',
                'iface eth19 inet6 static\n',
                '    address 2001:db8:dead:c0::3/64\n',
                '    gateway 2001:db8:dead:c0::1\n',
                '\n']},
        ]
# fmt: on


@skipIf(salt.utils.platform.is_windows(), "Do not run these tests on Windows")
class DebianIpTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.debian_ip
    """

    def setup_loader_modules(self):
        return {debian_ip: {}}

    # 'build_bond' function tests: 3

    def test_build_bond(self):
        """
        Test if it create a bond script in /etc/modprobe.d with the passed
        settings and load the bonding kernel module.
        """
        with patch(
            "salt.modules.debian_ip._parse_settings_bond", MagicMock(return_value={})
        ), patch("salt.modules.debian_ip._write_file", MagicMock(return_value=True)):
            mock = MagicMock(return_value=1)
            with patch.dict(debian_ip.__grains__, {"osrelease": mock}):
                mock = MagicMock(return_value=True)
                with patch.dict(
                    debian_ip.__salt__, {"kmod.load": mock, "pkg.install": mock}
                ):
                    self.assertEqual(debian_ip.build_bond("bond0"), "")

    def test_error_message_iface_should_process_non_str_expected(self):
        values = [1, True, False, "no-kaboom"]
        iface = "ethtest"
        option = "test"
        msg = debian_ip._error_msg_iface(iface, option, values)
        self.assertTrue(msg.endswith("[1|True|False|no-kaboom]"), msg)

    def test_error_message_network_should_process_non_str_expected(self):
        values = [1, True, False, "no-kaboom"]
        msg = debian_ip._error_msg_network("fnord", values)
        self.assertTrue(msg.endswith("[1|True|False|no-kaboom]"), msg)

    def test_build_bond_exception(self):
        """
        Test if it create a bond script in /etc/modprobe.d with the passed
        settings and load the bonding kernel module.
        """
        with patch(
            "salt.modules.debian_ip._parse_settings_bond", MagicMock(return_value={})
        ):
            mock = MagicMock(return_value=1)
            with patch.dict(debian_ip.__grains__, {"osrelease": mock}):
                mock = MagicMock(
                    side_effect=jinja2.exceptions.TemplateNotFound("error")
                )
                with patch.object(jinja2.Environment, "get_template", mock):
                    self.assertEqual(debian_ip.build_bond("bond0"), "")

    def test_build_bond_data(self):
        """
        Test if it create a bond script in /etc/modprobe.d with the passed
        settings and load the bonding kernel module.
        """
        with patch(
            "salt.modules.debian_ip._parse_settings_bond", MagicMock(return_value={})
        ), patch("salt.modules.debian_ip._read_temp", MagicMock(return_value=True)):
            mock = MagicMock(return_value=1)
            with patch.dict(debian_ip.__grains__, {"osrelease": mock}):
                self.assertTrue(debian_ip.build_bond("bond0", test="True"))

    # 'build_routes' function tests: 2

    def test_build_routes(self):
        """
        Test if it add route scripts for a network interface using up commands.
        """
        with patch(
            "salt.modules.debian_ip._parse_routes",
            MagicMock(return_value={"routes": []}),
        ), patch(
            "salt.modules.debian_ip._write_file_routes", MagicMock(return_value=True)
        ), patch(
            "salt.modules.debian_ip._read_file", MagicMock(return_value="salt")
        ):
            self.assertEqual(debian_ip.build_routes("eth0"), "saltsalt")

    def test_build_routes_exception(self):
        """
        Test if it add route scripts for a network interface using up commands.
        """
        with patch(
            "salt.modules.debian_ip._parse_routes",
            MagicMock(return_value={"routes": []}),
        ):
            self.assertTrue(debian_ip.build_routes("eth0", test="True"))

            mock = MagicMock(side_effect=jinja2.exceptions.TemplateNotFound("err"))
            with patch.object(jinja2.Environment, "get_template", mock):
                self.assertEqual(debian_ip.build_routes("eth0"), "")

    # 'down' function tests: 1

    def test_down(self):
        """
        Test if it shutdown a network interface
        """
        self.assertEqual(debian_ip.down("eth0", "slave"), None)

        mock = MagicMock(return_value="Salt")
        with patch.dict(debian_ip.__salt__, {"cmd.run": mock}):
            self.assertEqual(debian_ip.down("eth0", "eth"), "Salt")

    # 'get_bond' function tests: 1

    def test_get_bond(self):
        """
        Test if it return the content of a bond script
        """
        self.assertEqual(debian_ip.get_bond("bond0"), "")

    # '_parse_interfaces' function tests: 1

    def test_parse_interfaces(self):
        """
        Test if it returns the correct data for parsed configuration file
        """
        with tempfile.NamedTemporaryFile(mode="r", delete=True) as tfile:
            for iface in test_interfaces:
                iname = iface["iface_name"]
                if iface.get("skip_test", False):
                    continue
                with salt.utils.files.fopen(str(tfile.name), "w") as fh:
                    fh.writelines(iface["return"])
                for inet in ["inet", "inet6"]:
                    if inet in iface["get_interface"][iname]["data"]:
                        iface["get_interface"][iname]["data"][inet]["filename"] = str(
                            tfile.name
                        )
                self.assertDictEqual(
                    debian_ip._parse_interfaces([str(tfile.name)]),
                    iface["get_interface"],
                )

    # 'get_interface' function tests: 1

    def test_get_interface(self):
        """
        Test if it return the contents of an interface script
        """
        for iface in test_interfaces:
            if iface.get("skip_test", False):
                continue
            with patch.object(
                debian_ip,
                "_parse_interfaces",
                MagicMock(return_value=iface["get_interface"]),
            ):
                self.assertListEqual(
                    debian_ip.get_interface(iface["iface_name"]), iface["return"]
                )

    # 'build_interface' function tests: 1

    def test_build_interface(self):
        """
        Test if it builds an interface script for a network interface.
        """
        with patch(
            "salt.modules.debian_ip._write_file_ifaces", MagicMock(return_value="salt")
        ):
            self.assertEqual(
                debian_ip.build_interface("eth0", "eth", "enabled"),
                ["s\n", "a\n", "l\n", "t\n"],
            )

            self.assertTrue(
                debian_ip.build_interface("eth0", "eth", "enabled", test="True")
            )

            with patch.object(
                debian_ip, "_parse_settings_eth", MagicMock(return_value={"routes": []})
            ):
                for eth_t in ["bridge", "slave", "bond"]:
                    self.assertRaises(
                        AttributeError,
                        debian_ip.build_interface,
                        "eth0",
                        eth_t,
                        "enabled",
                    )

            self.assertTrue(
                debian_ip.build_interface("eth0", "eth", "enabled", test="True")
            )

        with tempfile.NamedTemporaryFile(mode="r", delete=True) as tfile:
            with patch("salt.modules.debian_ip._DEB_NETWORK_FILE", str(tfile.name)):
                for iface in test_interfaces:
                    if iface.get("skip_test", False):
                        continue
                    # Skip tests that require __salt__['pkg.install']()
                    if iface["iface_type"] in ["bridge", "pppoe", "vlan"]:
                        continue
                    self.assertListEqual(
                        debian_ip.build_interface(
                            iface=iface["iface_name"],
                            iface_type=iface["iface_type"],
                            enabled=iface["enabled"],
                            interface_file=tfile.name,
                            **iface["build_interface"]
                        ),
                        iface["return"],
                    )

    # 'up' function tests: 1

    def test_up(self):
        """
        Test if it start up a network interface
        """
        self.assertEqual(debian_ip.down("eth0", "slave"), None)

        mock = MagicMock(return_value="Salt")
        with patch.dict(debian_ip.__salt__, {"cmd.run": mock}):
            self.assertEqual(debian_ip.up("eth0", "eth"), "Salt")

    # 'get_network_settings' function tests: 1

    def test_get_network_settings(self):
        """
        Test if it return the contents of the global network script.
        """
        with patch.dict(
            debian_ip.__grains__, {"osfullname": "Ubuntu", "osrelease": "14"}
        ), patch(
            "salt.modules.debian_ip._parse_hostname",
            MagicMock(return_value="SaltStack"),
        ), patch(
            "salt.modules.debian_ip._parse_domainname",
            MagicMock(return_value="saltstack.com"),
        ):
            mock_avai = MagicMock(return_value=True)
            with patch.dict(
                debian_ip.__salt__,
                {"service.available": mock_avai, "service.status": mock_avai},
            ):
                self.assertEqual(
                    debian_ip.get_network_settings(),
                    [
                        "NETWORKING=yes\n",
                        "HOSTNAME=SaltStack\n",
                        "DOMAIN=saltstack.com\n",
                    ],
                )

                mock = MagicMock(
                    side_effect=jinja2.exceptions.TemplateNotFound("error")
                )
                with patch.object(jinja2.Environment, "get_template", mock):
                    self.assertEqual(debian_ip.get_network_settings(), "")

    # 'get_routes' function tests: 1

    def test_get_routes(self):
        """
        Test if it return the routes for the interface
        """
        with patch("salt.modules.debian_ip._read_file", MagicMock(return_value="salt")):
            self.assertEqual(debian_ip.get_routes("eth0"), "saltsalt")

    # 'apply_network_settings' function tests: 1

    @skipIf(True, "SLOWTEST skip")
    def test_apply_network_settings(self):
        """
        Test if it apply global network configuration.
        """
        mock = MagicMock(return_value=True)
        with patch.dict(
            debian_ip.__salt__,
            {"network.mod_hostname": mock, "service.stop": mock, "service.start": mock},
        ):
            self.assertEqual(debian_ip.apply_network_settings(), True)

    # 'build_network_settings' function tests: 1

    def test_build_network_settings(self):
        """
        Test if it build the global network script.
        """
        with patch(
            "salt.modules.debian_ip._parse_network_settings",
            MagicMock(
                return_value={
                    "networking": "yes",
                    "hostname": "Salt.saltstack.com",
                    "domainname": "saltstack.com",
                    "search": "test.saltstack.com",
                }
            ),
        ), patch(
            "salt.modules.debian_ip._write_file_network", MagicMock(return_value=True)
        ):
            with patch.dict(
                debian_ip.__grains__, {"osfullname": "Ubuntu", "osrelease": "14"}
            ):
                mock = MagicMock(return_value=True)
                with patch.dict(
                    debian_ip.__salt__,
                    {
                        "service.available": mock,
                        "service.disable": mock,
                        "service.enable": mock,
                    },
                ):
                    self.assertEqual(
                        debian_ip.build_network_settings(),
                        [
                            "NETWORKING=yes\n",
                            "HOSTNAME=Salt\n",
                            "DOMAIN=saltstack.com\n",
                            "SEARCH=test.saltstack.com\n",
                        ],
                    )

                    mock = MagicMock(
                        side_effect=jinja2.exceptions.TemplateNotFound("error")
                    )
                    with patch.object(jinja2.Environment, "get_template", mock):
                        self.assertEqual(debian_ip.build_network_settings(), "")

            with patch.dict(
                debian_ip.__grains__, {"osfullname": "Ubuntu", "osrelease": "10"}
            ):
                mock = MagicMock(return_value=True)
                with patch.dict(
                    debian_ip.__salt__,
                    {
                        "service.available": mock,
                        "service.disable": mock,
                        "service.enable": mock,
                    },
                ):
                    mock = MagicMock(
                        side_effect=jinja2.exceptions.TemplateNotFound("error")
                    )
                    with patch.object(jinja2.Environment, "get_template", mock):
                        self.assertEqual(debian_ip.build_network_settings(), "")

                    with patch.object(
                        debian_ip, "_read_temp", MagicMock(return_value=True)
                    ):
                        self.assertTrue(debian_ip.build_network_settings(test="True"))
