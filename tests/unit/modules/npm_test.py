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
from salt.modules import npm
from salt.exceptions import CommandExecutionError
import json

# Globals
npm.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class NpmTestCase(TestCase):
    '''
    Test cases for salt.modules.npm
    '''
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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(NpmTestCase, needs_daemon=False)
