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

    @destructiveTest
    def test_database_creation_level1(self):
        '''
        Create database, test it exists and remove it
        '''
        # create
        ret = self.run_function(
          'mysql.db_create',
          name='foo 1',
          connection_user=self.user,
          connection_pass=self.password
        )
        self.assertEqual(True,ret)

        # test db exists
        ret = self.run_function(
          'mysql.db_exists',
          name='foo 1',
          connection_user=self.user,
          connection_pass=self.password
        )
        self.assertEqual(True,ret)

        # redoing the same should fail
        ret = self.run_function(
          'mysql.db_create',
          name='foo 1',
          connection_user=self.user,
          connection_pass=self.password
        )
        self.assertEqual(False,ret)

        # Now remove database
        ret = self.run_function(
          'mysql.db_remove',
          name='foo 1',
          connection_user=self.user,
          connection_pass=self.password
        )
        self.assertEqual(True,ret)

    @destructiveTest
    def test_database_creation_level2(self):
        '''
        Same as level1 with strange names and with character set and collate keywords
        '''
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
        self.assertEqual(True,ret)
        # test db exists
        ret = self.run_function(
          'mysql.db_exists',
          name='foo`2',
          connection_user=self.user,
          connection_pass=self.password
        )
        self.assertEqual(True,ret)
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
        self.assertEqual(False,ret)
        # redoing the same should fail
        ret = self.run_function(
          'mysql.db_create',
          name='foo`2',
          character_set='utf8',
          collate='utf8_general_ci',
          connection_user=self.user,
          connection_pass=self.password
        )
        self.assertEqual(False,ret)
        # Now remove database
        ret = self.run_function(
          'mysql.db_remove',
          name='foo`2',
          connection_user=self.user,
          connection_pass=self.password
        )
        self.assertEqual(True,ret)

        # '''''''
        # create
        # also with character_set only
        ret = self.run_function(
          'mysql.db_create',
          name="foo'3",
          character_set='utf8',
          connection_user=self.user,
          connection_pass=self.password
        )
        self.assertEqual(True,ret)
        # test db exists
        ret = self.run_function(
          'mysql.db_exists',
          name="foo'3",
          connection_user=self.user,
          connection_pass=self.password
        )
        self.assertEqual(True,ret)
        # Now remove database
        ret = self.run_function(
          'mysql.db_remove',
          name="foo'3",
          connection_user=self.user,
          connection_pass=self.password
        )
        self.assertEqual(True,ret)

        # """"""""
        # also with collate only
        ret = self.run_function(
          'mysql.db_create',
          name='foo"4',
          collate='utf8_general_ci',
          connection_user=self.user,
          connection_pass=self.password
        )
        self.assertEqual(True,ret)
        # test db exists
        ret = self.run_function(
          'mysql.db_exists',
          name='foo"4',
          connection_user=self.user,
          connection_pass=self.password
        )
        self.assertEqual(True,ret)
        # Now remove database
        ret = self.run_function(
          'mysql.db_remove',
          name='foo"4',
          connection_user=self.user,
          connection_pass=self.password
        )
        self.assertEqual(True,ret)

        # TODO: Simple accents :
        #db_name=u'notamérican'
        #ret = self.run_function(
        #    'mysql.db_create',
        #    name=db_name,
        #    connection_user=self.user,
        #    connection_pass=self.password
        #)
        #self.assertEqual(True,ret)
        # test db exists
        #ret = self.run_function(
        #    'mysql.db_exists',
        #    name=db_name,
        #    connection_user=self.user,
        #    connection_pass=self.password
        #)
        #self.assertEqual(True,ret)
        # Now remove database
        #ret = self.run_function(
        #    'mysql.db_remove',
        #    name=db_name,
        #    connection_user=self.user,
        #    connection_pass=self.password
        #)
        #self.assertEqual(True,ret)

        # TODO: Unicode, currently Failing on :
        # UnicodeDecodeError: \'ascii\' codec can\'t decode byte 0xe6 in position 1: ordinal not in range(128)
        # something like: '標準語'
        #unicode_str=u'\u6a19\u6e96\u8a9e'
        #db_name=unicode_str.encode('utf8')
        #ret = self.run_function(
        #    'mysql.db_create',
        #    name=db_name,
        #    connection_user=self.user,
        #    connection_pass=self.password
        #)
        #self.assertEqual(True,ret)
        # test db exists
        #ret = self.run_function(
        #    'mysql.db_exists',
        #    name=db_name,
        #    connection_user=self.user,
        #    connection_pass=self.password
        #)
        #self.assertEqual(True,ret)
        # Now remove database
        #ret = self.run_function(
        #    'mysql.db_remove',
        #    name=db_name,
        #    connection_user=self.user,
        #    connection_pass=self.password
        #)
        #self.assertEqual(True,ret)

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
        self.assertEqual(True,ret)
        # test db exists
        ret = self.run_function(
          'mysql.db_exists',
          name=dbname,
          connection_user=self.user,
          connection_pass=self.password
        )
        self.assertEqual(True,ret)
        # Create 3 tables
        tablenames = {'Atable "`1': 'MYISAM', 'Btable \'`2': 'InnoDB', 'Ctable --`3': 'MEMORY'}
        for tablename,engine in iter(sorted(tablenames.iteritems())):
            # prepare queries
            create_query = ('CREATE TABLE %(tblname)s ('
                ' id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,'
                ' data VARCHAR(100)) ENGINE=%(engine)s;') % dict(
                    tblname=mysqlmod.quoteIdentifier(tablename),
                    engine=engine,
                )
            insert_query = ('INSERT INTO %(tblname)s (data)'
                ' VALUES ') % dict(tblname=mysqlmod.quoteIdentifier(tablename))
            delete_query = ('DELETE from  %(tblname)s'
                ' order by rand() limit 50;') % dict(tblname=mysqlmod.quoteIdentifier(tablename))
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
            if not isinstance(ret,dict) or not ret.has_key('rows affected'):
                raise AssertionError(
                    'Unexpected query result while populating test table {0!r} : {1!r}'.format(
                         tablename,
                         ret,
                    )
                )
            self.assertEqual(ret['rows affected'],0)
            log.info('Populating table{0!r}'.format(tablename,))
            ret = self.run_function(
              'mysql.query',
              database=dbname,
              query=insert_query,
              connection_user=self.user,
              connection_pass=self.password
            )
            if not isinstance(ret,dict) or not ret.has_key('rows affected'):
                raise AssertionError(
                    'Unexpected query result while populating test table {0!r} : {1!r}'.format(
                         tablename,
                         ret,
                    )
                )
            self.assertEqual(ret['rows affected'],101)
            log.info('Removing some rows on table{0!r}'.format(tablename,))
            ret = self.run_function(
              'mysql.query',
              database=dbname,
              query=delete_query,
              connection_user=self.user,
              connection_pass=self.password
            )
            if not isinstance(ret,dict) or not ret.has_key('rows affected'):
                raise AssertionError(
                    ('Unexpected query result while removing rows on test table'
                     ' {0!r} : {1!r}').format(
                         tablename,
                         ret,
                    )
                )
            self.assertEqual(ret['rows affected'],50)
        # test check/repair/opimize on 1 table
        tablename='Atable "`1'
        ret = self.run_function(
          'mysql.db_check',
          name=dbname,
          table=tablename,
          connection_user=self.user,
          connection_pass=self.password
        )
        # Note that returned result does not quoteIdentifier of table and db
        self.assertEqual(ret,[{'Table': dbname+'.'+tablename, 'Msg_text': 'OK', 'Msg_type': 'status', 'Op': 'check'}])
        ret = self.run_function(
          'mysql.db_repair',
          name=dbname,
          table=tablename,
          connection_user=self.user,
          connection_pass=self.password
        )
        # Note that returned result does not quoteIdentifier of table and db
        self.assertEqual(ret,[{'Table': dbname+'.'+tablename, 'Msg_text': 'OK', 'Msg_type': 'status', 'Op': 'repair'}])
        ret = self.run_function(
          'mysql.db_optimize',
          name=dbname,
          table=tablename,
          connection_user=self.user,
          connection_pass=self.password
        )
        # Note that returned result does not quoteIdentifier of table and db
        self.assertEqual(ret,[{'Table': dbname+'.'+tablename, 'Msg_text': 'OK', 'Msg_type': 'status', 'Op': 'optimize'}])

        # test check/repair/opimize on all tables
        ret = self.run_function(
          'mysql.db_check',
          name=dbname,
          connection_user=self.user,
          connection_pass=self.password
        )
        expected=[]
        for tablename,engine in iter(sorted(tablenames.iteritems())):
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
        self.assertEqual(ret,expected)

        ret = self.run_function(
          'mysql.db_repair',
          name=dbname,
          connection_user=self.user,
          connection_pass=self.password
        )
        expected=[]
        for tablename,engine in iter(sorted(tablenames.iteritems())):
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
        self.assertEqual(ret,expected)

        ret = self.run_function(
          'mysql.db_optimize',
          name=dbname,
          connection_user=self.user,
          connection_pass=self.password
        )
        
        expected=[]
        for tablename,engine in iter(sorted(tablenames.iteritems())):
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
        self.assertEqual(ret,expected)
        # Teardown, remove database
        ret = self.run_function(
          'mysql.db_remove',
          name=dbname,
          connection_user=self.user,
          connection_pass=self.password
        )
        self.assertEqual(True,ret)

if __name__ == '__main__':
    from integration import run_tests
    run_tests(MysqlModuleTest)
