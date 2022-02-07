"""
Test Salt MySQL state module across various MySQL variants
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
def salt_cli_wrapper(salt_minion, salt_cli, mysql_container):
    def run_command(*command, **kwargs):
        return salt_cli.run(
            *command,
            minion_tgt=salt_minion.id,
            connection_user=mysql_container.mysql_user,
            connection_pass=mysql_container.mysql_passwd,
            connection_db="mysql",
            connection_port=mysql_container.mysql_port,
            **kwargs
        )

    return run_command


@pytest.fixture(scope="module")
def salt_call_cli_wrapper(salt_call_cli, mysql_container):
    def run_command(*command, **kwargs):
        return salt_call_cli.run(
            *command,
            connection_user=mysql_container.mysql_user,
            connection_pass=mysql_container.mysql_passwd,
            connection_db="mysql",
            connection_port=mysql_container.mysql_port,
            **kwargs
        )

    return run_command


def test_database_present_absent(salt_cli_wrapper):
    ret = salt_cli_wrapper(
        "state.single",
        "mysql_database.present",
        name="test_database",
    )
    state = ret.json["mysql_database_|-test_database_|-test_database_|-present"]
    assert ret.exitcode == 0, ret

    assert "changes" in state
    assert state["changes"] == {"test_database": "Present"}

    assert "comment" in state
    assert state["comment"] == "The database test_database has been created"

    ret = salt_cli_wrapper(
        "state.single",
        "mysql_database.absent",
        name="test_database",
    )
    state = ret.json["mysql_database_|-test_database_|-test_database_|-absent"]

    assert ret.exitcode == 0, ret

    assert "changes" in state
    assert state["changes"] == {"test_database": "Absent"}

    assert "comment" in state
    assert state["comment"] == "Database test_database has been removed"


def test_grants_present_absent(salt_cli_wrapper, salt_call_cli_wrapper):

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

    ret = salt_cli_wrapper(
        "state.single",
        "mysql_grants.present",
        name="add_salt_grants",
        grant="select,insert,update",
        database="salt.*",
        user="george",
        host="localhost",
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

    ret = salt_cli_wrapper(
        "state.single",
        "mysql_grants.absent",
        name="delete_salt_grants",
        grant="select,insert,update",
        database="salt.*",
        user="george",
        host="localhost",
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
    ret = salt_call_cli_wrapper("mysql.user_remove", "george", host="localhost")
    assert ret.json

    # Remove the database
    ret = salt_call_cli_wrapper("mysql.db_remove", "salt")
    assert ret.json


def test_user_present_absent(salt_cli_wrapper):

    ret = salt_cli_wrapper(
        "state.single",
        "mysql_user.present",
        name="george",
        host="localhost",
        password="password",
    )
    state = ret.json["mysql_user_|-george_|-george_|-present"]
    assert ret.exitcode == 0, ret

    assert "changes" in state
    assert state["changes"] == {"george": "Present"}

    assert "comment" in state
    assert state["comment"] == "The user george@localhost has been added"

    ret = salt_cli_wrapper(
        "state.single",
        "mysql_user.absent",
        name="george",
        host="localhost",
    )
    state = ret.json["mysql_user_|-george_|-george_|-absent"]
    assert ret.exitcode == 0, ret

    assert "changes" in state
    assert state["changes"] == {"george": "Absent"}

    assert "comment" in state
    assert state["comment"] == "User george@localhost has been removed"


def test_user_present_absent_passwordless(salt_cli_wrapper):

    ret = salt_cli_wrapper(
        "state.single",
        "mysql_user.present",
        name="george",
        host="localhost",
        allow_passwordless=True,
    )
    state = ret.json["mysql_user_|-george_|-george_|-present"]
    assert ret.exitcode == 0, ret

    assert "changes" in state
    assert state["changes"] == {"george": "Present"}

    assert "comment" in state
    log.debug("=== comment %s ===", state["comment"])
    assert (
        state["comment"]
        == "The user george@localhost has been added with passwordless login"
    )

    ret = salt_cli_wrapper(
        "state.single",
        "mysql_user.absent",
        name="george",
        host="localhost",
    )
    state = ret.json["mysql_user_|-george_|-george_|-absent"]
    assert ret.exitcode == 0, ret

    assert "changes" in state
    assert state["changes"] == {"george": "Absent"}

    assert "comment" in state
    assert state["comment"] == "User george@localhost has been removed"


def test_user_present_absent_unixsocket(salt_cli_wrapper, mysql_container):

    # The auth_socket plugin on MariaDB is unavailable
    # on versions 10.1 - 10.3
    if "mariadb" in mysql_container.mysql_name:
        if mysql_container.mysql_version in ("10.1", "10.2", "10.3"):
            pytest.skip(
                "The auth_socket plugin is unavaiable "
                "for the {}:{} docker image.".format(
                    mysql_container.mysql_name, mysql_container.mysql_version
                )
            )

    # enable the auth_socket plugin on MySQL
    # already enabled on MariaDB > 10.3
    if "mariadb" not in mysql_container.mysql_name:
        ret = salt_cli_wrapper("mysql.plugin_add", "auth_socket")
        assert ret.json

    ret = salt_cli_wrapper(
        "state.single",
        "mysql_user.present",
        name="george",
        host="localhost",
        unix_socket=True,
        allow_passwordless=False,
    )
    state = ret.json["mysql_user_|-george_|-george_|-present"]
    assert ret.exitcode == 0, ret

    assert "changes" in state
    assert state["changes"] == {"george": "Present"}

    assert "comment" in state
    assert (
        state["comment"] == "The user george@localhost has been added using unix_socket"
    )

    ret = salt_cli_wrapper(
        "state.single",
        "mysql_user.absent",
        name="george",
        host="localhost",
    )
    state = ret.json["mysql_user_|-george_|-george_|-absent"]
    assert ret.exitcode == 0, ret

    assert "changes" in state
    assert state["changes"] == {"george": "Absent"}

    assert "comment" in state
    assert state["comment"] == "User george@localhost has been removed"

    if "mariadb" not in mysql_container.mysql_name:
        ret = salt_cli_wrapper("mysql.plugin_remove", "auth_socket")
        assert ret.json
