"""
    tests.integration.statues.test_mysql
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test Salt MySQL state module across various MySQL variants
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
def test_database_present_absent(salt_cli, mysql_container, salt_minion):
    ret = salt_cli.run(
        "state.single",
        "mysql_database.present",
        name="test_database",
        minion_tgt=salt_minion.id,
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
    )
    state = ret.json["mysql_database_|-test_database_|-test_database_|-present"]
    assert ret.exitcode == 0, ret

    assert "changes" in state
    assert state["changes"] == {"test_database": "Present"}

    assert "comment" in state
    assert state["comment"] == "The database test_database has been created"

    ret = salt_cli.run(
        "state.single",
        "mysql_database.absent",
        name="test_database",
        minion_tgt=salt_minion.id,
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
    )
    state = ret.json["mysql_database_|-test_database_|-test_database_|-absent"]

    assert ret.exitcode == 0, ret

    assert "changes" in state
    assert state["changes"] == {"test_database": "Absent"}

    assert "comment" in state
    assert state["comment"] == "Database test_database has been removed"


@pytest.mark.slow_test
def test_grants_present_absent(salt_cli, salt_call_cli, mysql_container, salt_minion):

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

    ret = salt_cli.run(
        "state.single",
        "mysql_grants.present",
        name="add_salt_grants",
        grant="select,insert,update",
        database="salt.*",
        user="george",
        host="localhost",
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
        minion_tgt=salt_minion.id,
    )
    state = ret.json["mysql_grants_|-add_salt_grants_|-add_salt_grants_|-present"]
    assert ret.exitcode == 0, ret

    assert "changes" in state
    assert state["changes"] == {"add_salt_grants": "Present"}

    assert "comment" in state
    assert (
        state["comment"]
        == "Grant select,insert,update on salt.* to george@localhost has been added"
    )

    ret = salt_cli.run(
        "state.single",
        "mysql_grants.absent",
        name="delete_salt_grants",
        grant="select,insert,update",
        database="salt.*",
        user="george",
        host="localhost",
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
        minion_tgt=salt_minion.id,
    )
    state = ret.json["mysql_grants_|-delete_salt_grants_|-delete_salt_grants_|-absent"]
    assert ret.exitcode == 0, ret

    assert "changes" in state
    assert state["changes"] == {"delete_salt_grants": "Absent"}

    assert "comment" in state
    assert (
        state["comment"]
        == "Grant select,insert,update on salt.* for george@localhost has been revoked"
    )

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
def test_user_present_absent(salt_cli, salt_call_cli, mysql_container, salt_minion):

    ret = salt_cli.run(
        "state.single",
        "mysql_user.present",
        name="george",
        host="localhost",
        password="password",
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
        minion_tgt=salt_minion.id,
    )
    state = ret.json["mysql_user_|-george_|-george_|-present"]
    assert ret.exitcode == 0, ret

    assert "changes" in state
    assert state["changes"] == {"george": "Present"}

    assert "comment" in state
    assert state["comment"] == "The user george@localhost has been added"

    ret = salt_cli.run(
        "state.single",
        "mysql_user.absent",
        name="george",
        host="localhost",
        connection_user=mysql_container.mysql_user,
        connection_pass=mysql_container.mysql_passwd,
        connection_db="mysql",
        connection_port=mysql_container.mysql_port,
        minion_tgt=salt_minion.id,
    )
    state = ret.json["mysql_user_|-george_|-george_|-absent"]
    assert ret.exitcode == 0, ret

    assert "changes" in state
    assert state["changes"] == {"george": "Absent"}

    assert "comment" in state
    assert state["comment"] == "User george@localhost has been removed"
