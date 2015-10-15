# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    mock_open,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import nfs3

# Globals
nfs3.__grains__ = {}
nfs3.__salt__ = {}
nfs3.__context__ = {}
nfs3.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class NfsTestCase(TestCase):
    '''
    Test cases for salt.modules.nfs3
    '''
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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(NfsTestCase, needs_daemon=False)
