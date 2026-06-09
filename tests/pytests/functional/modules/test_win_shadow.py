import pytest
from saltfactories.utils import random_string

pytestmark = [
    pytest.mark.destructive_test,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.windows_whitelisted,
]


@pytest.fixture(scope="module")
def shadow(modules):
    return modules.shadow


@pytest.fixture(scope="module")
def lgpo(modules):
    return modules.lgpo


@pytest.fixture(scope="module")
def user(modules):
    return modules.user


@pytest.fixture
def account(modules):
    _username = random_string("test-shadow-", uppercase=False)
    with pytest.helpers.create_account(username=_username) as acct:
        yield acct


@pytest.fixture
def lockout_threshold_one(lgpo):
    """
    Temporarily set the account lockout threshold to 1 so that a single bad
    password attempt locks the account.  Restores the original value on teardown.
    """
    original = lgpo.get_policy("LockoutThreshold", "machine")
    lgpo.set_computer_policy("LockoutThreshold", 1)
    try:
        yield
    finally:
        lgpo.set_computer_policy("LockoutThreshold", original)


def test_verify_password_correct(shadow, account):
    """
    verify_password returns True when the correct password is supplied.
    """
    assert shadow.verify_password(account.username, account.password) is True


def test_verify_password_wrong(shadow, account):
    """
    verify_password returns False when the wrong password is supplied.
    """
    assert shadow.verify_password(account.username, "definitely-wrong-pw!") is False


def test_verify_password_unlocks_account_on_lockout(
    shadow, user, account, lockout_threshold_one
):
    """
    When a wrong password locks the account, verify_password should
    automatically unlock it and still return False.
    """
    result = shadow.verify_password(account.username, "definitely-wrong-pw!")
    assert result is False
    info = user.info(account.username)
    assert info["account_locked"] is False
