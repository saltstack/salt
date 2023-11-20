"""
integration tests for mac_shadow
"""

import datetime
import types

import pytest
from saltfactories.utils import random_string

pytestmark = [
    pytest.mark.skip_if_binaries_missing("dscl", "pwpolicy"),
    pytest.mark.skip_initial_gh_actions_failure,
    pytest.mark.slow_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.skip_unless_on_darwin,
]


@pytest.fixture(scope="function")
def accounts():
    with pytest.helpers.create_account(create_group=True) as _account:
        yield types.SimpleNamespace(
            created=_account.username, not_created=random_string("RS-", lowercase=False)
        )


def test_info(salt_call_cli, accounts):
    """
    Test shadow.info
    """
    # Correct Functionality
    ret = salt_call_cli.run("shadow.info", accounts.created)
    assert ret.data["name"] == accounts.created

    # User does not exist
    ret = salt_call_cli.run("shadow.info", accounts.not_created)
    assert ret.data["name"] == ""


def test_get_account_created(salt_call_cli, accounts):
    """
    Test shadow.get_account_created
    """
    # Correct Functionality
    text_date = salt_call_cli.run("shadow.get_account_created", accounts.created)
    assert text_date.data != "Invalid Timestamp"
    obj_date = datetime.datetime.strptime(text_date, "%Y-%m-%d %H:%M:%S")
    assert isinstance(obj_date, datetime.date)

    # User does not exist
    assert (
        salt_call_cli.run("shadow.get_account_created", accounts.not_created)
        == f"ERROR: User not found: {accounts.not_created}"
    )


def test_get_last_change(salt_call_cli, accounts):
    """
    Test shadow.get_last_change
    """
    # Correct Functionality
    text_date = salt_call_cli.run("shadow.get_last_change", accounts.created)
    assert text_date != "Invalid Timestamp"
    obj_date = datetime.datetime.strptime(text_date, "%Y-%m-%d %H:%M:%S")
    assert isinstance(obj_date, datetime.date)

    # User does not exist
    assert (
        salt_call_cli.run("shadow.get_last_change", accounts.not_created)
        == f"ERROR: User not found: {accounts.not_created}"
    )


def test_get_login_failed_last(salt_call_cli, accounts):
    """
    Test shadow.get_login_failed_last
    """
    # Correct Functionality
    text_date = salt_call_cli.run("shadow.get_login_failed_last", accounts.created)
    assert text_date != "Invalid Timestamp"
    obj_date = datetime.datetime.strptime(text_date, "%Y-%m-%d %H:%M:%S")
    assert isinstance(obj_date, datetime.date)

    # User does not exist
    assert (
        salt_call_cli.run("shadow.get_login_failed_last", accounts)
        == f"ERROR: User not found: {accounts.not_created}"
    )


def test_get_login_failed_count(salt_call_cli, accounts):
    """
    Test shadow.get_login_failed_count
    """
    # Correct Functionality
    assert salt_call_cli.run("shadow.get_login_failed_count", accounts.created) == "0"

    # User does not exist
    assert (
        salt_call_cli.run("shadow.get_login_failed_count", accounts.not_created)
        == f"ERROR: User not found: {accounts.not_created}"
    )


def test_get_set_maxdays(salt_call_cli, accounts):
    """
    Test shadow.get_maxdays
    Test shadow.set_maxdays
    """
    # Correct Functionality
    assert salt_call_cli.run("shadow.set_maxdays", accounts.created, 20)
    assert salt_call_cli.run("shadow.get_maxdays", accounts.created) == 20

    # User does not exist
    assert (
        salt_call_cli.run("shadow.set_maxdays", accounts.not_created, 7)
        == f"ERROR: User not found: {accounts.not_created}"
    )
    assert (
        salt_call_cli.run("shadow.get_maxdays", accounts.not_created)
        == f"ERROR: User not found: {accounts.not_created}"
    )


def test_get_set_change(salt_call_cli, accounts):
    """
    Test shadow.get_change
    Test shadow.set_change
    """
    # Correct Functionality
    assert salt_call_cli.run("shadow.set_change", accounts.created, "02/11/2011")
    assert salt_call_cli.run("shadow.get_change", accounts.created) == "02/11/2011"

    # User does not exist
    assert (
        salt_call_cli.run("shadow.set_change", accounts.not_created, "02/11/2012")
        == f"ERROR: User not found: {accounts.not_created}"
    )
    assert (
        salt_call_cli.run("shadow.get_change", accounts.not_created)
        == f"ERROR: User not found: {accounts.not_created}"
    )


def test_get_set_expire(salt_call_cli, accounts):
    """
    Test shadow.get_expire
    Test shadow.set_expire
    """
    # Correct Functionality
    assert salt_call_cli.run("shadow.set_expire", accounts.created, "02/11/2011")
    assert salt_call_cli.run("shadow.get_expire", accounts.created) == "02/11/2011"

    # User does not exist
    assert (
        salt_call_cli.run("shadow.set_expire", accounts.not_created, "02/11/2012")
        == f"ERROR: User not found: {accounts.not_created}"
    )
    assert (
        salt_call_cli.run("shadow.get_expire", accounts.not_created)
        == f"ERROR: User not found: {accounts.not_created}"
    )


def test_del_password(salt_call_cli, accounts):
    """
    Test shadow.del_password
    """
    # Correct Functionality
    assert salt_call_cli.run("shadow.del_password", accounts.created)
    assert salt_call_cli.run("shadow.info", accounts.created)["passwd"] == "*"

    # User does not exist
    assert (
        salt_call_cli.run("shadow.del_password", accounts.not_created)
        == f"ERROR: User not found: {accounts.not_created}"
    )


def test_set_password(salt_call_cli, accounts):
    """
    Test shadow.set_password
    """
    # Correct Functionality
    assert salt_call_cli.run("shadow.set_password", accounts.created, "Pa$$W0rd")

    # User does not exist
    assert (
        salt_call_cli.run("shadow.set_password", accounts.not_created, "P@SSw0rd")
        == f"ERROR: User not found: {accounts.not_created}"
    )
