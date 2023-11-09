"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""

import pytest
from saltfactories.utils import random_string

from salt.exceptions import CommandExecutionError

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.destructive_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.skip_unless_on_darwin,
]


# Create group name strings for tests
@pytest.fixture(scope="module")
def add_group():
    yield random_string("RS-", lowercase=False)


@pytest.fixture(scope="module")
def del_group():
    yield random_string("RS-", lowercase=False)


@pytest.fixture(scope="module")
def change_group():
    yield random_string("RS-", lowercase=False)


@pytest.fixture(scope="module")
def add_user():
    yield random_string("RS-", lowercase=False)


@pytest.fixture(scope="module")
def rep_user_group():
    yield random_string("RS-", lowercase=False)


pytest.fixture(scope="function")


def setup_teardown_vars(salt_call_cli, add_group, change_group, del_group):
    try:
        os_grain = salt_call_cli.run("grains.item", "kernel")
        if os_grain["kernel"] not in "Darwin":
            pytest.skip("Test not applicable to '{kernel}' kernel".format(**os_grain))
        yield
    finally:
        # Delete ADD_GROUP
        add_info = salt_call_cli.run("group.info", add_group)
        if add_info:
            salt_call_cli.run("group.delete", add_group)

        # Delete DEL_GROUP if something failed
        del_info = salt_call_cli.run("group.info", del_group)
        if del_info:
            salt_call_cli.run("group.delete", del_group)

        # Delete CHANGE_GROUP
        change_info = salt_call_cli.run("group.info", change_group)
        if change_info:
            salt_call_cli.run("group.delete", change_group)


def test_mac_group_add(salt_call_cli, add_group, setup_teardown_vars):
    """
    Tests the add group function
    """
    try:
        salt_call_cli.run("group.add", add_group, 3456)
        group_info = salt_call_cli.run("group.info", add_group)
        assert group_info["name"] == add_group
    except CommandExecutionError:
        salt_call_cli.run("group.delete", add_group)
        raise


def test_mac_group_delete(salt_call_cli, del_group, setup_teardown_vars):
    """
    Tests the delete group function
    """
    # Create a group to delete - If unsuccessful, skip the test
    if salt_call_cli.run("group.add", del_group, 4567) is not True:
        salt_call_cli.run("group.delete", del_group)
        pytest.skip("Failed to create a group to delete")

    # Now try to delete the added group
    ret = salt_call_cli.run("group.delete", del_group)
    assert ret


def test_mac_group_chgid(salt_call_cli, change_group, setup_teardown_vars):
    """
    Tests changing the group id
    """
    # Create a group to delete - If unsuccessful, skip the test
    if salt_call_cli.run("group.add", change_group, 5678) is not True:
        salt_call_cli.run("group.delete", change_group)
        pytest.skip("Failed to create a group to manipulate")

    try:
        salt_call_cli.run("group.chgid", change_group, 6789)
        group_info = salt_call_cli.run("group.info", change_group)
        assert group_info["gid"] == 6789
    except AssertionError:
        salt_call_cli.run("group.delete", change_group)
        raise


def test_mac_adduser(salt_call_cli, add_group, add_user, setup_teardown_vars):
    """
    Tests adding user to the group
    """
    # Create a group to use for test - If unsuccessful, skip the test
    if salt_call_cli.run("group.add", add_group, 5678) is not True:
        salt_call_cli.run("group.delete", add_group)
        pytest.skip("Failed to create a group to manipulate")

    try:
        salt_call_cli.run("group.adduser", add_group, add_user)
        group_info = salt_call_cli.run("group.info", add_group)
        assert add_user == "".join(group_info["members"])
    except AssertionError:
        salt_call_cli.run("group.delete", add_group)
        raise


def test_mac_deluser(salt_call_cli, add_group, add_user, setup_teardown_vars):
    """
    Test deleting user from a group
    """
    # Create a group to use for test - If unsuccessful, skip the test
    if (
        salt_call_cli.run("group.add", add_group, 5678)
        and salt_call_cli.run("group.adduser", add_group, add_user) is not True
    ):
        salt_call_cli.run("group.delete", add_group)
        pytest.skip("Failed to create a group to manipulate")

    delusr = salt_call_cli.run("group.deluser", add_group, add_user)
    assert delusr

    group_info = salt_call_cli.run("group.info", add_group)
    assert add_user not in "".join(group_info["members"])


def test_mac_members(
    salt_call_cli, add_group, add_user, rep_user_group, setup_teardown_vars
):
    """
    Test replacing members of a group
    """
    if (
        salt_call_cli.run("group.add", add_group, 5678)
        and salt_call_cli.run("group.adduser", add_group, add_user) is not True
    ):
        salt_call_cli.run("group.delete", add_group)
        pytest.skip(
            "Failed to create the {} group or add user {} to group "
            "to manipulate".format(add_group, add_user)
        )

    rep_group_mem = salt_call_cli.run("group.members", add_group, rep_user_group)
    assert rep_group_mem

    # ensure new user is added to group and previous user is removed
    group_info = salt_call_cli.run("group.info", [add_group])
    assert rep_user_group in str(group_info["members"])
    assert add_user not in str(group_info["members"])


def test_mac_getent(salt_call_cli, add_group, add_user, setup_teardown_vars):
    """
    Test returning info on all groups
    """
    if (
        salt_call_cli.run("group.add", add_group, 5678)
        and salt_call_cli.run("group.adduser", add_group, add_user) is not True
    ):
        salt_call_cli.run("group.delete", add_group)
        pytest.skip(
            "Failed to create the {} group or add user {} to group "
            "to manipulate".format(add_group, add_user)
        )

    getinfo = salt_call_cli.run("group.getent")
    assert getinfo
    assert add_group in str(getinfo)
    assert add_user in str(getinfo)
