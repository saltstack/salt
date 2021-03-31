import pytest
import salt.modules.postgres as postgres
import salt.states.postgres_user as postgres_user
from tests.support.mock import create_autospec, patch


class ScramHash:
    def __eq__(self, other):
        return other.startswith("SCRAM-SHA-256$4096:")


@pytest.fixture(name="db_args")
def fixture_db_args():
    return {
        "runas": None,
        "host": None,
        "port": None,
        "maintenance_db": None,
        "user": None,
        "password": None,
    }


@pytest.fixture(name="md5_pw")
def fixture_md5_pw():
    # 'md5' + md5('password' + 'username')
    return "md55a231fcdb710d73268c4f44283487ba2"


@pytest.fixture(name="scram_pw")
def fixture_scram_pw():
    # scram_sha_256('password')
    return (
        "SCRAM-SHA-256$4096:wLr5nqC+3F+r7FdQPnB+nA==$"
        "0hn08ZdX8kirGaL4TM0j13digH9Wl365OOzCtAuF2pE=:"
        "LzAh/MGUdjYkdbDzcOKpfGwa3WwPUsyGcY+TEnSpcto="
    )


@pytest.fixture(name="existing_user")
def fixture_existing_user(md5_pw):
    return {
        "superuser": False,
        "inherits privileges": True,
        "can create roles": False,
        "can create databases": False,
        "can update system catalogs": None,
        "can login": True,
        "replication": False,
        "connections": None,
        "expiry time": None,
        "defaults variables": "",
        "password": md5_pw,
        "groups": [],
    }


@pytest.fixture(name="test_mode")
def fixture_test_mode():
    with patch.dict(postgres_user.__opts__, {"test": True}):
        yield


@pytest.fixture(name="mocks")
def fixture_mocks():
    return {
        "postgres.role_get": create_autospec(postgres.role_get, return_value=None),
        "postgres.user_exists": create_autospec(
            postgres.user_exists, return_value=False
        ),
        "postgres.user_create": create_autospec(
            postgres.user_create, return_value=True
        ),
        "postgres.user_update": create_autospec(
            postgres.user_update, return_value=True
        ),
        "postgres.user_remove": create_autospec(
            postgres.user_remove, return_value=True
        ),
    }


@pytest.fixture(autouse=True)
def setup_loader(mocks):
    setup_loader_modules = {
        postgres_user: {"__opts__": {"test": False}, "__salt__": mocks},
        postgres: {"__opts__": {"test": False}},
    }
    with pytest.helpers.loader_mock(setup_loader_modules) as loader_mock:
        yield loader_mock


# ==========
# postgres_user.present
# ==========


def test_present_create_basic(mocks, db_args):
    assert postgres_user.present("username") == {
        "name": "username",
        "result": True,
        "changes": {"username": "Present"},
        "comment": "The user username has been created",
    }
    mocks["postgres.role_get"].assert_called_once_with(
        "username", return_password=True, **db_args
    )
    mocks["postgres.user_create"].assert_called_once_with(
        username="username",
        createdb=None,
        createroles=None,
        encrypted="md5",
        superuser=None,
        login=None,
        inherit=None,
        replication=None,
        rolepassword=None,
        valid_until=None,
        groups=None,
        **db_args
    )
    mocks["postgres.user_update"].assert_not_called()


@pytest.mark.usefixtures("test_mode")
def test_present_create_basic_test(mocks, db_args):
    assert postgres_user.present("username") == {
        "name": "username",
        "result": None,
        "changes": {},
        "comment": "User username is set to be created",
    }
    mocks["postgres.role_get"].assert_called_once_with(
        "username", return_password=True, **db_args
    )
    mocks["postgres.user_create"].assert_not_called()
    mocks["postgres.user_update"].assert_not_called()


def test_present_exists_basic(mocks, existing_user, db_args):
    mocks["postgres.role_get"].return_value = existing_user

    assert postgres_user.present("username") == {
        "name": "username",
        "result": True,
        "changes": {},
        "comment": "User username is already present",
    }
    mocks["postgres.role_get"].assert_called_once_with(
        "username", return_password=True, **db_args
    )
    mocks["postgres.user_create"].assert_not_called()
    mocks["postgres.user_update"].assert_not_called()


def test_present_create_basic_error(mocks, db_args):
    mocks["postgres.user_create"].return_value = False

    assert postgres_user.present("username") == {
        "name": "username",
        "result": False,
        "changes": {},
        "comment": "Failed to create user username",
    }
    mocks["postgres.role_get"].assert_called_once_with(
        "username", return_password=True, **db_args
    )
    mocks["postgres.user_create"].assert_called_once()
    mocks["postgres.user_update"].assert_not_called()


def test_present_change_option(mocks, existing_user, db_args):
    mocks["postgres.role_get"].return_value = existing_user

    assert postgres_user.present("username", replication=True) == {
        "name": "username",
        "result": True,
        "changes": {"username": {"replication": True}},
        "comment": "The user username has been updated",
    }

    mocks["postgres.role_get"].assert_called_once()
    mocks["postgres.user_create"].assert_not_called()
    mocks["postgres.user_update"].assert_called_once_with(
        username="username",
        createdb=None,
        createroles=None,
        encrypted="md5",
        superuser=None,
        login=None,
        inherit=None,
        replication=True,
        rolepassword=None,
        valid_until=None,
        groups=None,
        **db_args
    )


def test_present_create_md5_password(mocks, md5_pw, db_args):
    assert postgres_user.present("username", password="password", encrypted=True) == {
        "name": "username",
        "result": True,
        "changes": {"username": "Present"},
        "comment": "The user username has been created",
    }
    mocks["postgres.role_get"].assert_called_once()
    mocks["postgres.user_create"].assert_called_once_with(
        username="username",
        createdb=None,
        createroles=None,
        encrypted=True,
        superuser=None,
        login=None,
        inherit=None,
        replication=None,
        rolepassword=md5_pw,
        valid_until=None,
        groups=None,
        **db_args
    )
    mocks["postgres.user_update"].assert_not_called()


def test_present_create_scram_password(mocks, db_args):
    assert postgres_user.present(
        "username", password="password", encrypted="scram-sha-256"
    ) == {
        "name": "username",
        "result": True,
        "changes": {"username": "Present"},
        "comment": "The user username has been created",
    }
    mocks["postgres.role_get"].assert_called_once()
    mocks["postgres.user_create"].assert_called_once_with(
        username="username",
        createdb=None,
        createroles=None,
        encrypted="scram-sha-256",
        superuser=None,
        login=None,
        inherit=None,
        replication=None,
        rolepassword=ScramHash(),
        valid_until=None,
        groups=None,
        **db_args
    )
    mocks["postgres.user_update"].assert_not_called()


def test_present_create_plain_password(mocks, db_args):
    assert postgres_user.present("username", password="password", encrypted=False) == {
        "name": "username",
        "result": True,
        "changes": {"username": "Present"},
        "comment": "The user username has been created",
    }
    mocks["postgres.role_get"].assert_called_once()
    mocks["postgres.user_create"].assert_called_once_with(
        username="username",
        createdb=None,
        createroles=None,
        encrypted=False,
        superuser=None,
        login=None,
        inherit=None,
        replication=None,
        rolepassword="password",
        valid_until=None,
        groups=None,
        **db_args
    )
    mocks["postgres.user_update"].assert_not_called()


def test_present_create_md5_password_default_plain(mocks, monkeypatch, md5_pw, db_args):
    monkeypatch.setattr(postgres, "_DEFAULT_PASSWORDS_ENCRYPTION", False)
    test_present_create_md5_password(mocks, md5_pw, db_args)


def test_present_create_md5_password_default_encrypted(
    mocks, monkeypatch, md5_pw, db_args
):
    monkeypatch.setattr(postgres, "_DEFAULT_PASSWORDS_ENCRYPTION", True)

    assert postgres_user.present("username", password="password") == {
        "name": "username",
        "result": True,
        "changes": {"username": "Present"},
        "comment": "The user username has been created",
    }
    mocks["postgres.role_get"].assert_called_once()
    mocks["postgres.user_create"].assert_called_once_with(
        username="username",
        createdb=None,
        createroles=None,
        encrypted=True,
        superuser=None,
        login=None,
        inherit=None,
        replication=None,
        rolepassword=md5_pw,
        valid_until=None,
        groups=None,
        **db_args
    )
    mocks["postgres.user_update"].assert_not_called()


def test_present_create_md5_prehashed(mocks, md5_pw, db_args):
    assert postgres_user.present("username", password=md5_pw, encrypted=True) == {
        "name": "username",
        "result": True,
        "changes": {"username": "Present"},
        "comment": "The user username has been created",
    }
    mocks["postgres.role_get"].assert_called_once()
    mocks["postgres.user_create"].assert_called_once_with(
        username="username",
        createdb=None,
        createroles=None,
        encrypted=True,
        superuser=None,
        login=None,
        inherit=None,
        replication=None,
        rolepassword=md5_pw,
        valid_until=None,
        groups=None,
        **db_args
    )
    mocks["postgres.user_update"].assert_not_called()


def test_present_md5_matches(mocks, existing_user):
    mocks["postgres.role_get"].return_value = existing_user

    assert postgres_user.present("username", password="password", encrypted=True) == {
        "name": "username",
        "result": True,
        "changes": {},
        "comment": "User username is already present",
    }
    mocks["postgres.role_get"].assert_called_once()
    mocks["postgres.user_create"].assert_not_called()
    mocks["postgres.user_update"].assert_not_called()


def test_present_md5_matches_prehashed(mocks, existing_user, md5_pw):
    mocks["postgres.role_get"].return_value = existing_user

    assert postgres_user.present("username", password=md5_pw, encrypted=True) == {
        "name": "username",
        "result": True,
        "changes": {},
        "comment": "User username is already present",
    }
    mocks["postgres.role_get"].assert_called_once()
    mocks["postgres.user_create"].assert_not_called()
    mocks["postgres.user_update"].assert_not_called()


def test_present_scram_matches(mocks, existing_user, scram_pw):
    existing_user["password"] = scram_pw
    mocks["postgres.role_get"].return_value = existing_user

    assert postgres_user.present(
        "username", password="password", encrypted="scram-sha-256"
    ) == {
        "name": "username",
        "result": True,
        "changes": {},
        "comment": "User username is already present",
    }
    mocks["postgres.role_get"].assert_called_once()
    mocks["postgres.user_create"].assert_not_called()
    mocks["postgres.user_update"].assert_not_called()


def test_present_scram_matches_prehashed(mocks, existing_user, scram_pw):
    existing_user["password"] = scram_pw
    mocks["postgres.role_get"].return_value = existing_user

    assert postgres_user.present(
        "username", password=scram_pw, encrypted="scram-sha-256"
    ) == {
        "name": "username",
        "result": True,
        "changes": {},
        "comment": "User username is already present",
    }
    mocks["postgres.role_get"].assert_called_once()
    mocks["postgres.user_create"].assert_not_called()
    mocks["postgres.user_update"].assert_not_called()


def test_present_update_md5_password(mocks, existing_user, md5_pw, db_args):
    existing_user["password"] = "md500000000000000000000000000000000"
    mocks["postgres.role_get"].return_value = existing_user

    assert postgres_user.present("username", password="password", encrypted=True) == {
        "name": "username",
        "result": True,
        "changes": {"username": {"password": True}},
        "comment": "The user username has been updated",
    }
    mocks["postgres.role_get"].assert_called_once()
    mocks["postgres.user_create"].assert_not_called()
    mocks["postgres.user_update"].assert_called_once_with(
        username="username",
        createdb=None,
        createroles=None,
        encrypted=True,
        superuser=None,
        login=None,
        inherit=None,
        replication=None,
        rolepassword=md5_pw,
        valid_until=None,
        groups=None,
        **db_args
    )


def test_present_refresh_scram_password(mocks, existing_user, scram_pw, db_args):
    existing_user["password"] = scram_pw
    mocks["postgres.role_get"].return_value = existing_user

    assert postgres_user.present(
        "username",
        password="password",
        encrypted="scram-sha-256",
        refresh_password=True,
    ) == {
        "name": "username",
        "result": True,
        "changes": {"username": {"password": True}},
        "comment": "The user username has been updated",
    }
    mocks["postgres.role_get"].assert_called_once_with(
        "username", return_password=False, **db_args
    )
    mocks["postgres.user_create"].assert_not_called()
    mocks["postgres.user_update"].assert_called_once_with(
        username="username",
        createdb=None,
        createroles=None,
        encrypted="scram-sha-256",
        superuser=None,
        login=None,
        inherit=None,
        replication=None,
        rolepassword=ScramHash(),
        valid_until=None,
        groups=None,
        **db_args
    )


def test_present_update_error(mocks, existing_user):
    existing_user["password"] = "md500000000000000000000000000000000"
    mocks["postgres.role_get"].return_value = existing_user
    mocks["postgres.user_update"].return_value = False

    assert postgres_user.present("username", password="password", encrypted=True) == {
        "name": "username",
        "result": False,
        "changes": {},
        "comment": "Failed to update user username",
    }
    mocks["postgres.role_get"].assert_called_once()
    mocks["postgres.user_create"].assert_not_called()
    mocks["postgres.user_update"].assert_called_once()


def test_present_update_password_no_check(mocks, existing_user, md5_pw, db_args):
    del existing_user["password"]
    mocks["postgres.role_get"].return_value = existing_user

    assert postgres_user.present(
        "username", password="password", encrypted=True, refresh_password=True
    ) == {
        "name": "username",
        "result": True,
        "changes": {"username": {"password": True}},
        "comment": "The user username has been updated",
    }
    mocks["postgres.role_get"].assert_called_once_with(
        "username", return_password=False, **db_args
    )
    mocks["postgres.user_create"].assert_not_called()
    mocks["postgres.user_update"].assert_called_once_with(
        username="username",
        createdb=None,
        createroles=None,
        encrypted=True,
        superuser=None,
        login=None,
        inherit=None,
        replication=None,
        rolepassword=md5_pw,
        valid_until=None,
        groups=None,
        **db_args
    )


def test_present_create_default_password(mocks, md5_pw, db_args):
    assert postgres_user.present(
        "username", default_password="password", encrypted=True
    ) == {
        "name": "username",
        "result": True,
        "changes": {"username": "Present"},
        "comment": "The user username has been created",
    }
    mocks["postgres.role_get"].assert_called_once()
    mocks["postgres.user_create"].assert_called_once_with(
        username="username",
        createdb=None,
        createroles=None,
        encrypted=True,
        superuser=None,
        login=None,
        inherit=None,
        replication=None,
        rolepassword=md5_pw,
        valid_until=None,
        groups=None,
        **db_args
    )


def test_present_create_unused_default_password(mocks, md5_pw, db_args):
    assert postgres_user.present(
        "username", password="password", default_password="changeme", encrypted=True
    ) == {
        "name": "username",
        "result": True,
        "changes": {"username": "Present"},
        "comment": "The user username has been created",
    }
    mocks["postgres.role_get"].assert_called_once()
    mocks["postgres.user_create"].assert_called_once_with(
        username="username",
        createdb=None,
        createroles=None,
        encrypted=True,
        superuser=None,
        login=None,
        inherit=None,
        replication=None,
        rolepassword=md5_pw,
        valid_until=None,
        groups=None,
        **db_args
    )
    mocks["postgres.user_update"].assert_not_called()


def test_present_existing_default_password(mocks, existing_user):
    mocks["postgres.role_get"].return_value = existing_user

    assert postgres_user.present(
        "username", default_password="changeme", encrypted=True, refresh_password=True
    ) == {
        "name": "username",
        "result": True,
        "changes": {},
        "comment": "User username is already present",
    }
    mocks["postgres.role_get"].assert_called_once()
    mocks["postgres.user_create"].assert_not_called()
    mocks["postgres.user_update"].assert_not_called()


def test_present_plain_to_scram(mocks, existing_user, db_args):
    existing_user["password"] = "password"
    mocks["postgres.role_get"].return_value = existing_user

    assert postgres_user.present(
        "username", password="password", encrypted="scram-sha-256"
    ) == {
        "name": "username",
        "result": True,
        "changes": {"username": {"password": True}},
        "comment": "The user username has been updated",
    }
    mocks["postgres.role_get"].assert_called_once()
    mocks["postgres.user_create"].assert_not_called()
    mocks["postgres.user_update"].assert_called_once_with(
        username="username",
        createdb=None,
        createroles=None,
        encrypted="scram-sha-256",
        superuser=None,
        login=None,
        inherit=None,
        replication=None,
        rolepassword=ScramHash(),
        valid_until=None,
        groups=None,
        **db_args
    )


def test_present_plain_to_md5(mocks, existing_user, md5_pw, db_args):
    existing_user["password"] = "password"
    mocks["postgres.role_get"].return_value = existing_user

    assert postgres_user.present("username", password="password", encrypted="md5") == {
        "name": "username",
        "result": True,
        "changes": {"username": {"password": True}},
        "comment": "The user username has been updated",
    }
    mocks["postgres.role_get"].assert_called_once()
    mocks["postgres.user_create"].assert_not_called()
    mocks["postgres.user_update"].assert_called_once_with(
        username="username",
        createdb=None,
        createroles=None,
        encrypted="md5",
        superuser=None,
        login=None,
        inherit=None,
        replication=None,
        rolepassword=md5_pw,
        valid_until=None,
        groups=None,
        **db_args
    )


def test_present_md5_to_scram(mocks, existing_user, db_args):
    mocks["postgres.role_get"].return_value = existing_user

    assert postgres_user.present(
        "username", password="password", encrypted="scram-sha-256"
    ) == {
        "name": "username",
        "result": True,
        "changes": {"username": {"password": True}},
        "comment": "The user username has been updated",
    }
    mocks["postgres.role_get"].assert_called_once()
    mocks["postgres.user_create"].assert_not_called()
    mocks["postgres.user_update"].assert_called_once_with(
        username="username",
        createdb=None,
        createroles=None,
        encrypted="scram-sha-256",
        superuser=None,
        login=None,
        inherit=None,
        replication=None,
        rolepassword=ScramHash(),
        valid_until=None,
        groups=None,
        **db_args
    )


def test_present_scram_to_md5(mocks, existing_user, scram_pw, md5_pw, db_args):
    existing_user["password"] = scram_pw
    mocks["postgres.role_get"].return_value = existing_user

    assert postgres_user.present("username", password="password", encrypted="md5") == {
        "name": "username",
        "result": True,
        "changes": {"username": {"password": True}},
        "comment": "The user username has been updated",
    }
    mocks["postgres.role_get"].assert_called_once()
    mocks["postgres.user_create"].assert_not_called()
    mocks["postgres.user_update"].assert_called_once_with(
        username="username",
        createdb=None,
        createroles=None,
        encrypted="md5",
        superuser=None,
        login=None,
        inherit=None,
        replication=None,
        rolepassword=md5_pw,
        valid_until=None,
        groups=None,
        **db_args
    )


# ==========
# postgres_user.absent
# ==========


def test_absent_delete(mocks, db_args):
    mocks["postgres.user_exists"].return_value = True

    assert postgres_user.absent("username") == {
        "name": "username",
        "result": True,
        "changes": {"username": "Absent"},
        "comment": "User username has been removed",
    }
    mocks["postgres.user_exists"].assert_called_once_with("username", **db_args)
    mocks["postgres.user_remove"].assert_called_once_with("username", **db_args)


@pytest.mark.usefixtures("test_mode")
def test_absent_test(mocks, db_args):
    mocks["postgres.user_exists"].return_value = True

    assert postgres_user.absent("username") == {
        "name": "username",
        "result": None,
        "changes": {},
        "comment": "User username is set to be removed",
    }
    mocks["postgres.user_exists"].assert_called_once_with("username", **db_args)
    mocks["postgres.user_remove"].assert_not_called()


def test_absent_already(mocks, db_args):
    mocks["postgres.user_exists"].return_value = False

    assert postgres_user.absent("username") == {
        "name": "username",
        "result": True,
        "changes": {},
        "comment": "User username is not present, so it cannot be removed",
    }
    mocks["postgres.user_exists"].assert_called_once_with("username", **db_args)
    mocks["postgres.user_remove"].assert_not_called()


def test_absent_error(mocks):
    mocks["postgres.user_exists"].return_value = True
    mocks["postgres.user_remove"].return_value = False

    assert postgres_user.absent("username") == {
        "name": "username",
        "result": False,
        "changes": {},
        "comment": "User username failed to be removed",
    }
    mocks["postgres.user_exists"].assert_called_once()
    mocks["postgres.user_remove"].assert_called_once()
