# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
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
from salt.modules import drac


# Globals
drac.__grains__ = {}
drac.__salt__ = {}
drac.__context__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class DracTestCase(TestCase):
    '''
    Test cases for salt.modules.drac
    '''
    def test_system_info(self):
        '''
        Tests to return System information
        '''
        mock = MagicMock(return_value={'retcode': 0, 'stdout': None})
        with patch.dict(drac.__salt__, {'cmd.run_all': mock}):
            mock = MagicMock(return_value='ABC')
            with patch.object(drac, '__parse_drac', mock):
                self.assertEqual(drac.system_info(), 'ABC')

    def test_network_info(self):
        '''
        Tests to return Network Configuration
        '''
        mock = MagicMock(return_value={'retcode': 0, 'stdout': None})
        with patch.dict(drac.__salt__, {'cmd.run_all': mock}):
            mock = MagicMock(return_value='ABC')
            with patch.object(drac, '__parse_drac', mock):
                self.assertEqual(drac.network_info(), 'ABC')

    def test_nameservers(self):
        '''
        tests for configure the nameservers on the DRAC
        '''
        self.assertFalse(drac.nameservers('a', 'b', 'c'))

        mock = MagicMock(return_value=False)
        with patch.object(drac, '__execute_cmd', mock):
            self.assertFalse(drac.nameservers('a'))

        mock = MagicMock(return_value=True)
        with patch.object(drac, '__execute_cmd', mock):
            self.assertTrue(drac.nameservers('a'))

    def test_syslog(self):
        '''
        Tests for configure syslog remote logging, by default syslog will
        automatically be enabled if a server is specified. However,
        if you want to disable syslog you will need to specify a server
        followed by False
        '''
        mock = MagicMock(return_value=True)
        with patch.object(drac, '__execute_cmd', mock):
            self.assertTrue(drac.syslog('server'))

        mock = MagicMock(return_value=True)
        with patch.object(drac, '__execute_cmd', mock):
            self.assertTrue(drac.syslog('server', False))

    def test_email_alerts(self):
        '''
        Test to Enable/Disable email alerts
        '''
        mock = MagicMock(return_value=True)
        with patch.object(drac, '__execute_cmd', mock):
            self.assertTrue(drac.email_alerts(True))

        mock = MagicMock(return_value=True)
        with patch.object(drac, '__execute_cmd', mock):
            self.assertTrue(drac.email_alerts(False))

    def test_list_users(self):
        '''
        Test for list all DRAC users
        '''
        mock = MagicMock(return_value={'retcode': 0,
                                       'stdout': 'cfgUserAdminUserName=value'})
        with patch.dict(drac.__salt__, {'cmd.run_all': mock}):
            self.assertEqual(drac.list_users(), {'value': {'index': 16}})

    def test_delete_user(self):
        '''
        Tests to delete a user
        '''
        mock = MagicMock(return_value='ABC')
        with patch.object(drac, '__execute_cmd', mock):
            self.assertEqual(drac.delete_user('username', 1), 'ABC')

        self.assertFalse(drac.delete_user('username', False))

    def test_change_password(self):
        '''
        Tests to change users password
        '''
        mock = MagicMock(return_value='ABC')
        with patch.object(drac, '__execute_cmd', mock):
            self.assertEqual(drac.change_password('username',
                                                  'password', 1), 'ABC')

        self.assertFalse(drac.change_password('username',
                                              'password', False), False)

    def test_create_user(self):
        '''
        Tests to create user accounts
        '''
        self.assertFalse(drac.create_user('username', 'password',
                                          'permissions', {'username': None}))

        mock = MagicMock(return_value=False)
        with patch.object(drac, '__execute_cmd', mock):
            mock = MagicMock(return_value=None)
            with patch.object(drac, 'delete_user', mock):
                self.assertFalse(drac.create_user('username', 'password',
                                                  'permissions',
                                                  {'username1': {'index': 1}}))

        mock = MagicMock(return_value=True)
        with patch.object(drac, '__execute_cmd', mock):
            mock = MagicMock(return_value=False)
            with patch.object(drac, 'set_permissions', mock):
                mock = MagicMock(return_value=None)
                with patch.object(drac, 'delete_user', mock):
                    self.assertFalse(drac.create_user('username', 'password',
                                                      'permissions',
                                                      {'username1':
                                                       {'index': 1}}))

            mock = MagicMock(return_value=True)
            with patch.object(drac, 'set_permissions', mock):
                mock = MagicMock(return_value=False)
                with patch.object(drac, 'change_password', mock):
                    mock = MagicMock(return_value=None)
                    with patch.object(drac, 'delete_user', mock):
                        self.assertFalse(drac.create_user('username',
                                                          'password',
                                                          'permissions',
                                                          {'username1':
                                                           {'index': 1}}))

        mock = MagicMock(side_effect=[True, False])
        with patch.object(drac, '__execute_cmd', mock):
            mock = MagicMock(return_value=True)
            with patch.object(drac, 'set_permissions', mock):
                mock = MagicMock(return_value=True)
                with patch.object(drac, 'change_password', mock):
                    mock = MagicMock(return_value=None)
                    with patch.object(drac, 'delete_user', mock):
                        self.assertFalse(drac.create_user('username',
                                                          'password',
                                                          'permissions',
                                                          {'username1':
                                                           {'index': 1}}))

        mock = MagicMock(side_effect=[True, True])
        with patch.object(drac, '__execute_cmd', mock):
            mock = MagicMock(return_value=True)
            with patch.object(drac, 'set_permissions', mock):
                mock = MagicMock(return_value=True)
                with patch.object(drac, 'change_password', mock):
                    mock = MagicMock(return_value=None)
                    with patch.object(drac, 'delete_user', mock):
                        self.assertTrue(drac.create_user('username',
                                                         'password',
                                                         'permissions',
                                                         {'username1':
                                                          {'index': 1}}))

    def test_set_permissions(self):
        '''
        Test to configure users permissions
        '''
        mock = MagicMock(return_value=True)
        with patch.object(drac, '__execute_cmd', mock):
            self.assertTrue(drac.set_permissions('username', 'A,B,C', 1))

    def test_set_snmp(self):
        '''
        Test to configure SNMP community string
        '''
        mock = MagicMock(return_value=True)
        with patch.object(drac, '__execute_cmd', mock):
            self.assertTrue(drac.set_snmp('username'))

    def test_set_network(self):
        '''
        Test to configure Network
        '''
        mock = MagicMock(return_value=True)
        with patch.object(drac, '__execute_cmd', mock):
            self.assertTrue(drac.set_network('ip', 'netmask', 'gateway'))

    def test_server_reboot(self):
        '''
        Tests for issues a power-cycle operation on the managed server.
        This action is similar to pressing the power button on the system's
        front panel to power down and then power up the system.
        '''
        mock = MagicMock(return_value=True)
        with patch.object(drac, '__execute_cmd', mock):
            self.assertTrue(drac.server_reboot())

    def test_server_poweroff(self):
        '''
        Tests for powers down the managed server.
        '''
        mock = MagicMock(return_value=True)
        with patch.object(drac, '__execute_cmd', mock):
            self.assertTrue(drac.server_poweroff())

    def test_server_poweron(self):
        '''
        Tests for powers up the managed server.
        '''
        mock = MagicMock(return_value=True)
        with patch.object(drac, '__execute_cmd', mock):
            self.assertTrue(drac.server_poweron())

    def test_server_hardreset(self):
        '''
        Tests for performs a reset (reboot) operation on the managed server.
        '''
        mock = MagicMock(return_value=True)
        with patch.object(drac, '__execute_cmd', mock):
            self.assertTrue(drac.server_hardreset())

    def test_server_pxe(self):
        '''
        Tests to configure server to PXE perform a one off PXE boot
        '''
        mock = MagicMock(return_value=True)
        with patch.object(drac, '__execute_cmd', mock):
            self.assertTrue(drac.server_pxe())

        mock = MagicMock(side_effect=[True, False])
        with patch.object(drac, '__execute_cmd', mock):
            self.assertFalse(drac.server_pxe())

        mock = MagicMock(return_value=False)
        with patch.object(drac, '__execute_cmd', mock):
            self.assertFalse(drac.server_pxe())
