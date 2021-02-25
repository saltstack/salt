"""
Integration tests for modules/useradd.py and modules/win_useradd.py.
"""
import pytest
from tests.support.helpers import random_string, requires_system_grains, runs_on

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
]


@runs_on(kernel="Linux")
@pytest.mark.destructive_test
@pytest.mark.skip_if_not_root
@requires_system_grains
def test_groups_includes_primary(grains, salt_call_cli):
    # Let's create a user, which usually creates the group matching the
    # name
    uname = random_string("RS-", lowercase=False)
    if salt_call_cli.run("user.add", [uname]) is not True:
        # Skip because creating is not what we're testing here
        salt_call_cli.run("user.delete", [uname, True, True])
        pytest.skip(reason="Failed to create user")

    try:
        uinfo = salt_call_cli.run("user.info", [uname])
        if grains["os_family"] in ("Suse",):
            assert "users" in uinfo["groups"]
        else:
            assert uname in uinfo["groups"]

        # This uid is available, store it
        uid = uinfo["uid"]

        salt_call_cli.run("user.delete", [uname, True, True])

        # Now, a weird group id
        gname = random_string("RS-", lowercase=False)
        if salt_call_cli.run("group.add", [gname]) is not True:
            salt_call_cli.run("group.delete", [gname, True, True])
            pytest.skip(reason="Failed to create group")

        ginfo = salt_call_cli.run("group.info", [gname])

        # And create the user with that gid
        if salt_call_cli.run("user.add", [uname, uid, ginfo["gid"]]) is False:
            # Skip because creating is not what we're testing here
            salt_call_cli.run("user.delete", [uname, True, True])
            pytest.skip(reason="Failed to create user")

        uinfo = salt_call_cli.run("user.info", [uname])
        assert gname in uinfo["groups"]

    except AssertionError:
        pytest.raises(salt_call_cli.run("user.delete", [uname, True, True]))


def test_user_primary_group(salt_call_cli):
    """
    Tests the primary_group function
    """
    name = "saltyuser"

    # Create a user to test primary group function
    if salt_call_cli.run("user.add", [name]) is not True:
        salt_call_cli.run("user.delete", [name])
        pytest.skip(reason="Failed to create a user")

    try:
        # Test useradd.primary_group
        primary_group = salt_call_cli.run("user.primary_group", [name])
        uid_info = salt_call_cli.run("user.info", [name])
        assert primary_group in uid_info["groups"]

    except Exception:  # pylint: disable=broad-except
        pytest.raises(salt_call_cli.run("user.delete", [name]))


@runs_on(kernel="Windows")
@pytest.mark.destructive_test
@pytest.mark.skip_if_not_root
@pytest.fixture(scope="function")
def setup_teardown_vars(salt_call_cli):
    user_name = random_string("RS-", lowercase=False)
    group_name = random_string("RS-", lowercase=False)
    try:
        yield user_name, group_name
    finally:
        salt_call_cli.run("user.delete", [user_name, True, True])
        salt_call_cli.run("group.delete", [group_name])


@pytest.mark.destructive_test
def test_add_user(setup_teardown_vars, salt_call_cli):
    """
    Test adding a user.
    """
    user_name = setup_teardown_vars[0]
    salt_call_cli.run("user.add", user_name)
    user_add = salt_call_cli.run("user.list_users")
    assert user_name in user_add.json


@pytest.mark.destructive_test
def test_add_group(setup_teardown_vars, salt_call_cli):
    """
    Test adding a user and check its apart of a group.
    """
    group_name = setup_teardown_vars[1]
    salt_call_cli.run("group.add", group_name)
    group_list = salt_call_cli.run("group.list_groups")
    assert group_name in group_list.json


@pytest.mark.destructive_test
def test_add_user_to_group(setup_teardown_vars, salt_call_cli):
    """
    Test adding a user to a group.
    """
    user_name = setup_teardown_vars[0]
    group_name = setup_teardown_vars[1]

    salt_call_cli.run("group.add", group_name)
    # And create the user as a member of that group
    salt_call_cli.run("user.add", user_name, groups=group_name)

    user_info = salt_call_cli.run("user.info", user_name)
    assert group_name in user_info.json["groups"]


@pytest.mark.destructive_test
def test_add_user_addgroup(setup_teardown_vars, salt_call_cli):
    """
    Test adding a user to a group with groupadd.
    """
    user_name = setup_teardown_vars[0]
    group_name = setup_teardown_vars[1]

    salt_call_cli.run("group.add", group_name)
    salt_call_cli.run("user.add", user_name)

    salt_call_cli.run("user.addgroup", user_name, group_name)
    info = salt_call_cli.run("user.info", user_name)
    assert [group_name] == info.json["groups"]


@pytest.mark.destructive_test
def test_user_chhome(setup_teardown_vars, salt_call_cli):
    """
    Test changing a users home dir.
    """
    user_dir = r"c:\salt"
    user_name = setup_teardown_vars[0]
    salt_call_cli.run("user.add", user_name)
    salt_call_cli.run("user.chhome", user_name, user_dir)

    info = salt_call_cli.run("user.info", user_name)
    assert user_dir == info.json["home"]


@pytest.mark.destructive_test
def test_user_chprofile(setup_teardown_vars, salt_call_cli):
    """
    Test changing a users profile.
    """
    config = r"c:\salt\config"
    user_name = setup_teardown_vars[0]
    salt_call_cli.run("user.add", user_name)

    salt_call_cli.run("user.chprofile", user_name, config)
    info = salt_call_cli.run("user.info", user_name)
    assert config == info.json["profile"]


@pytest.mark.destructive_test
def test_user_chfullname(setup_teardown_vars, salt_call_cli):
    """
    Test changing a users fullname.
    """
    name = "Salt Test"
    user_name = setup_teardown_vars[0]
    salt_call_cli.run("user.add", user_name)

    salt_call_cli.run("user.chfullname", user_name, name)
    info = salt_call_cli.run("user.info", user_name)
    assert name == info.json["fullname"]


@pytest.mark.destructive_test
def test_user_delete(setup_teardown_vars, salt_call_cli):
    """
    Test deleting a user.
    """
    user_name = setup_teardown_vars[0]
    salt_call_cli.run("user.add", user_name)
    salt_call_cli.run("user.delete", user_name)
    ret = salt_call_cli.run("user.info", user_name)
    assert {} == ret.json


@pytest.mark.destructive_test
def test_user_removegroup(setup_teardown_vars, salt_call_cli):
    """
    Test removing a group.
    """
    user_name = setup_teardown_vars[0]
    group_name = setup_teardown_vars[1]

    salt_call_cli.run("user.add", user_name)
    salt_call_cli.run("group.add", group_name)

    salt_call_cli.run("user.addgroup", user_name, group_name)
    ret = salt_call_cli.run("user.list_groups", user_name)
    assert [group_name] == ret.json

    salt_call_cli.run("user.removegroup", user_name, group_name)
    ret = salt_call_cli.run("user.list_groups", user_name)
    assert [group_name] not in ret.json


@pytest.mark.destructive_test
def test_user_rename(setup_teardown_vars, salt_call_cli):
    """
    Test changing a users name.
    """
    name = "newuser"
    user_name = setup_teardown_vars[0]
    salt_call_cli.run("user.add", user_name)

    salt_call_cli.run("user.rename", user_name, name)
    info = salt_call_cli.run("user.info", name)

    assert info.json["active"] is True


@pytest.mark.destructive_test
def test_user_setpassword(setup_teardown_vars, salt_call_cli):
    """
    Test setting a password.
    """
    passwd = "sup3rs3cr3T!"
    user_name = setup_teardown_vars[0]

    salt_call_cli.run("user.add", user_name)
    ret = salt_call_cli.run("user.setpassword", user_name, passwd)
    assert ret.json is True
