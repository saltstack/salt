"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""

import pytest
from saltfactories.utils import random_string

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


@pytest.fixture(scope="module", autouse=True)
def _setup_teardown_vars(salt_call_cli, add_group, change_group, del_group):
    try:
        ret = salt_call_cli.run("grains.item", "kernel")
        os_grain = ret.data
        if os_grain["kernel"] not in "Darwin":
            pytest.skip("Test not applicable to '{kernel}' kernel".format(**os_grain))
        yield
    finally:
        # Delete ADD_GROUP
        ret = salt_call_cli.run("group.info", add_group)
        add_info = ret.data
        if add_info:
            salt_call_cli.run("group.delete", add_group)

        # Delete DEL_GROUP if something failed
        ret = salt_call_cli.run("group.info", del_group)
        del_info = ret.data
        if del_info:
            salt_call_cli.run("group.delete", del_group)

        # Delete CHANGE_GROUP
        ret = salt_call_cli.run("group.info", change_group)
        change_info = ret.data
        if change_info:
            salt_call_cli.run("group.delete", change_group)


def test_mac_group_add(salt_call_cli, add_group):
    """
    Tests the add group function
    """
    salt_call_cli.run("group.add", add_group, 3456)
    ret = salt_call_cli.run("group.info", add_group)
    group_info = ret.data
    assert group_info["name"] == add_group


def test_mac_group_delete(salt_call_cli, del_group):
    """
    Tests the delete group function
    """
    # Create a group to delete - If unsuccessful, skip the test
    group_add_ret = salt_call_cli.run("group.add", del_group, 4567)
    if group_add_ret.data is not True:
        salt_call_cli.run("group.delete", del_group)
        pytest.skip("Failed to create a group to delete")

    # Now try to delete the added group
    ret = salt_call_cli.run("group.delete", del_group)
    assert ret


def test_mac_group_chgid(salt_call_cli, change_group):
    """
    Tests changing the group id
    """
    # Create a group to delete - If unsuccessful, skip the test
    ret = salt_call_cli.run("group.add", change_group, 5678)
    if ret.data is not True:
        salt_call_cli.run("group.delete", change_group)
        pytest.skip("Failed to create a group to manipulate")

    salt_call_cli.run("group.chgid", change_group, 6789)
    ret = salt_call_cli.run("group.info", change_group)
    group_info = ret.data
    assert group_info["gid"] == 6789


def test_mac_adduser(salt_call_cli, add_group, add_user):
    """
    Tests adding user to the group
    """
    # Create a group to use for test - If unsuccessful, skip the test
    ret = salt_call_cli.run("group.add", add_group, 5678)
    if ret.data is not True:
        salt_call_cli.run("group.delete", add_group)
        pytest.skip("Failed to create a group to manipulate")

    salt_call_cli.run("group.adduser", add_group, add_user)
    ret = salt_call_cli.run("group.info", add_group)
    group_info = ret.data
    assert add_user == "".join(group_info["members"])


def test_mac_deluser(salt_call_cli, add_group, add_user):
    """
    Test deleting user from a group
    """
    # Create a group to use for test - If unsuccessful, skip the test
    group_add_ret = salt_call_cli.run("group.add", add_group, 5678)
    user_add_ret = salt_call_cli.run("group.adduser", add_group, add_user)

    if group_add_ret.data and user_add_ret is not True:
        salt_call_cli.run("group.delete", add_group)
        pytest.skip("Failed to create a group to manipulate")

    delusr = salt_call_cli.run("group.deluser", add_group, add_user)
    assert delusr.data

    group_info = salt_call_cli.run("group.info", add_group)
    assert add_user.data not in "".join(group_info["members"])


def test_mac_members(salt_call_cli, add_group, add_user, rep_user_group):
    """
    Test replacing members of a group
    """
    group_add_ret = salt_call_cli.run("group.add", add_group, 5678)
    user_add_ret = salt_call_cli.run("group.adduser", add_group, add_user)

    if group_add_ret.data and user_add_ret is not True:
        salt_call_cli.run("group.delete", add_group)
        pytest.skip(
            "Failed to create the {} group or add user {} to group "
            "to manipulate".format(add_group, add_user)
        )

    rep_group_mem = salt_call_cli.run("group.members", add_group, rep_user_group)
    assert rep_group_mem.data

    # ensure new user is added to group and previous user is removed
    group_info = salt_call_cli.run("group.info", [add_group])
    assert rep_user_group.data in str(group_info.data["members"])
    assert add_user not in str(group_info.data["members"])


def test_mac_getent(salt_call_cli, add_group, add_user):
    """
    Test returning info on all groups
    """
    group_add_ret = salt_call_cli.run("group.add", add_group, 5678)
    user_add_ret = salt_call_cli.run("group.adduser", add_group, add_user)

    if group_add_ret.data and user_add_ret is not True:
        salt_call_cli.run("group.delete", add_group)
        pytest.skip(
            "Failed to create the {} group or add user {} to group "
            "to manipulate".format(add_group, add_user)
        )

    getinfo = salt_call_cli.run("group.getent")
    assert getinfo.data
    assert add_group in str(getinfo.data)
    assert add_user in str(getinfo.data)
