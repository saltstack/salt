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
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import oracle
import os

# Globals
oracle.__salt__ = {}
oracle.cx_Oracle = object()


@skipIf(NO_MOCK, NO_MOCK_REASON)
class OracleTestCase(TestCase):
    '''
    Test cases for salt.modules.oracle
    '''
    def test_run_query(self):
        '''
        Test for Run SQL query and return result
        '''
        with patch.object(oracle, '_connect', MagicMock()) as mock_connect:
            mock_connect.cursor.execute.fetchall.return_value = True
            with patch.object(oracle, 'show_dbs', MagicMock()):
                self.assertTrue(oracle.run_query('db', 'query'))

    def test_show_dbs(self):
        '''
        Test for Show databases configuration from pillar. Filter by `*args`
        '''
        with patch.dict(oracle.__salt__, {'pillar.get':
                                          MagicMock(return_value='a')}):
            self.assertDictEqual(oracle.show_dbs('A', 'B'),
                                 {'A': 'a', 'B': 'a'})

            self.assertEqual(oracle.show_dbs(), 'a')

    def test_version(self):
        '''
        Test for Server Version (select banner  from v$version)
        '''
        with patch.dict(oracle.__salt__, {'pillar.get':
                                          MagicMock(return_value='a')}):
            with patch.object(oracle, 'run_query', return_value='A'):
                self.assertDictEqual(oracle.version(), {})

    def test_client_version(self):
        '''
        Test for Oracle Client Version
        '''
        with patch.object(oracle, 'cx_Oracle',
                          MagicMock(side_effect=MagicMock())):
            self.assertEqual(oracle.client_version(), '')

    def test_show_pillar(self):
        '''
        Test for Show Pillar segment oracle.*
        '''
        with patch.dict(oracle.__salt__, {'pillar.get':
                                          MagicMock(return_value='a')}):
            self.assertEqual(oracle.show_pillar('item'), 'a')

    def test_show_env(self):
        '''
        Test for Show Environment used by Oracle Client
        '''
        with patch.object(os, 'environ',
                          return_value={'PATH': 'PATH',
                                        'ORACLE_HOME': 'ORACLE_HOME',
                                        'TNS_ADMIN': 'TNS_ADMIN',
                                        'NLS_LANG': 'NLS_LANG'}):
            self.assertDictEqual(oracle.show_env(), {})


if __name__ == '__main__':
    from integration import run_tests
    run_tests(OracleTestCase, needs_daemon=False)
