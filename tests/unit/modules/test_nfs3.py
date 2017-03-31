# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    mock_open,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.modules.nfs3 as nfs3


@skipIf(NO_MOCK, NO_MOCK_REASON)
class NfsTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.nfs3
    '''
    def setup_loader_modules(self):
        return {nfs3: {}}

    def test_list_exports(self):
        '''
        Test for List configured exports
        '''
        file_d = '\n'.join(['A B1(23'])
        with patch('salt.utils.fopen',
                   mock_open(read_data=file_d), create=True) as mfi:
            mfi.return_value.__iter__.return_value = file_d.splitlines()
            self.assertDictEqual(nfs3.list_exports(),
                                 {'A': [{'hosts': ['B1'], 'options': ['23']}]})

    def test_del_export(self):
        '''
        Test for Remove an export
        '''
        with patch.object(nfs3,
                          'list_exports',
                          return_value={'A':
                                        [{'hosts':
                                          ['B1'], 'options': ['23']}]}):
            with patch.object(nfs3, '_write_exports', return_value=None):
                self.assertDictEqual(nfs3.del_export(path='A'), {})
