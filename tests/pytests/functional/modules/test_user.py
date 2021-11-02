import pathlib

import pytest
import salt.utils.platform
from saltfactories.utils import random_string

pytestmark = [
    pytest.mark.skip_if_not_root,
    pytest.mark.destructive_test,
    pytest.mark.windows_whitelisted,
]


@pytest.fixture(scope="module")
def user(modules):
    return modules.user


@pytest.fixture
def username(user):
    _username = random_string("test-account-", uppercase=False)
    try:
        yield _username
    finally:
        try:
            user.delete(_username, remove=True, force=True)
        except Exception:  # pylint: disable=broad-except
            # The point here is just system cleanup. It can fail if no account was created
            pass


@pytest.fixture
def account(username):
    with pytest.helpers.create_account(username=username) as account:
        yield account


def test_add(user, username):
    ret = user.add(username)
    assert ret is True


def test_delete(user, account):
    ret = user.delete(account.username)
    assert ret is True


@pytest.mark.skip_on_windows(reason="The windows user module does not support 'remove'")
@pytest.mark.parametrize("remove", [False, True])
def test_delete_remove(user, account, remove):
    """
    Test deleting a user from the system and passing ``remove`` to the call
    """
    user_info = user.info(account.username)
    ret = user.delete(account.username, remove=remove)
    assert ret is True
    if remove is True:
        assert pathlib.Path(user_info["home"]).exists() is False
    else:
        assert pathlib.Path(user_info["home"]).exists() is True


def test_info_after_deletion(user, account):
    """
    This test targets a situation where, at least on macOS, the call to ``user.info(username)``
    returns data after the account has been deleted from the system.
    It's a weird caching issue with ``pwd.getpwnam``
    """
    kwargs = {}
    if not salt.utils.platform.is_windows():
        kwargs["remove"] = True
    ret = user.delete(account.username, **kwargs)
    assert ret is True
    assert not user.info(account.username)
