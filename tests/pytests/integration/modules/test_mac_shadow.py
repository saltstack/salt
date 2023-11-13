"""
integration tests for mac_shadow
"""

import datetime

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
def setup_teardown_vars(salt_call_cli):
    TEST_USER = random_string("RS-", lowercase=False)
    NO_USER = random_string("RS-", lowercase=False)

    salt_call_cli.run("user.add", TEST_USER)

    try:
        yield TEST_USER, NO_USER
    finally:
        salt_call_cli.run("user.delete", TEST_USER)


def test_info(salt_call_cli, setup_teardown_vars):
    """
    Test shadow.info
    """
    TEST_USER = setup_teardown_vars[0]
    NO_USER = setup_teardown_vars[1]

    # Correct Functionality
    ret = salt_call_cli.run("shadow.info", TEST_USER)
    assert ret.data["name"] == TEST_USER

    # User does not exist
    ret = salt_call_cli.run("shadow.info", NO_USER)
    assert ret.data["name"] == ""


def test_get_account_created(salt_call_cli, setup_teardown_vars):
    """
    Test shadow.get_account_created
    """
    TEST_USER = setup_teardown_vars[0]
    NO_USER = setup_teardown_vars[1]

    # Correct Functionality
    text_date = salt_call_cli.run("shadow.get_account_created", TEST_USER)
    assert text_date.data != "Invalid Timestamp"
    obj_date = datetime.datetime.strptime(text_date, "%Y-%m-%d %H:%M:%S")
    assert isinstance(obj_date, datetime.date)

    # User does not exist
    assert (
        salt_call_cli.run("shadow.get_account_created", NO_USER)
        == f"ERROR: User not found: {NO_USER}"
    )


def test_get_last_change(salt_call_cli, setup_teardown_vars):
    """
    Test shadow.get_last_change
    """
    TEST_USER = setup_teardown_vars[0]
    NO_USER = setup_teardown_vars[1]

    # Correct Functionality
    text_date = salt_call_cli.run("shadow.get_last_change", TEST_USER)
    assert text_date != "Invalid Timestamp"
    obj_date = datetime.datetime.strptime(text_date, "%Y-%m-%d %H:%M:%S")
    assert isinstance(obj_date, datetime.date)

    # User does not exist
    assert (
        salt_call_cli.run("shadow.get_last_change", NO_USER)
        == f"ERROR: User not found: {NO_USER}"
    )


def test_get_login_failed_last(salt_call_cli, setup_teardown_vars):
    """
    Test shadow.get_login_failed_last
    """
    TEST_USER = setup_teardown_vars[0]
    NO_USER = setup_teardown_vars[1]

    # Correct Functionality
    text_date = salt_call_cli.run("shadow.get_login_failed_last", TEST_USER)
    assert text_date != "Invalid Timestamp"
    obj_date = datetime.datetime.strptime(text_date, "%Y-%m-%d %H:%M:%S")
    assert isinstance(obj_date, datetime.date)

    # User does not exist
    assert (
        salt_call_cli.run("shadow.get_login_failed_last", NO_USER)
        == f"ERROR: User not found: {NO_USER}"
    )


def test_get_login_failed_count(salt_call_cli, setup_teardown_vars):
    """
    Test shadow.get_login_failed_count
    """
    TEST_USER = setup_teardown_vars[0]
    NO_USER = setup_teardown_vars[1]

    # Correct Functionality
    assert salt_call_cli.run("shadow.get_login_failed_count", TEST_USER) == "0"

    # User does not exist
    assert (
        salt_call_cli.run("shadow.get_login_failed_count", NO_USER)
        == f"ERROR: User not found: {NO_USER}"
    )


def test_get_set_maxdays(salt_call_cli, setup_teardown_vars):
    """
    Test shadow.get_maxdays
    Test shadow.set_maxdays
    """
    TEST_USER = setup_teardown_vars[0]
    NO_USER = setup_teardown_vars[1]

    # Correct Functionality
    assert salt_call_cli.run("shadow.set_maxdays", TEST_USER, 20)
    assert salt_call_cli.run("shadow.get_maxdays", TEST_USER) == 20

    # User does not exist
    assert (
        salt_call_cli.run("shadow.set_maxdays", NO_USER, 7)
        == f"ERROR: User not found: {NO_USER}"
    )
    assert (
        salt_call_cli.run("shadow.get_maxdays", NO_USER)
        == f"ERROR: User not found: {NO_USER}"
    )


def test_get_set_change(salt_call_cli, setup_teardown_vars):
    """
    Test shadow.get_change
    Test shadow.set_change
    """
    TEST_USER = setup_teardown_vars[0]
    NO_USER = setup_teardown_vars[1]

    # Correct Functionality
    assert salt_call_cli.run("shadow.set_change", TEST_USER, "02/11/2011")
    assert salt_call_cli.run("shadow.get_change", TEST_USER) == "02/11/2011"

    # User does not exist
    assert (
        salt_call_cli.run("shadow.set_change", NO_USER, "02/11/2012")
        == f"ERROR: User not found: {NO_USER}"
    )
    assert (
        salt_call_cli.run("shadow.get_change", NO_USER)
        == f"ERROR: User not found: {NO_USER}"
    )


def test_get_set_expire(salt_call_cli, setup_teardown_vars):
    """
    Test shadow.get_expire
    Test shadow.set_expire
    """
    TEST_USER = setup_teardown_vars[0]
    NO_USER = setup_teardown_vars[1]

    # Correct Functionality
    assert salt_call_cli.run("shadow.set_expire", TEST_USER, "02/11/2011")
    assert salt_call_cli.run("shadow.get_expire", TEST_USER) == "02/11/2011"

    # User does not exist
    assert (
        salt_call_cli.run("shadow.set_expire", NO_USER, "02/11/2012")
        == f"ERROR: User not found: {NO_USER}"
    )
    assert (
        salt_call_cli.run("shadow.get_expire", NO_USER)
        == f"ERROR: User not found: {NO_USER}"
    )


def test_del_password(salt_call_cli, setup_teardown_vars):
    """
    Test shadow.del_password
    """
    TEST_USER = setup_teardown_vars[0]
    NO_USER = setup_teardown_vars[1]

    # Correct Functionality
    assert salt_call_cli.run("shadow.del_password", TEST_USER)
    assert salt_call_cli.run("shadow.info", TEST_USER)["passwd"] == "*"

    # User does not exist
    assert (
        salt_call_cli.run("shadow.del_password", NO_USER)
        == f"ERROR: User not found: {NO_USER}"
    )


def test_set_password(salt_call_cli, setup_teardown_vars):
    """
    Test shadow.set_password
    """
    TEST_USER = setup_teardown_vars[0]
    NO_USER = setup_teardown_vars[1]

    # Correct Functionality
    assert salt_call_cli.run("shadow.set_password", TEST_USER, "Pa$$W0rd")

    # User does not exist
    assert (
        salt_call_cli.run("shadow.set_password", NO_USER, "P@SSw0rd")
        == f"ERROR: User not found: {NO_USER}"
    )
