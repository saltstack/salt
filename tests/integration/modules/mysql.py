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

_PKG_MYSQL = {
    'Debian': ['mysql-server', 'libmysqlclient-dev','python-mysqldb'],
    'RedHat': ['mysql-server', 'mysql','MySQL-python','python26-mysqldb'],
}

class MysqlModuleTest(integration.ModuleCase,
                      integration.SaltReturnAssertsMixIn):

    user='root'
    password='poney'
    present_packages=[]


    @destructiveTest
    @skipIf(salt.utils.is_windows(), 'not tested on windows yet')
    @requires_system_grains
    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    def setUp(self, grains=None):
        '''
        Initialize environnement with a MySQL server, a root password, and python bindings
        ''' 
        super(MysqlModuleTest, self).setUp()
        # Use salt to install MySQL server
        #os_family = self.run_function('grains.item', ['os_family'])
        os_family = grains.get('os_family', '')
        install_pkgs = _PKG_MYSQL.get(os_family, [])
        # Make sure that we have targets that match the os_family. If this
        # fails then the _PKG_MYSQL dict above needs to have an entry added,
        # with mysql packages and python bindings needed for theses test cases
        for pkg in install_pkgs:
            ret = self.run_state('pkg.installed', name=pkg)
            self.assertSaltTrueReturn(ret)
            key, value = ret.popitem()
            if 'is already installed' in value['comment']:
                self.present_packages.append(pkg)

            #if ret
        # now ensure we known the mysql root password
        # one of theses two should work
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

    @destructiveTest
    @skipIf(salt.utils.is_windows(), 'not tested on windows yet')
    @requires_system_grains
    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    def tearDown(self, grains=None):
        # remove ony added mysql packages
        os_family = grains.get('os_family', '')
        install_pkgs = _PKG_MYSQL.get(os_family, [])
        for pkg in install_pkgs:
            if pkg not in self.present_packages:
                self.run_state('pkg.removed', name=pkg)
        super(MysqlModuleTest, self).tearDown()

    @destructiveTest
    @skipIf(salt.utils.is_windows(), 'not tested on windows yet')
    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
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
    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
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
        # TODO: failure in salt highstates, so before me
        #ret = self.run_function(
        #    'mysql.db_create',
        #    name='標準語',
        #    connection_user=self.user,
        #    connection_pass=self.password
        #)
        #self.assertTrue(ret)
        # test db exists
        #ret = self.run_function(
        #    'mysql.db_exists',
        #    name='標準語',
        #    connection_user=self.user,
        #    connection_pass=self.password
        #)
        #self.assertTrue(ret)
        # Now remove database
        #ret = self.run_function(
        #    'mysql.db_remove',
        #    name='標準語',
        #    connection_user=self.user,
        #    connection_pass=self.password
        #)
        #self.assertTrue(ret)

if __name__ == '__main__':
    from integration import run_tests
    run_tests(MysqlModuleTest)
