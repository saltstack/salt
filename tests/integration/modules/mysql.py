# -*- coding: utf-8 -*-

# Import python libs
import os

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
    @skipIf(salt.utils.is_windows(), 'not tested on windows yet')
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
    @skipIf(salt.utils.is_windows(), 'not tested on windows yet')
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
        self.assertTrue(ret)

        # test db exists
        ret = self.run_function(
          'mysql.db_exists',
          name='foo 1',
          connection_user=self.user,
          connection_pass=self.password
        )
        self.assertTrue(ret)

        # redoing the same should fail
        ret = self.run_function(
          'mysql.db_create',
          name='foo 1',
          connection_user=self.user,
          connection_pass=self.password
        )
        self.assertFalse(ret)

        # Now remove database
        ret = self.run_function(
          'mysql.db_remove',
          name='foo 1',
          connection_user=self.user,
          connection_pass=self.password
        )
        self.assertTrue(ret)

    @destructiveTest
    @skipIf(salt.utils.is_windows(), 'not tested on windows yet')
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
        self.assertTrue(ret)
        # test db exists
        ret = self.run_function(
          'mysql.db_exists',
          name='foo`2',
          connection_user=self.user,
          connection_pass=self.password
        )
        self.assertTrue(ret)
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
        self.assertFalse(ret)
        # redoing the same should fail
        ret = self.run_function(
          'mysql.db_create',
          name='foo`2',
          character_set='utf8',
          collate='utf8_general_ci',
          connection_user=self.user,
          connection_pass=self.password
        )
        self.assertFalse(ret)
        # Now remove database
        ret = self.run_function(
          'mysql.db_remove',
          name='foo`2',
          connection_user=self.user,
          connection_pass=self.password
        )
        self.assertTrue(ret)

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
        self.assertTrue(ret)
        # test db exists
        ret = self.run_function(
          'mysql.db_exists',
          name="foo'3",
          connection_user=self.user,
          connection_pass=self.password
        )
        self.assertTrue(ret)
        # Now remove database
        ret = self.run_function(
          'mysql.db_remove',
          name="foo'3",
          connection_user=self.user,
          connection_pass=self.password
        )
        self.assertTrue(ret)

        # """"""""
        # also with collate only
        ret = self.run_function(
          'mysql.db_create',
          name='foo"4',
          collate='utf8_general_ci',
          connection_user=self.user,
          connection_pass=self.password
        )
        self.assertTrue(ret)
        # test db exists
        ret = self.run_function(
          'mysql.db_exists',
          name='foo"4',
          connection_user=self.user,
          connection_pass=self.password
        )
        self.assertTrue(ret)
        # Now remove database
        ret = self.run_function(
          'mysql.db_remove',
          name='foo"4',
          connection_user=self.user,
          connection_pass=self.password
        )
        self.assertTrue(ret)

        # Unicode
        ret = self.run_function(
            'mysql.db_create',
            name=u'標準語',
            connection_user=self.user,
            connection_pass=self.password
        )
        self.assertTrue(ret)
        # test db exists
        ret = self.run_function(
            'mysql.db_exists',
            name=u'標準語',
            connection_user=self.user,
            connection_pass=self.password
        )
        self.assertTrue(ret)
        # Now remove database
        ret = self.run_function(
            'mysql.db_remove',
            name=u'標準語',
            connection_user=self.user,
            connection_pass=self.password
        )
        self.assertTrue(ret)

if __name__ == '__main__':
    from integration import run_tests
    run_tests(MysqlModuleTest)
