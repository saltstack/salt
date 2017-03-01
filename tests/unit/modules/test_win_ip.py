# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import win_ip
from salt.exceptions import CommandExecutionError, SaltInvocationError

# Globals
win_ip.__salt__ = {}

ETHERNET_CONFIG = ('Configuration for interface "Ethernet"\n'
                   'DHCP enabled: Yes\n'
                   'IP Address: 1.2.3.74\n'
                   'Subnet Prefix: 1.2.3.0/24 (mask 255.255.255.0)\n'
                   'Default Gateway: 1.2.3.1\n'
                   'Gateway Metric: 0\n'
                   'InterfaceMetric: 20\n'
                   'DNS servers configured through DHCP: 1.2.3.4\n'
                   'Register with which suffix: Primary only\n'
                   'WINS servers configured through DHCP: None\n')

ETHERNET_ENABLE = ('Ethernet\n'
                   'Type: Dedicated\n'
                   'Administrative state: Enabled\n'
                   'Connect state: Connected')


@skipIf(NO_MOCK, NO_MOCK_REASON)
class WinShadowTestCase(TestCase):
    '''
    Test cases for salt.modules.win_ip
    '''
    # 'raw_interface_configs' function tests: 1

    def test_raw_interface_configs(self):
        '''
        Test if it return raw configs for all interfaces.
        '''
        mock_cmd = MagicMock(return_value=ETHERNET_CONFIG)
        with patch.dict(win_ip.__salt__, {'cmd.run': mock_cmd}):
            self.assertEqual(win_ip.raw_interface_configs(), ETHERNET_CONFIG)

    # 'get_all_interfaces' function tests: 1

    def test_get_all_interfaces(self):
        '''
        Test if it return configs for all interfaces.
        '''
        ret = {'Ethernet': {'DHCP enabled': 'Yes',
                            'DNS servers configured through DHCP': ['1.2.3.4'],
                            'Default Gateway': '1.2.3.1',
                            'Gateway Metric': '0',
                            'InterfaceMetric': '20',
                            'Register with which suffix': 'Primary only',
                            'WINS servers configured through DHCP': ['None'],
                            'ip_addrs': [{'IP Address': '1.2.3.74',
                                          'Netmask': '255.255.255.0',
                                          'Subnet': '1.2.3.0/24'}]}}

        mock_cmd = MagicMock(return_value=ETHERNET_CONFIG)
        with patch.dict(win_ip.__salt__, {'cmd.run': mock_cmd}):
            self.assertDictEqual(win_ip.get_all_interfaces(), ret)

    # 'get_interface' function tests: 1

    def test_get_interface(self):
        '''
        Test if it return the configuration of a network interface.
        '''
        ret = {'DHCP enabled': 'Yes',
               'DNS servers configured through DHCP': ['1.2.3.4'],
               'Default Gateway': '1.2.3.1', 'Gateway Metric': '0',
               'InterfaceMetric': '20',
               'Register with which suffix': 'Primary only',
               'WINS servers configured through DHCP': ['None'],
               'ip_addrs': [{'IP Address': '1.2.3.74',
                             'Netmask': '255.255.255.0',
                             'Subnet': '1.2.3.0/24'}]}

        mock_cmd = MagicMock(return_value=ETHERNET_CONFIG)
        with patch.dict(win_ip.__salt__, {'cmd.run': mock_cmd}):
            self.assertDictEqual(win_ip.get_interface('Ethernet'), ret)

    # 'is_enabled' function tests: 1

    def test_is_enabled(self):
        '''
        Test if it returns `True` if interface is enabled, otherwise `False`.
        '''
        mock_cmd = MagicMock(side_effect=[ETHERNET_ENABLE, ''])
        with patch.dict(win_ip.__salt__, {'cmd.run': mock_cmd}):
            self.assertTrue(win_ip.is_enabled('Ethernet'))
            self.assertRaises(CommandExecutionError, win_ip.is_enabled,
                              'Ethernet')

    # 'is_disabled' function tests: 1

    def test_is_disabled(self):
        '''
        Test if it returns `True` if interface is disabled, otherwise `False`.
        '''
        mock_cmd = MagicMock(return_value=ETHERNET_ENABLE)
        with patch.dict(win_ip.__salt__, {'cmd.run': mock_cmd}):
            self.assertFalse(win_ip.is_disabled('Ethernet'))

    # 'enable' function tests: 1

    def test_enable(self):
        '''
        Test if it enable an interface.
        '''
        mock_cmd = MagicMock(return_value=ETHERNET_ENABLE)
        with patch.dict(win_ip.__salt__, {'cmd.run': mock_cmd}):
            self.assertTrue(win_ip.enable('Ethernet'))

        mock_cmd = MagicMock(return_value='Connect state: Disconnected')
        with patch.dict(win_ip.__salt__, {'cmd.run': mock_cmd}):
            self.assertFalse(win_ip.enable('Ethernet'))

    # 'disable' function tests: 1

    def test_disable(self):
        '''
        Test if it disable an interface.
        '''
        mock_cmd = MagicMock(return_value=ETHERNET_ENABLE)
        with patch.dict(win_ip.__salt__, {'cmd.run': mock_cmd}):
            self.assertFalse(win_ip.disable('Ethernet'))

        mock_cmd = MagicMock(return_value='Connect state: Disconnected')
        with patch.dict(win_ip.__salt__, {'cmd.run': mock_cmd}):
            self.assertTrue(win_ip.disable('Ethernet'))

    # 'get_subnet_length' function tests: 1

    def test_get_subnet_length(self):
        '''
        Test if it disable an interface.
        '''
        self.assertEqual(win_ip.get_subnet_length('255.255.255.0'), 24)
        self.assertRaises(SaltInvocationError, win_ip.get_subnet_length,
                          '255.255.0')

    # 'set_static_ip' function tests: 1

    def test_set_static_ip(self):
        '''
        Test if it set static IP configuration on a Windows NIC.
        '''
        self.assertRaises(SaltInvocationError, win_ip.set_static_ip,
                          'Local Area Connection', '10.1.2/24')

        mock_cmd = MagicMock(return_value=ETHERNET_CONFIG)
        mock_all = MagicMock(return_value={'retcode': 1, 'stderr': 'Error'})
        with patch.dict(win_ip.__salt__, {'cmd.run': mock_cmd,
                                          'cmd.run_all': mock_all}):
            self.assertRaises(CommandExecutionError, win_ip.set_static_ip,
                              'Ethernet', '1.2.3.74/24', append=True)
            self.assertRaises(CommandExecutionError, win_ip.set_static_ip,
                              'Ethernet', '1.2.3.74/24')

        mock_all = MagicMock(return_value={'retcode': 0})
        with patch.dict(win_ip.__salt__, {'cmd.run': mock_cmd,
                                          'cmd.run_all': mock_all}):
            self.assertDictEqual(win_ip.set_static_ip('Local Area Connection',
                                                      '1.2.3.74/24'), {})
            self.assertDictEqual(win_ip.set_static_ip('Ethernet',
                                                      '1.2.3.74/24'),
                                 {'Address Info': {'IP Address': '1.2.3.74',
                                                   'Netmask': '255.255.255.0',
                                                   'Subnet': '1.2.3.0/24'}})

    # 'set_dhcp_ip' function tests: 1

    def test_set_dhcp_ip(self):
        '''
        Test if it set Windows NIC to get IP from DHCP.
        '''
        mock_cmd = MagicMock(return_value=ETHERNET_CONFIG)
        with patch.dict(win_ip.__salt__, {'cmd.run': mock_cmd}):
            self.assertDictEqual(win_ip.set_dhcp_ip('Ethernet'),
                                 {'DHCP enabled': 'Yes',
                                  'Interface': 'Ethernet'})

    # 'set_static_dns' function tests: 1

    def test_set_static_dns(self):
        '''
        Test if it set static DNS configuration on a Windows NIC.
        '''
        mock_cmd = MagicMock(return_value=ETHERNET_CONFIG)
        with patch.dict(win_ip.__salt__, {'cmd.run': mock_cmd}):
            self.assertDictEqual(win_ip.set_static_dns('Ethernet',
                                                       '192.168.1.252',
                                                       '192.168.1.253'),
                                 {'DNS Server': ('192.168.1.252',
                                                 '192.168.1.253'),
                                  'Interface': 'Ethernet'})

    # 'set_dhcp_dns' function tests: 1

    def test_set_dhcp_dns(self):
        '''
        Test if it set DNS source to DHCP on Windows.
        '''
        mock_cmd = MagicMock(return_value=ETHERNET_CONFIG)
        with patch.dict(win_ip.__salt__, {'cmd.run': mock_cmd}):
            self.assertDictEqual(win_ip.set_dhcp_dns('Ethernet'),
                                 {'DNS Server': 'DHCP',
                                  'Interface': 'Ethernet'})

    # 'set_dhcp_all' function tests: 1

    def test_set_dhcp_all(self):
        '''
        Test if it set both IP Address and DNS to DHCP.
        '''
        mock_cmd = MagicMock(return_value=ETHERNET_CONFIG)
        with patch.dict(win_ip.__salt__, {'cmd.run': mock_cmd}):
            self.assertDictEqual(win_ip.set_dhcp_all('Ethernet'),
                                 {'Interface': 'Ethernet', 'DNS Server': 'DHCP',
                                  'DHCP enabled': 'Yes'})

    # 'get_default_gateway' function tests: 1

    def test_get_default_gateway(self):
        '''
        Test if it set DNS source to DHCP on Windows.
        '''
        mock_cmd = MagicMock(return_value=ETHERNET_CONFIG)
        with patch.dict(win_ip.__salt__, {'cmd.run': mock_cmd}):
            self.assertEqual(win_ip.get_default_gateway(), '1.2.3.1')


if __name__ == '__main__':
    from integration import run_tests
    run_tests(WinShadowTestCase, needs_daemon=False)
