# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.modules import ilo

# Globals
ilo.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class IloTestCase(TestCase):
    '''
    Test cases for salt.modules.ilo
    '''
    # 'global_settings' function tests: 1

    @patch('salt.modules.ilo.__execute_cmd',
           MagicMock(return_value={'Global Settings': {}}))
    def test_global_settings(self):
        '''
        Test if it shows global_settings
        '''
        self.assertDictEqual(ilo.global_settings(), {'Global Settings': {}})

    # 'set_http_port' function tests: 1

    def test_set_http_port(self):
        '''
        Test if it configure the port HTTP should listen on
        '''
        with patch.object(ilo, 'global_settings',
                          return_value={'Global Settings': {'HTTP_PORT':
                                                            {'VALUE': 80}}}):
            self.assertTrue(ilo.set_http_port())

        with patch.object(ilo, 'global_settings',
                          return_value={'Global Settings': {'HTTP_PORT':
                                                            {'VALUE': 40}}}):
            with patch.object(ilo, '__execute_cmd',
                              return_value={'Set HTTP Port': {}}):
                self.assertDictEqual(ilo.set_http_port(),
                                     {'Set HTTP Port': {}})

    # 'set_https_port' function tests: 1

    def test_set_https_port(self):
        '''
        Test if it configure the port HTTPS should listen on
        '''
        with patch.object(ilo, 'global_settings',
                          return_value={'Global Settings': {'HTTP_PORT':
                                                            {'VALUE': 443}}}):
            self.assertTrue(ilo.set_https_port())

        with patch.object(ilo, 'global_settings',
                          return_value={'Global Settings': {'HTTP_PORT':
                                                            {'VALUE': 80}}}):
            with patch.object(ilo, '__execute_cmd',
                              return_value={'Set HTTPS Port': {}}):
                self.assertDictEqual(ilo.set_https_port(),
                                     {'Set HTTPS Port': {}})

    # 'enable_ssh' function tests: 1

    def test_enable_ssh(self):
        '''
        Test if it enable the SSH daemon
        '''
        with patch.object(ilo, 'global_settings',
                          return_value={'Global Settings': {'SSH_STATUS':
                                                            {'VALUE': 'Y'}}}):
            self.assertTrue(ilo.enable_ssh())

        with patch.object(ilo, 'global_settings',
                          return_value={'Global Settings': {'SSH_STATUS':
                                                            {'VALUE': 'N'}}}):
            with patch.object(ilo, '__execute_cmd',
                              return_value={'Enable SSH': {}}):
                self.assertDictEqual(ilo.enable_ssh(), {'Enable SSH': {}})

    # 'disable_ssh' function tests: 1

    def test_disable_ssh(self):
        '''
        Test if it disable the SSH daemon
        '''
        with patch.object(ilo, 'global_settings',
                          return_value={'Global Settings': {'SSH_STATUS':
                                                            {'VALUE': 'N'}}}):
            self.assertTrue(ilo.disable_ssh())

        with patch.object(ilo, 'global_settings',
                          return_value={'Global Settings': {'SSH_STATUS':
                                                            {'VALUE': 'Y'}}}):
            with patch.object(ilo, '__execute_cmd',
                              return_value={'Disable SSH': {}}):
                self.assertDictEqual(ilo.disable_ssh(), {'Disable SSH': {}})

    # 'set_ssh_port' function tests: 1

    def test_set_ssh_port(self):
        '''
        Test if it enable SSH on a user defined port
        '''
        with patch.object(ilo, 'global_settings',
                          return_value={'Global Settings': {'SSH_PORT':
                                                            {'VALUE': 22}}}):
            self.assertTrue(ilo.set_ssh_port())

        with patch.object(ilo, 'global_settings',
                          return_value={'Global Settings': {'SSH_PORT':
                                                            {'VALUE': 20}}}):
            with patch.object(ilo, '__execute_cmd',
                              return_value={'Configure SSH Port': {}}):
                self.assertDictEqual(ilo.set_ssh_port(),
                                     {'Configure SSH Port': {}})

    # 'set_ssh_key' function tests: 1

    @patch('salt.modules.ilo.__execute_cmd',
           MagicMock(return_value={'Import SSH Publickey': {}}))
    def test_set_ssh_key(self):
        '''
        Test if it configure SSH public keys for specific users
        '''
        self.assertDictEqual(ilo.set_ssh_key('ssh-rsa AAAAB3Nza Salt'),
                             {'Import SSH Publickey': {}})

    # 'delete_ssh_key' function tests: 1

    @patch('salt.modules.ilo.__execute_cmd',
           MagicMock(return_value={'Delete user SSH key': {}}))
    def test_delete_ssh_key(self):
        '''
        Test if it delete a users SSH key from the ILO
        '''
        self.assertDictEqual(ilo.delete_ssh_key('Salt'),
                             {'Delete user SSH key': {}})

    # 'list_users' function tests: 1

    @patch('salt.modules.ilo.__execute_cmd',
           MagicMock(return_value={'All users': {}}))
    def test_list_users(self):
        '''
        Test if it list all users
        '''
        self.assertDictEqual(ilo.list_users(), {'All users': {}})

    # 'list_users_info' function tests: 1

    @patch('salt.modules.ilo.__execute_cmd',
           MagicMock(return_value={'All users info': {}}))
    def test_list_users_info(self):
        '''
        Test if it List all users in detail
        '''
        self.assertDictEqual(ilo.list_users_info(), {'All users info': {}})

    # 'create_user' function tests: 1

    @patch('salt.modules.ilo.__execute_cmd',
           MagicMock(return_value={'Create user': {}}))
    def test_create_user(self):
        '''
        Test if it create user
        '''
        self.assertDictEqual(ilo.create_user('Salt', 'secretagent',
                                             'VIRTUAL_MEDIA_PRIV'),
                             {'Create user': {}})

    # 'delete_user' function tests: 1

    @patch('salt.modules.ilo.__execute_cmd',
           MagicMock(return_value={'Delete user': {}}))
    def test_delete_user(self):
        '''
        Test if it delete a user
        '''
        self.assertDictEqual(ilo.delete_user('Salt'), {'Delete user': {}})

    # 'get_user' function tests: 1

    @patch('salt.modules.ilo.__execute_cmd',
           MagicMock(return_value={'User Info': {}}))
    def test_get_user(self):
        '''
        Test if it returns local user information, excluding the password
        '''
        self.assertDictEqual(ilo.get_user('Salt'), {'User Info': {}})

    # 'change_username' function tests: 1

    @patch('salt.modules.ilo.__execute_cmd',
           MagicMock(return_value={'Change username': {}}))
    def test_change_username(self):
        '''
        Test if it change a username
        '''
        self.assertDictEqual(ilo.change_username('Salt', 'SALT'),
                             {'Change username': {}})

    # 'change_password' function tests: 1

    @patch('salt.modules.ilo.__execute_cmd',
           MagicMock(return_value={'Change password': {}}))
    def test_change_password(self):
        '''
        Test if it reset a users password
        '''
        self.assertDictEqual(ilo.change_password('Salt', 'saltpasswd'),
                             {'Change password': {}})

    # 'network' function tests: 1

    @patch('salt.modules.ilo.__execute_cmd',
           MagicMock(return_value={'Network Settings': {}}))
    def test_network(self):
        '''
        Test if it grab the current network settings
        '''
        self.assertDictEqual(ilo.network(), {'Network Settings': {}})

    # 'configure_network' function tests: 1

    @patch('salt.modules.ilo.__execute_cmd',
           MagicMock(return_value={'Configure_Network': {}}))
    def test_configure_network(self):
        '''
        Test if it configure Network Interface
        '''
        ret = {'Network Settings':
               {'IP_ADDRESS': {'VALUE': '10.0.0.10'},
                'SUBNET_MASK': {'VALUE': '255.255.255.0'},
                'GATEWAY_IP_ADDRESS': {'VALUE': '10.0.0.1'}}}
        with patch.object(ilo, 'network', return_value=ret):
            self.assertTrue(ilo.configure_network('10.0.0.10',
                                                  '255.255.255.0', '10.0.0.1'))

        with patch.object(ilo, 'network', return_value=ret):
            with patch.object(ilo, '__execute_cmd',
                              return_value={'Network Settings': {}}):
                self.assertDictEqual(ilo.configure_network('10.0.0.100',
                                                           '255.255.255.10',
                                                           '10.0.0.10'),
                                     {'Network Settings': {}})

    # 'enable_dhcp' function tests: 1

    def test_enable_dhcp(self):
        '''
        Test if it enable DHCP
        '''
        with patch.object(ilo, 'network',
                          return_value={'Network Settings': {'DHCP_ENABLE':
                                                             {'VALUE': 'Y'}}}):
            self.assertTrue(ilo.enable_dhcp())

        with patch.object(ilo, 'network',
                          return_value={'Network Settings': {'DHCP_ENABLE':
                                                             {'VALUE': 'N'}}}):
            with patch.object(ilo, '__execute_cmd',
                              return_value={'Enable DHCP': {}}):
                self.assertDictEqual(ilo.enable_dhcp(), {'Enable DHCP': {}})

    # 'disable_dhcp' function tests: 1

    def test_disable_dhcp(self):
        '''
        Test if it disable DHCP
        '''
        with patch.object(ilo, 'network',
                          return_value={'Network Settings': {'DHCP_ENABLE':
                                                             {'VALUE': 'N'}}}):
            self.assertTrue(ilo.disable_dhcp())

        with patch.object(ilo, 'network',
                          return_value={'Network Settings': {'DHCP_ENABLE':
                                                             {'VALUE': 'Y'}}}):
            with patch.object(ilo, '__execute_cmd',
                              return_value={'Disable DHCP': {}}):
                self.assertDictEqual(ilo.disable_dhcp(), {'Disable DHCP': {}})

    # 'configure_snmp' function tests: 1

    @patch('salt.modules.ilo.__execute_cmd',
           MagicMock(return_value={'Configure SNMP': {}}))
    def test_configure_snmp(self):
        '''
        Test if it configure SNMP
        '''
        self.assertDictEqual(ilo.configure_snmp('Salt'), {'Configure SNMP': {}})


if __name__ == '__main__':
    from integration import run_tests
    run_tests(IloTestCase, needs_daemon=False)
