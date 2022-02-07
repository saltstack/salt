"""
tests for user state
user absent
user present
user present with custom homedir
"""

import pathlib
import shutil
import sys

import pytest
import salt.utils.files
import salt.utils.platform
from saltfactories.utils import random_string

try:
    import grp
except ImportError:
    grp = None

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.destructive_test,
    pytest.mark.windows_whitelisted,
]

ANSI_FILESYSTEM_ENCODING = sys.getfilesystemencoding().startswith("ANSI")


@pytest.fixture
def username(sminion):
    _username = random_string("new-account-", uppercase=False)
    try:
        yield _username
    finally:
        try:
            sminion.functions.user.delete(_username, remove=True, force=True)
        except Exception:  # pylint: disable=broad-except
            # The point here is just system cleanup. It can fail if no account was created
            pass


@pytest.fixture
def user_home(username, tmp_path):
    if salt.utils.platform.is_windows():
        return tmp_path / username

    return pathlib.Path("/var/lib") / username


@pytest.fixture
def group_1(username):
    groupname = username
    if salt.utils.platform.is_darwin():
        groupname = "staff"
    with pytest.helpers.create_group(name=groupname) as group:
        yield group


@pytest.fixture
def group_2():
    with pytest.helpers.create_group() as group:
        yield group


@pytest.fixture
def existing_account():
    with pytest.helpers.create_account(create_group=True) as _account:
        yield _account


def test_user_absent(states):
    """
    Test user.absent with a non existing account
    """
    ret = states.user.absent(name=random_string("account-", uppercase=False))
    assert ret.result is True


def test_user_absent_existing_account(states, existing_account):
    """
    Test user.absent with an existing account
    """
    ret = states.user.absent(name=existing_account.username)
    assert ret.result is True


def test_user_present(states, username):
    """
    Test user.present with a non existing account
    """
    ret = states.user.present(name=username)
    assert ret.result is True


def test_user_present_with_existing_group(states, username, existing_account):
    ret = states.user.present(username, gid=existing_account.group.info.gid)
    assert ret.result is True


@pytest.mark.skip_on_windows(
    reason="Home directories are handled differently in Windows"
)
def test_user_present_when_home_dir_does_not_18843(states, existing_account):
    """
    User exists but home directory does not. Home directory get's created
    """
    shutil.rmtree(existing_account.info.home)
    ret = states.user.present(
        name=existing_account.username, home=existing_account.info.home
    )
    assert ret.result is True
    assert pathlib.Path(existing_account.info.home).is_dir()


def test_user_present_nondefault(grains, modules, states, username, user_home):
    ret = states.user.present(name=username, home=str(user_home))
    assert ret.result is True

    user_info = modules.user.info(username)
    assert user_info

    if salt.utils.platform.is_windows():
        group_name = modules.user.list_groups(username)
    else:
        group_name = grp.getgrgid(user_info["gid"]).gr_name

    if not salt.utils.platform.is_darwin() and not salt.utils.platform.is_windows():
        assert user_home.is_dir()

    if grains["os_family"] in ("Suse",):
        expected_group_name = "users"
    elif grains["os_family"] == "MacOS":
        expected_group_name = "staff"
    elif salt.utils.platform.is_windows():
        expected_group_name = []
    else:
        expected_group_name = username
    assert group_name == expected_group_name


@pytest.mark.skip_on_windows(reason="windows minion does not support 'usergroup'")
def test_user_present_usergroup_false(modules, states, username, group_1, user_home):
    ret = states.user.present(
        name=username,
        gid=group_1.info.gid,
        usergroup=False,
        home=str(user_home),
    )
    assert ret.result is True

    if not salt.utils.platform.is_darwin():
        assert user_home.is_dir()

    user_info = modules.user.info(username)
    assert user_info

    group_name = grp.getgrgid(user_info["gid"]).gr_name
    assert group_name == group_1.name


@pytest.mark.skip_on_windows(reason="windows minion does not support 'usergroup'")
def test_user_present_usergroup_true(modules, states, username, user_home, group_1):
    ret = states.user.present(
        name=username,
        gid=group_1.info.gid,
        usergroup=True,
        home=str(user_home),
    )
    assert ret.result is True

    if not salt.utils.platform.is_darwin():
        assert user_home.is_dir()

    user_info = modules.user.info(username)
    assert user_info

    group_name = grp.getgrgid(user_info["gid"]).gr_name
    assert group_name == group_1.name


@pytest.mark.skipif(
    ANSI_FILESYSTEM_ENCODING,
    reason=(
        "A system encoding which supports Unicode characters must be set. Current setting is: {}. "
        "Try setting $LANG='en_US.UTF-8'".format(ANSI_FILESYSTEM_ENCODING)
    ),
)
def test_user_present_unicode(states, username, subtests):
    """
    It ensures that unicode GECOS data will be properly handled, without
    any encoding-related failures.
    """
    with subtests.test("Non existing account"):
        ret = states.user.present(
            name=username,
            fullname="Sålt Test",
            roomnumber="①②③",
            workphone="١٢٣٤",
            homephone="६७८",
        )
        assert ret.result is True

    with subtests.test("Update existing account"):
        ret = states.user.present(
            name=username,
            fullname="Sålt Test",
            roomnumber="①②③",
            workphone="١٢٣٤",
            homephone="६७८",
        )
        assert ret.result is True


@pytest.mark.skip_on_windows(
    reason="windows minion does not support roomnumber or phone",
)
def test_user_present_gecos(modules, states, username):
    """
    It ensures that numeric GECOS data will be properly coerced to strings,
    otherwise the state will fail because the GECOS fields are written as
    strings (and show up in the user.info output as such). Thus the
    comparison will fail, since '12345' != 12345.
    """
    fullname = 123345
    roomnumber = 123
    workphone = homephone = 1234567890
    ret = states.user.present(
        name=username,
        fullname=fullname,
        roomnumber=roomnumber,
        workphone=workphone,
        homephone=homephone,
    )
    assert ret.result is True

    user_info = modules.user.info(username)
    assert user_info

    assert user_info["fullname"] == str(fullname)
    if not salt.utils.platform.is_darwin():
        # MacOS does not supply the following GECOS fields
        assert user_info["roomnumber"] == str(roomnumber)
        assert user_info["workphone"] == str(workphone)
        assert user_info["homephone"] == str(homephone)


@pytest.mark.skip_on_windows(
    reason="windows minion does not support roomnumber or phone",
)
def test_user_present_gecos_empty_fields(modules, states, username):
    """
    It ensures that if no GECOS data is supplied, the fields will be coerced
    into empty strings as opposed to the string "None".
    """
    fullname = roomnumber = workphone = homephone = ""
    ret = states.user.present(
        name=username,
        fullname=fullname,
        roomnumber=roomnumber,
        workphone=workphone,
        homephone=homephone,
    )
    assert ret.result is True

    user_info = modules.user.info(username)
    assert user_info

    assert user_info["fullname"] == fullname
    if not salt.utils.platform.is_darwin():
        # MacOS does not supply the following GECOS fields
        assert user_info["roomnumber"] == roomnumber
        assert user_info["workphone"] == workphone
        assert user_info["homephone"] == homephone


@pytest.mark.skip_on_windows(reason="windows minion does not support createhome")
@pytest.mark.parametrize("createhome", [True, False])
def test_user_present_home_directory_created(modules, states, username, createhome):
    """
    It ensures that the home directory is created.
    """
    ret = states.user.present(name=username, createhome=createhome)
    assert ret.result is True

    user_info = modules.user.info(username)
    assert user_info

    assert pathlib.Path(user_info["home"]).is_dir() is createhome


@pytest.mark.skip_on_darwin(reason="groups/gid not fully supported")
@pytest.mark.skip_on_windows(reason="groups/gid not fully supported")
def test_user_present_change_gid_but_keep_group(
    modules, states, username, group_1, group_2
):
    """
    This tests the case in which the default group is changed at the same
    time as it is also moved into the "groups" list.
    """

    # Add the user
    ret = states.user.present(name=username, gid=group_1.info.gid)
    assert ret.result is True

    user_info = modules.user.info(username)
    assert user_info

    assert user_info["gid"] == group_1.info.gid
    assert user_info["groups"] == [group_1.name]

    # Now change the gid and move alt_group to the groups list in the
    # same salt run.
    ret = states.user.present(
        name=username,
        gid=group_2.info.gid,
        groups=[group_1.name],
        allow_gid_change=True,
    )
    assert ret.result is True

    # Be sure that we did what we intended
    user_info = modules.user.info(username)
    assert user_info

    assert user_info["gid"] == group_2.info.gid
    assert user_info["groups"] == [group_2.name, group_1.name]


@pytest.mark.skip_unless_on_windows
def test_user_present_existing(states, username):
    win_profile = "C:\\User\\{}".format(username)
    win_logonscript = "C:\\logon.vbs"
    win_description = "Test User Account"
    ret = states.user.present(
        name=username,
        win_homedrive="U:",
        win_profile=win_profile,
        win_logonscript=win_logonscript,
        win_description=win_description,
    )
    assert ret.result is True

    win_profile = "C:\\Users\\{}".format(username)
    win_description = "Temporary Account"
    ret = states.user.present(
        name=username,
        win_homedrive="R:",
        win_profile=win_profile,
        win_logonscript=win_logonscript,
        win_description=win_description,
    )
    assert ret.result is True
    assert ret.changes
    assert "homedrive" in ret.changes
    assert ret.changes["homedrive"] == "R:"
    assert "profile" in ret.changes
    assert ret.changes["profile"] == win_profile
    assert "description" in ret.changes
    assert ret.changes["description"] == win_description
