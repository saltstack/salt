# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function
import socket
import os.path

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    mock_open,
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.ext import six
import salt.utils.network
import salt.utils.path
import salt.modules.network as network
from salt.exceptions import CommandExecutionError
if six.PY2:
    import salt.ext.ipaddress as ipaddress
    HAS_IPADDRESS = True
else:
    try:
        import ipaddress
        HAS_IPADDRESS = True
    except ImportError:
        HAS_IPADDRESS = False


@skipIf(NO_MOCK, NO_MOCK_REASON)
class NetworkTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.network
    '''
    def setup_loader_modules(self):
        return {network: {}}

    def test_wol_bad_mac(self):
        '''
        tests network.wol with bad mac
        '''
        bad_mac = '31337'
        self.assertRaises(ValueError, network.wol, bad_mac)

    def test_wol_success(self):
        '''
        tests network.wol success
        '''
        mac = '080027136977'
        bcast = '255.255.255.255 7'

        class MockSocket(object):
            def __init__(self, *args, **kwargs):
                pass

            def __call__(self, *args, **kwargs):
                pass

            def setsockopt(self, *args, **kwargs):
                pass

            def sendto(self, *args, **kwargs):
                pass

        with patch('socket.socket', MockSocket):
            self.assertTrue(network.wol(mac, bcast))

    def test_ping(self):
        '''
        Test for Performs a ping to a host
        '''
        with patch.object(salt.utils.network, 'sanitize_host',
                          return_value='A'):
            mock_all = MagicMock(side_effect=[{'retcode': 1}, {'retcode': 0}])
            with patch.dict(network.__salt__, {'cmd.run_all': mock_all}):
                self.assertFalse(network.ping('host', return_boolean=True))

                self.assertTrue(network.ping('host', return_boolean=True))

            with patch.dict(network.__salt__, {'cmd.run':
                                               MagicMock(return_value='A')}):
                self.assertEqual(network.ping('host'), 'A')

    def test_netstat(self):
        '''
        Test for return information on open ports and states
        '''
        with patch.dict(network.__grains__, {'kernel': 'Linux'}):
            with patch.object(network, '_netstat_linux', return_value='A'):
                with patch.object(network, '_ss_linux', return_value='A'):
                    self.assertEqual(network.netstat(), 'A')

        with patch.dict(network.__grains__, {'kernel': 'OpenBSD'}):
            with patch.object(network, '_netstat_bsd', return_value='A'):
                self.assertEqual(network.netstat(), 'A')

        with patch.dict(network.__grains__, {'kernel': 'A'}):
            self.assertRaises(CommandExecutionError, network.netstat)

    def test_active_tcp(self):
        '''
        Test for return a dict containing information on all
         of the running TCP connections
        '''
        with patch.object(salt.utils.network, 'active_tcp', return_value='A'):
            with patch.dict(network.__grains__, {'kernel': 'Linux'}):
                self.assertEqual(network.active_tcp(), 'A')

    def test_traceroute(self):
        '''
        Test for Performs a traceroute to a 3rd party host
        '''
        with patch.object(salt.utils.path, 'which', side_effect=[False, True]):
            self.assertListEqual(network.traceroute('host'), [])

            with patch.object(salt.utils.network, 'sanitize_host',
                              return_value='A'):
                with patch.dict(network.__salt__, {'cmd.run':
                                                   MagicMock(return_value="")}):
                    self.assertListEqual(network.traceroute('host'), [])

    def test_dig(self):
        '''
        Test for Performs a DNS lookup with dig
        '''
        with patch('salt.utils.path.which', MagicMock(return_value='dig')), \
                patch.object(salt.utils.network, 'sanitize_host',
                             return_value='A'), \
                patch.dict(network.__salt__, {'cmd.run':
                                              MagicMock(return_value='A')}):
            self.assertEqual(network.dig('host'), 'A')

    def test_arp(self):
        '''
        Test for return the arp table from the minion
        '''
        with patch.dict(network.__salt__,
                        {'cmd.run':
                         MagicMock(return_value='A,B,C,D\nE,F,G,H\n')}), \
                patch('salt.utils.path.which', MagicMock(return_value='')):
            self.assertDictEqual(network.arp(), {})

    def test_interfaces(self):
        '''
        Test for return a dictionary of information about
         all the interfaces on the minion
        '''
        with patch.object(salt.utils.network, 'interfaces', return_value={}):
            self.assertDictEqual(network.interfaces(), {})

    def test_hw_addr(self):
        '''
        Test for return the hardware address (a.k.a. MAC address)
         for a given interface
        '''
        with patch.object(salt.utils.network, 'hw_addr', return_value={}):
            self.assertDictEqual(network.hw_addr('iface'), {})

    def test_interface(self):
        '''
        Test for return the inet address for a given interface
        '''
        with patch.object(salt.utils.network, 'interface', return_value={}):
            self.assertDictEqual(network.interface('iface'), {})

    def test_interface_ip(self):
        '''
        Test for return the inet address for a given interface
        '''
        with patch.object(salt.utils.network, 'interface_ip', return_value={}):
            self.assertDictEqual(network.interface_ip('iface'), {})

    def test_subnets(self):
        '''
        Test for returns a list of subnets to which the host belongs
        '''
        with patch.object(salt.utils.network, 'subnets', return_value={}):
            self.assertDictEqual(network.subnets(), {})

    def test_in_subnet(self):
        '''
        Test for returns True if host is within specified
         subnet, otherwise False.
        '''
        with patch.object(salt.utils.network, 'in_subnet', return_value={}):
            self.assertDictEqual(network.in_subnet('iface'), {})

    def test_ip_addrs(self):
        '''
        Test for returns a list of IPv4 addresses assigned to the host.
        '''
        with patch.object(salt.utils.network, 'ip_addrs',
                          return_value=['0.0.0.0']):
            with patch.object(salt.utils.network, 'in_subnet',
                              return_value=True):
                self.assertListEqual(network.ip_addrs('interface',
                                                      'include_loopback',
                                                      'cidr'), ['0.0.0.0'])

            self.assertListEqual(network.ip_addrs('interface',
                                                  'include_loopback'),
                                 ['0.0.0.0'])

    def test_ip_addrs6(self):
        '''
        Test for returns a list of IPv6 addresses assigned to the host.
        '''
        with patch.object(salt.utils.network, 'ip_addrs6',
                          return_value=['A']):
            self.assertListEqual(network.ip_addrs6('int', 'include'), ['A'])

    def test_get_hostname(self):
        '''
        Test for Get hostname
        '''
        with patch.object(network.socket, 'gethostname', return_value='A'):
            self.assertEqual(network.get_hostname(), 'A')

    def test_mod_hostname(self):
        '''
        Test for Modify hostname
        '''
        self.assertFalse(network.mod_hostname(None))

        with patch.object(salt.utils.path, 'which', return_value='hostname'):
            with patch.dict(network.__salt__,
                            {'cmd.run': MagicMock(return_value=None)}):
                file_d = '\n'.join(['#', 'A B C D,E,F G H'])
                with patch('salt.utils.files.fopen', mock_open(read_data=file_d),
                           create=True) as mfi:
                    mfi.return_value.__iter__.return_value = file_d.splitlines()
                    with patch.dict(network.__grains__, {'os_family': 'A'}):
                        self.assertTrue(network.mod_hostname('hostname'))

    def test_connect(self):
        '''
        Test for Test connectivity to a host using a particular
        port from the minion.
        '''
        with patch('socket.socket') as mock_socket:
            self.assertDictEqual(network.connect(False, 'port'),
                                 {'comment': 'Required argument, host, is missing.',
                                  'result': False})

            self.assertDictEqual(network.connect('host', False),
                                 {'comment': 'Required argument, port, is missing.',
                                  'result': False})

            ret = 'Unable to connect to host (0) on tcp port port'
            mock_socket.side_effect = Exception('foo')
            with patch.object(salt.utils.network, 'sanitize_host',
                              return_value='A'):
                with patch.object(socket, 'getaddrinfo',
                                  return_value=[['ipv4', 'A', 6, 'B', '0.0.0.0']]):
                    self.assertDictEqual(network.connect('host', 'port'),
                                         {'comment': ret, 'result': False})

            ret = 'Successfully connected to host (0) on tcp port port'
            mock_socket.side_effect = MagicMock()
            mock_socket.settimeout().return_value = None
            mock_socket.connect().return_value = None
            mock_socket.shutdown().return_value = None
            with patch.object(salt.utils.network, 'sanitize_host',
                              return_value='A'):
                with patch.object(socket,
                                  'getaddrinfo',
                                  return_value=[['ipv4',
                                                'A', 6, 'B', '0.0.0.0']]):
                    self.assertDictEqual(network.connect('host', 'port'),
                                         {'comment': ret, 'result': True})

    @skipIf(HAS_IPADDRESS is False, 'unable to import \'ipaddress\'')
    def test_is_private(self):
        '''
        Test for Check if the given IP address is a private address
        '''
        with patch.object(ipaddress.IPv4Address, 'is_private',
                          return_value=True):
            self.assertTrue(network.is_private('0.0.0.0'))
        with patch.object(ipaddress.IPv6Address, 'is_private',
                          return_value=True):
            self.assertTrue(network.is_private('::1'))

    @skipIf(HAS_IPADDRESS is False, 'unable to import \'ipaddress\'')
    def test_is_loopback(self):
        '''
        Test for Check if the given IP address is a loopback address
        '''
        with patch.object(ipaddress.IPv4Address, 'is_loopback',
                          return_value=True):
            self.assertTrue(network.is_loopback('127.0.0.1'))
        with patch.object(ipaddress.IPv6Address, 'is_loopback',
                          return_value=True):
            self.assertTrue(network.is_loopback('::1'))

    def test_get_bufsize(self):
        '''
        Test for return network buffer sizes as a dict
        '''
        with patch.dict(network.__grains__, {'kernel': 'Linux'}):
            with patch.object(os.path, 'exists', return_value=True):
                with patch.object(network, '_get_bufsize_linux',
                                  return_value={'size': 1}):
                    self.assertDictEqual(network.get_bufsize('iface'),
                                         {'size': 1})

        with patch.dict(network.__grains__, {'kernel': 'A'}):
            self.assertDictEqual(network.get_bufsize('iface'), {})

    def test_mod_bufsize(self):
        '''
        Test for Modify network interface buffers (currently linux only)
        '''
        with patch.dict(network.__grains__, {'kernel': 'Linux'}):
            with patch.object(os.path, 'exists', return_value=True):
                with patch.object(network, '_mod_bufsize_linux',
                                  return_value={'size': 1}):
                    self.assertDictEqual(network.mod_bufsize('iface'),
                                         {'size': 1})

        with patch.dict(network.__grains__, {'kernel': 'A'}):
            self.assertFalse(network.mod_bufsize('iface'))

    def test_routes(self):
        '''
        Test for return currently configured routes from routing table
        '''
        self.assertRaises(CommandExecutionError, network.routes, 'family')

        with patch.dict(network.__grains__, {'kernel': 'A', 'os': 'B'}):
            self.assertRaises(CommandExecutionError, network.routes, 'inet')

        with patch.dict(network.__grains__, {'kernel': 'Linux'}):
            with patch.object(network, '_netstat_route_linux',
                              side_effect=['A', [{'addr_family': 'inet'}]]):
                with patch.object(network, '_ip_route_linux',
                                  side_effect=['A', [{'addr_family': 'inet'}]]):
                    self.assertEqual(network.routes(None), 'A')

                    self.assertListEqual(network.routes('inet'),
                                         [{'addr_family': 'inet'}])

    def test_default_route(self):
        '''
        Test for return default route(s) from routing table
        '''
        self.assertRaises(CommandExecutionError, network.default_route,
                          'family')

        with patch.object(network, 'routes',
                          side_effect=[[{'addr_family': 'inet'},
                                        {'destination': 'A'}], []]):
            with patch.dict(network.__grains__, {'kernel': 'A',
                                                 'os': 'B'}):
                self.assertRaises(CommandExecutionError,
                                  network.default_route, 'inet')

            with patch.dict(network.__grains__, {'kernel': 'Linux'}):
                self.assertListEqual(network.default_route('inet'), [])
