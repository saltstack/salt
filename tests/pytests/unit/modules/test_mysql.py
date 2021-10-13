"""
    :codeauthor: Mike Place (mp@saltstack.com)


    tests.unit.modules.mysql
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""


import logging

import pytest
import salt.modules.mysql as mysql
from tests.support.mock import MagicMock, call, mock_open, patch

try:
    import pymysql

    HAS_PYMYSQL = True
except ImportError:
    HAS_PYMYSQL = False


log = logging.getLogger(__name__)

__all_privileges__ = [
    "ALTER",
    "ALTER ROUTINE",
    "BACKUP_ADMIN",
    "BINLOG_ADMIN",
    "CONNECTION_ADMIN",
    "CREATE",
    "CREATE ROLE",
    "CREATE ROUTINE",
    "CREATE TABLESPACE",
    "CREATE TEMPORARY TABLES",
    "CREATE USER",
    "CREATE VIEW",
    "DELETE",
    "DROP",
    "DROP ROLE",
    "ENCRYPTION_KEY_ADMIN",
    "EVENT",
    "EXECUTE",
    "FILE",
    "GROUP_REPLICATION_ADMIN",
    "INDEX",
    "INSERT",
    "LOCK TABLES",
    "PERSIST_RO_VARIABLES_ADMIN",
    "PROCESS",
    "REFERENCES",
    "RELOAD",
    "REPLICATION CLIENT",
    "REPLICATION SLAVE",
    "REPLICATION_SLAVE_ADMIN",
    "RESOURCE_GROUP_ADMIN",
    "RESOURCE_GROUP_USER",
    "ROLE_ADMIN",
    "SELECT",
    "SET_USER_ID",
    "SHOW DATABASES",
    "SHOW VIEW",
    "SHUTDOWN",
    "SUPER",
    "SYSTEM_VARIABLES_ADMIN",
    "TRIGGER",
    "UPDATE",
    "XA_RECOVER_ADMIN",
]

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skipif(
        mysql.MySQLdb is None, reason="No python mysql client installed."
    ),
]


class MockMySQLConnect:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def autocommit(self, *args, **kwards):
        return True


@pytest.fixture
def configure_loader_modules():
    return {mysql: {}}


def test_user_exists():
    """
    Test to see if mysql module properly forms the MySQL query to see if a user exists

    Do it before test_user_create_when_user_exists mocks the user_exists call
    """
    with patch.object(mysql, "version", return_value="8.0.10"):
        _test_call(
            mysql.user_exists,
            {
                "sql": (
                    "SELECT User,Host FROM mysql.user WHERE "
                    "User = %(user)s AND Host = %(host)s AND "
                    "Password = PASSWORD(%(password)s)"
                ),
                "sql_args": {
                    "host": "localhost",
                    "password": "BLUECOW",
                    "user": "mytestuser",
                },
            },
            user="mytestuser",
            host="localhost",
            password="BLUECOW",
        )

    with patch.object(mysql, "version", return_value="10.1.38-MariaDB"):
        _test_call(
            mysql.user_exists,
            {
                "sql": (
                    "SELECT User,Host FROM mysql.user WHERE "
                    "User = %(user)s AND Host = %(host)s AND "
                    "Password = PASSWORD(%(password)s)"
                ),
                "sql_args": {
                    "host": "localhost",
                    "password": "BLUECOW",
                    "user": "mytestuser",
                },
            },
            user="mytestuser",
            host="localhost",
            password="BLUECOW",
        )

    with patch.object(mysql, "version", return_value="8.0.11"):
        _test_call(
            mysql.user_exists,
            {
                "sql": (
                    "SELECT User,Host FROM mysql.user WHERE "
                    "User = %(user)s AND Host = %(host)s"
                ),
                "sql_args": {"host": "localhost", "user": "mytestuser"},
            },
            user="mytestuser",
            host="localhost",
            password="BLUECOW",
        )

    with patch.object(mysql, "version", return_value="8.0.11"):
        with patch.object(
            mysql,
            "__get_auth_plugin",
            MagicMock(return_value="mysql_native_password"),
        ):
            _test_call(
                mysql.user_exists,
                {
                    "sql": (
                        "SELECT User,Host FROM mysql.user WHERE "
                        "User = %(user)s AND Host = %(host)s AND "
                        "Password = %(password)s"
                    ),
                    "sql_args": {
                        "host": "%",
                        "password": "*1A01CF8FBE6425398935FB90359AD8B817399102",
                        "user": "mytestuser",
                    },
                },
                user="mytestuser",
                host="%",
                password="BLUECOW",
            )

    with patch.object(mysql, "version", return_value="10.2.21-MariaDB"):
        _test_call(
            mysql.user_exists,
            {
                "sql": (
                    "SELECT User,Host FROM mysql.user WHERE "
                    "User = %(user)s AND Host = %(host)s AND "
                    "Password = PASSWORD(%(password)s)"
                ),
                "sql_args": {
                    "host": "localhost",
                    "password": "BLUECOW",
                    "user": "mytestuser",
                },
            },
            user="mytestuser",
            host="localhost",
            password="BLUECOW",
        )

    with patch.object(
        mysql, "version", side_effect=["", "10.2.21-MariaDB", "10.2.21-MariaDB"]
    ):
        _test_call(
            mysql.user_exists,
            {
                "sql": (
                    "SELECT User,Host FROM mysql.user WHERE "
                    "User = %(user)s AND Host = %(host)s AND "
                    "Password = PASSWORD(%(password)s)"
                ),
                "sql_args": {
                    "host": "localhost",
                    "password": "new_pass",
                    "user": "root",
                },
            },
            user="root",
            host="localhost",
            password="new_pass",
            connection_user="root",
            connection_pass="old_pass",
        )

    # test_user_create_when_user_exists():
    # ensure we don't try to create a user when one already exists
    # mock the version of MySQL
    with patch.object(mysql, "version", return_value="8.0.10"):
        with patch.object(mysql, "user_exists", MagicMock(return_value=True)):
            with patch.dict(mysql.__salt__, {"config.option": MagicMock()}):
                ret = mysql.user_create("testuser")
                assert not ret

    # test_user_create_when_user_exists():
    # ensure we don't try to create a user when one already exists
    # mock the version of MySQL
    with patch.object(mysql, "version", return_value="8.0.11"):
        with patch.object(mysql, "user_exists", MagicMock(return_value=True)):
            with patch.object(mysql, "verify_login", MagicMock(return_value=True)):
                with patch.dict(mysql.__salt__, {"config.option": MagicMock()}):
                    ret = mysql.user_create("testuser")
                    assert not False


def test_user_create():
    """
    Test the creation of a MySQL user in mysql exec module
    """
    with patch.object(mysql, "version", return_value="8.0.10"):
        with patch.object(
            mysql,
            "__get_auth_plugin",
            MagicMock(return_value="mysql_native_password"),
        ):
            _test_call(
                mysql.user_create,
                {
                    "sql": "CREATE USER %(user)s@%(host)s IDENTIFIED BY %(password)s",
                    "sql_args": {
                        "password": "BLUECOW",
                        "user": "testuser",
                        "host": "localhost",
                    },
                },
                "testuser",
                password="BLUECOW",
            )

    with patch.object(mysql, "version", return_value="8.0.11"):
        with patch.object(
            mysql,
            "__get_auth_plugin",
            MagicMock(return_value="mysql_native_password"),
        ):
            _test_call(
                mysql.user_create,
                {
                    "sql": "CREATE USER %(user)s@%(host)s IDENTIFIED WITH %(auth_plugin)s BY %(password)s",
                    "sql_args": {
                        "password": "BLUECOW",
                        "auth_plugin": "mysql_native_password",
                        "user": "testuser",
                        "host": "localhost",
                    },
                },
                "testuser",
                password="BLUECOW",
            )

    # Test creating a user with passwordless=True and unix_socket=True
    with patch.object(mysql, "version", return_value="8.0.10"):
        with patch.object(mysql, "plugin_status", MagicMock(return_value="ACTIVE")):
            _test_call(
                mysql.user_create,
                {
                    "sql": "CREATE USER %(user)s@%(host)s IDENTIFIED WITH auth_socket",
                    "sql_args": {"user": "testuser", "host": "localhost"},
                },
                "testuser",
                allow_passwordless=True,
                unix_socket=True,
            )

    with patch.object(mysql, "version", return_value="10.2.21-MariaDB"):
        with patch.object(mysql, "plugin_status", MagicMock(return_value="ACTIVE")):
            _test_call(
                mysql.user_create,
                {
                    "sql": "CREATE USER %(user)s@%(host)s IDENTIFIED VIA unix_socket",
                    "sql_args": {"user": "testuser", "host": "localhost"},
                },
                "testuser",
                allow_passwordless=True,
                unix_socket=True,
            )

    with patch.object(mysql, "version", side_effect=["", "8.0.10", "8.0.10"]):
        with patch.object(
            mysql, "user_exists", MagicMock(return_value=False)
        ), patch.object(
            mysql,
            "__get_auth_plugin",
            MagicMock(return_value="mysql_native_password"),
        ):
            _test_call(
                mysql.user_create,
                {
                    "sql": "CREATE USER %(user)s@%(host)s IDENTIFIED BY %(password)s",
                    "sql_args": {
                        "password": "new_pass",
                        "user": "root",
                        "host": "localhost",
                    },
                },
                "root",
                password="new_pass",
                connection_user="root",
                connection_pass="old_pass",
            )


def test_user_chpass():
    """
    Test changing a MySQL user password in mysql exec module
    """
    connect_mock = MagicMock()
    with patch.object(mysql, "_connect", connect_mock):
        with patch.object(mysql, "version", return_value="8.0.10"):
            with patch.object(mysql, "user_exists", MagicMock(return_value=True)):
                with patch.dict(mysql.__salt__, {"config.option": MagicMock()}):
                    mysql.user_chpass("testuser", password="BLUECOW")
                    calls = (
                        call()
                        .cursor()
                        .execute(
                            "UPDATE mysql.user SET Password=PASSWORD(%(password)s) WHERE User=%(user)s AND Host = %(host)s;",
                            {
                                "password": "BLUECOW",
                                "user": "testuser",
                                "host": "localhost",
                            },
                        ),
                        call().cursor().execute("FLUSH PRIVILEGES;"),
                    )
                    connect_mock.assert_has_calls(calls, any_order=True)

    connect_mock = MagicMock()
    with patch.object(mysql, "_connect", connect_mock):
        with patch.object(mysql, "version", return_value="8.0.11"):
            with patch.object(mysql, "user_exists", MagicMock(return_value=True)):
                with patch.object(
                    mysql,
                    "__get_auth_plugin",
                    MagicMock(return_value="mysql_native_password"),
                ):
                    with patch.dict(mysql.__salt__, {"config.option": MagicMock()}):
                        mysql.user_chpass("testuser", password="BLUECOW")
                        calls = (
                            call()
                            .cursor()
                            .execute(
                                "ALTER USER %(user)s@%(host)s IDENTIFIED WITH %(auth_plugin)s BY %(password)s;",
                                {
                                    "password": "BLUECOW",
                                    "user": "testuser",
                                    "host": "localhost",
                                    "auth_plugin": "mysql_native_password",
                                },
                            ),
                            call().cursor().execute("FLUSH PRIVILEGES;"),
                        )
                        connect_mock.assert_has_calls(calls, any_order=True)

    connect_mock = MagicMock()
    with patch.object(mysql, "_connect", connect_mock):
        with patch.object(mysql, "version", side_effect=["", "8.0.11", "8.0.11"]):
            with patch.object(mysql, "user_exists", MagicMock(return_value=True)):
                with patch.object(
                    mysql,
                    "__get_auth_plugin",
                    MagicMock(return_value="mysql_native_password"),
                ):
                    with patch.dict(mysql.__salt__, {"config.option": MagicMock()}):
                        mysql.user_chpass(
                            "root",
                            password="new_pass",
                            connection_user="root",
                            connection_pass="old_pass",
                        )
                        calls = (
                            call()
                            .cursor()
                            .execute(
                                "ALTER USER %(user)s@%(host)s IDENTIFIED WITH %(auth_plugin)s BY %(password)s;",
                                {
                                    "password": "new_pass",
                                    "user": "root",
                                    "host": "localhost",
                                    "auth_plugin": "mysql_native_password",
                                },
                            ),
                            call().cursor().execute("FLUSH PRIVILEGES;"),
                        )
                        connect_mock.assert_has_calls(calls, any_order=True)


def test_user_remove():
    """
    Test the removal of a MySQL user in mysql exec module
    """
    with patch.object(mysql, "user_exists", MagicMock(return_value=True)):
        _test_call(
            mysql.user_remove,
            {
                "sql": "DROP USER %(user)s@%(host)s",
                "sql_args": {"user": "testuser", "host": "localhost"},
            },
            "testuser",
        )


def test_db_check():
    """
    Test MySQL db check function in mysql exec module
    """
    _test_call(
        mysql.db_check,
        "CHECK TABLE `test``'\" db`.`my``'\" table`",
        "test`'\" db",
        "my`'\" table",
    )


def test_db_repair():
    """
    Test MySQL db repair function in mysql exec module
    """
    _test_call(
        mysql.db_repair,
        "REPAIR TABLE `test``'\" db`.`my``'\" table`",
        "test`'\" db",
        "my`'\" table",
    )


def test_db_optimize():
    """
    Test MySQL db optimize function in mysql exec module
    """
    _test_call(
        mysql.db_optimize,
        "OPTIMIZE TABLE `test``'\" db`.`my``'\" table`",
        "test`'\" db",
        "my`'\" table",
    )


def test_db_remove():
    """
    Test MySQL db remove function in mysql exec module
    """
    with patch.object(mysql, "db_exists", MagicMock(return_value=True)):
        _test_call(mysql.db_remove, "DROP DATABASE `test``'\" db`;", "test`'\" db")


def test_db_tables():
    """
    Test MySQL db_tables function in mysql exec module
    """
    with patch.object(mysql, "db_exists", MagicMock(return_value=True)):
        _test_call(mysql.db_tables, "SHOW TABLES IN `test``'\" db`", "test`'\" db")


def test_db_exists():
    """
    Test MySQL db_exists function in mysql exec module
    """
    _test_call(
        mysql.db_exists,
        {
            "sql": "SHOW DATABASES LIKE %(dbname)s;",
            "sql_args": {"dbname": r"""test%_`" db"""},
        },
        'test%_`" db',
    )


def test_db_create():
    """
    Test MySQL db_create function in mysql exec module
    """
    _test_call(
        mysql.db_create,
        "CREATE DATABASE IF NOT EXISTS `test``'\" db`;",
        "test`'\" db",
    )


def test_user_list():
    """
    Test MySQL user_list function in mysql exec module
    """
    _test_call(mysql.user_list, "SELECT User,Host FROM mysql.user")


def test_user_info():
    """
    Test to see if the mysql execution module correctly forms the SQL for information on a MySQL user.
    """
    _test_call(
        mysql.user_info,
        {
            "sql": "SELECT * FROM mysql.user WHERE User = %(user)s AND Host = %(host)s",
            "sql_args": {"host": "localhost", "user": "mytestuser"},
        },
        "mytestuser",
    )


def test_user_grants():
    """
    Test to ensure the mysql user_grants function returns properly formed SQL for a basic query
    """
    with patch.object(mysql, "user_exists", MagicMock(return_value=True)):
        _test_call(
            mysql.user_grants,
            {
                "sql": "SHOW GRANTS FOR %(user)s@%(host)s",
                "sql_args": {"host": "localhost", "user": "testuser"},
            },
            "testuser",
        )


def test_grant_exists_true():
    """
    Test to ensure that we can find a grant that exists
    """
    mock_grants = [
        "GRANT USAGE ON *.* TO 'testuser'@'%'",
        "GRANT SELECT, INSERT, UPDATE ON `testdb`.`testtableone` TO 'testuser'@'%'",
        "GRANT SELECT(column1,column2) ON `testdb`.`testtableone` TO 'testuser'@'%'",
        "GRANT SELECT(column1,column2), INSERT(column1,column2) ON `testdb`.`testtableone` TO 'testuser'@'%'",
        "GRANT SELECT(column1,column2), UPDATE ON `testdb`.`testtableone` TO 'testuser'@'%'",
        "GRANT SELECT ON `testdb`.`testtabletwo` TO 'testuser'@'%'",
        "GRANT SELECT ON `testdb`.`testtablethree` TO 'testuser'@'%'",
    ]
    with patch.object(mysql, "version", return_value="5.6.41"):
        mock = MagicMock(return_value=mock_grants)
        with patch.object(
            mysql, "user_grants", return_value=mock_grants
        ) as mock_user_grants:
            ret = mysql.grant_exists(
                "SELECT, INSERT, UPDATE", "testdb.testtableone", "testuser", "%"
            )
            assert ret


def test_grant_exists_false():
    """
    Test to ensure that we don't find a grant that doesn't exist
    """
    mock_grants = [
        "GRANT USAGE ON *.* TO 'testuser'@'%'",
        "GRANT SELECT, INSERT, UPDATE ON `testdb`.`testtableone` TO 'testuser'@'%'",
        "GRANT SELECT(column1,column2) ON `testdb`.`testtableone` TO 'testuser'@'%'",
        "GRANT SELECT(column1,column2), UPDATE ON `testdb`.`testtableone` TO 'testuser'@'%'",
        "GRANT SELECT ON `testdb`.`testtablethree` TO 'testuser'@'%'",
    ]
    with patch.object(mysql, "version", return_value="5.6.41"):
        mock = MagicMock(return_value=mock_grants)
        with patch.object(
            mysql, "user_grants", return_value=mock_grants
        ) as mock_user_grants:
            ret = mysql.grant_exists("SELECT", "testdb.testtabletwo", "testuser", "%")
            assert not ret


def test_grant_exists_all():
    """
    Test to ensure that we can find a grant that exists
    """
    mock_grants = ["GRANT ALL PRIVILEGES ON testdb.testtableone TO `testuser`@`%`"]
    with patch.object(mysql, "version", return_value="8.0.10"):
        mock = MagicMock(return_value=mock_grants)
        with patch.object(
            mysql, "user_grants", return_value=mock_grants
        ) as mock_user_grants:
            ret = mysql.grant_exists("ALL", "testdb.testtableone", "testuser", "%")
            assert ret

    with patch.object(mysql, "version", return_value="8.0.10"):
        mock = MagicMock(return_value=mock_grants)
        with patch.object(
            mysql, "user_grants", return_value=mock_grants
        ) as mock_user_grants:
            ret = mysql.grant_exists(
                "all privileges", "testdb.testtableone", "testuser", "%"
            )
            assert ret

    mock_grants = ["GRANT ALL PRIVILEGES ON testdb.testtableone TO `testuser`@`%`"]
    with patch.object(mysql, "version", return_value="5.6.41"):
        mock = MagicMock(return_value=mock_grants)
        with patch.object(
            mysql, "user_grants", return_value=mock_grants
        ) as mock_user_grants:
            ret = mysql.grant_exists(
                "ALL PRIVILEGES", "testdb.testtableone", "testuser", "%"
            )
            assert ret

    mock_grants = [
        "GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, RELOAD, SHUTDOWN, PROCESS, FILE, REFERENCES, INDEX, ALTER, SHOW DATABASES, SUPER, CREATE TEMPORARY TABLES, LOCK TABLES, EXECUTE, REPLICATION SLAVE, REPLICATION CLIENT, CREATE VIEW, SHOW VIEW, CREATE ROUTINE, ALTER ROUTINE, CREATE USER, EVENT, TRIGGER, CREATE TABLESPACE, CREATE ROLE, DROP ROLE ON *.* TO `testuser`@`%`",
        "GRANT BACKUP_ADMIN,BINLOG_ADMIN,CONNECTION_ADMIN,ENCRYPTION_KEY_ADMIN,GROUP_REPLICATION_ADMIN,PERSIST_RO_VARIABLES_ADMIN,REPLICATION_SLAVE_ADMIN,RESOURCE_GROUP_ADMIN,RESOURCE_GROUP_USER,ROLE_ADMIN,SET_USER_ID,SYSTEM_VARIABLES_ADMIN,XA_RECOVER_ADMIN ON *.* TO `testuser`@`%`",
    ]
    with patch.object(mysql, "version", return_value="8.0.10"):
        mock = MagicMock(return_value=mock_grants)
        with patch.object(
            mysql, "user_grants", return_value=mock_grants
        ) as mock_user_grants:
            ret = mysql.grant_exists("ALL", "*.*", "testuser", "%")
            assert ret

    with patch.object(mysql, "version", return_value="8.0.10"):
        mock = MagicMock(return_value=mock_grants)
        with patch.object(
            mysql, "user_grants", return_value=mock_grants
        ) as mock_user_grants:
            ret = mysql.grant_exists("all privileges", "*.*", "testuser", "%")
            assert ret


@pytest.mark.skipif(True, reason="TODO: Mock up user_grants()")
def test_grant_add():
    """
    Test grant_add function in mysql exec module
    """
    _test_call(
        mysql.grant_add,
        "",
        "SELECT,INSERT,UPDATE",
        "database.*",
        "frank",
        "localhost",
    )


@pytest.mark.skipif(True, reason="TODO: Mock up user_grants()")
def test_grant_revoke():
    """
    Test grant revoke in mysql exec module
    """
    _test_call(
        mysql.grant_revoke,
        "",
        "SELECT,INSERT,UPDATE",
        "database.*",
        "frank",
        "localhost",
    )


def test_processlist():
    """
    Test processlist function in mysql exec module
    """
    _test_call(mysql.processlist, "SHOW FULL PROCESSLIST")


def test_get_master_status():
    """
    Test get_master_status in the mysql execution module
    """
    _test_call(mysql.get_master_status, "SHOW MASTER STATUS")


def test_get_slave_status():
    """
    Test get_slave_status in the mysql execution module
    """
    _test_call(mysql.get_slave_status, "SHOW SLAVE STATUS")


def test_get_slave_status_bad_server():
    """
    Test get_slave_status in the mysql execution module, simulating a broken server
    """
    connect_mock = MagicMock(return_value=None)
    with patch.object(mysql, "_connect", connect_mock):
        with patch.dict(mysql.__salt__, {"config.option": MagicMock()}):
            rslt = mysql.get_slave_status()
            connect_mock.assert_has_calls([call()])
            assert rslt == []


@pytest.mark.skipif(
    True, reason="MySQL module claims this function is not ready for production"
)
def test_free_slave():
    pass


def test_query():
    _test_call(mysql.query, "SELECT * FROM testdb", "testdb", "SELECT * FROM testdb")


@pytest.mark.skipif(not HAS_PYMYSQL, reason="Could not import pymysql")
def test_query_error():
    connect_mock = MagicMock()
    with patch.object(mysql, "_connect", connect_mock):
        with patch.dict(mysql.__salt__, {"config.option": MagicMock()}):
            # Use the OperationalError from the salt mysql module because that
            # exception can come from either MySQLdb or pymysql
            side_effect = mysql.OperationalError(9999, "Something Went Wrong")
            with patch.object(mysql, "_execute", MagicMock(side_effect=side_effect)):
                mysql.query("testdb", "SELECT * FROM testdb")
        assert "mysql.error" in mysql.__context__
        expected = "MySQL Error 9999: Something Went Wrong"
        assert mysql.__context__["mysql.error"] == expected


def test_plugin_add():
    """
    Test the adding/installing a MySQL / MariaDB plugin
    """
    with patch.object(mysql, "plugin_status", MagicMock(return_value="")):
        _test_call(
            mysql.plugin_add,
            'INSTALL PLUGIN auth_socket SONAME "auth_socket.so"',
            "auth_socket",
        )


def test_plugin_remove():
    """
    Test the removing/uninstalling a MySQL / MariaDB plugin
    """
    with patch.object(mysql, "plugin_status", MagicMock(return_value="ACTIVE")):
        _test_call(
            mysql.plugin_remove,
            "UNINSTALL PLUGIN auth_socket",
            "auth_socket",
        )


def test_plugin_status():
    """
    Test checking the status of a MySQL / MariaDB plugin
    """
    _test_call(
        mysql.plugin_status,
        {
            "sql": "SELECT PLUGIN_STATUS FROM INFORMATION_SCHEMA.PLUGINS WHERE PLUGIN_NAME = %(name)s",
            "sql_args": {"name": "auth_socket"},
        },
        "auth_socket",
    )


def test_sanitize_comment():
    """
    Test comment sanitization
    """
    input_data = """/*
    multiline
    comment
    */
    CREATE TABLE test_update (a VARCHAR(25)); # end of line comment
    # example comment
    insert into test_update values ("some #hash value");            -- ending comment
    insert into test_update values ("crazy -- not comment"); -- another ending comment
    -- another comment type
    """
    expected_response = """CREATE TABLE test_update (a VARCHAR(25));

insert into test_update values ("some #hash value");
insert into test_update values ("crazy -- not comment");

"""
    output = mysql._sanitize_comments(input_data)
    assert output == expected_response

    input_data = """-- --------------------------------------------------------
                    -- SQL Commands to set up the pmadb as described in the documentation.
                    --
                    -- This file is meant for use with MySQL 5 and above!
                    --
                    -- This script expects the user pma to already be existing. If we would put a
                    -- line here to create them too many users might just use this script and end
                    -- up with having the same password for the controluser.
                    --
                    -- This user "pma" must be defined in config.inc.php (controluser/controlpass)
                    --
                    -- Please don't forget to set up the tablenames in config.inc.php
                    --
                    -- --------------------------------------------------------
                    --
                    CREATE DATABASE IF NOT EXISTS `phpmyadmin`
                      DEFAULT CHARACTER SET utf8 COLLATE utf8_bin;
                    USE phpmyadmin;
    """

    expected_response = """CREATE DATABASE IF NOT EXISTS `phpmyadmin`
                      DEFAULT CHARACTER SET utf8 COLLATE utf8_bin;
                    USE phpmyadmin;"""

    output = mysql._sanitize_comments(input_data)
    assert output == expected_response


def _test_call(function, expected_sql, *args, **kwargs):
    connect_mock = MagicMock()
    with patch.object(mysql, "_connect", connect_mock):
        with patch.dict(mysql.__salt__, {"config.option": MagicMock()}):
            function(*args, **kwargs)
            if isinstance(expected_sql, dict):
                calls = (
                    call()
                    .cursor()
                    .execute("{}".format(expected_sql["sql"]), expected_sql["sql_args"])
                )
            else:
                calls = call().cursor().execute("{}".format(expected_sql))
            connect_mock.assert_has_calls((calls,), True)


def test_file_query():
    """
    Test file_query
    """
    with patch.object(mysql, "HAS_SQLPARSE", False):
        ret = mysql.file_query("database", "filename")
        assert not ret

    file_data = """-- --------------------------------------------------------
                   -- SQL Commands to set up the pmadb as described in the documentation.
                   --
                   -- This file is meant for use with MySQL 5 and above!
                   --
                   -- This script expects the user pma to already be existing. If we would put a
                   -- line here to create them too many users might just use this script and end
                   -- up with having the same password for the controluser.
                   --
                   -- This user "pma" must be defined in config.inc.php (controluser/controlpass)
                   --
                   -- Please don't forget to set up the tablenames in config.inc.php
                   --
                   -- --------------------------------------------------------
                   --
                   USE phpmyadmin;

                   --
                   -- Table structure for table `pma__bookmark`
                   --

                   CREATE TABLE IF NOT EXISTS `pma__bookmark` (
                     `id` int(10) unsigned NOT NULL auto_increment,
                     `dbase` varchar(255) NOT NULL default '',
                     `user` varchar(255) NOT NULL default '',
                     `label` varchar(255) COLLATE utf8_general_ci NOT NULL default '',
                     `query` text NOT NULL,
                     PRIMARY KEY  (`id`)
                   )
                     COMMENT='Bookmarks'
                     DEFAULT CHARACTER SET utf8 COLLATE utf8_bin;
    """

    side_effect = [
        {"query time": {"human": "0.4ms", "raw": "0.00038"}, "rows affected": 0},
        {"query time": {"human": "8.9ms", "raw": "0.00893"}, "rows affected": 0},
    ]
    expected = {
        "query time": {"human": "8.9ms", "raw": "0.00893"},
        "rows affected": 0,
    }

    with patch("os.path.exists", MagicMock(return_value=True)):
        with patch("salt.utils.files.fopen", mock_open(read_data=file_data)):
            with patch.object(mysql, "query", side_effect=side_effect):
                ret = mysql.file_query("database", "filename")
                assert ret, expected


@pytest.mark.skipif(not HAS_PYMYSQL, reason="Could not import pymysql")
def test__connect_pymysql_exception():
    """
    Test the _connect function in the MySQL module
    """
    with patch.dict(mysql.__salt__, {"config.option": MagicMock()}):
        with patch(
            "MySQLdb.connect",
            side_effect=pymysql.err.InternalError(
                1698, "Access denied for user 'root'@'localhost'"
            ),
        ):
            ret = mysql._connect()
            assert "mysql.error" in mysql.__context__
            assert (
                mysql.__context__["mysql.error"]
                == "MySQL Error 1698: Access denied for user 'root'@'localhost'"
            )


def test__connect_mysqldb_exception():
    """
    Test the _connect function in the MySQL module
    """
    with patch.dict(mysql.__salt__, {"config.option": MagicMock()}):
        with patch(
            "MySQLdb.connect",
            side_effect=mysql.OperationalError(
                1698, "Access denied for user 'root'@'localhost'"
            ),
        ):
            ret = mysql._connect()
            assert "mysql.error" in mysql.__context__
            assert (
                mysql.__context__["mysql.error"]
                == "MySQL Error 1698: Access denied for user 'root'@'localhost'"
            )


def test__connect_mysqldb():
    """
    Test the _connect function in the MySQL module
    """
    mysqldb_connect_mock = MagicMock(autospec=True, return_value=MockMySQLConnect())
    with patch.dict(mysql.__salt__, {"config.option": MagicMock()}):
        with patch("MySQLdb.connect", mysqldb_connect_mock):
            mysql._connect()
            assert "mysql.error" not in mysql.__context__
