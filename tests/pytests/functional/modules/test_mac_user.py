"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""

import os

import pytest
from saltfactories.utils import random_string

import salt.utils.files

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.destructive_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.skip_unless_on_darwin,
]


@pytest.fixture(scope="module")
def user(modules):
    return modules.user


@pytest.fixture(scope="function")
def setup_teardown_vars(user):
    ADD_USER = random_string("RS-", lowercase=False)
    DEL_USER = random_string("RS-", lowercase=False)
    PRIMARY_GROUP_USER = random_string("RS-", lowercase=False)
    CHANGE_USER = random_string("RS-", lowercase=False)

    try:
        yield ADD_USER, DEL_USER, PRIMARY_GROUP_USER, CHANGE_USER
    finally:
        # Delete ADD_USER
        add_info = user.info(ADD_USER)
        if add_info:
            user.delete(ADD_USER)

        # Delete DEL_USER if something failed
        del_info = user.info(DEL_USER)
        if del_info:
            user.delete(DEL_USER)

        # Delete CHANGE_USER
        change_info = user.info(CHANGE_USER)
        if change_info:
            user.delete(CHANGE_USER)


def test_mac_user_add(user, setup_teardown_vars):
    """
    Tests the add function
    """
    ADD_USER = setup_teardown_vars[0]

    user.add(ADD_USER)
    user_info = user.info(ADD_USER)
    assert ADD_USER == user_info["name"]


@pytest.mark.slow_test
def test_mac_user_delete(user, setup_teardown_vars):
    """
    Tests the delete function
    """
    DEL_USER = setup_teardown_vars[1]

    # Create a user to delete - If unsuccessful, skip the test
    ret = user.add(DEL_USER)
    if ret is not True:
        user.delete(DEL_USER)
        pytest.skip("Failed to create a user to delete")

    # Now try to delete the added user
    ret = user.delete(DEL_USER)
    assert ret


@pytest.mark.slow_test
def test_mac_user_primary_group(user, setup_teardown_vars):
    """
    Tests the primary_group function
    """
    PRIMARY_GROUP_USER = setup_teardown_vars[2]

    # Create a user to test primary group function
    ret = user.add(PRIMARY_GROUP_USER)
    if ret is not True:
        user.delete(PRIMARY_GROUP_USER)
        pytest.skip("Failed to create a user")

    # Test mac_user.primary_group
    primary_group = user.primary_group(PRIMARY_GROUP_USER)
    uid_info = user.info(PRIMARY_GROUP_USER)
    assert primary_group in uid_info["groups"]


@pytest.mark.slow_test
def test_mac_user_changes(user, setup_teardown_vars):
    """
    Tests mac_user functions that change user properties
    """
    CHANGE_USER = setup_teardown_vars[3]

    # Create a user to manipulate - if unsuccessful, skip the test
    ret = user.add(CHANGE_USER)
    if ret is not True:
        user.delete(CHANGE_USER)
        pytest.skip("Failed to create a user")

    # Test mac_user.chuid
    user.chuid(CHANGE_USER, 4376)
    uid_info = user.info(CHANGE_USER)
    assert uid_info["uid"] == 4376

    # Test mac_user.chgid
    user.chgid(CHANGE_USER, 4376)
    gid_info = user.info(CHANGE_USER)
    assert gid_info["gid"] == 4376

    # Test mac.user.chshell
    user.chshell(CHANGE_USER, "/bin/zsh")
    shell_info = user.info(CHANGE_USER)
    assert shell_info["shell"] == "/bin/zsh"

    # Test mac_user.chhome
    user.chhome(CHANGE_USER, "/Users/foo")
    home_info = user.info(CHANGE_USER)
    assert home_info["home"] == "/Users/foo"

    # Test mac_user.chfullname
    user.chfullname(CHANGE_USER, "Foo Bar")
    fullname_info = user.info(CHANGE_USER)
    assert fullname_info["fullname"] == "Foo Bar"

    # Test mac_user.chgroups
    ret = user.info(CHANGE_USER)
    pre_info = ret["groups"]
    expected = pre_info + ["wheel"]
    user.chgroups(CHANGE_USER, "wheel")
    groups_info = user.info(CHANGE_USER)
    assert groups_info["groups"] == expected


@pytest.mark.slow_test
def test_mac_user_enable_auto_login(user):
    """
    Tests mac_user functions that enable auto login
    """
    # Make sure auto login is disabled before we start
    if user.get_auto_login():
        pytest.skip("Auto login already enabled")

    try:
        # Does enable return True
        ret = user.enable_auto_login("Spongebob", "Squarepants")
        assert ret

        # Did it set the user entry in the plist file
        ret = user.get_auto_login()
        assert ret == "Spongebob"

        # Did it generate the `/etc/kcpassword` file
        assert os.path.exists("/etc/kcpassword")

        # Are the contents of the file correct
        test_data = bytes.fromhex("2e f8 27 42 a0 d9 ad 8b cd cd 6c 7d")
        with salt.utils.files.fopen("/etc/kcpassword", "rb") as f:
            file_data = f.read()
        assert test_data == file_data

        # Does disable return True
        ret = user.disable_auto_login()
        assert ret

        # Does it remove the user entry in the plist file
        ret = user.get_auto_login()
        assert not ret

        # Is the `/etc/kcpassword` file removed
        assert not os.path.exists("/etc/kcpassword")

    finally:
        # Make sure auto_login is disabled
        ret = user.disable_auto_login()
        assert ret

        # Make sure autologin is disabled
        ret = user.get_auto_login()
        if ret:
            raise Exception("Failed to disable auto login")


@pytest.mark.slow_test
def test_mac_user_disable_auto_login(user):
    """
    Tests mac_user functions that disable auto login
    """
    # Make sure auto login is enabled before we start
    # Is there an existing setting
    if user.get_auto_login():
        pytest.skip("Auto login already enabled")

    try:
        # Enable auto login for the test
        user.enable_auto_login("Spongebob", "Squarepants")

        # Make sure auto login got set up
        ret = user.get_auto_login()
        if not ret == "Spongebob":
            raise Exception("Failed to enable auto login")

        # Does disable return True
        ret = user.disable_auto_login()
        assert ret

        # Does it remove the user entry in the plist file
        ret = user.get_auto_login()
        assert not ret

        # Is the `/etc/kcpassword` file removed
        assert not os.path.exists("/etc/kcpassword")

    finally:
        # Make sure auto login is disabled
        ret = user.disable_auto_login()
        assert ret

        # Make sure auto login is disabled
        ret = user.get_auto_login()
        if ret:
            raise Exception("Failed to disable auto login")
