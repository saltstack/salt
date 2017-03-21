# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python libs
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
import salt.modules.dpkg as dpkg


@skipIf(NO_MOCK, NO_MOCK_REASON)
class DpkgTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.dpkg
    '''
    loader_module = dpkg
    # 'unpurge' function tests: 2

    def test_unpurge(self):
        '''
        Test if it change package selection for each package
        specified to 'install'
        '''
        mock = MagicMock(return_value=[])
        with patch.dict(dpkg.__salt__, {'pkg.list_pkgs': mock,
                                        'cmd.run': mock}):
            self.assertDictEqual(dpkg.unpurge('curl'), {})

    def test_unpurge_empty_package(self):
        '''
        Test if it change package selection for each package
        specified to 'install'
        '''
        self.assertDictEqual(dpkg.unpurge(), {})

    # 'list_pkgs' function tests: 1

    def test_list_pkgs(self):
        '''
        Test if it lists the packages currently installed
        '''
        mock = MagicMock(return_value={'retcode': 0,
                                       'stderr': '',
                                       'stdout': 'Salt'})
        with patch.dict(dpkg.__salt__, {'cmd.run_all': mock}):
            self.assertDictEqual(dpkg.list_pkgs('httpd'), {})

        mock = MagicMock(return_value={'retcode': 1,
                                       'stderr': 'error',
                                       'stdout': 'Salt'})
        with patch.dict(dpkg.__salt__, {'cmd.run_all': mock}):
            self.assertEqual(dpkg.list_pkgs('httpd'), 'Error:  error')

    # 'file_list' function tests: 1

    def test_file_list(self):
        '''
        Test if it lists the files that belong to a package.
        '''
        mock = MagicMock(return_value={'retcode': 0,
                                       'stderr': '',
                                       'stdout': 'Salt'})
        with patch.dict(dpkg.__salt__, {'cmd.run_all': mock}):
            self.assertDictEqual(dpkg.file_list('httpd'),
                                 {'errors': [], 'files': []})

        mock = MagicMock(return_value={'retcode': 1,
                                       'stderr': 'error',
                                       'stdout': 'Salt'})
        with patch.dict(dpkg.__salt__, {'cmd.run_all': mock}):
            self.assertEqual(dpkg.file_list('httpd'), 'Error:  error')

    # 'file_dict' function tests: 1

    def test_file_dict(self):
        '''
        Test if it lists the files that belong to a package, grouped by package
        '''
        mock = MagicMock(return_value={'retcode': 0,
                                       'stderr': '',
                                       'stdout': 'Salt'})
        with patch.dict(dpkg.__salt__, {'cmd.run_all': mock}):
            self.assertDictEqual(dpkg.file_dict('httpd'),
                                 {'errors': [], 'packages': {}})

        mock = MagicMock(return_value={'retcode': 1,
                                       'stderr': 'error',
                                       'stdout': 'Salt'})
        with patch.dict(dpkg.__salt__, {'cmd.run_all': mock}):
            self.assertEqual(dpkg.file_dict('httpd'), 'Error:  error')
