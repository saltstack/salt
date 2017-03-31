# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase
from tests.support.mock import (
    MagicMock,
    patch
)

# Import Salt Libs
from salt.exceptions import CommandExecutionError
import salt.modules.mac_assistive as assistive


class AssistiveTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        return {assistive: {}}

    def test_install_assistive_bundle(self):
        '''
        Test installing a bundle ID as being allowed to run with assistive access
        '''
        mock_ret = MagicMock(return_value={'retcode': 0})
        with patch.dict(assistive.__salt__, {'cmd.run_all': mock_ret}):
            with patch.dict(assistive.__grains__, {'osrelease': '10.11.3'}):
                self.assertTrue(assistive.install('foo'))

    def test_install_assistive_error(self):
        '''
        Test installing a bundle ID as being allowed to run with assistive access
        '''
        mock_ret = MagicMock(return_value={'retcode': 1})
        with patch.dict(assistive.__salt__, {'cmd.run_all': mock_ret}):
            with patch.dict(assistive.__grains__, {'osrelease': '10.11.3'}):
                self.assertRaises(CommandExecutionError, assistive.install, 'foo')

    @patch('salt.modules.mac_assistive._get_assistive_access', MagicMock(return_value=[('foo', 0)]))
    def test_installed_bundle(self):
        '''
        Test checking to see if a bundle id is installed as being able to use assistive access
        '''
        self.assertTrue(assistive.installed('foo'))

    @patch('salt.modules.mac_assistive._get_assistive_access',
           MagicMock(return_value=[]))
    def test_installed_bundle_not(self):
        '''
        Test checking to see if a bundle id is installed as being able to use assistive access
        '''
        self.assertFalse(assistive.installed('foo'))

    @patch('salt.modules.mac_assistive._get_assistive_access',
           MagicMock(return_value=[('foo', 0)]))
    def test_enable_assistive(self):
        '''
        Test enabling a bundle ID as being allowed to run with assistive access
        '''
        mock_ret = MagicMock(return_value={'retcode': 0})
        with patch.dict(assistive.__salt__, {'cmd.run_all': mock_ret}):
            self.assertTrue(assistive.enable('foo', True))

    @patch('salt.modules.mac_assistive._get_assistive_access',
           MagicMock(return_value=[('foo', 0)]))
    def test_enable_error(self):
        '''
        Test enabled a bundle ID that throws a command error
        '''
        mock_ret = MagicMock(return_value={'retcode': 1})
        with patch.dict(assistive.__salt__, {'cmd.run_all': mock_ret}):
            self.assertRaises(CommandExecutionError,
                              assistive.enable,
                              'foo')

    @patch('salt.modules.mac_assistive._get_assistive_access',
           MagicMock(return_value=[]))
    def test_enable_false(self):
        '''
        Test return of enable function when app isn't found.
        '''
        self.assertFalse(assistive.enable('foo'))

    @patch('salt.modules.mac_assistive._get_assistive_access',
           MagicMock(return_value=[('foo', '1')]))
    def test_enabled_assistive(self):
        '''
        Test enabling a bundle ID as being allowed to run with assistive access
        '''
        self.assertTrue(assistive.enabled('foo'))

    @patch('salt.modules.mac_assistive._get_assistive_access',
           MagicMock(return_value=[]))
    def test_enabled_assistive_false(self):
        '''
        Test if a bundle ID is disabled for assistive access
        '''
        self.assertFalse(assistive.enabled('foo'))

    def test_remove_assistive(self):
        '''
        Test removing an assitive bundle.
        '''
        mock_ret = MagicMock(return_value={'retcode': 0})
        with patch.dict(assistive.__salt__, {'cmd.run_all': mock_ret}):
            self.assertTrue(assistive.remove('foo'))

    def test_remove_assistive_error(self):
        '''
        Test removing an assitive bundle.
        '''
        mock_ret = MagicMock(return_value={'retcode': 1})
        with patch.dict(assistive.__salt__, {'cmd.run_all': mock_ret}):
            self.assertRaises(CommandExecutionError,
                              assistive.remove,
                              'foo')

    def test_get_assistive_access(self):
        '''
        Test if a bundle ID is enabled for assistive access
        '''
        mock_out = 'kTCCServiceAccessibility|/bin/bash|1|1|1|\n' \
                   'kTCCServiceAccessibility|/usr/bin/osascript|1|1|1|'
        mock_ret = MagicMock(return_value={'retcode': 0, 'stdout': mock_out})
        expected = [('/bin/bash', '1'), ('/usr/bin/osascript', '1')]
        with patch.dict(assistive.__salt__, {'cmd.run_all': mock_ret}):
            self.assertEqual(assistive._get_assistive_access(), expected)

    def test_get_assistive_access_error(self):
        '''
        Test a CommandExecutionError is raised when something goes wrong.
        '''
        mock_ret = MagicMock(return_value={'retcode': 1})
        with patch.dict(assistive.__salt__, {'cmd.run_all': mock_ret}):
            self.assertRaises(CommandExecutionError,
                              assistive._get_assistive_access)
