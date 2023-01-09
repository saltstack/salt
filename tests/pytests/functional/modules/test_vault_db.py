import time

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
            "cache": {
                "backend": "disk",  # ensure a persistent cache is available for get_creds
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
def testreissuerole():
    return {
        "default_ttl": 180,
        "max_ttl": 180,
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
        "allowed_roles": "testrole,teststaticrole,testreissuerole",
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
def vault_db(modules, db_engine):
    try:
        yield modules.vault_db
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


@pytest.mark.usefixtures("connection_setup")
def test_list_connections(vault_db):
    ret = vault_db.list_connections()
    assert ret == ["testdb"]


@pytest.mark.usefixtures("connection_setup")
def test_fetch_connection(vault_db, testdb):
    ret = vault_db.fetch_connection("testdb")
    assert ret
    for var, val in testdb.items():
        if var == "password":
            continue
        if var in ["connection_url", "username"]:
            assert var in ret["connection_details"]
            assert ret["connection_details"][var] == val
        else:
            assert var in ret
            if var == "allowed_roles":
                assert ret[var] == list(val.split(","))
            else:
                assert ret[var] == val


def test_write_connection(vault_db, testdb, mysql_container):
    args = {
        "plugin": "mysql",
        "connection_url": f"{{{{username}}}}:{{{{password}}}}@tcp(172.17.0.1:{mysql_container.mysql_port})/",
        "allowed_roles": ["testrole", "teststaticrole"],
        "username": "root",
        "password": mysql_container.mysql_passwd,
        "rotate": False,
    }
    ret = vault_db.write_connection("testdb", **args)
    assert ret
    assert "testdb" in vault_list("database/config")


@pytest.mark.usefixtures("connection_setup")
def test_delete_connection(vault_db):
    ret = vault_db.delete_connection("testdb")
    assert ret
    assert "testdb" not in vault_list("database/config")


@pytest.mark.usefixtures("connection_setup")
def test_reset_connection(vault_db):
    ret = vault_db.reset_connection("testdb")
    assert ret


@pytest.mark.usefixtures("roles_setup")
def test_list_roles(vault_db):
    ret = vault_db.list_roles()
    assert ret == ["testrole"]


@pytest.mark.usefixtures("role_static_setup")
def test_list_roles_static(vault_db):
    ret = vault_db.list_roles(static=True)
    assert ret == ["teststaticrole"]


@pytest.mark.usefixtures("roles_setup")
def test_fetch_role(vault_db, testrole):
    ret = vault_db.fetch_role("testrole")
    assert ret
    for var, val in testrole.items():
        assert var in ret
        if var == "creation_statements":
            assert ret[var] == [val]
        else:
            assert ret[var] == val


@pytest.mark.usefixtures("role_static_setup")
def test_fetch_role_static(vault_db, teststaticrole):
    ret = vault_db.fetch_role("teststaticrole", static=True)
    assert ret
    for var, val in teststaticrole.items():
        assert var in ret
        assert ret[var] == val


@pytest.mark.usefixtures("connection_setup")
def test_write_role(vault_db):
    args = {
        "connection": "testdb",
        "creation_statements": r"CREATE USER '{{name}}'@'%' IDENTIFIED BY '{{password}}';GRANT SELECT ON *.* TO '{{name}}'@'%';",
    }
    ret = vault_db.write_role("testrole", **args)
    assert ret
    assert "testrole" in vault_list("database/roles")


@pytest.mark.usefixtures("connection_setup")
def test_write_static_role(vault_db, mysql_container):
    args = {
        "connection": "testdb",
        "username": mysql_container.mysql_user,
        "rotation_period": 86400,
    }
    ret = vault_db.write_static_role("teststaticrole", **args)
    assert ret
    assert "teststaticrole" in vault_list("database/static-roles")


@pytest.mark.usefixtures("roles_setup")
def test_delete_role(vault_db):
    ret = vault_db.delete_role("testrole")
    assert ret
    assert "testrole" not in vault_list("database/roles")


@pytest.mark.usefixtures("role_static_setup")
def test_delete_role_static(vault_db):
    ret = vault_db.delete_role("teststaticrole", static=True)
    assert ret
    assert "teststaticrole" not in vault_list("database/static-roles")


@pytest.mark.usefixtures("roles_setup")
def test_get_creds(vault_db):
    ret = vault_db.get_creds("testrole", cache=False)
    assert ret
    assert "username" in ret
    assert "password" in ret


@pytest.mark.usefixtures("role_static_setup")
def test_get_creds_static(vault_db, teststaticrole):
    ret = vault_db.get_creds("teststaticrole", static=True, cache=False)
    assert ret
    assert "username" in ret
    assert "password" in ret
    assert ret["username"] == teststaticrole["username"]


@pytest.mark.usefixtures("roles_setup")
def test_get_creds_cached(vault_db):
    ret = vault_db.get_creds("testrole", cache=True)
    assert ret
    assert "username" in ret
    assert "password" in ret
    ret_new = vault_db.get_creds("testrole", cache=True)
    assert ret_new
    assert "username" in ret_new
    assert "password" in ret_new
    assert ret_new["username"] == ret["username"]
    assert ret_new["password"] == ret["password"]


@pytest.mark.usefixtures("roles_setup")
def test_get_creds_cached_multiple(vault_db):
    ret = vault_db.get_creds("testrole", cache="one")
    assert ret
    assert "username" in ret
    assert "password" in ret
    ret_new = vault_db.get_creds("testrole", cache="two")
    assert ret_new
    assert "username" in ret_new
    assert "password" in ret_new
    assert ret_new["username"] != ret["username"]
    assert ret_new["password"] != ret["password"]
    assert vault_db.get_creds("testrole", cache="one") == ret
    assert vault_db.get_creds("testrole", cache="two") == ret_new


@pytest.mark.usefixtures("roles_setup")
@pytest.mark.parametrize("roles_setup", [["testreissuerole"]], indirect=True)
def test_get_creds_cached_valid_for_reissue(vault_db, testreissuerole):
    """
    Test that valid cached credentials that do not fulfill valid_for
    and cannot be renewed as required are reissued
    """
    ret = vault_db.get_creds("testreissuerole", cache=True)
    assert ret
    assert "username" in ret
    assert "password" in ret
    # 3 seconds because of leeway in lease validity check after renewals
    time.sleep(3)
    ret_new = vault_db.get_creds(
        "testreissuerole", cache=True, valid_for=testreissuerole["default_ttl"]
    )
    assert ret_new
    assert "username" in ret_new
    assert "password" in ret_new
    assert ret_new["username"] != ret["username"]
    assert ret_new["password"] != ret["password"]


@pytest.mark.usefixtures("role_static_setup")
def test_rotate_static_role(vault_db):
    ret = vault_db.get_creds("teststaticrole", static=True, cache=False)
    assert ret
    old_pw = ret["password"]
    ret = vault_db.rotate_static_role("teststaticrole")
    assert ret
    ret = vault_db.get_creds("teststaticrole", static=True, cache=False)
    assert ret
    assert ret["password"] != old_pw
