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
@pytest.fixture(scope="function")
def non_existing_group_name(group):
    group_name = random_string("group-", lowercase=False)
    try:
        yield group_name
    finally:
        # Delete the added group
        group_info = group.info(group_name)
        if group_info:
            group.delete(group_name)


@pytest.fixture(scope="function")
def existing_group_name(group):
    group_name = random_string("group-", lowercase=False)
    try:
        ret = group.add(group_name, 4567)
        if ret is not True:
            pytest.skip("Failed to create a group to delete")
        yield group_name
    finally:
        # Delete the added group
        group_info = group.info(group_name)
        if group_info:
            group.delete(group_name)


@pytest.fixture(scope="function")
def non_existing_user(group):
    group_name = random_string("user-", lowercase=False)
    try:
        yield group_name
    finally:
        # Delete the added group
        group_info = group.info(group_name)
        if group_info:
            group.delete(group_name)


@pytest.fixture(scope="function")
def existing_user(group, existing_group_name):
    group_name = random_string("user-", lowercase=False)
    try:
        ret = group.adduser(existing_group_name, group_name)
        if ret is not True:
            pytest.skip("Failed to create an existing group member")
        yield group_name
    finally:
        # Delete the added group
        group_info = group.info(group_name)
        if group_info:
            group.delete(group_name)


@pytest.fixture(scope="module")
def rep_user_group():
    yield random_string("RS-", lowercase=False)


@pytest.fixture(scope="function")
def non_existing_group_member(group):
    group_name = random_string("user-", lowercase=False)
    try:
        yield group_name
    finally:
        # Delete the added group
        group_info = group.info(group_name)
        if group_info:
            group.delete(group_name)


def test_mac_group_add(group, non_existing_group_name):
    """
    Tests the add group function
    """
    group.add(non_existing_group_name, 3456)
    group_info = group.info(non_existing_group_name)
    assert group_info["name"] == non_existing_group_name


def test_mac_group_delete(group, existing_group_name):
    """
    Tests the delete group function
    """
    ret = group.delete(existing_group_name)
    assert ret


def test_mac_group_chgid(group, existing_group_name):
    """
    Tests changing the group id
    """
    gid = 6789
    group_info = group.info(existing_group_name)
    assert group_info["gid"] != gid
    group.chgid(existing_group_name, gid)
    group_info = group.info(existing_group_name)
    assert group_info["gid"] == gid


def test_mac_adduser(group, non_existing_group_name, non_existing_user):
    """
    Tests adding user to the group
    """
    # Create a group to use for test - If unsuccessful, skip the test
    ret = group.add(non_existing_group_name, 5678)
    if ret is not True:
        group.delete(non_existing_group_name)
        pytest.skip("Failed to create a group to manipulate")

    group.adduser(non_existing_group_name, non_existing_user)
    group_info = group.info(non_existing_group_name)
    assert non_existing_user in group_info["members"]
    assert group_info["members"] == [non_existing_user]


def test_mac_deluser(group, existing_group_name, existing_user):
    """
    Test deleting user from a group
    """
    delusr = group.deluser(existing_group_name, existing_user)
    assert delusr

    group_info = group.info(existing_group_name)
    assert existing_user not in group_info["members"]


def test_mac_members(
    group, existing_group_name, existing_user, non_existing_group_member
):
    """
    Test replacing members of a group
    """
    group.members(existing_group_name, existing_user)
    group_info = group.info(existing_group_name)
    assert non_existing_group_member not in group_info["members"]
    assert existing_user in group_info["members"]

    # Replace group members
    rep_group_mem = group.members(existing_group_name, non_existing_group_member)
    assert rep_group_mem

    # ensure new user is added to group and previous user is removed
    group_info = group.info(existing_group_name)
    assert non_existing_group_member in group_info["members"]
    assert existing_user not in group_info["members"]


def test_mac_getent(group, existing_user, existing_group_name):
    """
    Test returning info on all groups
    """
    getinfo = group.getent()
    assert getinfo
    assert existing_group_name in str(getinfo)
    assert existing_user in str(getinfo)
