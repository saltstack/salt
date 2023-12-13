"""
integration tests for mac_shadow
"""

import datetime
import types

import pytest
from saltfactories.utils import random_string

from salt.exceptions import CommandExecutionError

pytestmark = [
    pytest.mark.skip_if_binaries_missing("dscl", "pwpolicy"),
    pytest.mark.slow_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.skip_unless_on_darwin,
]


@pytest.fixture(scope="module")
def shadow(modules):
    return modules.shadow


@pytest.fixture
def accounts():
    with pytest.helpers.create_account(create_group=True) as _account:
        yield types.SimpleNamespace(
            existing=_account.username,
            non_existing=random_string("account-", lowercase=False),
        )


def test_info(shadow, accounts):
    """
    Test shadow.info
    """
    # Correct Functionality
    ret = shadow.info(accounts.existing)
    assert ret["name"] == accounts.existing

    # User does not exist
    ret = shadow.info(accounts.non_existing)
    assert ret["name"] == ""


def test_get_last_change(shadow, accounts):
    """
    Test shadow.get_last_change
    """
    # Correct Functionality
    text_date = shadow.get_last_change(accounts.existing)
    assert text_date != "Invalid Timestamp"
    obj_date = datetime.datetime.strptime(text_date, "%Y-%m-%d %H:%M:%S")
    assert isinstance(obj_date, datetime.date)

    # User does not exist
    with pytest.raises(CommandExecutionError) as exc:
        shadow.get_last_change(accounts.non_existing)
        assert f"ERROR: User not found: {accounts.non_existing}" in str(exc.value)


def test_get_login_failed_last(shadow, accounts):
    """
    Test shadow.get_login_failed_last
    """
    # Correct Functionality
    text_date = shadow.get_login_failed_last(accounts.existing)
    assert text_date != "Invalid Timestamp"
    obj_date = datetime.datetime.strptime(text_date, "%Y-%m-%d %H:%M:%S")
    assert isinstance(obj_date, datetime.date)

    # User does not exist
    with pytest.raises(CommandExecutionError) as exc:
        shadow.get_login_failed_last(accounts)
        assert f"ERROR: User not found: {accounts.non_existing}" in str(exc.value)


def test_get_login_failed_count(shadow, accounts):
    """
    Test shadow.get_login_failed_count
    """
    # Correct Functionality
    assert shadow.get_login_failed_count(accounts.existing) == "0"

    # User does not exist
    with pytest.raises(CommandExecutionError) as exc:
        shadow.get_login_failed_count(accounts.non_existing)
        assert f"ERROR: User not found: {accounts.non_existing}" in str(exc.value)


def test_get_set_maxdays(shadow, accounts):
    """
    Test shadow.get_maxdays
    Test shadow.set_maxdays
    """
    # Correct Functionality
    assert shadow.set_maxdays(accounts.existing, 20)
    assert shadow.get_maxdays(accounts.existing) == 20

    # User does not exist
    with pytest.raises(CommandExecutionError) as exc:
        shadow.set_maxdays(accounts.non_existing, 7)
        assert f"ERROR: User not found: {accounts.non_existing}" in str(exc.value)

    with pytest.raises(CommandExecutionError) as exc:
        shadow.get_maxdays(accounts.non_existing)
        assert f"ERROR: User not found: {accounts.non_existing}" in str(exc.value)


def test_get_set_change(shadow, accounts):
    """
    Test shadow.get_change
    Test shadow.set_change
    """
    # Correct Functionality
    assert shadow.set_change(accounts.existing, "02/11/2011")
    assert shadow.get_change(accounts.existing) == "02/11/2011"

    # User does not exist
    with pytest.raises(CommandExecutionError) as exc:
        shadow.set_change(accounts.non_existing, "02/11/2012")
        assert f"ERROR: User not found: {accounts.non_existing}" in str(exc.value)

    with pytest.raises(CommandExecutionError) as exc:
        shadow.get_change(accounts.non_existing)
        assert f"ERROR: User not found: {accounts.non_existing}" in str(exc.value)


def test_get_set_expire(shadow, accounts):
    """
    Test shadow.get_expire
    Test shadow.set_expire
    """
    # Correct Functionality
    assert shadow.set_expire(accounts.existing, "02/11/2011")
    assert shadow.get_expire(accounts.existing) == "02/11/2011"

    # User does not exist
    with pytest.raises(CommandExecutionError) as exc:
        shadow.set_expire(accounts.non_existing, "02/11/2012")
        assert f"ERROR: User not found: {accounts.non_existing}" in str(exc.value)

    with pytest.raises(CommandExecutionError) as exc:
        shadow.get_expire(accounts.non_existing)
        assert f"ERROR: User not found: {accounts.non_existing}" in str(exc.value)


def test_del_password(shadow, accounts):
    """
    Test shadow.del_password
    """
    # Correct Functionality
    assert shadow.del_password(accounts.existing)
    assert shadow.info(accounts.existing)["passwd"] == "*"

    # User does not exist
    with pytest.raises(CommandExecutionError) as exc:
        shadow.del_password(accounts.non_existing)
        assert f"ERROR: User not found: {accounts.non_existing}" in str(exc.value)


def test_set_password(shadow, accounts):
    """
    Test shadow.set_password
    """
    # Correct Functionality
    assert shadow.set_password(accounts.existing, "Pa$$W0rd")

    # User does not exist
    with pytest.raises(CommandExecutionError) as exc:
        shadow.set_password(accounts.non_existing, "P@SSw0rd")
        assert f"ERROR: User not found: {accounts.non_existing}" in str(exc.value)
