"""
Test Salt MySQL module across various MySQL variants
"""
import logging

import pytest
import salt.modules.mysql as mysql
from tests.support.pytest.mysql import mysql_container  # pylint: disable=unused-import

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("dockerd"),
    pytest.mark.skipif(
        mysql.MySQLdb is None, reason="No python mysql client installed."
    ),
]


@pytest.fixture(scope="module")
def salt_call_cli_wrapper(salt_call_cli, mysql_container):
    def run_command(*command, **kwargs):
        connection_user = kwargs.pop("connection_user", mysql_container.mysql_user)
        connection_pass = kwargs.pop("connection_pass", mysql_container.mysql_passwd)
        connection_db = kwargs.pop("connection_db", "mysql")
        connection_port = kwargs.pop("connection_port", mysql_container.mysql_port)

        return salt_call_cli.run(
            *command,
            connection_user=connection_user,
            connection_pass=connection_pass,
            connection_db=connection_db,
            connection_port=connection_port,
            **kwargs
        )

    return run_command


def test_query(salt_call_cli_wrapper):
    ret = salt_call_cli_wrapper("mysql.query", "mysql", "SELECT 1")
    assert ret.json
    assert ret.json["results"] == [["1"]]


def test_version(salt_call_cli_wrapper, mysql_container):
    ret = salt_call_cli_wrapper("mysql.version")

    assert ret.json
    assert mysql_container.mysql_version in ret.json


def test_status(salt_call_cli_wrapper):
    ret = salt_call_cli_wrapper("mysql.status")
    assert ret.json


def test_db_list(salt_call_cli_wrapper):
    ret = salt_call_cli_wrapper("mysql.db_list")

    assert ret.json
    assert "mysql" in ret.json


def test_db_create_alter_remove(salt_call_cli_wrapper):
    ret = salt_call_cli_wrapper("mysql.db_create", "salt")
    assert ret.json

    ret = salt_call_cli_wrapper(
        "mysql.alter_db",
        name="salt",
        character_set="latin1",
        collate="latin1_general_ci",
    )
    assert ret.json

    ret = salt_call_cli_wrapper("mysql.db_remove", name="salt")
    assert ret.json


def test_user_list(salt_call_cli_wrapper):
    ret = salt_call_cli_wrapper("mysql.user_list")
    assert ret.json
    assert {"User": "root", "Host": "%"} in ret.json


def test_user_exists(salt_call_cli_wrapper):
    ret = salt_call_cli_wrapper("mysql.user_exists", "root", "%", "password")
    assert ret.json

    ret = salt_call_cli_wrapper(
        "mysql.user_exists",
        "george",
        "hostname",
        "badpassword",
    )
    assert not ret.json


def test_user_info(salt_call_cli_wrapper):
    ret = salt_call_cli_wrapper("mysql.user_info", "root", "%")
    assert ret.json

    # Check that a subset of the information
    # is available in the returned user information.
    expected = {
        "Host": "%",
        "User": "root",
        "Select_priv": "Y",
        "Insert_priv": "Y",
        "Update_priv": "Y",
        "Delete_priv": "Y",
        "Create_priv": "Y",
        "Drop_priv": "Y",
        "Reload_priv": "Y",
        "Shutdown_priv": "Y",
        "Process_priv": "Y",
        "File_priv": "Y",
        "Grant_priv": "Y",
        "References_priv": "Y",
        "Index_priv": "Y",
        "Alter_priv": "Y",
        "Show_db_priv": "Y",
        "Super_priv": "Y",
        "Create_tmp_table_priv": "Y",
        "Lock_tables_priv": "Y",
        "Execute_priv": "Y",
        "Repl_slave_priv": "Y",
        "Repl_client_priv": "Y",
        "Create_view_priv": "Y",
        "Show_view_priv": "Y",
        "Create_routine_priv": "Y",
        "Alter_routine_priv": "Y",
        "Create_user_priv": "Y",
        "Event_priv": "Y",
        "Trigger_priv": "Y",
        "Create_tablespace_priv": "Y",
    }
    assert all(ret.json.get(key, None) == val for key, val in expected.items())


def test_user_create_chpass_delete(salt_call_cli_wrapper):
    ret = salt_call_cli_wrapper(
        "mysql.user_create",
        "george",
        host="localhost",
        password="badpassword",
    )
    assert ret.json

    ret = salt_call_cli_wrapper(
        "mysql.user_chpass",
        "george",
        host="localhost",
        password="different_password",
    )
    assert ret.json

    ret = salt_call_cli_wrapper("mysql.user_remove", "george", host="localhost")
    assert ret.json


def test_user_grants(salt_call_cli_wrapper):
    ret = salt_call_cli_wrapper("mysql.user_grants", "root", host="%")
    assert ret.json


def test_grant_add_revoke(salt_call_cli_wrapper):
    # Create the database
    ret = salt_call_cli_wrapper("mysql.db_create", "salt")
    assert ret.json

    # Create a user
    ret = salt_call_cli_wrapper(
        "mysql.user_create",
        "george",
        host="localhost",
        password="badpassword",
    )
    assert ret.json

    # Grant privileges to user to specific table
    ret = salt_call_cli_wrapper(
        "mysql.grant_add",
        grant="ALL PRIVILEGES",
        database="salt.*",
        user="george",
        host="localhost",
    )
    assert ret.json

    # Check the grant exists
    ret = salt_call_cli_wrapper(
        "mysql.grant_exists",
        grant="ALL PRIVILEGES",
        database="salt.*",
        user="george",
        host="localhost",
    )
    assert ret.json

    # Revoke the grant
    ret = salt_call_cli_wrapper(
        "mysql.grant_revoke",
        grant="ALL PRIVILEGES",
        database="salt.*",
        user="george",
        host="localhost",
    )
    assert ret.json

    # Check the grant does not exist
    ret = salt_call_cli_wrapper(
        "mysql.grant_exists",
        grant="ALL PRIVILEGES",
        database="salt.*",
        user="george",
        host="localhost",
    )
    assert not ret.json

    # Grant privileges to user globally
    ret = salt_call_cli_wrapper(
        "mysql.grant_add",
        grant="ALL PRIVILEGES",
        database="*.*",
        user="george",
        host="localhost",
    )
    assert ret.json

    # Check the global exists
    ret = salt_call_cli_wrapper(
        "mysql.grant_exists",
        grant="ALL PRIVILEGES",
        database="*.*",
        user="george",
        host="localhost",
    )
    assert ret.json

    # Revoke the global grant
    ret = salt_call_cli_wrapper(
        "mysql.grant_revoke",
        grant="ALL PRIVILEGES",
        database="*.*",
        user="george",
        host="localhost",
    )
    assert ret.json

    # Check the grant does not exist
    ret = salt_call_cli_wrapper(
        "mysql.grant_exists",
        grant="ALL PRIVILEGES",
        database="salt.*",
        user="george",
        host="localhost",
    )
    assert not ret.json

    # Remove the user
    ret = salt_call_cli_wrapper("mysql.user_remove", "george", host="localhost")
    assert ret.json

    # Remove the database
    ret = salt_call_cli_wrapper("mysql.db_remove", "salt")
    assert ret.json


def test_plugin_add_status_remove(salt_call_cli_wrapper, mysql_container):

    if "mariadb" in mysql_container.mysql_name:
        plugin = "simple_password_check"
    else:
        plugin = "auth_socket"

    ret = salt_call_cli_wrapper("mysql.plugin_status", plugin, host="%")
    assert not ret.json

    ret = salt_call_cli_wrapper("mysql.plugin_add", plugin)
    assert ret.json

    ret = salt_call_cli_wrapper("mysql.plugin_status", plugin, host="%")
    assert ret.json
    assert ret.json == "ACTIVE"

    ret = salt_call_cli_wrapper("mysql.plugin_remove", plugin)
    assert ret.json

    ret = salt_call_cli_wrapper("mysql.plugin_status", plugin, host="%")
    assert not ret.json


def test_plugin_list(salt_call_cli_wrapper, mysql_container):
    if "mariadb" in mysql_container.mysql_name:
        plugin = "simple_password_check"
    else:
        plugin = "auth_socket"

    ret = salt_call_cli_wrapper("mysql.plugins_list")
    assert {"name": plugin, "status": "ACTIVE"} not in ret.json
    assert ret.json

    ret = salt_call_cli_wrapper("mysql.plugin_add", plugin)
    assert ret.json

    ret = salt_call_cli_wrapper("mysql.plugins_list")
    assert ret.json
    assert {"name": plugin, "status": "ACTIVE"} in ret.json

    ret = salt_call_cli_wrapper("mysql.plugin_remove", plugin)
    assert ret.json


def test_grant_add_revoke_password_hash(salt_call_cli_wrapper):
    # Create the database
    ret = salt_call_cli_wrapper("mysql.db_create", "salt")
    assert ret.json

    # Create a user
    ret = salt_call_cli_wrapper(
        "mysql.user_create",
        "george",
        host="%",
        password_hash="*2470C0C06DEE42FD1618BB99005ADCA2EC9D1E19",
    )
    assert ret.json

    # Grant privileges to user to specific table
    ret = salt_call_cli_wrapper(
        "mysql.grant_add",
        grant="ALL PRIVILEGES",
        database="salt.*",
        user="george",
        host="%",
    )
    assert ret.json

    # Check the grant exists
    ret = salt_call_cli_wrapper(
        "mysql.grant_exists",
        grant="ALL PRIVILEGES",
        database="salt.*",
        user="george",
        host="%",
    )
    assert ret.json

    # Check the grant exists via a query
    ret = salt_call_cli_wrapper(
        "mysql.query",
        database="salt",
        query="SELECT 1",
        connection_user="george",
        connection_pass="password",
        connection_db="salt",
    )
    assert ret.json

    # Revoke the grant
    ret = salt_call_cli_wrapper(
        "mysql.grant_revoke",
        grant="ALL PRIVILEGES",
        database="salt.*",
        user="george",
        host="%",
    )
    assert ret.json

    # Check the grant does not exist
    ret = salt_call_cli_wrapper(
        "mysql.grant_exists",
        grant="ALL PRIVILEGES",
        database="salt.*",
        user="george",
        host="%",
    )
    assert not ret.json

    # Remove the user
    ret = salt_call_cli_wrapper("mysql.user_remove", "george", host="%")
    assert ret.json

    # Remove the database
    ret = salt_call_cli_wrapper("mysql.db_remove", "salt")
    assert ret.json


def test_create_alter_password_hash(salt_call_cli_wrapper):
    # Create the database
    ret = salt_call_cli_wrapper("mysql.db_create", "salt")
    assert ret.json

    # Create a user
    ret = salt_call_cli_wrapper(
        "mysql.user_create",
        "george",
        host="%",
        password_hash="*2470C0C06DEE42FD1618BB99005ADCA2EC9D1E19",
    )
    assert ret.json

    # Grant privileges to user to specific table
    ret = salt_call_cli_wrapper(
        "mysql.grant_add",
        grant="ALL PRIVILEGES",
        database="salt.*",
        user="george",
        host="%",
    )
    assert ret.json

    # Check the grant exists
    ret = salt_call_cli_wrapper(
        "mysql.grant_exists",
        grant="ALL PRIVILEGES",
        database="salt.*",
        user="george",
        host="%",
    )
    assert ret.json

    # Check we can query as the new user
    ret = salt_call_cli_wrapper(
        "mysql.query",
        database="salt",
        query="SELECT 1",
        connection_user="george",
        connection_pass="password",
        connection_db="salt",
    )
    assert ret.json

    # Change the user password
    ret = salt_call_cli_wrapper(
        "mysql.user_chpass",
        "george",
        host="%",
        password_hash="*F4A5147613F01DEC0C5226BF24CD1D5762E6AAF2",
    )
    assert ret.json

    # Check we can query with the new password
    ret = salt_call_cli_wrapper(
        "mysql.query",
        database="salt",
        query="SELECT 1",
        connection_user="george",
        connection_pass="badpassword",
        connection_db="salt",
    )
    assert ret.json

    # Revoke the grant
    ret = salt_call_cli_wrapper(
        "mysql.grant_revoke",
        grant="ALL PRIVILEGES",
        database="salt.*",
        user="george",
        host="%",
    )
    assert ret.json

    # Check the grant does not exist
    ret = salt_call_cli_wrapper(
        "mysql.grant_exists",
        grant="ALL PRIVILEGES",
        database="salt.*",
        user="george",
        host="%",
    )
    assert not ret.json

    # Remove the user
    ret = salt_call_cli_wrapper("mysql.user_remove", "george", host="%")
    assert ret.json

    # Remove the database
    ret = salt_call_cli_wrapper("mysql.db_remove", "salt")
    assert ret.json
