# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Alexander Pyatkin <asp@thexyz.net>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import MagicMock, patch, NO_MOCK, NO_MOCK_REASON

# Import Salt Libs
from salt.modules import bower
from salt.exceptions import CommandExecutionError


@skipIf(NO_MOCK, NO_MOCK_REASON)
class BowerTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.bower
    '''
    loader_module = bower

    @patch('salt.modules.bower._check_valid_version',
           MagicMock(return_value=True))
    def test_install_with_error(self):
        '''
        Test if it raises an exception when install package fails
        '''
        mock = MagicMock(return_value={'retcode': 1, 'stderr': 'error'})
        with patch.dict(bower.__salt__, {'cmd.run_all': mock}):
            self.assertRaises(
                CommandExecutionError,
                bower.install,
                '/path/to/project',
                'underscore')

    @patch('salt.modules.bower._check_valid_version',
           MagicMock(return_value=True))
    def test_install_new_package(self):
        '''
        Test if it returns True when install package succeeds
        '''
        mock = MagicMock(return_value={'retcode': 0,
                                       'stdout': '{"underscore":{}}'})
        with patch.dict(bower.__salt__, {'cmd.run_all': mock}):
            self.assertTrue(bower.install('/path/to/project', 'underscore'))

    @patch('salt.modules.bower._check_valid_version',
           MagicMock(return_value=True))
    def test_install_existing_package(self):
        '''
        Test if it returns False when package already installed
        '''
        mock = MagicMock(return_value={'retcode': 0,
                                       'stdout': '{}'})
        with patch.dict(bower.__salt__, {'cmd.run_all': mock}):
            self.assertFalse(bower.install('/path/to/project', 'underscore'))

    @patch('salt.modules.bower._check_valid_version',
           MagicMock(return_value=True))
    def test_uninstall_with_error(self):
        '''
        Test if it raises an exception when uninstall package fails
        '''
        mock = MagicMock(return_value={'retcode': 1, 'stderr': 'error'})
        with patch.dict(bower.__salt__, {'cmd.run_all': mock}):
            self.assertRaises(
                CommandExecutionError,
                bower.uninstall,
                '/path/to/project',
                'underscore')

    @patch('salt.modules.bower._check_valid_version',
           MagicMock(return_value=True))
    def test_uninstall_existing_package(self):
        '''
        Test if it returns True when uninstall package succeeds
        '''
        mock = MagicMock(return_value={'retcode': 0,
                                       'stdout': '{"underscore": {}}'})
        with patch.dict(bower.__salt__, {'cmd.run_all': mock}):
            self.assertTrue(bower.uninstall('/path/to/project', 'underscore'))

    @patch('salt.modules.bower._check_valid_version',
           MagicMock(return_value=True))
    def test_uninstall_missing_package(self):
        '''
        Test if it returns False when package is not installed
        '''
        mock = MagicMock(return_value={'retcode': 0,
                                       'stdout': '{}'})
        with patch.dict(bower.__salt__, {'cmd.run_all': mock}):
            self.assertFalse(bower.uninstall('/path/to/project', 'underscore'))

    @patch('salt.modules.bower._check_valid_version',
           MagicMock(return_value=True))
    def test_list_packages_with_error(self):
        '''
        Test if it raises an exception when list installed packages fails
        '''
        mock = MagicMock(return_value={'retcode': 1, 'stderr': 'error'})
        with patch.dict(bower.__salt__, {'cmd.run_all': mock}):
            self.assertRaises(
                CommandExecutionError,
                bower.list_,
                '/path/to/project')

    @patch('salt.modules.bower._check_valid_version',
           MagicMock(return_value=True))
    def test_list_packages_success(self):
        '''
        Test if it lists installed Bower packages
        '''
        output = '{"dependencies": {"underscore": {}, "jquery":{}}}'
        mock = MagicMock(return_value={'retcode': 0, 'stdout': output})
        with patch.dict(bower.__salt__, {'cmd.run_all': mock}):
            self.assertEqual(bower.list_('/path/to/project'),
                             {'underscore': {}, 'jquery': {}})
