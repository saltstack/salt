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


@pytest.fixture(scope="module")
def group(modules):
    return modules.group


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
def _setup_teardown_vars(group, add_group, change_group, del_group):
    try:
        yield
    finally:
        # Delete ADD_GROUP
        add_info = group.info(add_group)
        if add_info:
            group.delete(add_group)

        # Delete DEL_GROUP if something failed
        del_info = group.info(del_group)
        if del_info:
            group.delete(del_group)

        # Delete CHANGE_GROUP
        change_info = group.info(change_group)
        if change_info:
            group.delete(change_group)


def test_mac_group_add(group, add_group):
    """
    Tests the add group function
    """
    group.add(add_group, 3456)
    group_info = group.info(add_group)
    assert group_info["name"] == add_group


def test_mac_group_delete(group, del_group):
    """
    Tests the delete group function
    """
    # Create a group to delete - If unsuccessful, skip the test
    group_add_ret = group.add(del_group, 4567)
    if group_add_ret is not True:
        group.delete(del_group)
        pytest.skip("Failed to create a group to delete")

    # Now try to delete the added group
    ret = group.delete(del_group)
    assert ret


def test_mac_group_chgid(group, change_group):
    """
    Tests changing the group id
    """
    # Create a group to delete - If unsuccessful, skip the test
    ret = group.add(change_group, 5678)
    if ret is not True:
        group.delete(change_group)
        pytest.skip("Failed to create a group to manipulate")

    group.chgid(change_group, 6789)
    group_info = group.info(change_group)
    assert group_info["gid"] == 6789


def test_mac_adduser(group, add_group, add_user):
    """
    Tests adding user to the group
    """
    # Create a group to use for test - If unsuccessful, skip the test
    ret = group.add(add_group, 5678)
    if ret is not True:
        group.delete(add_group)
        pytest.skip("Failed to create a group to manipulate")

    group.adduser(add_group, add_user)
    group_info = group.info(add_group)
    assert add_user == "".join(group_info["members"])


def test_mac_deluser(group, add_group, add_user):
    """
    Test deleting user from a group
    """
    # Create a group to use for test - If unsuccessful, skip the test
    group_add_ret = group.add(add_group, 5678)
    user_add_ret = group.adduser(add_group, add_user)

    if group_add_ret and user_add_ret is not True:
        group.delete(add_group)
        pytest.skip("Failed to create a group to manipulate")

    delusr = group.deluser(add_group, add_user)
    assert delusr.data

    group_info = group.info(add_group)
    assert add_user not in "".join(group_info["members"])


def test_mac_members(group, add_group, add_user, rep_user_group):
    """
    Test replacing members of a group
    """
    group_add_ret = group.add(add_group, 5678)
    user_add_ret = group.adduser(add_group, add_user)

    if group_add_ret and user_add_ret is not True:
        group.delete(add_group)
        pytest.skip(
            "Failed to create the {} group or add user {} to group "
            "to manipulate".format(add_group, add_user)
        )

    rep_group_mem = group.members(add_group, rep_user_group)
    assert rep_group_mem

    # ensure new user is added to group and previous user is removed
    group_info = group.info(add_group)
    assert rep_user_group in str(group_info["members"])
    assert add_user not in str(group_info["members"])


def test_mac_getent(group, add_group, add_user):
    """
    Test returning info on all groups
    """
    group_add_ret = group.add(add_group, 5678)
    user_add_ret = group.adduser(add_group, add_user)

    if group_add_ret and user_add_ret is not True:
        group.delete(add_group)
        pytest.skip(
            "Failed to create the {} group or add user {} to group "
            "to manipulate".format(add_group, add_user)
        )

    getinfo = group.getent()
    assert getinfo.data
    assert add_group in str(getinfo)
    assert add_user in str(getinfo)
