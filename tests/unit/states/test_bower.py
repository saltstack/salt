# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Alexander Pyatkin <asp@thexyz.net>`
'''

# Import Python Libs
from __future__ import absolute_import

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
from salt.states import bower
from salt.exceptions import CommandExecutionError


@skipIf(NO_MOCK, NO_MOCK_REASON)
class BowerTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.bower
    '''
    loader_module = bower
    loader_module_globals = {'__opts__': {'test': False}}

    def test_removed_not_installed(self):
        '''
        Test if it returns True when specified package is not installed
        '''

        mock = MagicMock(return_value={'underscore': {}})

        with patch.dict(bower.__salt__, {'bower.list': mock}):
            ret = bower.removed('jquery', '/path/to/project')
            expected = {'name': 'jquery',
                        'result': True,
                        'comment': 'Package \'jquery\' is not installed',
                        'changes': {}}
            self.assertEqual(ret, expected)

    def test_removed_with_error(self):
        '''
        Test if returns False when list packages fails
        '''

        mock = MagicMock(side_effect=CommandExecutionError)

        with patch.dict(bower.__salt__, {'bower.list': mock}):
            ret = bower.removed('underscore', '/path/to/project')
            expected = {'name': 'underscore',
                        'result': False,
                        'comment': 'Error removing \'underscore\': ',
                        'changes': {}}
            self.assertEqual(ret, expected)

    def test_removed_existing(self):
        '''
        Test if it returns True when specified package is installed and
        uninstall succeeds
        '''

        mock_list = MagicMock(return_value={'underscore': {}})
        mock_uninstall = MagicMock(return_value=True)

        with patch.dict(bower.__salt__, {'bower.list': mock_list,
                                         'bower.uninstall': mock_uninstall}):
            ret = bower.removed('underscore', '/path/to/project')
            expected = {'name': 'underscore',
                        'result': True,
                        'comment':
                            'Package \'underscore\' was successfully removed',
                        'changes': {'underscore': 'Removed'}}
            self.assertEqual(ret, expected)

    def test_removed_existing_with_error(self):
        '''
        Test if it returns False when specified package is installed and
        uninstall fails
        '''

        mock_list = MagicMock(return_value={'underscore': {}})
        mock_uninstall = MagicMock(side_effect=CommandExecutionError)

        with patch.dict(bower.__salt__, {'bower.list': mock_list,
                                         'bower.uninstall': mock_uninstall}):
            ret = bower.removed('underscore', '/path/to/project')
            expected = {'name': 'underscore',
                        'result': False,
                        'comment':
                            'Error removing \'underscore\': ',
                        'changes': {}}
            self.assertEqual(ret, expected)

    def test_bootstrap_with_error(self):
        '''
        Test if it return False when install packages fails
        '''

        mock = MagicMock(side_effect=CommandExecutionError)

        with patch.dict(bower.__salt__, {'bower.install': mock}):
            ret = bower.bootstrap('/path/to/project')
            expected = {'name': '/path/to/project',
                        'result': False,
                        'comment':
                            'Error bootstrapping \'/path/to/project\': ',
                        'changes': {}}
            self.assertEqual(ret, expected)

    def test_bootstrap_not_needed(self):
        '''
        Test if it returns True when there is nothing to install
        '''

        mock = MagicMock(return_value=False)

        with patch.dict(bower.__salt__, {'bower.install': mock}):
            ret = bower.bootstrap('/path/to/project')
            expected = {'name': '/path/to/project',
                        'result': True,
                        'comment':
                            'Directory is already bootstrapped',
                        'changes': {}}
            self.assertEqual(ret, expected)

    def test_bootstrap_success(self):
        '''
        Test if it returns True when install packages succeeds
        '''

        mock = MagicMock(return_value=True)

        with patch.dict(bower.__salt__, {'bower.install': mock}):
            ret = bower.bootstrap('/path/to/project')
            expected = {'name': '/path/to/project',
                        'result': True,
                        'comment':
                            'Directory was successfully bootstrapped',
                        'changes': {'/path/to/project': 'Bootstrapped'}}
            self.assertEqual(ret, expected)

    def test_installed_with_error(self):
        '''
        Test if it returns False when list packages fails
        '''

        mock = MagicMock(side_effect=CommandExecutionError)

        with patch.dict(bower.__salt__, {'bower.list': mock}):
            ret = bower.installed('underscore', '/path/to/project')
            expected = {'name': 'underscore',
                        'result': False,
                        'comment': 'Error looking up \'underscore\': ',
                        'changes': {}}
            self.assertEqual(ret, expected)

    def test_installed_not_needed(self):
        '''
        Test if it returns True when there is nothing to install
        '''

        mock = MagicMock(return_value={
            'underscore': {
                'pkgMeta': {'version': '1.7.0'}},
            'jquery': {
                'pkgMeta': {'version': '2.0.0'}}})

        with patch.dict(bower.__salt__, {'bower.list': mock}):
            ret = bower.installed('test', '/path/to/project',
                                  ['underscore', 'jquery#2.0.0'])
            expected = {'name': 'test',
                        'result': True,
                        'comment':
                            ('Package(s) \'underscore, jquery#2.0.0\''
                             ' satisfied by underscore#1.7.0, jquery#2.0.0'),
                        'changes': {}}
            self.assertEqual(ret, expected)

    def test_installed_new_with_exc(self):
        '''
        Test if it returns False when install packages fails (exception)
        '''

        mock_list = MagicMock(return_value={})
        mock_install = MagicMock(side_effect=CommandExecutionError)

        with patch.dict(bower.__salt__, {'bower.list': mock_list,
                                         'bower.install': mock_install}):
            ret = bower.installed('underscore', '/path/to/project')
            expected = {'name': 'underscore',
                        'result': False,
                        'comment': 'Error installing \'underscore\': ',
                        'changes': {}}
            self.assertEqual(ret, expected)

    def test_installed_new_with_error(self):
        '''
        Test if returns False when install packages fails (bower error)
        '''

        mock_list = MagicMock(return_value={})
        mock_install = MagicMock(return_value=False)

        with patch.dict(bower.__salt__, {'bower.list': mock_list,
                                         'bower.install': mock_install}):
            ret = bower.installed('underscore', '/path/to/project')
            expected = {'name': 'underscore',
                        'result': False,
                        'comment':
                            'Could not install package(s) \'underscore\'',
                        'changes': {}}
            self.assertEqual(ret, expected)

    def test_installed_success(self):
        '''
        Test if it returns True when install succeeds
        '''

        mock_list = MagicMock(return_value={})
        mock_install = MagicMock(return_value=True)

        with patch.dict(bower.__salt__, {'bower.list': mock_list,
                                         'bower.install': mock_install}):
            ret = bower.installed('underscore', '/path/to/project')
            expected = {'name': 'underscore',
                        'result': True,
                        'comment':
                            'Package(s) \'underscore\' successfully installed',
                        'changes': {'new': ['underscore'], 'old': []}}
            self.assertEqual(ret, expected)
