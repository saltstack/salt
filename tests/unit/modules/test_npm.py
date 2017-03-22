# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import
import json

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
import salt.modules.npm as npm
from salt.exceptions import CommandExecutionError


@skipIf(NO_MOCK, NO_MOCK_REASON)
class NpmTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.npm
    '''
    def setup_loader_modules(self):
        return {npm: {}}

    # 'install' function tests: 1

    @patch('salt.modules.npm._check_valid_version',
           MagicMock(return_value=True))
    def test_install(self):
        '''
        Test if it install an NPM package.
        '''
        mock = MagicMock(return_value={'retcode': 1, 'stderr': 'error'})
        with patch.dict(npm.__salt__, {'cmd.run_all': mock}):
            self.assertRaises(CommandExecutionError, npm.install,
                              'coffee-script')

        mock = MagicMock(return_value={'retcode': 0, 'stderr': 'error',
                                       'stdout': '{"salt": ["SALT"]}'})
        with patch.dict(npm.__salt__, {'cmd.run_all': mock}):
            mock_err = MagicMock(return_value='SALT')
            with patch.object(json, 'loads', mock_err):
                self.assertEqual(npm.install('coffee-script'), 'SALT')

        mock = MagicMock(return_value={'retcode': 0, 'stderr': 'error',
                                       'stdout': '{"salt": ["SALT"]}'})
        with patch.dict(npm.__salt__, {'cmd.run_all': mock}):
            mock_err = MagicMock(side_effect=ValueError())
            with patch.object(json, 'loads', mock_err):
                self.assertEqual(npm.install('coffee-script'),
                                 '{"salt": ["SALT"]}')

    # 'uninstall' function tests: 1

    @patch('salt.modules.npm._check_valid_version',
           MagicMock(return_value=True))
    def test_uninstall(self):
        '''
        Test if it uninstall an NPM package.
        '''
        mock = MagicMock(return_value={'retcode': 1, 'stderr': 'error'})
        with patch.dict(npm.__salt__, {'cmd.run_all': mock}):
            self.assertFalse(npm.uninstall('coffee-script'))

        mock = MagicMock(return_value={'retcode': 0, 'stderr': 'error'})
        with patch.dict(npm.__salt__, {'cmd.run_all': mock}):
            self.assertTrue(npm.uninstall('coffee-script'))

    # 'list_' function tests: 1

    @patch('salt.modules.npm._check_valid_version',
           MagicMock(return_value=True))
    def test_list(self):
        '''
        Test if it list installed NPM packages.
        '''
        mock = MagicMock(return_value={'retcode': 1, 'stderr': 'error'})
        with patch.dict(npm.__salt__, {'cmd.run_all': mock}):
            self.assertRaises(CommandExecutionError, npm.list_, 'coffee-script')

        mock = MagicMock(return_value={'retcode': 0, 'stderr': 'error',
                                       'stdout': '{"salt": ["SALT"]}'})
        with patch.dict(npm.__salt__, {'cmd.run_all': mock}):
            mock_err = MagicMock(return_value={'dependencies': 'SALT'})
            with patch.object(json, 'loads', mock_err):
                self.assertEqual(npm.list_('coffee-script'), 'SALT')

    # 'cache_clean' function tests: 1

    @patch('salt.modules.npm._check_valid_version',
           MagicMock(return_value=True))
    def test_cache_clean(self):
        '''
        Test if it cleans the cached NPM packages.
        '''
        mock = MagicMock(return_value={'retcode': 1, 'stderr': 'error'})
        with patch.dict(npm.__salt__, {'cmd.run_all': mock}):
            self.assertFalse(npm.cache_clean())

        mock = MagicMock(return_value={'retcode': 0})
        with patch.dict(npm.__salt__, {'cmd.run_all': mock}):
            self.assertTrue(npm.cache_clean())

        mock = MagicMock(return_value={'retcode': 0})
        with patch.dict(npm.__salt__, {'cmd.run_all': mock}):
            self.assertTrue(npm.cache_clean('coffee-script'))

    # 'cache_list' function tests: 1

    @patch('salt.modules.npm._check_valid_version',
           MagicMock(return_value=True))
    def test_cache_list(self):
        '''
        Test if it lists the NPM cache.
        '''
        mock = MagicMock(return_value={'retcode': 1, 'stderr': 'error'})
        with patch.dict(npm.__salt__, {'cmd.run_all': mock}):
            self.assertRaises(CommandExecutionError, npm.cache_list)

        mock = MagicMock(return_value={'retcode': 0, 'stderr': 'error',
                                       'stdout': ['~/.npm']})
        with patch.dict(npm.__salt__, {'cmd.run_all': mock}):
            self.assertEqual(npm.cache_list(), ['~/.npm'])

        mock = MagicMock(return_value={'retcode': 0, 'stderr': 'error',
                                       'stdout': ''})
        with patch.dict(npm.__salt__, {'cmd.run_all': mock}):
            self.assertEqual(npm.cache_list('coffee-script'), '')

    # 'cache_path' function tests: 1

    @patch('salt.modules.npm._check_valid_version',
           MagicMock(return_value=True))
    def test_cache_path(self):
        '''
        Test if it prints the NPM cache path.
        '''
        mock = MagicMock(return_value={'retcode': 1, 'stderr': 'error'})
        with patch.dict(npm.__salt__, {'cmd.run_all': mock}):
            self.assertEqual(npm.cache_path(), 'error')

        mock = MagicMock(return_value={'retcode': 0, 'stderr': 'error',
                                       'stdout': '/User/salt/.npm'})
        with patch.dict(npm.__salt__, {'cmd.run_all': mock}):
            self.assertEqual(npm.cache_path(), '/User/salt/.npm')
