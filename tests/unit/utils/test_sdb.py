# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Vernon Cole <vernondcole@gmail.com>`
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import os

# Import Salt Testing Libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.utils.sdb as sdb

TEMP_DATABASE_FILE = os.path.join(RUNTIME_VARS.TMP, 'test_sdb.sqlite')

SDB_OPTS = {
            'extension_modules': '',
            'test_sdb_data': {
                'driver': 'sqlite3',
                'database': TEMP_DATABASE_FILE,
                'table': 'sdb',
                'create_table': True
                }
            }


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SdbTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.sdb
    '''

    @classmethod
    def tearDownClass(cls):
        try:
            os.unlink(TEMP_DATABASE_FILE)
        except OSError:
            pass

    def setup_loader_modules(self):
        return {sdb: {}}

    # test with SQLite database key not presest

    def test_sqlite_get_not_found(self):
        what = sdb.sdb_get(
                'sdb://test_sdb_data/thisKeyDoesNotExist', SDB_OPTS)
        self.assertEqual(what, None)

    # test with SQLite database write and read

    def test_sqlite_get_found(self):
        expected = {b'name': b'testone', b'number': 46}
        sdb.sdb_set('sdb://test_sdb_data/test1', expected, SDB_OPTS)
        resp = sdb.sdb_get('sdb://test_sdb_data/test1', SDB_OPTS)
        self.assertEqual(resp, expected)
