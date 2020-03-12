# -*- coding: utf-8 -*-
# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Testing Libs
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch, MagicMock
from tests.support.unit import TestCase, skipIf

# Import Salt Libs
import salt.utils.platform
import salt.utils.win_network as win_network

mock_base = MagicMock(return_value={
    'alias': 'Ethernet',
    'description': 'Dell GigabitEthernet',
    'id': '{C5F468C0-DD5F-4C2B-939F-A411DCB5DE16}',
    'receive_only': False,
    'status': 'Up',
    'type': 'Ethernet',
    'physical_address': '02:D5:F1:DD:31:E0'
})

mock_ip_base = MagicMock(return_value={
    'dns_enabled': False,
    'dns_suffix': '',
    'dynamic_dns_enabled': False,
})

mock_unicast = MagicMock(return_value={
    'ip_addresses': [{
        'address': '172.18.87.49',
        'broadcast': '172.18.87.63',
        'loopback': '127.0.0.1',
        'netmask': '255.255.255.240',
        'prefix_length': 28,
        'prefix_origin': 'Manual',
        'suffix_origin': 'Manual'}],
    'ipv6_addresses': [{
        'address': 'fe80::e8a4:1224:5548:2b81',
        'interface_index': 32,
        'prefix_length': 64,
        'prefix_origin': 'WellKnown',
        'suffix_origin': 'Router'}],
})

mock_gateway = MagicMock(return_value={
    'ip_gateways': ['192.168.0.1'],
    'ipv6_gateways': ['fe80::208:a2ff:fe0b:de70']
})

mock_dns = MagicMock(return_value={
    'ip_dns': ['10.4.0.1', '10.1.0.1', '8.8.8.8'],
    'ipv6_dns': ['2600:740a:1:304::1']
})

mock_multicast = MagicMock(return_value={
    u'ip_multicast': ['224.0.0.1',
                      '224.0.0.251',
                      '224.0.0.252',
                      '230.230.230.230',
                      '239.0.0.250',
                      '239.255.255.250'],
    'ipv6_multicast': ['ff01::1',
                       'ff02::1',
                       'ff02::c',
                       'ff02::fb',
                       'ff02::1:3',
                       'ff02::1:ff0f:4c48',
                       'ff02::1:ffa6:f6e6'],
})

mock_anycast = MagicMock(return_value={'ip_anycast': [],
                                       'ipv6_anycast': []})

mock_wins = MagicMock(return_value={'ip_wins': []})


class Interface(object):
    Name = 'Ethernet'


mock_int = MagicMock(return_value=[Interface()])


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not salt.utils.platform.is_windows(), 'System is not Windows')
class WinNetworkTestCase(TestCase):
    def test_get_interface_info_dot_net(self):
        expected = {
            'Ethernet': {
                'alias': 'Ethernet',
                'description': 'Dell GigabitEthernet',
                'dns_enabled': False,
                'dns_suffix': '',
                'dynamic_dns_enabled': False,
                'id': '{C5F468C0-DD5F-4C2B-939F-A411DCB5DE16}',
                'ip_addresses': [{'address': u'172.18.87.49',
                                  'broadcast': u'172.18.87.63',
                                  'loopback': u'127.0.0.1',
                                  'netmask': u'255.255.255.240',
                                  'prefix_length': 28,
                                  'prefix_origin': u'Manual',
                                  'suffix_origin': u'Manual'}],
               'ip_anycast': [],
               'ip_dns': ['10.4.0.1', '10.1.0.1', '8.8.8.8'],
               'ip_gateways': ['192.168.0.1'],
               'ip_multicast': ['224.0.0.1',
                                '224.0.0.251',
                                '224.0.0.252',
                                '230.230.230.230',
                                '239.0.0.250',
                                '239.255.255.250'],
               'ip_wins': [],
               'ipv6_addresses': [{'address': u'fe80::e8a4:1224:5548:2b81',
                                   'interface_index': 32,
                                   'prefix_length': 64,
                                   'prefix_origin': u'WellKnown',
                                   'suffix_origin': u'Router'}],
               'ipv6_anycast': [],
               'ipv6_dns': ['2600:740a:1:304::1'],
               'ipv6_gateways': ['fe80::208:a2ff:fe0b:de70'],
               'ipv6_multicast': ['ff01::1',
                                  'ff02::1',
                                  'ff02::c',
                                  'ff02::fb',
                                  'ff02::1:3',
                                  'ff02::1:ff0f:4c48',
                                  'ff02::1:ffa6:f6e6'],
               'physical_address': '02:D5:F1:DD:31:E0',
               'receive_only': False,
               'status': 'Up',
               'type': 'Ethernet'}}

        with patch.object(win_network, '_get_network_interfaces', mock_int), \
                patch.object(win_network, '_get_base_properties', mock_base), \
                patch.object(win_network, '_get_ip_base_properties', mock_ip_base), \
                patch.object(win_network, '_get_ip_unicast_info', mock_unicast), \
                patch.object(win_network, '_get_ip_gateway_info', mock_gateway), \
                patch.object(win_network, '_get_ip_dns_info', mock_dns), \
                patch.object(win_network, '_get_ip_multicast_info', mock_multicast), \
                patch.object(win_network, '_get_ip_anycast_info', mock_anycast), \
                patch.object(win_network, '_get_ip_wins_info', mock_wins):

            # ret = win_network._get_base_properties()
            results = win_network.get_interface_info_dot_net()

        self.assertDictEqual(expected, results)

    def test_get_network_info(self):
        expected = {
            'Dell GigabitEthernet': {
                'hwaddr': '02:D5:F1:DD:31:E0',
                'inet': [{'address': '172.18.87.49',
                          'broadcast': '172.18.87.63',
                          'gateway': '192.168.0.1',
                          'label': 'Dell GigabitEthernet',
                          'netmask': '255.255.255.240'}],
                'inet6': [{'address': 'fe80::e8a4:1224:5548:2b81',
                           'gateway': 'fe80::208:a2ff:fe0b:de70'}],
                'up': True}}
        with patch.object(win_network, '_get_network_interfaces', mock_int), \
                patch.object(win_network, '_get_base_properties', mock_base), \
                patch.object(win_network, '_get_ip_base_properties', mock_ip_base), \
                patch.object(win_network, '_get_ip_unicast_info', mock_unicast), \
                patch.object(win_network, '_get_ip_gateway_info', mock_gateway), \
                patch.object(win_network, '_get_ip_dns_info', mock_dns), \
                patch.object(win_network, '_get_ip_multicast_info', mock_multicast), \
                patch.object(win_network, '_get_ip_anycast_info', mock_anycast), \
                patch.object(win_network, '_get_ip_wins_info', mock_wins):

            # ret = win_network._get_base_properties()
            results = win_network.get_interface_info()

        self.assertDictEqual(expected, results)
