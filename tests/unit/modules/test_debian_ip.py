# -*- coding: utf-8 -*-
'''
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import tempfile

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.modules.debian_ip as debian_ip
import salt.utils.platform

# Import third party libs
import jinja2.exceptions


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(salt.utils.platform.is_windows(), 'Do not run these tests on Windows')
class DebianIpTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.debian_ip
    '''
    def setup_loader_modules(self):
        return {debian_ip: {}}

    # 'build_bond' function tests: 3

    def test_build_bond(self):
        '''
        Test if it create a bond script in /etc/modprobe.d with the passed
        settings and load the bonding kernel module.
        '''
        with patch('salt.modules.debian_ip._parse_settings_bond',
                   MagicMock(return_value={})), \
                           patch('salt.modules.debian_ip._write_file',
                                 MagicMock(return_value=True)):
            mock = MagicMock(return_value=1)
            with patch.dict(debian_ip.__grains__, {'osrelease': mock}):
                mock = MagicMock(return_value=True)
                with patch.dict(debian_ip.__salt__, {'kmod.load': mock,
                                                     'pkg.install': mock}):
                    self.assertEqual(debian_ip.build_bond('bond0'), '')

    def test_error_message_iface_should_process_non_str_expected(self):
        values = [1, True, False, 'no-kaboom']
        iface = 'ethtest'
        option = 'test'
        msg = debian_ip._error_msg_iface(iface, option, values)
        self.assertTrue(msg.endswith('[1|True|False|no-kaboom]'), msg)

    def test_error_message_network_should_process_non_str_expected(self):
        values = [1, True, False, 'no-kaboom']
        msg = debian_ip._error_msg_network('fnord', values)
        self.assertTrue(msg.endswith('[1|True|False|no-kaboom]'), msg)

    def test_build_bond_exception(self):
        '''
        Test if it create a bond script in /etc/modprobe.d with the passed
        settings and load the bonding kernel module.
        '''
        with patch('salt.modules.debian_ip._parse_settings_bond',
                   MagicMock(return_value={})):
            mock = MagicMock(return_value=1)
            with patch.dict(debian_ip.__grains__, {'osrelease': mock}):
                mock = MagicMock(side_effect=
                                 jinja2.exceptions.TemplateNotFound('error'))
                with patch.object(jinja2.Environment, 'get_template', mock):
                    self.assertEqual(debian_ip.build_bond('bond0'), '')

    def test_build_bond_data(self):
        '''
        Test if it create a bond script in /etc/modprobe.d with the passed
        settings and load the bonding kernel module.
        '''
        with patch('salt.modules.debian_ip._parse_settings_bond',
                   MagicMock(return_value={})), \
                           patch('salt.modules.debian_ip._read_temp',
                                 MagicMock(return_value=True)):
            mock = MagicMock(return_value=1)
            with patch.dict(debian_ip.__grains__, {'osrelease': mock}):
                self.assertTrue(debian_ip.build_bond('bond0', test='True'))

    # 'build_routes' function tests: 2

    def test_build_routes(self):
        '''
        Test if it add route scripts for a network interface using up commands.
        '''
        with patch('salt.modules.debian_ip._parse_routes',
                   MagicMock(return_value={'routes': []})), \
                           patch('salt.modules.debian_ip._write_file_routes',
                                 MagicMock(return_value=True)), \
                                         patch('salt.modules.debian_ip._read_file',
                                               MagicMock(return_value='salt')):
            self.assertEqual(debian_ip.build_routes('eth0'), 'saltsalt')

    def test_build_routes_exception(self):
        '''
        Test if it add route scripts for a network interface using up commands.
        '''
        with patch('salt.modules.debian_ip._parse_routes',
                   MagicMock(return_value={'routes': []})):
            self.assertTrue(debian_ip.build_routes('eth0', test='True'))

            mock = MagicMock(side_effect=jinja2.exceptions.TemplateNotFound('err'))
            with patch.object(jinja2.Environment, 'get_template', mock):
                self.assertEqual(debian_ip.build_routes('eth0'), '')

    # 'down' function tests: 1

    def test_down(self):
        '''
        Test if it shutdown a network interface
        '''
        self.assertEqual(debian_ip.down('eth0', 'slave'), None)

        mock = MagicMock(return_value='Salt')
        with patch.dict(debian_ip.__salt__, {'cmd.run': mock}):
            self.assertEqual(debian_ip.down('eth0', 'eth'), 'Salt')

    # 'get_bond' function tests: 1

    def test_get_bond(self):
        '''
        Test if it return the content of a bond script
        '''
        self.assertEqual(debian_ip.get_bond('bond0'), '')

    # 'get_interface' function tests: 1

    def test_get_interface(self):
        '''
        Test if it return the contents of an interface script
        '''
        with patch.object(debian_ip, '_parse_interfaces',
                          MagicMock(return_value={})):
            self.assertListEqual(debian_ip.get_interface('eth0'), [])

        mock_ret = {'lo': {'enabled': True, 'data':
                           {'inet': {'addrfam': 'inet', 'proto': 'loopback'}}}}
        with patch.object(debian_ip, '_parse_interfaces',
                          MagicMock(return_value=mock_ret)):
            self.assertListEqual(debian_ip.get_interface('lo'),
                                 ['auto lo\n',
                                  'iface lo inet loopback\n',
                                  '\n'])

            mock = MagicMock(side_effect=jinja2.exceptions.TemplateNotFound
                             ('error'))
            with patch.object(jinja2.Environment, 'get_template', mock):
                self.assertEqual(debian_ip.get_interface('lo'), '')

    # 'build_interface' function tests: 1

    def test_build_interface(self):
        '''
        Test if it builds an interface script for a network interface.
        '''
        with patch('salt.modules.debian_ip._write_file_ifaces',
                   MagicMock(return_value='salt')):
            self.assertEqual(debian_ip.build_interface('eth0', 'eth', 'enabled'),
                             ['s\n', 'a\n', 'l\n', 't\n'])

            self.assertTrue(debian_ip.build_interface('eth0', 'eth', 'enabled',
                                                      test='True'))

            with patch.object(debian_ip, '_parse_settings_eth',
                              MagicMock(return_value={'routes': []})):
                self.assertRaises(AttributeError, debian_ip.build_interface,
                                  'eth0', 'bridge', 'enabled')

                self.assertRaises(AttributeError, debian_ip.build_interface,
                                  'eth0', 'slave', 'enabled')

                self.assertRaises(AttributeError, debian_ip.build_interface,
                                  'eth0', 'bond', 'enabled')

            self.assertTrue(debian_ip.build_interface('eth0', 'eth', 'enabled',
                                                      test='True'))

        interfaces = [
                # IPv4-only interface; single address
                {'iface_name': 'eth1', 'iface_type': 'eth', 'enabled': True,
                    'settings': {
                        'proto': 'static',
                        'ipaddr': '192.168.4.9',
                        'netmask': '255.255.255.0',
                        'gateway': '192.168.4.1',
                        'enable_ipv6': False,
                        'noifupdown': True,
                        },
                    'return': [
                        'auto eth1\n',
                        'iface eth1 inet static\n',
                        '    address 192.168.4.9\n',
                        '    netmask 255.255.255.0\n',
                        '    gateway 192.168.4.1\n',
                        '\n']},
                # IPv6-only; single address
                {'iface_name': 'eth2', 'iface_type': 'eth', 'enabled': True,
                    'settings': {
                        'proto': 'static',
                        'ipv6proto': 'static',
                        'ipv6ipaddr': '2001:db8:dead:beef::3',
                        'ipv6netmask': '64',
                        'ipv6gateway': '2001:db8:dead:beef::1',
                        'enable_ipv6': True,
                        'noifupdown': True,
                        },
                    'return': [
                        'auto eth2\n',
                        'iface eth2 inet6 static\n',
                        '    address 2001:db8:dead:beef::3\n',
                        '    netmask 64\n',
                        '    gateway 2001:db8:dead:beef::1\n',
                        '\n']},
                # IPv4 and IPv6; shared/overridden settings
                {'iface_name': 'eth3', 'iface_type': 'eth', 'enabled': True,
                    'settings': {
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
                    'return': [
                        'auto eth3\n',
                        'iface eth3 inet static\n',
                        '    address 192.168.4.9\n',
                        '    netmask 255.255.255.0\n',
                        '    gateway 192.168.4.1\n',
                        '    ttl 18\n',
                        '    mtu 1480\n',
                        'iface eth3 inet6 static\n',
                        '    address 2001:db8:dead:beef::3\n',
                        '    netmask 64\n',
                        '    gateway 2001:db8:dead:beef::1\n',
                        '    ttl 15\n',
                        '    mtu 1480\n',
                        '\n']},
                # Slave iface
                {'iface_name': 'eth4', 'iface_type': 'slave', 'enabled': True,
                    'settings': {
                        'master': 'bond0',
                        'noifupdown': True,
                        },
                    'return': [
                        'auto eth4\n',
                        'iface eth4 inet manual\n',
                        '    bond-master bond0\n',
                        '\n']},
                # Bond; with address IPv4 and IPv6 address; slaves as string
                {'iface_name': 'bond5', 'iface_type': 'bond', 'enabled': True,
                    'settings': {
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
                    'return': [
                        'auto bond5\n',
                        'iface bond5 inet static\n',
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
                        'iface bond5 inet6 static\n',
                        '    address 2001:db8:dead:c0::3\n',
                        '    netmask 64\n',
                        '    gateway 2001:db8:dead:c0::1\n',
                             # TODO: I suspect there should be more here.
                        '\n']},
                # Bond; with address IPv4 and IPv6 address; slaves as list
                {'iface_name': 'bond6', 'iface_type': 'bond', 'enabled': True,
                    'settings': {
                        'proto': 'static',
                        'ipaddr': '10.1.0.14',
                        'netmask': '255.255.255.0',
                        'gateway': '10.1.0.1',
                        'ipv6proto': 'static',
                        'ipv6ipaddr': '2001:db8:dead:c0::3',
                        'ipv6netmask': '64',
                        'ipv6gateway': '2001:db8:dead:c0::1',
                        'mode': '802.3ad',
                        # TODO: Need to add this support
                        #'slaves': ['eth4', 'eth5'],
                        'slaves': 'eth4 eth5',
                        'enable_ipv6': True,
                        'noifupdown': True,
                        },
                    'return': [
                        'auto bond6\n',
                        'iface bond6 inet static\n',
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
                        'iface bond6 inet6 static\n',
                        '    address 2001:db8:dead:c0::3\n',
                        '    netmask 64\n',
                        '    gateway 2001:db8:dead:c0::1\n',
                             # TODO: I suspect there should be more here.
                        '\n']},
                # Bond VLAN; with IPv4 address
                {'iface_name': 'bond1.7', 'iface_type': 'vlan', 'enabled': True,
                    'settings': {
                        'proto': 'static',
                        'ipaddr': '10.7.0.8',
                        'netmask': '255.255.255.0',
                        'gateway': '10.7.0.1',
                        'slaves': 'eth6 eth7',
                        'mode': '802.3ad',
                        'enable_ipv6': False,
                        'noifupdown': True,
                        },
                    'return': [
                        'auto bond1.7\n',
                        'iface bond1.7 inet static\n',
                        '    vlan-raw-device bond1\n',
                        '    address 10.7.0.8\n',
                        '    netmask 255.255.255.0\n',
                        '    gateway 10.7.0.1\n',
                        '    mode 802.3ad\n',
                        '\n']},
                # Bond; without address
                {'iface_name': 'bond1.8', 'iface_type': 'vlan', 'enabled': True,
                    'settings': {
                        'proto': 'static',
                        'slaves': 'eth6 eth7',
                        'mode': '802.3ad',
                        'enable_ipv6': False,
                        'noifupdown': True,
                        },
                    'return': [
                        'auto bond1.8\n',
                        'iface bond1.8 inet static\n',
                        '    vlan-raw-device bond1\n',
                        '    mode 802.3ad\n',
                        '\n']},
                # DNS NS as list
                {'iface_name': 'eth9', 'iface_type': 'eth', 'enabled': True,
                    'settings': {
                        'proto': 'static',
                        'ipaddr': '192.168.4.9',
                        'netmask': '255.255.255.0',
                        'gateway': '192.168.4.1',
                        'enable_ipv6': False,
                        'noifupdown': True,
                        'dns': ['8.8.8.8', '8.8.4.4'],
                        },
                    'return': [
                        'auto eth9\n',
                        'iface eth9 inet static\n',
                        '    address 192.168.4.9\n',
                        '    netmask 255.255.255.0\n',
                        '    gateway 192.168.4.1\n',
                        '    dns-nameservers 8.8.8.8 8.8.4.4\n',
                        '\n']},
                # DNS NS as string
                {'iface_name': 'eth10', 'iface_type': 'eth', 'enabled': True,
                    'settings': {
                        'proto': 'static',
                        'ipaddr': '192.168.4.9',
                        'netmask': '255.255.255.0',
                        'gateway': '192.168.4.1',
                        'enable_ipv6': False,
                        'noifupdown': True,
                        'dns': '8.8.8.8 8.8.4.4',
                        },
                    'return': [
                        'auto eth10\n',
                        'iface eth10 inet static\n',
                        '    address 192.168.4.9\n',
                        '    netmask 255.255.255.0\n',
                        '    gateway 192.168.4.1\n',
                        '    dns-nameservers 8.8.8.8 8.8.4.4\n',
                        '\n']},
                # Loopback; with IPv4 and IPv6 address
                {'iface_name': 'lo11', 'iface_type': 'eth', 'enabled': True,
                    'settings': {
                        'proto': 'loopback',
                        'ipaddr': '192.168.4.9',
                        'netmask': '255.255.255.0',
                        'gateway': '192.168.4.1',
                        'ipv6ipaddr': 'fc00::1',
                        'ipv6netmask': '128',
                        'ipv6_autoconf': False,
                        'enable_ipv6': True,
                        'noifupdown': True,
                        },
                    'return': [
                        'auto lo11\n',
                        'iface lo11 inet loopback\n',
                        '    address 192.168.4.9\n',
                        '    netmask 255.255.255.0\n',
                        '    gateway 192.168.4.1\n',
                        'iface lo11 inet6 loopback\n',
                        '    address fc00::1\n',
                        '    netmask 128\n',
                        '\n']},
                # Loopback; without address
                {'iface_name': 'lo12', 'iface_type': 'eth', 'enabled': True,
                    'settings': {
                        'proto': 'loopback',
                        'enable_ipv6': False,
                        'noifupdown': True,
                        },
                    'return': [
                        'auto lo12\n',
                        'iface lo12 inet loopback\n',
                        '\n']},
                ]

        with tempfile.NamedTemporaryFile(mode='r', delete=True) as tfile:
            with patch('salt.modules.debian_ip._DEB_NETWORK_FILE', str(tfile.name)):
                for iface in interfaces:
                    # Skip tests that require __salt__['pkg.install']()
                    if iface['iface_type'] not in ['bridge', 'pppoe', 'vlan']:
                        self.assertListEqual(debian_ip.build_interface(
                                                    iface=iface['iface_name'],
                                                    iface_type=iface['iface_type'],
                                                    enabled=iface['enabled'],
                                                    interface_file=tfile.name,
                                                    **iface['settings']),
                                             iface['return'])

    # 'up' function tests: 1

    def test_up(self):
        '''
        Test if it start up a network interface
        '''
        self.assertEqual(debian_ip.down('eth0', 'slave'), None)

        mock = MagicMock(return_value='Salt')
        with patch.dict(debian_ip.__salt__, {'cmd.run': mock}):
            self.assertEqual(debian_ip.up('eth0', 'eth'), 'Salt')

    # 'get_network_settings' function tests: 1

    def test_get_network_settings(self):
        '''
        Test if it return the contents of the global network script.
        '''
        with patch.dict(debian_ip.__grains__, {'osfullname': 'Ubuntu',
                                               'osrelease': '14'}), \
                patch('salt.modules.debian_ip._parse_hostname',
                      MagicMock(return_value='SaltStack')), \
                        patch('salt.modules.debian_ip._parse_domainname',
                              MagicMock(return_value='saltstack.com')), \
                                      patch('salt.modules.debian_ip._parse_searchdomain',
                                              MagicMock(return_value='test.saltstack.com')):
            mock_avai = MagicMock(return_value=True)
            with patch.dict(debian_ip.__salt__, {'service.available': mock_avai,
                                                 'service.status': mock_avai}):
                self.assertEqual(debian_ip.get_network_settings(),
                                 [u'NETWORKING=yes\n',
                                  u'HOSTNAME=SaltStack\n',
                                  u'DOMAIN=saltstack.com\n',
                                  u'SEARCH=test.saltstack.com\n'])

                mock = MagicMock(side_effect=jinja2.exceptions.TemplateNotFound
                                 ('error'))
                with patch.object(jinja2.Environment, 'get_template', mock):
                    self.assertEqual(debian_ip.get_network_settings(), '')

    # 'get_routes' function tests: 1

    def test_get_routes(self):
        '''
        Test if it return the routes for the interface
        '''
        with patch('salt.modules.debian_ip._read_file', MagicMock(return_value='salt')):
            self.assertEqual(debian_ip.get_routes('eth0'), 'saltsalt')

    # 'apply_network_settings' function tests: 1

    def test_apply_network_settings(self):
        '''
        Test if it apply global network configuration.
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(debian_ip.__salt__, {'network.mod_hostname': mock,
                                             'service.stop': mock,
                                             'service.start': mock}):
            self.assertEqual(debian_ip.apply_network_settings(), True)

    # 'build_network_settings' function tests: 1

    def test_build_network_settings(self):
        '''
        Test if it build the global network script.
        '''
        with patch('salt.modules.debian_ip._parse_network_settings',
                   MagicMock(return_value={'networking': 'yes',
                                           'hostname': 'Salt.saltstack.com',
                                           'domainname': 'saltstack.com',
                                           'search': 'test.saltstack.com'})), \
                patch('salt.modules.debian_ip._write_file_network',
                      MagicMock(return_value=True)):
            with patch.dict(debian_ip.__grains__, {'osfullname': 'Ubuntu',
                                                   'osrelease': '14'}):
                mock = MagicMock(return_value=True)
                with patch.dict(debian_ip.__salt__, {'service.available': mock,
                                                     'service.disable': mock,
                                                     'service.enable': mock}):
                    self.assertEqual(debian_ip.build_network_settings(),
                                     ['NETWORKING=yes\n',
                                      'HOSTNAME=Salt\n',
                                      'DOMAIN=saltstack.com\n',
                                      'SEARCH=test.saltstack.com\n'])

                    mock = MagicMock(side_effect=jinja2.exceptions.TemplateNotFound
                                     ('error'))
                    with patch.object(jinja2.Environment, 'get_template', mock):
                        self.assertEqual(debian_ip.build_network_settings(), '')

            with patch.dict(debian_ip.__grains__, {'osfullname': 'Ubuntu',
                                                   'osrelease': '10'}):
                mock = MagicMock(return_value=True)
                with patch.dict(debian_ip.__salt__, {'service.available': mock,
                                                     'service.disable': mock,
                                                     'service.enable': mock}):
                    mock = MagicMock(side_effect=jinja2.exceptions.TemplateNotFound
                                     ('error'))
                    with patch.object(jinja2.Environment, 'get_template', mock):
                        self.assertEqual(debian_ip.build_network_settings(), '')

                    with patch.object(debian_ip, '_read_temp',
                                      MagicMock(return_value=True)):
                        self.assertTrue(debian_ip.build_network_settings
                                        (test='True'))
