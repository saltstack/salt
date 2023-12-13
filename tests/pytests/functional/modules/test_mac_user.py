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


@pytest.fixture
def _reset_enable_auto_login(user):
    # Make sure auto login is disabled before we start
    if user.get_auto_login():
        pytest.skip("Auto login already enabled")

    try:
        yield
    finally:
        # Make sure auto_login is disabled
        ret = user.disable_auto_login()
        assert ret

        # Make sure autologin is disabled
        ret = user.get_auto_login()
        if ret:
            pytest.fail("Failed to disable auto login")


@pytest.fixture
def existing_user(user):
    username = random_string("account-", uppercase=False)
    try:
        ret = user.add(username)
        if ret is not True:
            pytest.skip("Failed to create an account to manipulate")
        yield username
    finally:
        user_info = user.info(username)
        if user_info:
            user.delete(username)


@pytest.fixture
def non_existing_user(user):
    username = random_string("account-", uppercase=False)
    try:
        yield username
    finally:
        user_info = user.info(username)
        if user_info:
            user.delete(username)


def test_mac_user_add(user, non_existing_user):
    """
    Tests the add function
    """
    user.add(non_existing_user)
    user_info = user.info(non_existing_user)
    assert user_info["name"] == non_existing_user


def test_mac_user_delete(user, existing_user):
    """
    Tests the delete function
    """
    ret = user.delete(existing_user)
    assert ret


def test_mac_user_primary_group(user, existing_user):
    """
    Tests the primary_group function
    """
    primary_group = user.primary_group(existing_user)
    uid_info = user.info(existing_user)
    assert primary_group in uid_info["groups"]


def test_mac_user_changes(user, existing_user):
    """
    Tests mac_user functions that change user properties
    """
    # Test mac_user.chuid
    user.chuid(existing_user, 4376)
    uid_info = user.info(existing_user)
    assert uid_info["uid"] == 4376

    # Test mac_user.chgid
    user.chgid(existing_user, 4376)
    gid_info = user.info(existing_user)
    assert gid_info["gid"] == 4376

    # Test mac.user.chshell
    user.chshell(existing_user, "/bin/zsh")
    shell_info = user.info(existing_user)
    assert shell_info["shell"] == "/bin/zsh"

    # Test mac_user.chhome
    user.chhome(existing_user, "/Users/foo")
    home_info = user.info(existing_user)
    assert home_info["home"] == "/Users/foo"

    # Test mac_user.chfullname
    user.chfullname(existing_user, "Foo Bar")
    fullname_info = user.info(existing_user)
    assert fullname_info["fullname"] == "Foo Bar"

    # Test mac_user.chgroups
    ret = user.info(existing_user)
    pre_info = ret["groups"]
    expected = pre_info + ["wheel"]
    user.chgroups(existing_user, "wheel")
    groups_info = user.info(existing_user)
    assert groups_info["groups"] == expected


@pytest.mark.usefixtures("_reset_enable_auto_login")
def test_mac_user_enable_auto_login(user):
    """
    Tests mac_user functions that enable auto login
    """
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


@pytest.mark.usefixtures("_reset_enable_auto_login")
def test_mac_user_disable_auto_login(user):
    """
    Tests mac_user functions that disable auto login
    """
    # Enable auto login for the test
    user.enable_auto_login("Spongebob", "Squarepants")

    # Make sure auto login got set up
    ret = user.get_auto_login()
    if not ret == "Spongebob":
        raise pytest.fail("Failed to enable auto login")

    # Does disable return True
    ret = user.disable_auto_login()
    assert ret

    # Does it remove the user entry in the plist file
    ret = user.get_auto_login()
    assert not ret

    # Is the `/etc/kcpassword` file removed
    assert not os.path.exists("/etc/kcpassword")
