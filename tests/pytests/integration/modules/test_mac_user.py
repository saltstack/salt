"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""

import os

import pytest
from saltfactories.utils import random_string

import salt.utils.files
from salt.exceptions import CommandExecutionError

# Create user strings for tests

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.destructive_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.skip_unless_on_darwin,
]


@pytest.fixture(scope="function")
def setup_teardown_vars(salt_call_cli):
    ret = salt_call_cli.run("grains.item", "kernel")
    os_grain = ret.data
    if os_grain["kernel"] not in "Darwin":
        pytest.skip("Test not applicable to '{kernel}' kernel".format(**os_grain))

    ADD_USER = random_string("RS-", lowercase=False)
    DEL_USER = random_string("RS-", lowercase=False)
    PRIMARY_GROUP_USER = random_string("RS-", lowercase=False)
    CHANGE_USER = random_string("RS-", lowercase=False)

    try:
        yield ADD_USER, DEL_USER, PRIMARY_GROUP_USER, CHANGE_USER
    finally:
        # Delete ADD_USER
        ret = salt_call_cli.run("user.info", ADD_USER)
        add_info = ret.data
        if add_info:
            salt_call_cli.run("user.delete", ADD_USER)

        # Delete DEL_USER if something failed
        ret = salt_call_cli.run("user.info", DEL_USER)
        del_info = ret.data
        if del_info:
            salt_call_cli.run("user.delete", DEL_USER)

        # Delete CHANGE_USER
        ret = salt_call_cli.run("user.info", CHANGE_USER)
        change_info = ret.data
        if change_info:
            salt_call_cli.run("user.delete", CHANGE_USER)


def test_mac_user_add(salt_call_cli, setup_teardown_vars):
    """
    Tests the add function
    """
    ADD_USER = setup_teardown_vars[0]

    try:
        salt_call_cli.run("user.add", ADD_USER)
        ret = salt_call_cli.run("user.info", ADD_USER)
        user_info = ret.data
        assert ADD_USER == user_info["name"]
    except CommandExecutionError:
        salt_call_cli.run("user.delete", ADD_USER)
        raise


@pytest.mark.slow_test
def test_mac_user_delete(salt_call_cli, setup_teardown_vars):
    """
    Tests the delete function
    """
    DEL_USER = setup_teardown_vars[1]

    # Create a user to delete - If unsuccessful, skip the test
    ret = salt_call_cli.run("user.add", DEL_USER)
    if ret.data is not True:
        salt_call_cli.run("user.delete", DEL_USER)
        pytest.skip("Failed to create a user to delete")

    # Now try to delete the added user
    ret = salt_call_cli.run("user.delete", DEL_USER)
    assert ret.data


@pytest.mark.slow_test
def test_mac_user_primary_group(salt_call_cli, setup_teardown_vars):
    """
    Tests the primary_group function
    """
    PRIMARY_GROUP_USER = setup_teardown_vars[2]

    # Create a user to test primary group function
    ret = salt_call_cli.run("user.add", PRIMARY_GROUP_USER)
    if ret.data is not True:
        salt_call_cli.run("user.delete", PRIMARY_GROUP_USER)
        pytest.skip("Failed to create a user")

    try:
        # Test mac_user.primary_group
        ret = salt_call_cli.run("user.primary_group", PRIMARY_GROUP_USER)
        primary_group = ret.data
        ret = salt_call_cli.run("user.info", PRIMARY_GROUP_USER)
        uid_info = ret.data
        assert primary_group in uid_info["groups"]

    except AssertionError:
        salt_call_cli.run("user.delete", PRIMARY_GROUP_USER)
        raise


@pytest.mark.slow_test
def test_mac_user_changes(salt_call_cli, setup_teardown_vars):
    """
    Tests mac_user functions that change user properties
    """
    CHANGE_USER = setup_teardown_vars[3]

    # Create a user to manipulate - if unsuccessful, skip the test
    ret = salt_call_cli.run("user.add", CHANGE_USER)
    if ret.data is not True:
        salt_call_cli.run("user.delete", CHANGE_USER)
        pytest.skip("Failed to create a user")

    try:
        # Test mac_user.chuid
        salt_call_cli.run("user.chuid", CHANGE_USER, 4376)
        ret = salt_call_cli.run("user.info", CHANGE_USER)
        uid_info = ret.data
        assert uid_info["uid"] == 4376

        # Test mac_user.chgid
        salt_call_cli.run("user.chgid", CHANGE_USER, 4376)
        ret = salt_call_cli.run("user.info", CHANGE_USER)
        gid_info = ret.data
        assert gid_info["gid"] == 4376

        # Test mac.user.chshell
        salt_call_cli.run("user.chshell", CHANGE_USER, "/bin/zsh")
        shell_info = salt_call_cli.run("user.info", CHANGE_USER)
        assert shell_info["shell"] == "/bin/zsh"

        # Test mac_user.chhome
        salt_call_cli.run("user.chhome", CHANGE_USER, "/Users/foo")
        ret = salt_call_cli.run("user.info", CHANGE_USER)
        home_info = ret.data
        assert home_info["home"] == "/Users/foo"

        # Test mac_user.chfullname
        salt_call_cli.run("user.chfullname", CHANGE_USER, "Foo Bar")
        ret = salt_call_cli.run("user.info", CHANGE_USER)
        fullname_info = ret.data
        assert fullname_info["fullname"] == "Foo Bar"

        # Test mac_user.chgroups
        ret = salt_call_cli.run("user.info", CHANGE_USER)["groups"]
        pre_info = ret.data
        expected = pre_info + ["wheel"]
        salt_call_cli.run("user.chgroups", CHANGE_USER, "wheel")
        ret = salt_call_cli.run("user.info", CHANGE_USER)
        groups_info = ret.data
        assert groups_info["groups"] == expected

    except AssertionError:
        salt_call_cli.run("user.delete", CHANGE_USER)
        raise


@pytest.mark.slow_test
def test_mac_user_enable_auto_login(salt_call_cli):
    """
    Tests mac_user functions that enable auto login
    """
    # Make sure auto login is disabled before we start
    if salt_call_cli.run("user.get_auto_login"):
        pytest.skip("Auto login already enabled")

    try:
        # Does enable return True
        ret = salt_call_cli.run("user.enable_auto_login", ["Spongebob", "Squarepants"])
        assert ret.data

        # Did it set the user entry in the plist file
        ret = salt_call_cli.run("user.get_auto_login")
        assert ret.data == "Spongebob"

        # Did it generate the `/etc/kcpassword` file
        assert os.path.exists("/etc/kcpassword")

        # Are the contents of the file correct
        test_data = bytes.fromhex("2e f8 27 42 a0 d9 ad 8b cd cd 6c 7d")
        with salt.utils.files.fopen("/etc/kcpassword", "rb") as f:
            file_data = f.read()
        assert test_data == file_data

        # Does disable return True
        ret = salt_call_cli.run("user.disable_auto_login")
        assert ret.data

        # Does it remove the user entry in the plist file
        ret = salt_call_cli.run("user.get_auto_login")
        assert not ret

        # Is the `/etc/kcpassword` file removed
        assert not os.path.exists("/etc/kcpassword")

    finally:
        # Make sure auto_login is disabled
        ret = salt_call_cli.run("user.disable_auto_login")
        assert ret.data

        # Make sure autologin is disabled
        ret = salt_call_cli.run("user.get_auto_login")
        if ret.data:
            raise Exception("Failed to disable auto login")


@pytest.mark.slow_test
def test_mac_user_disable_auto_login(salt_call_cli):
    """
    Tests mac_user functions that disable auto login
    """
    # Make sure auto login is enabled before we start
    # Is there an existing setting
    if salt_call_cli.run("user.get_auto_login"):
        pytest.skip("Auto login already enabled")

    try:
        # Enable auto login for the test
        salt_call_cli.run("user.enable_auto_login", ["Spongebob", "Squarepants"])

        # Make sure auto login got set up
        ret = salt_call_cli.run("user.get_auto_login")
        if not ret.data == "Spongebob":
            raise Exception("Failed to enable auto login")

        # Does disable return True
        ret = salt_call_cli.run("user.disable_auto_login")
        assert ret.data

        # Does it remove the user entry in the plist file
        ret = salt_call_cli.run("user.get_auto_login")
        assert not ret.data

        # Is the `/etc/kcpassword` file removed
        assert not os.path.exists("/etc/kcpassword")

    finally:
        # Make sure auto login is disabled
        ret = salt_call_cli.run("user.disable_auto_login")
        assert ret.data

        # Make sure auto login is disabled
        ret = salt_call_cli.run("user.get_auto_login")
        if ret.data:
            raise Exception("Failed to disable auto login")
