# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON
)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import sqlite3
import salt


class MockSqlite3(object):
    '''
    Mock sqlite3 class
    '''
    version = '2.6.0'
    sqlite_version = '3.8.2'

    def __init__(self):
        self.dbase = None
        self.isolation_level = None

    def connect(self, dbase, isolation_level=None):
        '''
        Mock connect method
        '''
        self.dbase = dbase
        self.isolation_level = isolation_level
        return MockSqlite3()

    @staticmethod
    def cursor():
        '''
        Mock connect method
        '''
        return MockSqlite3()

    @staticmethod
    def execute(sql):
        '''
        Mock connect method
        '''
        return sql

    @staticmethod
    def fetchall():
        '''
        Mock connect method
        '''
        return True

salt.modules.sqlite3.sqlite3 = MockSqlite3()


@skipIf(NO_MOCK, NO_MOCK_REASON)
class Sqlite3TestCase(TestCase):
    '''
    TestCase for salt.modules.sqlite3
    '''
    # 'version' function tests: 1

    def test_version(self):
        '''
        Tests if it return version of pysqlite.
        '''
        self.assertEqual(sqlite3.version(), '2.6.0')

    # 'sqlite_version' function tests: 1

    def test_sqlite_version(self):
        '''
        Tests if it return version of sqlite.
        '''
        self.assertEqual(sqlite3.sqlite_version(), '3.8.2')

    # 'modify' function tests: 1

    def test_modify(self):
        '''
        Tests if it issue an SQL query to sqlite3 (with no return data).
        '''
        self.assertFalse(sqlite3.modify())

        self.assertTrue(sqlite3.modify
                        ('/root/test.db',
                         'CREATE TABLE test(id INT, testdata TEXT);'))

    # 'fetch' function tests: 1

    def test_fetch(self):
        '''
        Tests if it retrieve data from an sqlite3 db
        (returns all rows, be careful!)
        '''
        self.assertFalse(sqlite3.fetch())

        self.assertTrue(sqlite3.fetch
                        ('/root/test.db',
                         'CREATE TABLE test(id INT, testdata TEXT);'))

    # 'tables' function tests: 1

    def test_tables(self):
        '''
        Tests if it show all tables in the database.
        '''
        self.assertFalse(sqlite3.tables())

        self.assertTrue(sqlite3.tables('/root/test.db'))

    # 'indices' function tests: 1

    def test_indices(self):
        '''
        Tests if it show all indices in the database.
        '''
        self.assertFalse(sqlite3.indices())

        self.assertTrue(sqlite3.indices('/root/test.db'))

    # 'indexes' function tests: 1

    def test_indexes(self):
        '''
        Tests if it show all indices in the database,
        for people with poor spelling skills
        '''
        self.assertTrue(sqlite3.indexes('/root/test.db'))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(Sqlite3TestCase, needs_daemon=False)
