"""
Test Salt MySQL module across various MySQL variants
"""

import logging
import time

import pytest
from pytestshellutils.utils import format_callback_to_string

import salt.modules.mysql as mysqlmod
from salt.utils.versions import version_cmp
from tests.support.pytest.mysql import *  # pylint: disable=wildcard-import,unused-wildcard-import

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("dockerd"),
    pytest.mark.skipif(
        mysqlmod.MySQLdb is None, reason="No python mysql client installed."
    ),
    pytest.mark.skip_on_fips_enabled_platform,
]


def _get_mysql_error(context):
    return context.pop("mysql.error", None)


class CallWrapper:
    def __init__(self, func, container, ctx):
        self.func = func
        self.container = container
        self.ctx = ctx

    def __call__(self, *args, **kwargs):
        kwargs.update(self.container.get_credentials(**kwargs))
        retry = 1
        retries = 3
        ret = None
        while True:
            ret = self.func(*list(args), **kwargs.copy())
            mysql_error = _get_mysql_error(self.ctx)
            if mysql_error is None:
                break
            retry += 1

            if retry > retries:
                break

            time.sleep(0.5)
            log.debug(
                "Retrying(%s out of %s) %s because of the following error: %s",
                retry,
                retries,
                format_callback_to_string(self.func, args, kwargs),
                mysql_error,
            )
        return ret


@pytest.fixture(scope="module")
def mysql(modules, mysql_container, loaders):
    for name in list(modules):
        if not name.startswith("mysql."):
            continue
        modules._dict[name] = CallWrapper(
            modules._dict[name],
            mysql_container,
            loaders.context,
        )
    return modules.mysql


def test_query(mysql):
    ret = mysql.query("mysql", "SELECT 1")
    assert ret
    assert ret["results"] == (("1",),)


def test_version(mysql, mysql_container):
    ret = mysql.version()
    assert ret
    assert mysql_container.mysql_version in ret


def test_status(mysql):
    ret = mysql.status()
    assert ret


def test_db_list(mysql):
    ret = mysql.db_list()
    assert ret
    assert "mysql" in ret


def test_db_create_alter_remove(mysql):
    ret = mysql.db_create("salt")
    assert ret

    ret = mysql.alter_db(
        name="salt",
        character_set="latin1",
        collate="latin1_general_ci",
    )
    assert ret

    ret = mysql.db_remove(name="salt")
    assert ret


def test_user_list(mysql, mysql_combo):
    ret = mysql.user_list()
    assert ret
    assert {
        "User": mysql_combo.mysql_root_user,
        "Host": mysql_combo.mysql_host,
    } in ret


def test_user_exists(mysql, mysql_combo):
    ret = mysql.user_exists(
        mysql_combo.mysql_root_user,
        host=mysql_combo.mysql_host,
        password=mysql_combo.mysql_passwd,
    )
    assert ret

    ret = mysql.user_exists(
        "george",
        "hostname",
        "badpassword",
    )
    assert not ret


def test_user_info(mysql, mysql_combo):
    ret = mysql.user_info(mysql_combo.mysql_root_user, host=mysql_combo.mysql_host)
    assert ret

    # Check that a subset of the information
    # is available in the returned user information.
    expected = {
        "Host": mysql_combo.mysql_host,
        "User": mysql_combo.mysql_root_user,
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
    data = ret.copy()
    for key in list(data):
        if key not in expected:
            data.pop(key)
    assert data == expected


def test_user_create_chpass_delete(mysql):
    ret = mysql.user_create(
        "george",
        host="localhost",
        password="badpassword",
    )
    assert ret

    ret = mysql.user_chpass(
        "george",
        host="localhost",
        password="different_password",
    )
    assert ret

    ret = mysql.user_remove("george", host="localhost")
    assert ret


def test_user_grants(mysql, mysql_combo):
    ret = mysql.user_grants(mysql_combo.mysql_root_user, host=mysql_combo.mysql_host)
    assert ret


def test_grant_add_revoke(mysql):
    # Create the database
    ret = mysql.db_create("salt")
    assert ret

    # Create a user
    ret = mysql.user_create(
        "george",
        host="localhost",
        password="badpassword",
    )
    assert ret

    # Grant privileges to user to specific table
    ret = mysql.grant_add(
        grant="ALL PRIVILEGES",
        database="salt.*",
        user="george",
        host="localhost",
    )
    assert ret

    # Check the grant exists
    ret = mysql.grant_exists(
        grant="ALL PRIVILEGES",
        database="salt.*",
        user="george",
        host="localhost",
    )
    assert ret

    # Revoke the grant
    ret = mysql.grant_revoke(
        grant="ALL PRIVILEGES",
        database="salt.*",
        user="george",
        host="localhost",
    )
    assert ret

    # Check the grant does not exist
    ret = mysql.grant_exists(
        grant="ALL PRIVILEGES",
        database="salt.*",
        user="george",
        host="localhost",
    )
    assert not ret

    # Grant privileges to user globally
    ret = mysql.grant_add(
        grant="ALL PRIVILEGES",
        database="*.*",
        user="george",
        host="localhost",
    )
    assert ret

    # Check the global exists
    ret = mysql.grant_exists(
        grant="ALL PRIVILEGES",
        database="*.*",
        user="george",
        host="localhost",
    )
    assert ret

    # Revoke the global grant
    ret = mysql.grant_revoke(
        grant="ALL PRIVILEGES",
        database="*.*",
        user="george",
        host="localhost",
    )
    assert ret

    # Check the grant does not exist
    ret = mysql.grant_exists(
        grant="ALL PRIVILEGES",
        database="salt.*",
        user="george",
        host="localhost",
    )
    assert not ret

    # Remove the user
    ret = mysql.user_remove("george", host="localhost")
    assert ret

    # Remove the database
    ret = mysql.db_remove("salt")
    assert ret


def test_grant_replication_replica_add_revoke(mysql, mysql_container):
    # The REPLICATION REPLICA grant is only available for mariadb
    if "mariadb" not in mysql_container.mysql_name:
        pytest.skip(
            "The REPLICATION REPLICA grant is unavailable "
            "for the {}:{} docker image.".format(
                mysql_container.mysql_name, mysql_container.mysql_version
            )
        )

    # The REPLICATION REPLICA grant was added in mariadb 10.5.1
    if version_cmp(mysql_container.mysql_version, "10.5.1") < 0:
        pytest.skip(
            "The REPLICATION REPLICA grant is unavailable "
            "for the {}:{} docker image.".format(
                mysql_container.mysql_name, mysql_container.mysql_version
            )
        )

    # Create the database
    ret = mysql.db_create("salt")
    assert ret

    # Create a user
    ret = mysql.user_create(
        "george",
        host="localhost",
        password="badpassword",
    )
    assert ret

    # Grant privileges to user to specific table
    ret = mysql.grant_add(
        grant="REPLICATION REPLICA",
        database="*.*",
        user="george",
        host="localhost",
    )
    assert ret

    # Check the grant exists
    ret = mysql.grant_exists(
        grant="REPLICATION REPLICA",
        database="*.*",
        user="george",
        host="localhost",
    )
    assert ret

    # Revoke the global grant
    ret = mysql.grant_revoke(
        grant="REPLICATION REPLICA",
        database="*.*",
        user="george",
        host="localhost",
    )
    assert ret

    # Check the grant does not exist
    ret = mysql.grant_exists(
        grant="REPLICATION REPLICA",
        database="*.*",
        user="george",
        host="localhost",
    )
    assert not ret

    # Remove the user
    ret = mysql.user_remove("george", host="localhost")
    assert ret

    # Remove the database
    ret = mysql.db_remove("salt")
    assert ret


def test_grant_replication_slave_add_revoke(mysql, mysql_container):
    # Create the database
    ret = mysql.db_create("salt")
    assert ret

    # Create a user
    ret = mysql.user_create(
        "george",
        host="localhost",
        password="badpassword",
    )
    assert ret

    # Grant privileges to user to specific table
    ret = mysql.grant_add(
        grant="REPLICATION SLAVE",
        database="*.*",
        user="george",
        host="localhost",
    )
    assert ret

    # Check the grant exists
    ret = mysql.grant_exists(
        grant="REPLICATION SLAVE",
        database="*.*",
        user="george",
        host="localhost",
    )
    assert ret

    # Revoke the global grant
    ret = mysql.grant_revoke(
        grant="REPLICATION SLAVE",
        database="*.*",
        user="george",
        host="localhost",
    )
    assert ret

    # Check the grant does not exist
    ret = mysql.grant_exists(
        grant="REPLICATION SLAVE",
        database="*.*",
        user="george",
        host="localhost",
    )
    assert not ret

    # Remove the user
    ret = mysql.user_remove("george", host="localhost")
    assert ret

    # Remove the database
    ret = mysql.db_remove("salt")
    assert ret


def test_grant_replication_client_add_revoke(mysql, mysql_container):
    # Create the database
    ret = mysql.db_create("salt")
    assert ret

    # Create a user
    ret = mysql.user_create(
        "george",
        host="localhost",
        password="badpassword",
    )
    assert ret

    # Grant privileges to user to specific table
    ret = mysql.grant_add(
        grant="REPLICATION CLIENT",
        database="*.*",
        user="george",
        host="localhost",
    )
    assert ret

    # Check the grant exists
    ret = mysql.grant_exists(
        grant="REPLICATION CLIENT",
        database="*.*",
        user="george",
        host="localhost",
    )
    assert ret

    # Revoke the global grant
    ret = mysql.grant_revoke(
        grant="REPLICATION CLIENT",
        database="*.*",
        user="george",
        host="localhost",
    )
    assert ret

    # Check the grant does not exist
    ret = mysql.grant_exists(
        grant="REPLICATION CLIENT",
        database="*.*",
        user="george",
        host="localhost",
    )
    assert not ret

    # Remove the user
    ret = mysql.user_remove("george", host="localhost")
    assert ret

    # Remove the database
    ret = mysql.db_remove("salt")
    assert ret


def test_grant_binlog_monitor_add_revoke(mysql, mysql_container):
    # The BINLOG MONITOR grant is only available for mariadb
    if "mariadb" not in mysql_container.mysql_name:
        pytest.skip(
            "The BINLOG MONITOR grant is unavailable "
            "for the {}:{} docker image.".format(
                mysql_container.mysql_name, mysql_container.mysql_version
            )
        )

    # The BINLOG MONITOR grant was added in mariadb 10.5.2
    if version_cmp(mysql_container.mysql_version, "10.5.2") < 0:
        pytest.skip(
            "The BINLOG_MONITOR grant is unavailable "
            "for the {}:{} docker image.".format(
                mysql_container.mysql_name, mysql_container.mysql_version
            )
        )

    # Create the database
    ret = mysql.db_create("salt")
    assert ret

    # Create a user
    ret = mysql.user_create(
        "george",
        host="localhost",
        password="badpassword",
    )
    assert ret

    # Grant privileges to user to specific table
    ret = mysql.grant_add(
        grant="BINLOG MONITOR",
        database="salt.*",
        user="george",
        host="localhost",
    )
    assert ret

    # Check the grant exists
    ret = mysql.grant_exists(
        grant="BINLOG MONITOR",
        database="salt.*",
        user="george",
        host="localhost",
    )
    assert ret

    # Revoke the global grant
    ret = mysql.grant_revoke(
        grant="BINLOG MONITOR",
        database="*.*",
        user="george",
        host="localhost",
    )
    assert ret

    # Check the grant does not exist
    ret = mysql.grant_exists(
        grant="BINLOG MONITOR",
        database="salt.*",
        user="george",
        host="localhost",
    )
    assert not ret

    # Remove the user
    ret = mysql.user_remove("george", host="localhost")
    assert ret

    # Remove the database
    ret = mysql.db_remove("salt")
    assert ret


def test_grant_replica_monitor_add_revoke(mysql, mysql_container):
    # The REPLICA MONITOR grant is only available for mariadb
    if "mariadb" not in mysql_container.mysql_name:
        pytest.skip(
            "The REPLICA MONITOR grant is unavailable "
            "for the {}:{} docker image.".format(
                mysql_container.mysql_name, mysql_container.mysql_version
            )
        )

    # The REPLICA MONITOR grant was added in mariadb 10.5.9
    if version_cmp(mysql_container.mysql_version, "10.5.9") < 0:
        pytest.skip(
            "The REPLICA MONITOR grant is unavailable "
            "for the {}:{} docker image.".format(
                mysql_container.mysql_name, mysql_container.mysql_version
            )
        )

    # Create the database
    ret = mysql.db_create("salt")
    assert ret

    # Create a user
    ret = mysql.user_create(
        "george",
        host="localhost",
        password="badpassword",
    )
    assert ret

    # Grant privileges to user to specific table
    ret = mysql.grant_add(
        grant="REPLICA MONITOR",
        database="*.*",
        user="george",
        host="localhost",
    )
    assert ret

    # Check the grant exists
    ret = mysql.grant_exists(
        grant="REPLICA MONITOR",
        database="*.*",
        user="george",
        host="localhost",
    )
    assert ret

    # Revoke the global grant
    ret = mysql.grant_revoke(
        grant="REPLICA MONITOR",
        database="*.*",
        user="george",
        host="localhost",
    )
    assert ret

    # Check the grant does not exist
    ret = mysql.grant_exists(
        grant="REPLICA MONITOR",
        database="*.*",
        user="george",
        host="localhost",
    )
    assert not ret

    # Remove the user
    ret = mysql.user_remove("george", host="localhost")
    assert ret

    # Remove the database
    ret = mysql.db_remove("salt")
    assert ret


def test_grant_slave_monitor_add_revoke(mysql, mysql_container):
    # The SLAVE MONITOR grant is only available for mariadb
    if "mariadb" not in mysql_container.mysql_name:
        pytest.skip(
            "The SLAVE MONITOR grant is unavailable "
            "for the {}:{} docker image.".format(
                mysql_container.mysql_name, mysql_container.mysql_version
            )
        )

    # The SLAVE MONITOR grant was added in mariadb 10.5.9
    if version_cmp(mysql_container.mysql_version, "10.5.9") < 0:
        pytest.skip(
            "The SLAVE MONITOR grant is unavailable "
            "for the {}:{} docker image.".format(
                mysql_container.mysql_name, mysql_container.mysql_version
            )
        )

    # Create the database
    ret = mysql.db_create("salt")
    assert ret

    # Create a user
    ret = mysql.user_create(
        "george",
        host="localhost",
        password="badpassword",
    )
    assert ret

    # Grant privileges to user to specific table
    ret = mysql.grant_add(
        grant="SLAVE MONITOR",
        database="*.*",
        user="george",
        host="localhost",
    )
    assert ret

    # Check the grant exists
    ret = mysql.grant_exists(
        grant="SLAVE MONITOR",
        database="*.*",
        user="george",
        host="localhost",
    )
    assert ret

    # Revoke the global grant
    ret = mysql.grant_revoke(
        grant="SLAVE MONITOR",
        database="*.*",
        user="george",
        host="localhost",
    )
    assert ret

    # Check the grant does not exist
    ret = mysql.grant_exists(
        grant="SLAVE MONITOR",
        database="salt.*",
        user="george",
        host="localhost",
    )
    assert not ret

    # Remove the user
    ret = mysql.user_remove("george", host="localhost")
    assert ret

    # Remove the database
    ret = mysql.db_remove("salt")
    assert ret


def test_plugin_add_status_remove(mysql, mysql_combo):

    if "mariadb" in mysql_combo.mysql_name:
        plugin = "simple_password_check"
    else:
        plugin = "auth_socket"

    ret = mysql.plugin_status(plugin, host=mysql_combo.mysql_host)
    assert not ret

    ret = mysql.plugin_add(plugin)
    assert ret

    ret = mysql.plugin_status(plugin, host=mysql_combo.mysql_host)
    assert ret
    assert ret == "ACTIVE"

    ret = mysql.plugin_remove(plugin)
    assert ret

    ret = mysql.plugin_status(plugin, host=mysql_combo.mysql_host)
    assert not ret


def test_plugin_list(mysql, mysql_container):
    if "mariadb" in mysql_container.mysql_name:
        plugin = "simple_password_check"
    else:
        plugin = "auth_socket"

    ret = mysql.plugins_list()
    assert {"name": plugin, "status": "ACTIVE"} not in ret
    assert ret

    ret = mysql.plugin_add(plugin)
    assert ret

    ret = mysql.plugins_list()
    assert ret
    assert {"name": plugin, "status": "ACTIVE"} in ret

    ret = mysql.plugin_remove(plugin)
    assert ret


def test_grant_add_revoke_password_hash(mysql):
    # Create the database
    ret = mysql.db_create("salt")
    assert ret

    # Create a user
    ret = mysql.user_create(
        "george",
        host="%",
        password_hash="*2470C0C06DEE42FD1618BB99005ADCA2EC9D1E19",
    )
    assert ret

    # Grant privileges to user to specific table
    ret = mysql.grant_add(
        grant="ALL PRIVILEGES",
        database="salt.*",
        user="george",
        host="%",
    )
    assert ret

    # Check the grant exists
    ret = mysql.grant_exists(
        grant="ALL PRIVILEGES",
        database="salt.*",
        user="george",
        host="%",
    )
    assert ret

    # Check the grant exists via a query
    ret = mysql.query(
        database="salt",
        query="SELECT 1",
        connection_user="george",
        connection_pass="password",
        connection_db="salt",
    )
    assert ret

    # Revoke the grant
    ret = mysql.grant_revoke(
        grant="ALL PRIVILEGES",
        database="salt.*",
        user="george",
        host="%",
    )
    assert ret

    # Check the grant does not exist
    ret = mysql.grant_exists(
        grant="ALL PRIVILEGES",
        database="salt.*",
        user="george",
        host="%",
    )
    assert not ret

    # Remove the user
    ret = mysql.user_remove("george", host="%")
    assert ret

    # Remove the database
    ret = mysql.db_remove("salt")
    assert ret


def test_create_alter_password_hash(mysql):
    # Create the database
    ret = mysql.db_create("salt")
    assert ret

    # Create a user
    ret = mysql.user_create(
        "george",
        host="%",
        password_hash="*2470C0C06DEE42FD1618BB99005ADCA2EC9D1E19",
    )
    assert ret

    # Grant privileges to user to specific table
    ret = mysql.grant_add(
        grant="ALL PRIVILEGES",
        database="salt.*",
        user="george",
        host="%",
    )
    assert ret

    # Check the grant exists
    ret = mysql.grant_exists(
        grant="ALL PRIVILEGES",
        database="salt.*",
        user="george",
        host="%",
    )
    assert ret

    # Check we can query as the new user
    ret = mysql.query(
        database="salt",
        query="SELECT 1",
        connection_user="george",
        connection_pass="password",
        connection_db="salt",
    )
    assert ret

    # Change the user password
    ret = mysql.user_chpass(
        "george",
        host="%",
        password_hash="*F4A5147613F01DEC0C5226BF24CD1D5762E6AAF2",
    )
    assert ret

    # Check we can query with the new password
    ret = mysql.query(
        database="salt",
        query="SELECT 1",
        connection_user="george",
        connection_pass="badpassword",
        connection_db="salt",
    )
    assert ret

    # Revoke the grant
    ret = mysql.grant_revoke(
        grant="ALL PRIVILEGES",
        database="salt.*",
        user="george",
        host="%",
    )
    assert ret

    # Check the grant does not exist
    ret = mysql.grant_exists(
        grant="ALL PRIVILEGES",
        database="salt.*",
        user="george",
        host="%",
    )
    assert not ret

    # Remove the user
    ret = mysql.user_remove("george", host="%")
    assert ret

    # Remove the database
    ret = mysql.db_remove("salt")
    assert ret
