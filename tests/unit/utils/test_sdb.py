# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Vernon Cole <vernondcole@gmail.com>`
'''

# Import Python Libs
from __future__ import absolute_import
import os

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.utils.sdb as sdb
import salt.exceptions

TEMP_DATABASE_FILE = '/tmp/salt-tests-tmpdir/test_sdb.sqlite'

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
        except:
            pass

    def setup_loader_modules(self):
        return {sdb: {}}

    # test with SQLite database key not presest

    def test_sqlite_get_not_found(self):
        what = sdb.sdb_get(
                'sdb://test_sdb_data/thisKeyDoesNotExist', SDB_OPTS)
        self.assertEqual(what, None, 'what is "{!r}"'.format(what))

    # test with SQLite database write and read

    def test_sqlite_get_found(self):
        expected = dict(name='testone',
                        number=46,
                        )
        sdb.sdb_set('sdb://test_sdb_data/test1', expected, SDB_OPTS)
        resp = sdb.sdb_get('sdb://test_sdb_data/test1', SDB_OPTS)
        self.assertEqual(resp, expected)
