# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import
import salt.utils
import sys
import types

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    Mock,
    NO_MOCK,
    NO_MOCK_REASON
)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# wmi modules are platform specific...
wmi = types.ModuleType('wmi')
sys.modules['wmi'] = wmi

if NO_MOCK is False:
    WMI = Mock()
    wmi.WMI = Mock(return_value=WMI)

# Import Salt Libs
from salt.modules import win_network

win_network.__salt__ = {}


class Mockwmi(object):
    '''
    Mock wmi class
    '''
    NetConnectionID = 'Ethernet'

    def __init__(self):
        pass


class Mockwinapi(object):
    '''
    Mock winapi class
    '''
    def __init__(self):
        pass

    class winapi(object):
        '''
        Mock winapi class
        '''
        def __init__(self):
            pass

        @staticmethod
        def Com():
            '''
            Mock Com method
            '''
            return True


@skipIf(NO_MOCK, NO_MOCK_REASON)
class WinNetworkTestCase(TestCase):
    '''
    Test cases for salt.modules.win_network
    '''
    # 'ping' function tests: 1

    def test_ping(self):
        '''
        Test if it performs a ping to a host.
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(win_network.__salt__, {'cmd.run': mock}):
            self.assertTrue(win_network.ping('127.0.0.1'))

    # 'netstat' function tests: 1

    def test_netstat(self):
        '''
        Test if it return information on open ports and states
        '''
        ret = ('  Proto  Local Address    Foreign Address    State    PID\n'
               '  TCP    127.0.0.1:1434    0.0.0.0:0    LISTENING    1728\n'
               '  UDP    127.0.0.1:1900    *:*        4240')
        mock = MagicMock(return_value=ret)
        with patch.dict(win_network.__salt__, {'cmd.run': mock}):
            self.assertListEqual(win_network.netstat(),
                                 [{'local-address': '127.0.0.1:1434',
                                   'program': '1728', 'proto': 'TCP',
                                   'remote-address': '0.0.0.0:0',
                                   'state': 'LISTENING'},
                                  {'local-address': '127.0.0.1:1900',
                                   'program': '4240', 'proto': 'UDP',
                                   'remote-address': '*:*', 'state': None}])

    # 'traceroute' function tests: 1

    def test_traceroute(self):
        '''
        Test if it performs a traceroute to a 3rd party host
        '''
        ret = ('  1     1 ms    <1 ms    <1 ms  172.27.104.1\n'
               '  2     1 ms    <1 ms     1 ms  121.242.35.1.s[121.242.35.1]\n'
               '  3     3 ms     2 ms     2 ms  121.242.4.53.s[121.242.4.53]\n')
        mock = MagicMock(return_value=ret)
        with patch.dict(win_network.__salt__, {'cmd.run': mock}):
            self.assertListEqual(win_network.traceroute('google.com'),
                                 [{'count': '1', 'hostname': None,
                                   'ip': '172.27.104.1', 'ms1': '1',
                                   'ms2': '<1', 'ms3': '<1'},
                                  {'count': '2', 'hostname': None,
                                   'ip': '121.242.35.1.s[121.242.35.1]',
                                   'ms1': '1', 'ms2': '<1', 'ms3': '1'},
                                  {'count': '3', 'hostname': None,
                                   'ip': '121.242.4.53.s[121.242.4.53]',
                                   'ms1': '3', 'ms2': '2', 'ms3': '2'}])

    # 'nslookup' function tests: 1

    def test_nslookup(self):
        '''
        Test if it query DNS for information about a domain or ip address
        '''
        ret = ('Server:  ct-dc-3-2.cybage.com\n'
               'Address:  172.27.172.12\n'
               'Non-authoritative answer:\n'
               'Name:    google.com\n'
               'Addresses:  2404:6800:4007:806::200e\n'
               '216.58.196.110\n')
        mock = MagicMock(return_value=ret)
        with patch.dict(win_network.__salt__, {'cmd.run': mock}):
            self.assertListEqual(win_network.nslookup('google.com'),
                                 [{'Server': 'ct-dc-3-2.cybage.com'},
                                  {'Address': '172.27.172.12'},
                                  {'Name': 'google.com'},
                                  {'Addresses': ['2404:6800:4007:806::200e',
                                                 '216.58.196.110']}])

    # 'dig' function tests: 1

    def test_dig(self):
        '''
        Test if it performs a DNS lookup with dig
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(win_network.__salt__, {'cmd.run': mock}):
            self.assertTrue(win_network.dig('google.com'))

    # 'interfaces_names' function tests: 1

    @patch('salt.utils', Mockwinapi)
    def test_interfaces_names(self):
        '''
        Test if it return a list of all the interfaces names
        '''
        WMI.Win32_NetworkAdapter = MagicMock(return_value=Mockwmi)
        with patch('salt.utils.winapi.Com', MagicMock()):
            with patch.object(WMI, 'Win32_NetworkAdapter',
                              return_value=[Mockwmi()]):
                self.assertListEqual(win_network.interfaces_names(),
                                     ['Ethernet'])

    # 'interfaces' function tests: 1

    def test_interfaces(self):
        '''
        Test if it return information about all the interfaces on the minion
        '''
        with patch.object(salt.utils.network, 'win_interfaces',
                          MagicMock(return_value=True)):
            self.assertTrue(win_network.interfaces())

    # 'hw_addr' function tests: 1

    def test_hw_addr(self):
        '''
        Test if it return the hardware address (a.k.a. MAC address)
        for a given interface
        '''
        with patch.object(salt.utils.network, 'hw_addr',
                          MagicMock(return_value='Ethernet')):
            self.assertEqual(win_network.hw_addr('Ethernet'), 'Ethernet')

    # 'subnets' function tests: 1

    def test_subnets(self):
        '''
        Test if it returns a list of subnets to which the host belongs
        '''
        with patch.object(salt.utils.network, 'subnets',
                          MagicMock(return_value='10.1.1.0/24')):
            self.assertEqual(win_network.subnets(), '10.1.1.0/24')

    # 'in_subnet' function tests: 1

    def test_in_subnet(self):
        '''
        Test if it returns True if host is within specified subnet,
        otherwise False
        '''
        with patch.object(salt.utils.network, 'in_subnet',
                          MagicMock(return_value=True)):
            self.assertTrue(win_network.in_subnet('10.1.1.0/16'))

    # 'get_route' function tests: 1

    def test_get_route(self):
        '''
        Test if it return information on open ports and states
        '''
        ret = ('\n\n'
               'IPAddress         : 10.0.0.15\n'
               'InterfaceIndex    : 3\n'
               'InterfaceAlias    : Wi-Fi\n'
               'AddressFamily     : IPv4\n'
               'Type              : Unicast\n'
               'PrefixLength      : 24\n'
               'PrefixOrigin      : Dhcp\n'
               'SuffixOrigin      : Dhcp\n'
               'AddressState      : Preferred\n'
               'ValidLifetime     : 6.17:52:39\n'
               'PreferredLifetime : 6.17:52:39\n'
               'SkipAsSource      : False\n'
               'PolicyStore       : ActiveStore\n'
               '\n\n'
               'Caption            :\n'
               'Description        :\n'
               'ElementName        :\n'
               'InstanceID         : :8:8:8:9:55=55;:8;8;:8;55;\n'
               'AdminDistance      :\n'
               'DestinationAddress :\n'
               'IsStatic           :\n'
               'RouteMetric        : 0\n'
               'TypeOfRoute        : 3\n'
               'AddressFamily      : IPv4\n'
               'CompartmentId      : 1\n'
               'DestinationPrefix  : 0.0.0.0/0\n'
               'InterfaceAlias     : Wi-Fi\n'
               'InterfaceIndex     : 3\n'
               'NextHop            : 10.0.0.1\n'
               'PreferredLifetime  : 6.23:14:43\n'
               'Protocol           : NetMgmt\n'
               'Publish            : No\n'
               'Store              : ActiveStore\n'
               'ValidLifetime      : 6.23:14:43\n'
               'PSComputerName     :\n'
               'ifIndex            : 3')
        mock = MagicMock(return_value=ret)
        with patch.dict(win_network.__salt__, {'cmd.run': mock}):
            self.assertDictEqual(win_network.get_route('192.0.0.8'),
                                 {'destination': '192.0.0.8',
                                  'gateway': '10.0.0.1',
                                  'interface': 'Wi-Fi',
                                  'source': '10.0.0.15'})


if __name__ == '__main__':
    from integration import run_tests
    run_tests(WinNetworkTestCase, needs_daemon=False)
