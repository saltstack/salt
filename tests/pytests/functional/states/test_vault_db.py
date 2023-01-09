import pytest
from saltfactories.utils import random_string

# pylint: disable=unused-import
from tests.support.pytest.mysql import (
    MySQLImage,
    create_mysql_combo,
    mysql_combo,
    mysql_container,
)

# pylint: disable=unused-import
from tests.support.pytest.vault import (
    vault_container_version,
    vault_delete,
    vault_disable_secret_engine,
    vault_enable_secret_engine,
    vault_environ,
    vault_list,
    vault_read,
    vault_revoke,
    vault_write,
)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("dockerd", "vault", "getent"),
    pytest.mark.usefixtures("vault_container_version"),
    pytest.mark.parametrize("vault_container_version", ["latest"], indirect=True),
]


@pytest.fixture(scope="module")
def minion_config_overrides(vault_port):
    return {
        "vault": {
            "auth": {
                "method": "token",
                "token": "testsecret",
            },
            "server": {
                "url": f"http://127.0.0.1:{vault_port}",
            },
        }
    }


@pytest.fixture(scope="module")
def mysql_image(request):
    version = "10.3"
    return MySQLImage(
        name="mariadb",
        tag=version,
        container_id=random_string(f"mariadb-{version}-"),
    )


@pytest.fixture
def role_args_common():
    return {
        "db_name": "testdb",
        "creation_statements": r"CREATE USER '{{name}}'@'%' IDENTIFIED BY '{{password}}';GRANT SELECT ON *.* TO '{{name}}'@'%';",
    }


@pytest.fixture
def testrole():
    return {
        "default_ttl": 3600,
        "max_ttl": 86400,
    }


@pytest.fixture
def teststaticrole(mysql_container):
    return {
        "db_name": "testdb",
        "rotation_period": 86400,
        "username": mysql_container.mysql_user,
    }


@pytest.fixture
def testdb(mysql_container):
    # This uses the default IP address of the host on the default network
    # (hardcoded) because I could not get hostname resolution working properly.
    return {
        "plugin_name": "mysql-database-plugin",
        "connection_url": f"{{{{username}}}}:{{{{password}}}}@tcp(172.17.0.1:{mysql_container.mysql_port})/",
        "allowed_roles": "testrole,teststaticrole",
        "username": "root",
        "password": mysql_container.mysql_passwd,
    }


@pytest.fixture(scope="module")
def db_engine(vault_container_version):
    assert vault_enable_secret_engine("database")
    yield
    assert vault_disable_secret_engine("database")


@pytest.fixture
def connection_setup(vault_container_version, testdb, db_engine):
    try:
        vault_write("database/config/testdb", **testdb)
        assert "testdb" in vault_list("database/config")
        yield
    finally:
        # prevent dangling leases, which prevent disabling the secret engine
        assert vault_revoke("database/creds", prefix=True)
        if "testdb" in vault_list("database/config"):
            vault_delete("database/config/testdb")
            assert "testdb" not in vault_list("database/config")


@pytest.fixture(params=[["testrole"]])
def roles_setup(connection_setup, request, role_args_common):
    try:
        for role_name in request.param:
            role_args = request.getfixturevalue(role_name)
            role_args.update(role_args_common)
            vault_write(f"database/roles/{role_name}", **role_args)
            assert role_name in vault_list("database/roles")
        yield
    finally:
        for role_name in request.param:
            if role_name in vault_list("database/roles"):
                vault_delete(f"database/roles/{role_name}")
                assert role_name not in vault_list("database/roles")


@pytest.fixture
def role_static_setup(connection_setup, teststaticrole):
    role_name = "teststaticrole"
    try:
        vault_write(f"database/static-roles/{role_name}", **teststaticrole)
        assert role_name in vault_list("database/static-roles")
        yield
    finally:
        if role_name in vault_list("database/static-roles"):
            vault_delete(f"database/static-roles/{role_name}")
            assert role_name not in vault_list("database/static-roles")


@pytest.fixture
def vault_db(states, db_engine):
    try:
        yield states.vault_db
    finally:
        # prevent dangling leases, which prevent disabling the secret engine
        assert vault_revoke("database/creds", prefix=True)
        if "testdb" in vault_list("database/config"):
            vault_delete("database/config/testdb")
            assert "testdb" not in vault_list("database/config")
        if "testrole" in vault_list("database/roles"):
            vault_delete("database/roles/testrole")
            assert "testrole" not in vault_list("database/roles")
        if "teststaticrole" in vault_list("database/static-roles"):
            vault_delete("database/static-roles/teststaticrole")
            assert "teststaticrole" not in vault_list("database/static-roles")


@pytest.fixture
def connargs(mysql_container):
    return {
        "plugin": "mysql",
        "connection_url": f"{{{{username}}}}:{{{{password}}}}@tcp(172.17.0.1:{mysql_container.mysql_port})/",
        "allowed_roles": ["testrole", "teststaticrole"],
        "username": "root",
        "password": mysql_container.mysql_passwd,
        "rotate": False,
    }


@pytest.fixture
def roleargs():
    return {
        "connection": "testdb",
        "creation_statements": r"CREATE USER '{{name}}'@'%' IDENTIFIED BY '{{password}}';GRANT SELECT ON *.* TO '{{name}}'@'%';",
    }


@pytest.fixture
def roleargs_static(mysql_container):
    return {
        "connection": "testdb",
        "username": mysql_container.mysql_user,
        "rotation_period": 86400,
    }


def test_connection_present(vault_db, connargs):
    ret = vault_db.connection_present("testdb", **connargs)
    assert ret.result
    assert ret.changes
    assert "created" in ret.changes
    assert ret.changes["created"] == "testdb"
    assert "testdb" in vault_list("database/config")


@pytest.mark.usefixtures("connection_setup")
def test_connection_present_no_changes(vault_db, connargs):
    ret = vault_db.connection_present("testdb", **connargs)
    assert ret.result
    assert not ret.changes


@pytest.mark.usefixtures("connection_setup")
def test_connection_present_allowed_roles_change(vault_db, connargs):
    connargs["allowed_roles"] = ["testrole", "teststaticrole", "newrole"]
    ret = vault_db.connection_present("testdb", **connargs)
    assert ret.result
    assert ret.changes
    assert "allowed_roles" in ret.changes
    assert (
        vault_read("database/config/testdb")["data"]["allowed_roles"]
        == connargs["allowed_roles"]
    )


@pytest.mark.usefixtures("connection_setup")
def test_connection_present_new_param(vault_db, connargs):
    connargs["username_template"] = r"{{random 20}}"
    ret = vault_db.connection_present("testdb", **connargs)
    assert ret.result
    assert ret.changes
    assert "username_template" in ret.changes
    assert (
        vault_read("database/config/testdb")["data"]["connection_details"][
            "username_template"
        ]
        == connargs["username_template"]
    )


def test_connection_present_test_mode(vault_db, connargs):
    ret = vault_db.connection_present("testdb", test=True, **connargs)
    assert ret.result is None
    assert ret.changes
    assert "created" in ret.changes
    assert ret.changes["created"] == "testdb"
    assert "testdb" not in vault_list("database/config")


@pytest.mark.usefixtures("connection_setup")
def test_connection_absent(vault_db, connargs):
    ret = vault_db.connection_absent("testdb")
    assert ret.result
    assert ret.changes
    assert "deleted" in ret.changes
    assert ret.changes["deleted"] == "testdb"
    assert "testdb" not in vault_list("database/config")


def test_connection_absent_no_changes(vault_db, connargs):
    ret = vault_db.connection_absent("testdb")
    assert ret.result
    assert not ret.changes


@pytest.mark.usefixtures("connection_setup")
def test_connection_absent_test_mode(vault_db, connargs):
    ret = vault_db.connection_absent("testdb", test=True)
    assert ret.result is None
    assert ret.changes
    assert "deleted" in ret.changes
    assert ret.changes["deleted"] == "testdb"
    assert "testdb" in vault_list("database/config")


@pytest.mark.usefixtures("connection_setup")
def test_role_present(vault_db, roleargs):
    ret = vault_db.role_present("testrole", **roleargs)
    assert ret.result
    assert ret.changes
    assert "created" in ret.changes
    assert ret.changes["created"] == "testrole"
    assert "testrole" in vault_list("database/roles")


@pytest.mark.usefixtures("roles_setup")
def test_role_present_no_changes(vault_db, roleargs):
    ret = vault_db.role_present("testrole", **roleargs)
    assert ret.result
    assert not ret.changes


@pytest.mark.usefixtures("roles_setup")
def test_role_present_no_changes_with_time_string(vault_db, roleargs):
    roleargs["default_ttl"] = "1h"
    ret = vault_db.role_present("testrole", **roleargs)
    assert ret.result
    assert not ret.changes


@pytest.mark.usefixtures("roles_setup")
def test_role_present_param_change(vault_db, roleargs):
    roleargs["default_ttl"] = 1337
    ret = vault_db.role_present("testrole", **roleargs)
    assert ret.result
    assert ret.changes
    assert "default_ttl" in ret.changes
    assert vault_read("database/roles/testrole")["data"]["default_ttl"] == 1337


@pytest.mark.usefixtures("connection_setup")
def test_role_present_test_mode(vault_db, roleargs):
    ret = vault_db.role_present("testrole", test=True, **roleargs)
    assert ret.result is None
    assert ret.changes
    assert "created" in ret.changes
    assert ret.changes["created"] == "testrole"
    assert "testrole" not in vault_list("database/roles")


@pytest.mark.usefixtures("connection_setup")
def test_static_role_present(vault_db, roleargs_static):
    ret = vault_db.static_role_present("teststaticrole", **roleargs_static)
    assert ret.result
    assert ret.changes
    assert "created" in ret.changes
    assert ret.changes["created"] == "teststaticrole"
    assert "teststaticrole" in vault_list("database/static-roles")


@pytest.mark.usefixtures("role_static_setup")
def test_static_role_present_no_changes(vault_db, roleargs_static):
    ret = vault_db.static_role_present("teststaticrole", **roleargs_static)
    assert ret.result
    assert not ret.changes


@pytest.mark.usefixtures("role_static_setup")
def test_static_role_present_param_change(vault_db, roleargs_static):
    roleargs_static["rotation_period"] = 1337
    ret = vault_db.static_role_present("teststaticrole", **roleargs_static)
    assert ret.result
    assert ret.changes
    assert "rotation_period" in ret.changes
    assert (
        vault_read("database/static-roles/teststaticrole")["data"]["rotation_period"]
        == 1337
    )


@pytest.mark.usefixtures("connection_setup")
def test_static_role_present_test_mode(vault_db, roleargs_static):
    ret = vault_db.static_role_present("teststaticrole", test=True, **roleargs_static)
    assert ret.result is None
    assert ret.changes
    assert "created" in ret.changes
    assert ret.changes["created"] == "teststaticrole"
    assert "teststaticrole" not in vault_list("database/static-roles")


@pytest.mark.usefixtures("roles_setup")
def test_role_absent(vault_db):
    ret = vault_db.role_absent("testrole")
    assert ret.result
    assert ret.changes
    assert "deleted" in ret.changes
    assert ret.changes["deleted"] == "testrole"
    assert "testrole" not in vault_list("database/roles")


@pytest.mark.usefixtures("role_static_setup")
def test_role_absent_static(vault_db):
    ret = vault_db.role_absent("teststaticrole", static=True)
    assert ret.result
    assert ret.changes
    assert "deleted" in ret.changes
    assert ret.changes["deleted"] == "teststaticrole"
    assert "teststaticrole" not in vault_list("database/static-roles")


def test_role_absent_no_changes(vault_db):
    ret = vault_db.role_absent("testrole")
    assert ret.result
    assert not ret.changes


@pytest.mark.usefixtures("roles_setup")
def test_role_absent_test_mode(vault_db):
    ret = vault_db.role_absent("testrole", test=True)
    assert ret.result is None
    assert ret.changes
    assert "deleted" in ret.changes
    assert ret.changes["deleted"] == "testrole"
    assert "testrole" in vault_list("database/roles")
