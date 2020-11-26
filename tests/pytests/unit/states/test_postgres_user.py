import pytest
import salt.modules.postgres as postgres
import salt.states.postgres_user as postgres_user
from tests.support.mock import create_autospec, patch

DB_ARGS = {
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


def test_present_create_basic(mocks):
    assert postgres_user.present("username") == {
        "name": "username",
        "result": True,
        "changes": {"username": "Present"},
        "comment": "The user username has been created",
    }
    mocks["postgres.role_get"].assert_called_once_with(
        "username", return_password=True, **DB_ARGS
    )
    mocks["postgres.user_create"].assert_called_once_with(
        username="username",
        createdb=None,
        createroles=None,
        encrypted=True,
        superuser=None,
        login=None,
        inherit=None,
        replication=None,
        rolepassword=None,
        valid_until=None,
        groups=None,
        **DB_ARGS
    )
    mocks["postgres.user_update"].assert_not_called()


@pytest.mark.usefixtures("test_mode")
def test_present_create_basic_test(mocks):
    assert postgres_user.present("username") == {
        "name": "username",
        "result": None,
        "changes": {},
        "comment": "User username is set to be created",
    }
    mocks["postgres.role_get"].assert_called_once_with(
        "username", return_password=True, **DB_ARGS
    )
    mocks["postgres.user_create"].assert_not_called()
    mocks["postgres.user_update"].assert_not_called()


def test_present_exists_basic(mocks, existing_user):
    mocks["postgres.role_get"].return_value = existing_user

    assert postgres_user.present("username") == {
        "name": "username",
        "result": True,
        "changes": {},
        "comment": "User username is already present",
    }
    mocks["postgres.role_get"].assert_called_once_with(
        "username", return_password=True, **DB_ARGS
    )
    mocks["postgres.user_create"].assert_not_called()
    mocks["postgres.user_update"].assert_not_called()


def test_present_create_basic_error(mocks):
    mocks["postgres.user_create"].return_value = False

    assert postgres_user.present("username") == {
        "name": "username",
        "result": False,
        "changes": {},
        "comment": "Failed to create user username",
    }
    mocks["postgres.role_get"].assert_called_once_with(
        "username", return_password=True, **DB_ARGS
    )
    mocks["postgres.user_create"].assert_called_once()
    mocks["postgres.user_update"].assert_not_called()


def test_present_create_md5_password(mocks, md5_pw):
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
        **DB_ARGS
    )
    mocks["postgres.user_update"].assert_not_called()


def test_present_create_plain_password(mocks):
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
        **DB_ARGS
    )
    mocks["postgres.user_update"].assert_not_called()


def test_present_create_md5_password_default_plain(mocks, monkeypatch, md5_pw):
    monkeypatch.setattr(postgres, "_DEFAULT_PASSWORDS_ENCRYPTION", False)
    test_present_create_md5_password(mocks, md5_pw)


def test_present_create_md5_password_default_encrypted(mocks, monkeypatch, md5_pw):
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
        **DB_ARGS
    )
    mocks["postgres.user_update"].assert_not_called()


def test_present_create_md5_prehashed(mocks, md5_pw):
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
        **DB_ARGS
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


def test_present_update_md5_password(mocks, existing_user, md5_pw):
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
        **DB_ARGS
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


def test_present_update_password_no_check(mocks, existing_user, md5_pw):
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
        "username", return_password=False, **DB_ARGS
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
        **DB_ARGS
    )


def test_present_create_default_password(mocks, md5_pw):
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
        **DB_ARGS
    )


def test_present_create_unused_default_password(mocks, md5_pw):
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
        **DB_ARGS
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


# ==========
# postgres_user.absent
# ==========


def test_absent_delete(mocks):
    mocks["postgres.user_exists"].return_value = True

    assert postgres_user.absent("username") == {
        "name": "username",
        "result": True,
        "changes": {"username": "Absent"},
        "comment": "User username has been removed",
    }
    mocks["postgres.user_exists"].assert_called_once_with("username", **DB_ARGS)
    mocks["postgres.user_remove"].assert_called_once_with("username", **DB_ARGS)


@pytest.mark.usefixtures("test_mode")
def test_absent_test(mocks):
    mocks["postgres.user_exists"].return_value = True

    assert postgres_user.absent("username") == {
        "name": "username",
        "result": None,
        "changes": {},
        "comment": "User username is set to be removed",
    }
    mocks["postgres.user_exists"].assert_called_once_with("username", **DB_ARGS)
    mocks["postgres.user_remove"].assert_not_called()


def test_absent_already(mocks):
    mocks["postgres.user_exists"].return_value = False

    assert postgres_user.absent("username") == {
        "name": "username",
        "result": True,
        "changes": {},
        "comment": "User username is not present, so it cannot be removed",
    }
    mocks["postgres.user_exists"].assert_called_once_with("username", **DB_ARGS)
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
