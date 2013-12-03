# -*- coding: utf-8 -*-

# Import python libs
import os
import logging

from mock import patch, MagicMock

# Import Salt Testing libs
from salttesting import skipIf
from salttesting.helpers import (
    destructiveTest,
    ensure_in_syspath,
    requires_system_grains
)
ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils
from salt.modules import mysql as mysqlmod

log = logging.getLogger(__name__)

NO_MYSQL = False
try:
    import MySQLdb
except Exception:
    NO_MYSQL = True


@skipIf(NO_MYSQL, 'Install MySQL bindings and a MySQL Server before running MySQL integration tests.')
class MysqlModuleTest(integration.ModuleCase,
                      integration.SaltReturnAssertsMixIn):

    user = 'root'
    password = 'poney'

    @destructiveTest
    def setUp(self):
        '''
        Test presence of MySQL server, enforce a root password
        '''
        super(MysqlModuleTest, self).setUp()
        NO_MYSQL_SERVER = True
        # now ensure we know the mysql root password
        # one of theses two at least should work
        ret1 = self.run_state(
            'cmd.run',
             name='mysqladmin -u '
               + self.user
               + ' flush-privileges password "'
               + self.password
               + '"'
        )
        ret2 = self.run_state(
            'cmd.run',
             name='mysqladmin -u '
               + self.user
               + ' --password="'
               + self.password
               + '" flush-privileges password "'
               + self.password
               + '"'
        )
        key, value = ret2.popitem()
        if value['result']:
            NO_MYSQL_SERVER = False
        else:
            self.skipTest('No MySQL Server running, or no root access on it.')

    def _db_creation_loop(self, db_name, returning_name, **kwargs):
        '''
        Used in testCase, create, check existence, check name in db list and removes database
        '''
        ret = self.run_function(
            'mysql.db_create',
            name=db_name,
            **kwargs
        )
        self.assertEqual(True, ret, 'Problem while creating db for db name: {0!r}'.format(db_name))
        # test db exists
        ret = self.run_function(
            'mysql.db_exists',
            name=db_name,
            **kwargs
        )
        self.assertEqual(True, ret, 'Problem while testing db exists for db name: {0!r}'.format(db_name))
        # List db names to ensure db is created with the right utf8 string
        ret = self.run_function(
            'mysql.db_list',
            **kwargs
        )
        if not isinstance(ret, list):
            raise AssertionError(
                    'Unexpected query result while retrieving databases list {0!r} for {1!r} test'.format(
                         ret,
                         db_name
                    )
                )
        self.assertIn(returning_name,
                      ret,
                      ('Problem while testing presence of db name in db lists'
                       ' for db name: {0!r} in list {1!r}').format(
                          db_name,
                          ret
                     ))
        # Now remove database
        ret = self.run_function(
            'mysql.db_remove',
            name=db_name,
            **kwargs
        )
        self.assertEqual(True, ret, 'Problem while removing db for db name: {0!r}'.format(db_name))

    @destructiveTest
    def test_database_creation_level1(self):
        '''
        Create database, test presence, then drop db. All theses with complex names.
        '''
        # name with space
        db_name = 'foo 1'
        self._db_creation_loop(db_name=db_name,
                               returning_name=db_name,
                               connection_user=self.user,
                               connection_pass=self.password
        )

        # ```````
        # create
        # also with character_set and collate only
        ret = self.run_function(
          'mysql.db_create',
          name='foo`2',
          character_set='utf8',
          collate='utf8_general_ci',
          connection_user=self.user,
          connection_pass=self.password
        )
        self.assertEqual(True, ret)
        # test db exists
        ret = self.run_function(
          'mysql.db_exists',
          name='foo`2',
          connection_user=self.user,
          connection_pass=self.password
        )
        self.assertEqual(True, ret)
        # redoing the same should fail
        # even with other character sets or collations
        ret = self.run_function(
          'mysql.db_create',
          name='foo`2',
          character_set='utf8',
          collate='utf8_general_ci',
          connection_user=self.user,
          connection_pass=self.password
        )
        self.assertEqual(False, ret)
        # redoing the same should fail
        ret = self.run_function(
          'mysql.db_create',
          name='foo`2',
          character_set='utf8',
          collate='utf8_general_ci',
          connection_user=self.user,
          connection_pass=self.password
        )
        self.assertEqual(False, ret)
        # Now remove database
        ret = self.run_function(
          'mysql.db_remove',
          name='foo`2',
          connection_user=self.user,
          connection_pass=self.password
        )
        self.assertEqual(True, ret)

        # '''''''
        # create
        # also with character_set only
        db_name = "foo'3"
        self._db_creation_loop(db_name=db_name,
                               returning_name=db_name,
                               character_set='utf8',
                               connection_user=self.user,
                               connection_pass=self.password
        )

        # """"""""
        # also with collate only
        db_name = 'foo"4'
        self._db_creation_loop(db_name=db_name,
                               returning_name=db_name,
                               collate='utf8_general_ci',
                               connection_user=self.user,
                               connection_pass=self.password
        )
        # fuzzy
        db_name = '<foo` --"5>'
        self._db_creation_loop(db_name=db_name,
                               returning_name=db_name,
                               connection_user=self.user,
                               connection_pass=self.password
        )

    @destructiveTest
    def test_database_creation_utf8(self):
        '''
        Test support of utf8 in database names
        '''
        # Simple accents : using utf8 string
        db_name_unicode = u'notam\xe9rican'
        # same as 'notamérican' because of file encoding
        # but ensure it on this test
        db_name_utf8 = 'notam\xc3\xa9rican'
        db_name = db_name_utf8
        self._db_creation_loop(db_name=db_name_utf8,
                               returning_name=db_name_utf8,
                               connection_user=self.user,
                               connection_pass=self.password,
                               connection_use_unicode=True,
                               connection_charset='utf8',
                               saltenv={"LC_ALL": "en_US.utf8"}
        )
        # test unicode entry will also return utf8 name
        self._db_creation_loop(db_name=db_name_unicode,
                               returning_name=db_name_utf8,
                               connection_user=self.user,
                               connection_pass=self.password,
                               connection_use_unicode=True,
                               connection_charset='utf8',
                               saltenv={"LC_ALL": "en_US.utf8"}
        )
        # Using more complex unicode characters:
        db_name_unicode = u'\u6a19\u6e96\u8a9e'
        # same as '標準語' because of file encoding
        # but ensure it on this test
        db_name_utf8 = '\xe6\xa8\x99\xe6\xba\x96\xe8\xaa\x9e'
        self._db_creation_loop(db_name=db_name_utf8,
                               returning_name=db_name_utf8,
                               connection_user=self.user,
                               connection_pass=self.password,
                               connection_use_unicode=True,
                               connection_charset='utf8',
                               saltenv={"LC_ALL": "en_US.utf8"}
        )
        # test unicode entry will also return utf8 name
        self._db_creation_loop(db_name=db_name_unicode,
                               returning_name=db_name_utf8,
                               connection_user=self.user,
                               connection_pass=self.password,
                               connection_use_unicode=True,
                               connection_charset='utf8',
                               saltenv={"LC_ALL": "en_US.utf8"}
        )

    @destructiveTest
    def test_database_maintenance(self):
        '''
        Test maintenance operations on a created database
        '''
        dbname = u"foo'-- `\"'"
        # create database
        # but first silently try to remove it
        # in case of previous tests failures
        ret = self.run_function(
          'mysql.db_remove',
          name=dbname,
          connection_user=self.user,
          connection_pass=self.password
        )
        ret = self.run_function(
          'mysql.db_create',
          name=dbname,
          character_set='utf8',
          collate='utf8_general_ci',
          connection_user=self.user,
          connection_pass=self.password
        )
        self.assertEqual(True, ret)
        # test db exists
        ret = self.run_function(
          'mysql.db_exists',
          name=dbname,
          connection_user=self.user,
          connection_pass=self.password
        )
        self.assertEqual(True, ret)
        # Create 3 tables
        tablenames = {'Atable "`1': 'MYISAM', 'Btable \'`2': 'InnoDB', 'Ctable --`3': 'MEMORY'}
        for tablename, engine in iter(sorted(tablenames.iteritems())):
            # prepare queries
            create_query = ('CREATE TABLE %(tblname)s ('
                ' id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,'
                ' data VARCHAR(100)) ENGINE=%(engine)s;') % dict(
                    tblname=mysqlmod.quote_identifier(tablename),
                    engine=engine,
                )
            insert_query = ('INSERT INTO %(tblname)s (data)'
                ' VALUES ') % dict(tblname=mysqlmod.quote_identifier(tablename))
            delete_query = ('DELETE from  %(tblname)s'
                ' order by rand() limit 50;') % dict(tblname=mysqlmod.quote_identifier(tablename))
            for x in range(100):
                insert_query += "('foo"+str(x)+"'),"
            insert_query += "('bar');"

            # populate database
            log.info('Adding table{0!r}'.format(tablename,))
            ret = self.run_function(
              'mysql.query',
              database=dbname,
              query=create_query,
              connection_user=self.user,
              connection_pass=self.password
            )
            if not isinstance(ret, dict) or 'rows affected' not in ret:
                raise AssertionError(
                    'Unexpected query result while populating test table {0!r} : {1!r}'.format(
                         tablename,
                         ret,
                    )
                )
            self.assertEqual(ret['rows affected'], 0)
            log.info('Populating table{0!r}'.format(tablename,))
            ret = self.run_function(
              'mysql.query',
              database=dbname,
              query=insert_query,
              connection_user=self.user,
              connection_pass=self.password
            )
            if not isinstance(ret, dict) or 'rows affected' not in ret:
                raise AssertionError(
                    'Unexpected query result while populating test table {0!r} : {1!r}'.format(
                         tablename,
                         ret,
                    )
                )
            self.assertEqual(ret['rows affected'], 101)
            log.info('Removing some rows on table{0!r}'.format(tablename,))
            ret = self.run_function(
              'mysql.query',
              database=dbname,
              query=delete_query,
              connection_user=self.user,
              connection_pass=self.password
            )
            if not isinstance(ret, dict) or 'rows affected' not in ret:
                raise AssertionError(
                    ('Unexpected query result while removing rows on test table'
                     ' {0!r} : {1!r}').format(
                         tablename,
                         ret,
                    )
                )
            self.assertEqual(ret['rows affected'], 50)
        # test check/repair/opimize on 1 table
        tablename = 'Atable "`1'
        ret = self.run_function(
          'mysql.db_check',
          name=dbname,
          table=tablename,
          connection_user=self.user,
          connection_pass=self.password
        )
        # Note that returned result does not quote_identifier of table and db
        self.assertEqual(ret, [{'Table': dbname+'.'+tablename, 'Msg_text': 'OK', 'Msg_type': 'status', 'Op': 'check'}])
        ret = self.run_function(
          'mysql.db_repair',
          name=dbname,
          table=tablename,
          connection_user=self.user,
          connection_pass=self.password
        )
        # Note that returned result does not quote_identifier of table and db
        self.assertEqual(ret, [{'Table': dbname+'.'+tablename, 'Msg_text': 'OK', 'Msg_type': 'status', 'Op': 'repair'}])
        ret = self.run_function(
          'mysql.db_optimize',
          name=dbname,
          table=tablename,
          connection_user=self.user,
          connection_pass=self.password
        )
        # Note that returned result does not quote_identifier of table and db
        self.assertEqual(ret, [{'Table': dbname+'.'+tablename, 'Msg_text': 'OK', 'Msg_type': 'status', 'Op': 'optimize'}])

        # test check/repair/opimize on all tables
        ret = self.run_function(
          'mysql.db_check',
          name=dbname,
          connection_user=self.user,
          connection_pass=self.password
        )
        expected = []
        for tablename, engine in iter(sorted(tablenames.iteritems())):
            if engine is 'MEMORY':
                expected.append([{
                    'Table': dbname+'.'+tablename,
                    'Msg_text': "The storage engine for the table doesn't support check",
                    'Msg_type': 'note',
                    'Op': 'check'
                }])
            else:
                expected.append([{
                    'Table': dbname+'.'+tablename,
                    'Msg_text': 'OK',
                    'Msg_type': 'status',
                    'Op': 'check'
                }])
        self.assertEqual(ret, expected)

        ret = self.run_function(
          'mysql.db_repair',
          name=dbname,
          connection_user=self.user,
          connection_pass=self.password
        )
        expected = []
        for tablename, engine in iter(sorted(tablenames.iteritems())):
            if engine is 'MYISAM':
                expected.append([{
                    'Table': dbname+'.'+tablename,
                    'Msg_text': 'OK',
                    'Msg_type': 'status',
                    'Op': 'repair'
                }])
            else:
                expected.append([{
                    'Table': dbname+'.'+tablename,
                    'Msg_text': "The storage engine for the table doesn't support repair",
                    'Msg_type': 'note',
                    'Op': 'repair'
                }])
        self.assertEqual(ret, expected)

        ret = self.run_function(
          'mysql.db_optimize',
          name=dbname,
          connection_user=self.user,
          connection_pass=self.password
        )

        expected = []
        for tablename, engine in iter(sorted(tablenames.iteritems())):
            if engine is 'MYISAM':
                expected.append([{
                    'Table': dbname+'.'+tablename,
                    'Msg_text': 'OK',
                    'Msg_type': 'status',
                    'Op': 'optimize'
                }])
            elif engine is 'InnoDB':
                expected.append([{
                    'Table': dbname+'.'+tablename,
                    'Msg_text': ("Table does not support optimize, "
                                 "doing recreate + analyze instead"),
                    'Msg_type': 'note',
                    'Op': 'optimize'
                },
                {
                    'Table': dbname+'.'+tablename,
                    'Msg_text': 'OK',
                    'Msg_type': 'status',
                    'Op': 'optimize'
                }])
            elif engine is 'MEMORY':
                expected.append([{
                    'Table': dbname+'.'+tablename,
                    'Msg_text': "The storage engine for the table doesn't support optimize",
                    'Msg_type': 'note',
                    'Op': 'optimize'
                }])
        self.assertEqual(ret, expected)
        # Teardown, remove database
        ret = self.run_function(
          'mysql.db_remove',
          name=dbname,
          connection_user=self.user,
          connection_pass=self.password
        )
        self.assertEqual(True, ret)

if __name__ == '__main__':
    from integration import run_tests
    run_tests(MysqlModuleTest)
