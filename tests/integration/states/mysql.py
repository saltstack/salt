# -*- coding: utf-8 -*-
'''
Tests for the MySQL states
'''

# Import python libs
from __future__ import absolute_import
import logging

# Import Salt Testing libs
from salttesting import skipIf
from salttesting.helpers import (
    destructiveTest,
    ensure_in_syspath
)
ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.ext.six as six
from salt.modules import mysql as mysqlmod

log = logging.getLogger(__name__)

NO_MYSQL = False
try:
    import MySQLdb  # pylint: disable=import-error,unused-import
except ImportError:
    NO_MYSQL = True


@skipIf(
    NO_MYSQL,
    'Please install MySQL bindings and a MySQL Server before running'
    'MySQL integration tests.'
)
class MysqlDatabaseStateTest(integration.ModuleCase,
                             integration.SaltReturnAssertsMixIn):
    '''
    Validate the mysql_database state
    '''

    user = 'root'
    password = 'poney'

    @destructiveTest
    def setUp(self):
        '''
        Test presence of MySQL server, enforce a root password
        '''
        super(MysqlDatabaseStateTest, self).setUp()
        NO_MYSQL_SERVER = True
        # now ensure we know the mysql root password
        # one of theses two at least should work
        ret1 = self.run_state(
            'cmd.run',
             name='mysqladmin --host="localhost" -u '
               + self.user
               + ' flush-privileges password "'
               + self.password
               + '"'
        )
        ret2 = self.run_state(
            'cmd.run',
             name='mysqladmin --host="localhost" -u '
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

    def _test_database(self, db_name, second_db_name, test_conn, **kwargs):
        '''
        Create db two times, test conn, remove it two times
        '''
        # In case of...
        ret = self.run_state('mysql_database.absent',
                             name=db_name,
                             **kwargs
        )
        ret = self.run_state('mysql_database.present',
                             name=db_name,
                             **kwargs
        )
        self.assertSaltTrueReturn(ret)
        self.assertInSaltComment(
            'The database ' + db_name + ' has been created',
            ret
        )
        #2nd run
        ret = self.run_state('mysql_database.present',
                             name=second_db_name,
                             **kwargs
        )
        self.assertSaltTrueReturn(ret)
        self.assertInSaltComment(
            'Database ' + db_name + ' is already present',
            ret
        )
        if test_conn:
            # test root connection
            ret = self.run_function(
                'mysql.query',
                database=db_name,
                query='SELECT 1',
                **kwargs
            )
            if not isinstance(ret, dict) or 'results' not in ret:
                raise AssertionError(
                    ('Unexpected result while testing connection'
                    ' on db {0!r}: {1}').format(
                        db_name,
                        repr(ret)
                    )
                )
            self.assertEqual([['1']], ret['results'])

        # Now removing databases
        kwargs.pop('character_set')
        kwargs.pop('collate')
        ret = self.run_state('mysql_database.absent',
                             name=db_name,
                             **kwargs
        )
        self.assertSaltTrueReturn(ret)
        self.assertInSaltComment(
            'Database ' + db_name + ' has been removed',
            ret
        )
        #2nd run
        ret = self.run_state('mysql_database.absent',
                             name=second_db_name,
                            ** kwargs
        )
        self.assertSaltTrueReturn(ret)
        self.assertInSaltComment(
            'Database ' + db_name + ' is not present, so it cannot be removed',
            ret
        )
        self.assertSaltStateChangesEqual(ret, {})

    @destructiveTest
    def test_present_absent(self):
        '''
        mysql_database.present
        '''
        self._test_database(
            'testdb1',
            'testdb1',
            test_conn=True,
            character_set='utf8',
            collate='utf8_general_ci',
            connection_user=self.user,
            connection_pass=self.password,
            connection_charset='utf8'
        )

    # TODO: test with variations on collate and charset, check for db alter
    # once it will be done in mysql_database.present state

    @destructiveTest
    def test_present_absent_fuzzy(self):
        '''
        mysql_database.present with utf-8 andf fuzzy db name
        '''
        # this is : ":() ;,?@=`&'\
        dbname_fuzzy = '":() ;,?@=`&/\'\\'
        # \xe6\xa8\x99\ = \u6a19 = 標
        # this is : "();,?:@=`&/標'\
        dbname_utf8 = '"();,?@=`&//\xe6\xa8\x99\'\\'
        dbname_unicode = u'"();,?@=`&//\u6a19\'\\'

        self._test_database(
            dbname_fuzzy,
            dbname_fuzzy,
            test_conn=True,
            character_set='utf8',
            collate='utf8_general_ci',
            connection_user=self.user,
            connection_pass=self.password,
            connection_charset='utf8'
        )

        # FIXME: MySQLdb bugs on dbnames with utf-8?
        self._test_database(
            dbname_utf8,
            dbname_unicode,
            test_conn=False,
            character_set='utf8',
            collate='utf8_general_ci',
            connection_user=self.user,
            connection_pass=self.password,
            connection_charset='utf8',
            #saltenv={"LC_ALL": "en_US.utf8"}
        )

    @destructiveTest
    @skipIf(True, 'This tests needs issue #8947 to be fixed first')
    def test_utf8_from_sls_file(self):
        '''
        Try to create/destroy an utf-8 database name from an sls file #8947
        '''
        expected_result = {
            'mysql_database_|-A_|-foo \xe6\xba\x96`bar_|-present': {
                '__run_num__': 0,
                'comment': 'The database foo \xe6\xba\x96`bar has been created',
                'result': True},
            'mysql_database_|-B_|-foo \xe6\xba\x96`bar_|-absent': {
                '__run_num__': 1,
                'comment': 'Database foo \xe6\xba\x96`bar has been removed',
                'result': True},
        }
        result = {}
        ret = self.run_function('state.sls', mods='mysql_utf8')
        if not isinstance(ret, dict):
            raise AssertionError(
                ('Unexpected result while testing external mysql utf8 sls'
                ': {0}').format(
                    repr(ret)
                )
            )
        for item, descr in six.iteritems(ret):
            result[item] = {
                '__run_num__': descr['__run_num__'],
                'comment': descr['comment'],
                'result': descr['result']
            }
        self.assertEqual(expected_result, result)


@skipIf(
    NO_MYSQL,
    'Please install MySQL bindings and a MySQL Server before running'
    'MySQL integration tests.'
)
class MysqlGrantsStateTest(integration.ModuleCase,
                           integration.SaltReturnAssertsMixIn):
    '''
    Validate the mysql_grants states
    '''

    user = 'root'
    password = 'poney'
    # yep, theses are valid MySQL db names
    # very special chars are _ % and .
    testdb1 = 'tes.t\'"saltdb'
    testdb2 = 't_st `(:=salt%b)'
    testdb3 = 'test `(:=salteeb)'
    table1 = 'foo'
    table2 = "foo `\'%_bar"
    users = {
        'user1': {
            'name': 'foo',
            'pwd': 'bar',
        },
        'user2': {
            'name': 'user ";--,?:&/\\',
            'pwd': '";--(),?:@=&/\\',
        },
        # this is : passwd 標標
        'user3': {
            'name': 'user( @ )=foobar',
            'pwd': '\xe6\xa8\x99\xe6\xa8\x99',
        },
        # this is : user/password containing 標標
        'user4': {
            'name': 'user \xe6\xa8\x99',
            'pwd': '\xe6\xa8\x99\xe6\xa8\x99',
        },
    }

    @destructiveTest
    def setUp(self):
        '''
        Test presence of MySQL server, enforce a root password
        '''
        super(MysqlGrantsStateTest, self).setUp()
        NO_MYSQL_SERVER = True
        # now ensure we know the mysql root password
        # one of theses two at least should work
        ret1 = self.run_state(
            'cmd.run',
             name='mysqladmin --host="localhost" -u '
               + self.user
               + ' flush-privileges password "'
               + self.password
               + '"'
        )
        ret2 = self.run_state(
            'cmd.run',
             name='mysqladmin --host="localhost" -u '
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
        # Create some users and a test db
        for user, userdef in six.iteritems(self.users):
            self._userCreation(uname=userdef['name'], password=userdef['pwd'])
        self.run_state(
            'mysql_database.present',
            name=self.testdb1,
            character_set='utf8',
            collate='utf8_general_ci',
            connection_user=self.user,
            connection_pass=self.password,
        )
        self.run_state(
            'mysql_database.present',
            name=self.testdb2,
            character_set='utf8',
            collate='utf8_general_ci',
            connection_user=self.user,
            connection_pass=self.password,
        )
        create_query = ('CREATE TABLE {tblname} ('
            ' id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,'
            ' data VARCHAR(100)) ENGINE={engine};'.format(
            tblname=mysqlmod.quote_identifier(self.table1),
            engine='MYISAM',
        ))
        log.info('Adding table {0!r}'.format(self.table1,))
        self.run_function(
            'mysql.query',
            database=self.testdb2,
            query=create_query,
            connection_user=self.user,
            connection_pass=self.password
        )
        create_query = ('CREATE TABLE {tblname} ('
            ' id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,'
            ' data VARCHAR(100)) ENGINE={engine};'.format(
            tblname=mysqlmod.quote_identifier(self.table2),
            engine='MYISAM',
        ))
        log.info('Adding table {0!r}'.format(self.table2,))
        self.run_function(
            'mysql.query',
            database=self.testdb2,
            query=create_query,
            connection_user=self.user,
            connection_pass=self.password
        )

    @destructiveTest
    def tearDown(self):
        '''
        Removes created users and db
        '''
        for user, userdef in six.iteritems(self.users):
            self._userRemoval(uname=userdef['name'], password=userdef['pwd'])
        self.run_state(
            'mysql_database.absent',
            name=self.testdb1,
            connection_user=self.user,
            connection_pass=self.password,
       )
        self.run_function(
            'mysql_database.absent',
            name=self.testdb2,
            connection_user=self.user,
            connection_pass=self.password,
       )

    def _userCreation(self,
                      uname,
                      password=None):
        '''
        Create a test user
        '''
        self.run_state(
            'mysql_user.present',
            name=uname,
            host='localhost',
            password=password,
            connection_user=self.user,
            connection_pass=self.password,
            connection_charset='utf8',
            saltenv={"LC_ALL": "en_US.utf8"}
        )

    def _userRemoval(self,
                     uname,
                     password=None):
        '''
        Removes a test user
        '''
        self.run_state(
            'mysql_user.absent',
            name=uname,
            host='localhost',
            connection_user=self.user,
            connection_pass=self.password,
            connection_charset='utf8',
            saltenv={"LC_ALL": "en_US.utf8"}
        )

    @destructiveTest
    def test_grant_present_absent(self):
        '''
        mysql_database.present
        '''
        ret = self.run_state(
            'mysql_grants.present',
            name='grant test 1',
            grant='SELECT, INSERT',
            database=self.testdb1 + '.*',
            user=self.users['user1']['name'],
            host='localhost',
            grant_option=True,
            revoke_first=True,
            connection_user=self.user,
            connection_pass=self.password,
            connection_charset='utf8'
        )
        self.assertSaltTrueReturn(ret)
        ret = self.run_state(
            'mysql_grants.present',
            name='grant test 2',
            grant='SELECT, ALTER,CREATE TEMPORARY tables, execute',
            database=self.testdb1 + '.*',
            user=self.users['user1']['name'],
            host='localhost',
            grant_option=True,
            revoke_first=True,
            connection_user=self.user,
            connection_pass=self.password,
            connection_charset='utf8'
        )
        self.assertSaltTrueReturn(ret)
        ret = self.run_state(
            'mysql_grants.present',
            name='grant test 3',
            grant='SELECT, INSERT',
            database=self.testdb2 + '.' + self.table2,
            user=self.users['user2']['name'],
            host='localhost',
            grant_option=True,
            revoke_first=True,
            connection_user=self.user,
            connection_pass=self.password,
            connection_charset='utf8'
        )
        self.assertSaltTrueReturn(ret)
        ret = self.run_state(
            'mysql_grants.present',
            name='grant test 4',
            grant='SELECT, INSERT',
            database=self.testdb2 + '.' + self.table2,
            user=self.users['user2']['name'],
            host='localhost',
            grant_option=True,
            revoke_first=True,
            connection_user=self.user,
            connection_pass=self.password,
            connection_charset='utf8'
        )
        self.assertSaltTrueReturn(ret)
        ret = self.run_state(
            'mysql_grants.present',
            name='grant test 5',
            grant='SELECT, UPDATE',
            database=self.testdb2 + '.*',
            user=self.users['user1']['name'],
            host='localhost',
            grant_option=True,
            revoke_first=False,
            connection_user=self.user,
            connection_pass=self.password,
            connection_charset='utf8'
        )
        self.assertSaltTrueReturn(ret)
        ret = self.run_state(
            'mysql_grants.absent',
            name='grant test 6',
            grant='SELECT,update',
            database=self.testdb2 + '.*',
            user=self.users['user1']['name'],
            host='localhost',
            grant_option=True,
            revoke_first=False,
            connection_user=self.user,
            connection_pass=self.password,
            connection_charset='utf8'
        )
        self.assertSaltTrueReturn(ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MysqlDatabaseStateTest, MysqlGrantsStateTest)
