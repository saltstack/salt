# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.modules import debian_ip

# Import third party libs
import jinja2.exceptions

# Globals
debian_ip.__grains__ = {}
debian_ip.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class DebianIpTestCase(TestCase):
    '''
    Test cases for salt.modules.debian_ip
    '''
    # 'build_bond' function tests: 3

    @patch('salt.modules.debian_ip._parse_settings_bond',
           MagicMock(return_value={}))
    @patch('salt.modules.debian_ip._write_file', MagicMock(return_value=True))
    def test_build_bond(self):
        '''
        Test if it create a bond script in /etc/modprobe.d with the passed
        settings and load the bonding kernel module.
        '''
        mock = MagicMock(return_value=1)
        with patch.dict(debian_ip.__grains__, {'osrelease': mock}):
            mock = MagicMock(return_value=True)
            with patch.dict(debian_ip.__salt__, {'kmod.load': mock,
                                                 'pkg.install': mock}):
                self.assertEqual(debian_ip.build_bond('bond0'), '')

    @patch('salt.modules.debian_ip._parse_settings_bond',
           MagicMock(return_value={}))
    def test_build_bond_exception(self):
        '''
        Test if it create a bond script in /etc/modprobe.d with the passed
        settings and load the bonding kernel module.
        '''
        mock = MagicMock(return_value=1)
        with patch.dict(debian_ip.__grains__, {'osrelease': mock}):
            mock = MagicMock(side_effect=
                             jinja2.exceptions.TemplateNotFound('error'))
            with patch.object(jinja2.Environment, 'get_template', mock):
                self.assertEqual(debian_ip.build_bond('bond0'), '')

    @patch('salt.modules.debian_ip._parse_settings_bond',
           MagicMock(return_value={}))
    @patch('salt.modules.debian_ip._read_temp', MagicMock(return_value=True))
    def test_build_bond_data(self):
        '''
        Test if it create a bond script in /etc/modprobe.d with the passed
        settings and load the bonding kernel module.
        '''
        mock = MagicMock(return_value=1)
        with patch.dict(debian_ip.__grains__, {'osrelease': mock}):
            self.assertTrue(debian_ip.build_bond('bond0', test='True'))

    # 'build_interface' function tests: 1

    @patch('salt.modules.debian_ip._write_file_ifaces',
           MagicMock(return_value='salt'))
    def test_build_interface(self):
        '''
        Test if it builds an interface script for a network interface.
        '''
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

    # 'build_routes' function tests: 2

    @patch('salt.modules.debian_ip._parse_routes',
           MagicMock(return_value={'routes': []}))
    @patch('salt.modules.debian_ip._write_file_routes',
           MagicMock(return_value=True))
    @patch('salt.modules.debian_ip._read_file', MagicMock(return_value='salt'))
    def test_build_routes(self):
        '''
        Test if it add route scripts for a network interface using up commands.
        '''
        self.assertEqual(debian_ip.build_routes('eth0'), 'saltsalt')

    @patch('salt.modules.debian_ip._parse_routes',
           MagicMock(return_value={'routes': []}))
    def test_build_routes_exception(self):
        '''
        Test if it add route scripts for a network interface using up commands.
        '''
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
                                 [u'auto lo\n',
                                  u'iface lo inet loopback\n',
                                  u'\n'])

            mock = MagicMock(side_effect=jinja2.exceptions.TemplateNotFound
                             ('error'))
            with patch.object(jinja2.Environment, 'get_template', mock):
                self.assertEqual(debian_ip.get_interface('lo'), '')

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

    @patch('salt.modules.debian_ip._parse_hostname',
           MagicMock(return_value='SaltStack'))
    @patch('salt.modules.debian_ip._parse_domainname',
           MagicMock(return_value='saltstack.com'))
    def test_get_network_settings(self):
        '''
        Test if it return the contents of the global network script.
        '''
        with patch.dict(debian_ip.__grains__, {'osfullname': 'Ubuntu',
                                               'osrelease': '14'}):
            mock_avai = MagicMock(return_value=True)
            with patch.dict(debian_ip.__salt__, {'service.available': mock_avai,
                                                 'service.status': mock_avai}):
                self.assertEqual(debian_ip.get_network_settings(),
                                 [u'NETWORKING=yes\n',
                                  u'HOSTNAME=SaltStack\n',
                                  u'DOMAIN=saltstack.com\n'])

                mock = MagicMock(side_effect=jinja2.exceptions.TemplateNotFound
                                 ('error'))
                with patch.object(jinja2.Environment, 'get_template', mock):
                    self.assertEqual(debian_ip.get_network_settings(), '')

    # 'get_routes' function tests: 1

    @patch('salt.modules.debian_ip._read_file', MagicMock(return_value='salt'))
    def test_get_routes(self):
        '''
        Test if it return the routes for the interface
        '''
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

    @patch('salt.modules.debian_ip._parse_network_settings',
           MagicMock(return_value={'networking': 'yes',
                                   'hostname': 'Salt.saltstack.com',
                                   'domainname': 'saltstack.com',
                                   'search': 'test.saltstack.com'}))
    @patch('salt.modules.debian_ip._write_file_network',
           MagicMock(return_value=True))
    def test_build_network_settings(self):
        '''
        Test if it build the global network script.
        '''
        with patch.dict(debian_ip.__grains__, {'osfullname': 'Ubuntu',
                                               'osrelease': '14'}):
            mock = MagicMock(return_value=True)
            with patch.dict(debian_ip.__salt__, {'service.available': mock,
                                                 'service.disable': mock,
                                                 'service.enable': mock}):
                self.assertEqual(debian_ip.build_network_settings(),
                                 [u'NETWORKING=yes\n',
                                  u'HOSTNAME=Salt\n',
                                  u'DOMAIN=saltstack.com\n',
                                  u'SEARCH=test.saltstack.com\n'])

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
