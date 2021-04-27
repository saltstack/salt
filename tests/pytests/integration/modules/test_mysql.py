"""
    tests.integration.modules.test_mysql
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test Salt MySQL module across various MySQL variants
"""
import logging
import os
import time

import attr
import pytest

docker = pytest.importorskip("docker")

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.skip_if_binaries_missing("dockerd"),
]


@attr.s(kw_only=True, slots=True)
class MySQLImage:
    name = attr.ib()
    tag = attr.ib()
    container_id = attr.ib()


@attr.s(kw_only=True, slots=True)
class MySQLCombo:
    mysql_name = attr.ib()
    mysql_version = attr.ib()
    mysql_port = attr.ib()
    mysql_user = attr.ib()
    mysql_passwd = attr.ib()


def _get_test_versions():
    test_versions = []
    name = "mysql/mysql-server"
    for version in ("5.5", "5.6", "5.7", "8.0"):
        test_versions.append(
            MySQLImage(name=name, tag=version, container_id="mysql-{}".format(version))
        )
    name = "mariadb"
    for version in ("10.1", "10.2", "10.3", "10.4", "10.5"):
        test_versions.append(
            MySQLImage(
                name=name, tag=version, container_id="mariadb-{}".format(version)
            )
        )
    name = "percona"
    for version in ("5.5", "5.6", "5.7", "8.0"):
        test_versions.append(
            MySQLImage(
                name=name, tag=version, container_id="percona-{}".format(version)
            )
        )
    return test_versions


def mysql_container_id(value):
    return "{}".format(value.container_id)


@pytest.fixture(
    scope="module", autouse=True, params=_get_test_versions(), ids=mysql_container_id,
)
def mysql_container(request, salt_call_cli, mysql_port):
    mysql_image = request.param
    mysql_name = mysql_image.name
    mysql_version = mysql_image.tag
    mysql_container_name = mysql_image.container_id

    mysql_user = "root"
    mysql_passwd = "password"

    container_started = False
    try:
        ret = salt_call_cli.run(
            "state.single", "docker_image.present", name=mysql_name, tag=mysql_version
        )
        assert ret.exitcode == 0
        assert ret.json
        state_run = next(iter(ret.json.values()))
        assert state_run["result"] is True

        container_started = True
        attempts = 0
        env = os.environ.copy()
        while attempts < 5:
            attempts += 1
            ret = salt_call_cli.run(
                "state.single",
                "docker_container.running",
                name=mysql_container_name,
                image="{}:{}".format(mysql_name, mysql_version),
                port_bindings="{}:3306".format(mysql_port),
                environment={
                    "MYSQL_ROOT_PASSWORD": mysql_passwd,
                    "MYSQL_ROOT_HOST": "%",
                },
            )
            assert ret.exitcode == 0
            assert ret.json
            state_run = next(iter(ret.json.values()))
            assert state_run["result"] is True

            time.sleep(1)

            # Make sure "MYSQL" is ready
            ret = salt_call_cli.run(
                "docker.run",
                name=mysql_container_name,
                cmd="mysql --user=root --password=password -e 'SELECT 1'",
            )
            if ret.exitcode == 0:
                break

            time.sleep(2)
        else:
            pytest.fail("Failed to login to mysql")

        yield MySQLCombo(
            mysql_name=mysql_name,
            mysql_version=mysql_version,
            mysql_port=mysql_port,
            mysql_user=mysql_user,
            mysql_passwd=mysql_passwd,
        )
    finally:
        if container_started:
            ret = salt_call_cli.run(
                "state.single", "docker_container.stopped", name=mysql_container_name
            )
            assert ret.exitcode == 0
            assert ret.json
            state_run = next(iter(ret.json.values()))
            assert state_run["result"] is True
            ret = salt_call_cli.run(
                "state.single", "docker_container.absent", name=mysql_container_name
            )
            assert ret.exitcode == 0
            assert ret.json
            state_run = next(iter(ret.json.values()))
            assert state_run["result"] is True


@pytest.mark.slow_test
def test_query(salt_call_cli, mysql_container):
    ret = salt_call_cli.run(
        "mysql.query",
        "mysql",
        "SELECT 1",
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
    )

    assert ret.json
    assert ret.json["results"] == [["1"]]


@pytest.mark.slow_test
def test_version(salt_call_cli, mysql_container):
    ret = salt_call_cli.run(
        "mysql.version",
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
    )

    assert ret.json
    assert mysql_container.mysql_version in ret.json


@pytest.mark.slow_test
def test_status(salt_call_cli, mysql_container):
    ret = salt_call_cli.run(
        "mysql.status",
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
    )

    assert ret.json


@pytest.mark.slow_test
def test_db_list(salt_call_cli, mysql_container):
    ret = salt_call_cli.run(
        "mysql.db_list",
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
    )

    assert ret.json
    assert "mysql" in ret.json


@pytest.mark.slow_test
def test_db_create_alter_remove(salt_call_cli, mysql_container):
    ret = salt_call_cli.run(
        "mysql.db_create",
        "salt",
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
    )
    assert ret.json

    ret = salt_call_cli.run(
        "mysql.alter_db",
        name="salt",
        character_set="latin1",
        collate="latin1_general_ci",
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
    )
    assert ret.json

    ret = salt_call_cli.run(
        "mysql.db_remove",
        name="salt",
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
    )
    assert ret.json


@pytest.mark.slow_test
def test_user_list(salt_call_cli, mysql_container):
    ret = salt_call_cli.run(
        "mysql.user_list",
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
    )

    assert ret.json
    assert {"User": "root", "Host": "%"} in ret.json


@pytest.mark.slow_test
def test_user_exists(salt_call_cli, mysql_container):
    ret = salt_call_cli.run(
        "mysql.user_exists",
        "root",
        "%",
        "password",
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
    )
    assert ret.json

    ret = salt_call_cli.run(
        "mysql.user_exists",
        "george",
        "hostname",
        "badpassword",
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
    )
    assert not ret.json


@pytest.mark.slow_test
def test_user_info(salt_call_cli, mysql_container):
    ret = salt_call_cli.run(
        "mysql.user_info",
        "root",
        "%",
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
    )
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


@pytest.mark.slow_test
def test_user_create_chpass_delete(salt_call_cli, mysql_container):
    ret = salt_call_cli.run(
        "mysql.user_create",
        "george",
        host="localhost",
        password="badpassword",
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
    )
    assert ret.json

    ret = salt_call_cli.run(
        "mysql.user_chpass",
        "george",
        host="localhost",
        password="different_password",
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
    )
    assert ret.json

    ret = salt_call_cli.run(
        "mysql.user_remove",
        "george",
        host="localhost",
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
    )
    assert ret.json


@pytest.mark.slow_test
def test_user_grants(salt_call_cli, mysql_container):
    ret = salt_call_cli.run(
        "mysql.user_grants",
        "root",
        host="%",
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
    )
    assert ret.json


@pytest.mark.slow_test
def test_grant_add_revoke(salt_call_cli, mysql_container):
    # Create the database
    ret = salt_call_cli.run(
        "mysql.db_create",
        "salt",
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
    )
    assert ret.json

    # Create a user
    ret = salt_call_cli.run(
        "mysql.user_create",
        "george",
        host="localhost",
        password="badpassword",
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
    )
    assert ret.json

    # Grant privileges to user to specific table
    ret = salt_call_cli.run(
        "mysql.grant_add",
        grant="ALL PRIVILEGES",
        database="salt.*",
        user="george",
        host="localhost",
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
    )
    assert ret.json

    # Check the grant exists
    ret = salt_call_cli.run(
        "mysql.grant_exists",
        grant="ALL PRIVILEGES",
        database="salt.*",
        user="george",
        host="localhost",
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
    )
    assert ret.json

    # Revoke the grant
    ret = salt_call_cli.run(
        "mysql.grant_revoke",
        grant="ALL PRIVILEGES",
        database="salt.*",
        user="george",
        host="localhost",
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
    )
    assert ret.json

    # Check the grant does not exist
    ret = salt_call_cli.run(
        "mysql.grant_exists",
        grant="ALL PRIVILEGES",
        database="salt.*",
        user="george",
        host="localhost",
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
    )
    assert not ret.json

    # Grant privileges to user globally
    ret = salt_call_cli.run(
        "mysql.grant_add",
        grant="ALL PRIVILEGES",
        database="*.*",
        user="george",
        host="localhost",
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
    )
    assert ret.json

    # Check the global exists
    ret = salt_call_cli.run(
        "mysql.grant_exists",
        grant="ALL PRIVILEGES",
        database="*.*",
        user="george",
        host="localhost",
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
    )
    assert ret.json

    # Revoke the global grant
    ret = salt_call_cli.run(
        "mysql.grant_revoke",
        grant="ALL PRIVILEGES",
        database="*.*",
        user="george",
        host="localhost",
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
    )
    assert ret.json

    # Check the grant does not exist
    ret = salt_call_cli.run(
        "mysql.grant_exists",
        grant="ALL PRIVILEGES",
        database="salt.*",
        user="george",
        host="localhost",
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
    )
    assert not ret.json

    # Remove the user
    ret = salt_call_cli.run(
        "mysql.user_remove",
        "george",
        host="localhost",
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
    )
    assert ret.json

    # Remove the database
    ret = salt_call_cli.run(
        "mysql.db_remove",
        "salt",
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
    )
    assert ret.json


@pytest.mark.slow_test
def test_plugin_add_status_remove(salt_call_cli, mysql_container):

    if "mariadb" in mysql_container.mysql_name:
        plugin = "simple_password_check"
    else:
        plugin = "auth_socket"

    ret = salt_call_cli.run(
        "mysql.plugin_status",
        plugin,
        host="%",
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
    )
    assert not ret.json

    ret = salt_call_cli.run(
        "mysql.plugin_add",
        plugin,
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
    )
    assert ret.json

    ret = salt_call_cli.run(
        "mysql.plugin_status",
        plugin,
        host="%",
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
    )
    assert ret.json
    assert "ACTIVE" == ret.json

    ret = salt_call_cli.run(
        "mysql.plugin_remove",
        plugin,
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
    )
    assert ret.json

    ret = salt_call_cli.run(
        "mysql.plugin_status",
        plugin,
        host="%",
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
    )
    assert not ret.json


@pytest.mark.slow_test
def test_plugin_list(salt_call_cli, mysql_container):
    if "mariadb" in mysql_container.mysql_name:
        plugin = "simple_password_check"
    else:
        plugin = "auth_socket"

    ret = salt_call_cli.run(
        "mysql.plugins_list",
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
    )
    assert {"name": plugin, "status": "ACTIVE"} not in ret.json
    assert ret.json

    ret = salt_call_cli.run(
        "mysql.plugin_add",
        plugin,
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
    )
    assert ret.json

    ret = salt_call_cli.run(
        "mysql.plugins_list",
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
    )
    assert ret.json
    assert {"name": plugin, "status": "ACTIVE"} in ret.json

    ret = salt_call_cli.run(
        "mysql.plugin_remove",
        plugin,
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
    )
    assert ret.json
