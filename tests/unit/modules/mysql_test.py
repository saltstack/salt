# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Mike Place (mp@saltstack.com)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details
    :license: Apache 2.0, see LICENSE for more details.


    tests.unit.modules.mysql
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch, call

ensure_in_syspath('../../')

# Import salt libs
from salt.modules import mysql

NO_MYSQL = False
try:
    import MySQLdb
except Exception:
    NO_MYSQL = True

mysql.__salt__ = {}

DEBUG = True


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(NO_MYSQL, 'Install MySQL bindings before running MySQL unit tests.')
class MySQLTestCase(TestCase):

    def test_user_create_when_user_exists(self):
        '''
        Test to ensure we don't try to create a user when one already exists
        '''
        mock = MagicMock(return_value=True)
        mysql.user_exists = mock
        with patch.dict(mysql.__salt__, {'config.option': MagicMock()}):
            ret = mysql.user_create('testuser')
            self.assertEqual(False, ret)

    def test_user_create(self):
        '''
        Test the creation of a MySQL user in mysql exec module
        '''
        self._test_call(mysql.user_create,
                        "CREATE USER 'testuser'@'localhost' IDENTIFIED BY 'BLUECOW'",
                        'testuser',
                        password='BLUECOW')

    def test_user_chpass(self):
        '''
        Test changing a MySQL user password in mysql exec module
        '''
        connect_mock = MagicMock()
        mysql._connect = connect_mock

        with patch.dict(mysql.__salt__, {'config.option': MagicMock()}):
            mysql.user_chpass('testuser', password='BLUECOW')
            calls = (
                call().cursor().execute(
                    "UPDATE mysql.user SET password=PASSWORD('BLUECOW') WHERE User='testuser' AND Host = 'localhost';"),
                call().cursor().execute('FLUSH PRIVILEGES;'),
            )
            connect_mock.assert_has_calls(calls, any_order=True)

    def test_user_remove(self):
        '''
        Test the removal of a MySQL user in mysql exec module
        '''
        self._test_call(mysql.user_remove, "DROP USER 'testuser'@'localhost'", 'testuser')

    def test_db_check(self):
        '''
        Test MySQL db check function in mysql exec module
        '''
        self._test_call(mysql.db_check, 'CHECK TABLE `test``\'" db`.`my``\'" table`', 'test`\'" db', 'my`\'" table')

    def test_db_repair(self):
        '''
        Test MySQL db repair function in mysql exec module
        '''
        self._test_call(mysql.db_repair, 'REPAIR TABLE `test``\'" db`.`my``\'" table`', 'test`\'" db', 'my`\'" table')

    def test_db_optimize(self):
        '''
        Test MySQL db optimize function in mysql exec module
        '''
        self._test_call(mysql.db_optimize, 'OPTIMIZE TABLE `test``\'" db`.`my``\'" table`', 'test`\'" db', 'my`\'" table')

    def test_db_remove(self):
        '''
        Test MySQL db remove function in mysql exec module
        '''
        mysql.db_exists = MagicMock(return_value=True)
        self._test_call(mysql.db_remove, 'DROP DATABASE `test``\'" db`;', 'test`\'" db')

    def test_db_tables(self):
        '''
        Test MySQL db_tables function in mysql exec module
        '''
        self._test_call(mysql.db_tables, 'SHOW TABLES IN `test``\'" db`', 'test`\'" db')

    def test_db_exists(self):
        '''
        Test MySQL db_exists function in mysql exec module
        '''
        self._test_call(
            mysql.db_exists,
            {'sql': 'SHOW DATABASES LIKE %(dbname)s;',
             'sql_args': {'dbname': 'test`\'" db'}
             },
            'test`\'" db'
        )

    def test_db_create(self):
        '''
        Test MySQL db_create function in mysql exec module
        '''
        self._test_call(
            mysql.db_create,
            {'sql': 'CREATE DATABASE `test``\'" db`;',
             'sql_args': {}},
            'test`\'" db'
        )

    def test_user_list(self):
        '''
        Test MySQL user_list function in mysql exec module
        '''
        self._test_call(mysql.user_list, 'SELECT User,Host FROM mysql.user')

    @skipIf(True, 'This test is broken and it is not clear why')
    def test_user_exists(self):
        '''
        Test to see if mysql module properly forms the MySQL query to see if a user exists
        '''
        self._test_call(mysql.user_exists, '', 'mytestuser')

    def test_user_info(self):
        '''
        Test to see if the mysql execution module correctly forms the SQL for information on a MySQL user.
        '''
        self._test_call(mysql.user_info,
                        "SELECT * FROM mysql.user WHERE User = 'mytestuser' AND Host = 'localhost'",
                       'mytestuser'
        )

    def test_user_grants(self):
        '''
        Test to ensure the mysql user_grants function returns properly formed SQL for a basic query
        '''
        self._test_call(mysql.user_grants, "SHOW GRANTS FOR 'testuser'@'localhost'", 'testuser')

    @skipIf(True, 'TODO: Mock up user_grants()')
    def test_grant_exists(self):
        '''
        Test to ensure a basic query for grants works in the mysql exec module
        '''
        self._test_call(mysql.grant_exists, '', 'SELECT,INSERT,UPDATE', 'database.*', 'frank')

    @skipIf(True, 'TODO: Mock up user_grants()')
    def test_grant_add(self):
        '''
        Test grant_add function in mysql exec module
        '''
        self._test_call(mysql.grant_add, '', 'SELECT,INSERT,UPDATE', 'database.*', 'frank', 'localhost')

    @skipIf(True, 'TODO: Mock up user_grants()')
    def test_grant_revoke(self):
        '''
        Test grant revoke in mysql exec module
        '''
        self._test_call(mysql.grant_revoke, '', 'SELECT,INSERT,UPDATE', 'database.*', 'frank', 'localhost')

    def test_processlist(self):
        '''
        Test processlist function in mysql exec module
        '''
        self._test_call(mysql.processlist, 'SHOW FULL PROCESSLIST')

    def test_get_master_status(self):
        '''
        Test get_master_status in the mysql execution module
        '''
        self._test_call(mysql.get_master_status, 'SHOW MASTER STATUS')

    def test_get_slave_status(self):
        '''
        Test get_slave_status in the mysql execution module
        '''
        self._test_call(mysql.get_slave_status, 'SHOW SLAVE STATUS')

    @skipIf(True, 'MySQL module claims this function is not ready for production')
    def test_free_slave(self):
        self.assertTrue(False)

    def test_query(self):
        self._test_call(mysql.query, 'SELECT * FROM testdb', 'testdb', 'SELECT * FROM testdb')

    def _test_call(self, function, expected_sql, *args, **kwargs):
        connect_mock = MagicMock()
        mysql._connect = connect_mock
        with patch.dict(mysql.__salt__, {'config.option': MagicMock()}):
            function(*args, **kwargs)
            if isinstance(expected_sql, dict):
                calls = (call().cursor().execute('{0}'.format(expected_sql['sql']), expected_sql['sql_args']))
            else:
                calls = (call().cursor().execute('{0}'.format(expected_sql)))
            connect_mock.assert_has_calls(calls)
