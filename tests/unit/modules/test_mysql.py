# -*- coding: utf-8 -*-
'''
    :codeauthor: Mike Place (mp@saltstack.com)


    tests.unit.modules.mysql
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch, call

# Import salt libs
import salt.modules.mysql as mysql

NO_MYSQL = False
try:
    import MySQLdb  # pylint: disable=W0611
except Exception:
    NO_MYSQL = True

__all_privileges__ = [
    'ALTER',
    'ALTER ROUTINE',
    'BACKUP_ADMIN',
    'BINLOG_ADMIN',
    'CONNECTION_ADMIN',
    'CREATE',
    'CREATE ROLE',
    'CREATE ROUTINE',
    'CREATE TABLESPACE',
    'CREATE TEMPORARY TABLES',
    'CREATE USER',
    'CREATE VIEW',
    'DELETE',
    'DROP',
    'DROP ROLE',
    'ENCRYPTION_KEY_ADMIN',
    'EVENT',
    'EXECUTE',
    'FILE',
    'GROUP_REPLICATION_ADMIN',
    'INDEX',
    'INSERT',
    'LOCK TABLES',
    'PERSIST_RO_VARIABLES_ADMIN',
    'PROCESS',
    'REFERENCES',
    'RELOAD',
    'REPLICATION CLIENT',
    'REPLICATION SLAVE',
    'REPLICATION_SLAVE_ADMIN',
    'RESOURCE_GROUP_ADMIN',
    'RESOURCE_GROUP_USER',
    'ROLE_ADMIN',
    'SELECT',
    'SET_USER_ID',
    'SHOW DATABASES',
    'SHOW VIEW',
    'SHUTDOWN',
    'SUPER',
    'SYSTEM_VARIABLES_ADMIN',
    'TRIGGER',
    'UPDATE',
    'XA_RECOVER_ADMIN'
]


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(NO_MYSQL, 'Install MySQL bindings before running MySQL unit tests.')
class MySQLTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        return {mysql: {}}

    def test_user_exists(self):
        '''
        Test to see if mysql module properly forms the MySQL query to see if a user exists

        Do it before test_user_create_when_user_exists mocks the user_exists call
        '''
        with patch.object(mysql, 'version', return_value='8.0.10'):
            self._test_call(mysql.user_exists,
                            {'sql': ('SELECT User,Host FROM mysql.user WHERE '
                                     'User = %(user)s AND Host = %(host)s AND '
                                     'Password = PASSWORD(%(password)s)'),
                             'sql_args': {'host': 'localhost',
                                          'password': 'BLUECOW',
                                          'user': 'mytestuser'
                                         }
                            },
                            user='mytestuser',
                            host='localhost',
                            password='BLUECOW'
            )

        with patch.object(mysql, 'version', return_value='10.1.38-MariaDB'):
            self._test_call(mysql.user_exists,
                            {'sql': ('SELECT User,Host FROM mysql.user WHERE '
                                     'User = %(user)s AND Host = %(host)s AND '
                                     'Password = PASSWORD(%(password)s)'),
                             'sql_args': {'host': 'localhost',
                                          'password': 'BLUECOW',
                                          'user': 'mytestuser'
                                         }
                            },
                            user='mytestuser',
                            host='localhost',
                            password='BLUECOW'
            )

        with patch.object(mysql, 'version', return_value='8.0.11'):
            self._test_call(mysql.user_exists,
                            {'sql': ('SELECT User,Host FROM mysql.user WHERE '
                                     'User = %(user)s AND Host = %(host)s'),
                             'sql_args': {'host': 'localhost',
                                          'user': 'mytestuser'
                                         }
                            },
                            user='mytestuser',
                            host='localhost',
                            password='BLUECOW'
            )

        with patch.object(mysql, 'version', return_value='8.0.11'):
            self._test_call(mysql.user_exists,
                            {'sql': ('SELECT User,Host FROM mysql.user WHERE '
                                     'User = %(user)s AND Host = %(host)s'),
                             'sql_args': {'host': '%',
                                          'user': 'mytestuser'
                                         }
                            },
                            user='mytestuser',
                            host='%',
                            password='BLUECOW'
            )

        with patch.object(mysql, 'version', return_value='10.2.21-MariaDB'):
            self._test_call(mysql.user_exists,
                            {'sql': ('SELECT User,Host FROM mysql.user WHERE '
                                     'User = %(user)s AND Host = %(host)s'),
                             'sql_args': {'host': 'localhost',
                                          'user': 'mytestuser'
                                         }
                            },
                            user='mytestuser',
                            host='localhost',
                            password='BLUECOW'
            )

        # test_user_create_when_user_exists(self):
        # ensure we don't try to create a user when one already exists
        # mock the version of MySQL
        with patch.object(mysql, 'version', return_value='8.0.10'):
            with patch.object(mysql, 'user_exists', MagicMock(return_value=True)):
                with patch.dict(mysql.__salt__, {'config.option': MagicMock()}):
                    ret = mysql.user_create('testuser')
                    self.assertEqual(False, ret)

        # test_user_create_when_user_exists(self):
        # ensure we don't try to create a user when one already exists
        # mock the version of MySQL
        with patch.object(mysql, 'version', return_value='8.0.11'):
            with patch.object(mysql, 'user_exists', MagicMock(return_value=True)):
                with patch.object(mysql, 'verify_login', MagicMock(return_value=True)):
                    with patch.dict(mysql.__salt__, {'config.option': MagicMock()}):
                        ret = mysql.user_create('testuser')
                        self.assertEqual(False, ret)

    def test_user_create(self):
        '''
        Test the creation of a MySQL user in mysql exec module
        '''
        self._test_call(mysql.user_create,
                        {'sql': 'CREATE USER %(user)s@%(host)s IDENTIFIED BY %(password)s',
                         'sql_args': {'password': 'BLUECOW',
                                      'user': 'testuser',
                                      'host': 'localhost',
                                     }
                        },
                        'testuser',
                        password='BLUECOW'
        )

    def test_user_chpass(self):
        '''
        Test changing a MySQL user password in mysql exec module
        '''
        connect_mock = MagicMock()
        with patch.object(mysql, '_connect', connect_mock):
            with patch.object(mysql, 'version', return_value='8.0.10'):
                with patch.dict(mysql.__salt__, {'config.option': MagicMock()}):
                    mysql.user_chpass('testuser', password='BLUECOW')
                    calls = (
                        call().cursor().execute(
                            'UPDATE mysql.user SET Password=PASSWORD(%(password)s) WHERE User=%(user)s AND Host = %(host)s;',
                            {'password': 'BLUECOW',
                             'user': 'testuser',
                             'host': 'localhost',
                            }
                        ),
                        call().cursor().execute('FLUSH PRIVILEGES;'),
                    )
                    connect_mock.assert_has_calls(calls, any_order=True)

        connect_mock = MagicMock()
        with patch.object(mysql, '_connect', connect_mock):
            with patch.object(mysql, 'version', return_value='8.0.11'):
                with patch.dict(mysql.__salt__, {'config.option': MagicMock()}):
                    mysql.user_chpass('testuser', password='BLUECOW')
                    calls = (
                        call().cursor().execute(
                            "ALTER USER %(user)s@%(host)s IDENTIFIED BY %(password)s;",
                            {'password': 'BLUECOW',
                             'user': 'testuser',
                             'host': 'localhost',
                            }
                        ),
                        call().cursor().execute('FLUSH PRIVILEGES;'),
                    )
                    connect_mock.assert_has_calls(calls, any_order=True)

    def test_user_remove(self):
        '''
        Test the removal of a MySQL user in mysql exec module
        '''
        self._test_call(mysql.user_remove,
                        {'sql': 'DROP USER %(user)s@%(host)s',
                         'sql_args': {'user': 'testuser',
                                      'host': 'localhost',
                                     }
                        },
                        'testuser'
        )

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
        with patch.object(mysql, 'db_exists', MagicMock(return_value=True)):
            self._test_call(mysql.db_remove, 'DROP DATABASE `test``\'" db`;', 'test`\'" db')

    def test_db_tables(self):
        '''
        Test MySQL db_tables function in mysql exec module
        '''
        with patch.object(mysql, 'db_exists', MagicMock(return_value=True)):
            self._test_call(mysql.db_tables, 'SHOW TABLES IN `test``\'" db`', 'test`\'" db')

    def test_db_exists(self):
        '''
        Test MySQL db_exists function in mysql exec module
        '''
        self._test_call(
            mysql.db_exists,
            {'sql': 'SHOW DATABASES LIKE %(dbname)s;',
             'sql_args': {'dbname': r'''test%_`" db'''}
             },
            'test%_`" db'
        )

    def test_db_create(self):
        '''
        Test MySQL db_create function in mysql exec module
        '''
        self._test_call(
            mysql.db_create,
            'CREATE DATABASE IF NOT EXISTS `test``\'" db`;',
            'test`\'" db'
        )

    def test_user_list(self):
        '''
        Test MySQL user_list function in mysql exec module
        '''
        self._test_call(mysql.user_list, 'SELECT User,Host FROM mysql.user')

    def test_user_info(self):
        '''
        Test to see if the mysql execution module correctly forms the SQL for information on a MySQL user.
        '''
        self._test_call(mysql.user_info,
                        {'sql': 'SELECT * FROM mysql.user WHERE User = %(user)s AND Host = %(host)s',
                         'sql_args': {'host': 'localhost',
                                      'user': 'mytestuser',
                                     }
                        },
                       'mytestuser'
        )

    def test_user_grants(self):
        '''
        Test to ensure the mysql user_grants function returns properly formed SQL for a basic query
        '''
        with patch.object(mysql, 'user_exists', MagicMock(return_value=True)):
            self._test_call(mysql.user_grants,
                            {'sql': 'SHOW GRANTS FOR %(user)s@%(host)s',
                             'sql_args': {'host': 'localhost',
                                          'user': 'testuser',
                                         }
                            },
                           'testuser')

    def test_grant_exists_true(self):
        '''
        Test to ensure that we can find a grant that exists
        '''
        mock_grants = [
            "GRANT USAGE ON *.* TO 'testuser'@'%'",
            "GRANT SELECT, INSERT, UPDATE ON `testdb`.`testtableone` TO 'testuser'@'%'",
            "GRANT SELECT ON `testdb`.`testtabletwo` TO 'testuer'@'%'",
            "GRANT SELECT ON `testdb`.`testtablethree` TO 'testuser'@'%'",
        ]
        with patch.object(mysql, 'version', return_value='5.6.41'):
            mock = MagicMock(return_value=mock_grants)
            with patch.object(mysql, 'user_grants', return_value=mock_grants) as mock_user_grants:
                ret = mysql.grant_exists(
                    'SELECT, INSERT, UPDATE',
                    'testdb.testtableone',
                    'testuser',
                    '%'
                )
                self.assertEqual(ret, True)

    def test_grant_exists_false(self):
        '''
        Test to ensure that we don't find a grant that doesn't exist
        '''
        mock_grants = [
            "GRANT USAGE ON *.* TO 'testuser'@'%'",
            "GRANT SELECT, INSERT, UPDATE ON `testdb`.`testtableone` TO 'testuser'@'%'",
            "GRANT SELECT ON `testdb`.`testtablethree` TO 'testuser'@'%'",
        ]
        with patch.object(mysql, 'version', return_value='5.6.41'):
            mock = MagicMock(return_value=mock_grants)
            with patch.object(mysql, 'user_grants', return_value=mock_grants) as mock_user_grants:
                ret = mysql.grant_exists(
                    'SELECT',
                    'testdb.testtabletwo',
                    'testuser',
                    '%'
                )
                self.assertEqual(ret, False)

    def test_grant_exists_all(self):
        '''
        Test to ensure that we can find a grant that exists
        '''
        mock_grants = [
            "GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, RELOAD, SHUTDOWN, PROCESS, FILE, REFERENCES, INDEX, ALTER, SHOW DATABASES, SUPER, CREATE TEMPORARY TABLES, LOCK TABLES, EXECUTE, REPLICATION SLAVE, REPLICATION CLIENT, CREATE VIEW, SHOW VIEW, CREATE ROUTINE, ALTER ROUTINE, CREATE USER, EVENT, TRIGGER, CREATE TABLESPACE, CREATE ROLE, DROP ROLE ON testdb.testtableone TO `testuser`@`%`",
            "GRANT BACKUP_ADMIN,BINLOG_ADMIN,CONNECTION_ADMIN,ENCRYPTION_KEY_ADMIN,GROUP_REPLICATION_ADMIN,PERSIST_RO_VARIABLES_ADMIN,REPLICATION_SLAVE_ADMIN,RESOURCE_GROUP_ADMIN,RESOURCE_GROUP_USER,ROLE_ADMIN,SET_USER_ID,SYSTEM_VARIABLES_ADMIN,XA_RECOVER_ADMIN ON testdb.testtableone TO `testuser`@`%`"
        ]
        with patch.object(mysql, 'version', return_value='8.0.10'):
            mock = MagicMock(return_value=mock_grants)
            with patch.object(mysql, 'user_grants', return_value=mock_grants) as mock_user_grants:
                ret = mysql.grant_exists(
                    'ALL',
                    'testdb.testtableone',
                    'testuser',
                    '%'
                )
                self.assertEqual(ret, True)

        mock_grants = ["GRANT ALL PRIVILEGES ON testdb.testtableone TO `testuser`@`%`"]
        with patch.object(mysql, 'version', return_value='5.6.41'):
            mock = MagicMock(return_value=mock_grants)
            with patch.object(mysql, 'user_grants', return_value=mock_grants) as mock_user_grants:
                ret = mysql.grant_exists(
                    'ALL PRIVILEGES',
                    'testdb.testtableone',
                    'testuser',
                    '%'
                )
                self.assertEqual(ret, True)

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

    def test_get_slave_status_bad_server(self):
        '''
        Test get_slave_status in the mysql execution module, simulating a broken server
        '''
        connect_mock = MagicMock(return_value=None)
        with patch.object(mysql, '_connect', connect_mock):
            with patch.dict(mysql.__salt__, {'config.option': MagicMock()}):
                rslt = mysql.get_slave_status()
                connect_mock.assert_has_calls([call()])
                self.assertEqual(rslt, [])

    @skipIf(True, 'MySQL module claims this function is not ready for production')
    def test_free_slave(self):
        pass

    def test_query(self):
        self._test_call(mysql.query, 'SELECT * FROM testdb', 'testdb', 'SELECT * FROM testdb')

    def test_query_error(self):
        connect_mock = MagicMock()
        with patch.object(mysql, '_connect', connect_mock):
            with patch.dict(mysql.__salt__, {'config.option': MagicMock()}):
                # Use the OperationalError from the salt mysql module because that
                # exception can come from either MySQLdb or pymysql
                side_effect = mysql.OperationalError(9999, 'Something Went Wrong')
                with patch.object(mysql, '_execute', MagicMock(side_effect=side_effect)):
                    mysql.query('testdb', 'SELECT * FROM testdb')
            self.assertIn('mysql.error', mysql.__context__)
            expected = 'MySQL Error 9999: Something Went Wrong'
            self.assertEqual(mysql.__context__['mysql.error'], expected)

    def _test_call(self, function, expected_sql, *args, **kwargs):
        connect_mock = MagicMock()
        with patch.object(mysql, '_connect', connect_mock):
            with patch.dict(mysql.__salt__, {'config.option': MagicMock()}):
                function(*args, **kwargs)
                if isinstance(expected_sql, dict):
                    calls = call().cursor().execute('{0}'.format(expected_sql['sql']), expected_sql['sql_args'])
                else:
                    calls = call().cursor().execute('{0}'.format(expected_sql))
                connect_mock.assert_has_calls((calls,), True)
