"""
Test Salt MySQL state module across various MySQL variants
"""
import logging

import pytest
import salt.modules.mysql as mysqlmod
from saltfactories.utils.functional import StateResult
from tests.support.pytest.mysql import *  # pylint: disable=wildcard-import,unused-wildcard-import

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("dockerd"),
    pytest.mark.skipif(
        mysqlmod.MySQLdb is None, reason="No python mysql client installed."
    ),
]


class CallWrapper:
    def __init__(self, func, container):
        self.func = func
        self.container = container

    def __call__(self, *args, **kwargs):
        kwargs.update(self.container.get_credentials(**kwargs))
        return self.func(*args, **kwargs)


class StateSingleWrapper:
    def __init__(self, func, container):
        self.func = func
        self.container = container

    def __call__(self, statefunc, *args, **kwargs):
        if statefunc.startswith("mysql_"):
            kwargs.update(self.container.get_credentials(**kwargs))
        ret = self.func(statefunc, *args, **kwargs)
        if isinstance(ret, StateResult):
            # Sadly, because we're wrapping, we need to return the raw
            # attribute for a StateResult class to be recreated.
            return ret.raw
        return ret


@pytest.fixture(scope="module")
def mysql(modules, mysql_container):
    for name in list(modules):
        if name.startswith("mysql."):
            modules._dict[name] = CallWrapper(
                modules._dict[name],
                mysql_container,
            )
        if name == "state.single":
            modules._dict[name] = StateSingleWrapper(
                modules._dict[name],
                mysql_container,
            )
    return modules.mysql


@pytest.fixture(scope="module")
def mysql_states(mysql, states, mysql_container):
    # Just so we also have the container running
    return states


@pytest.fixture(scope="module")
def mysql_user(mysql_states):
    return mysql_states.mysql_user


@pytest.fixture(scope="module")
def mysql_query(mysql_states):
    return mysql_states.mysql_query


@pytest.fixture(scope="module")
def mysql_grants(mysql_states):
    return mysql_states.mysql_grants


@pytest.fixture(scope="module")
def mysql_database(mysql_states):
    return mysql_states.mysql_database


def test_database_present_absent(mysql_database):
    ret = mysql_database.present(name="test_database")
    assert ret.changes
    assert ret.changes == {"test_database": "Present"}
    assert ret.comment
    assert ret.comment == "The database test_database has been created"

    ret = mysql_database.absent(name="test_database")
    assert ret.changes
    assert ret.changes == {"test_database": "Absent"}
    assert ret.comment
    assert ret.comment == "Database test_database has been removed"


def test_grants_present_absent(mysql, mysql_grants):

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

    try:

        ret = mysql_grants.present(
            name="add_salt_grants",
            grant="select,insert,update",
            database="salt.*",
            user="george",
            host="localhost",
        )
        assert ret.changes
        assert ret.changes == {"add_salt_grants": "Present"}
        assert ret.comment
        assert (
            ret.comment
            == "Grant select,insert,update on salt.* to george@localhost has been added"
        )

        ret = mysql_grants.absent(
            name="delete_salt_grants",
            grant="select,insert,update",
            database="salt.*",
            user="george",
            host="localhost",
        )
        assert ret.changes
        assert ret.changes == {"delete_salt_grants": "Absent"}
        assert ret.comment
        assert (
            ret.comment
            == "Grant select,insert,update on salt.* for george@localhost has been revoked"
        )

    finally:
        # Remove the user
        ret = mysql.user_remove("george", host="localhost")
        assert ret

        # Remove the database
        ret = mysql.db_remove("salt")
        assert ret


def test_user_present_absent(mysql_user):

    ret = mysql_user.present(
        name="george",
        host="localhost",
        password="password",
    )
    assert ret.changes
    assert ret.changes == {"george": "Present"}
    assert ret.comment
    assert ret.comment == "The user george@localhost has been added"

    ret = mysql_user.absent(
        name="george",
        host="localhost",
    )
    assert ret.changes
    assert ret.changes == {"george": "Absent"}
    assert ret.comment
    assert ret.comment == "User george@localhost has been removed"


def test_user_present_absent_passwordless(mysql_user):

    ret = mysql_user.present(
        name="george",
        host="localhost",
        allow_passwordless=True,
    )
    assert ret.changes
    assert ret.changes == {"george": "Present"}
    assert ret.comment
    assert (
        ret.comment
        == "The user george@localhost has been added with passwordless login"
    )

    ret = mysql_user.absent(
        name="george",
        host="localhost",
    )
    assert ret.changes
    assert ret.changes == {"george": "Absent"}
    assert ret.comment
    assert ret.comment == "User george@localhost has been removed"


def test_user_present_absent_unixsocket(mysql, mysql_user, mysql_container):

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
    try:
        if "mariadb" not in mysql_container.mysql_name:
            ret = mysql.plugin_add("auth_socket")
            assert ret

        ret = mysql_user.present(
            name="george",
            host="localhost",
            unix_socket=True,
            allow_passwordless=False,
        )
        assert ret.changes
        assert ret.changes == {"george": "Present"}
        assert ret.comment
        assert (
            ret.comment == "The user george@localhost has been added using unix_socket"
        )

        ret = mysql_user.absent(
            name="george",
            host="localhost",
        )
        assert ret.changes
        assert ret.changes == {"george": "Absent"}
        assert ret.comment
        assert ret.comment == "User george@localhost has been removed"
    finally:
        if "mariadb" not in mysql_container.mysql_name:
            ret = mysql.plugin_remove("auth_socket")
            assert ret
