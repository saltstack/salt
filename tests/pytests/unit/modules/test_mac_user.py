"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""

import pytest
import salt.modules.mac_user as mac_user
from salt.exceptions import CommandExecutionError, SaltInvocationError
from tests.support.mock import MagicMock, patch

pwd = pytest.importorskip("pwd")


@pytest.fixture
def configure_loader_modules():
    return {mac_user: {}}


@pytest.fixture
def mock_pwall():
    return [
        pwd.struct_passwd(
            (
                "_amavisd",
                "*",
                83,
                83,
                "AMaViS Daemon",
                "/var/virusmails",
                "/usr/bin/false",
            )
        ),
        pwd.struct_passwd(
            (
                "_appleevents",
                "*",
                55,
                55,
                "AppleEvents Daemon",
                "/var/empty",
                "/usr/bin/false",
            )
        ),
        pwd.struct_passwd(
            (
                "_appowner",
                "*",
                87,
                87,
                "Application Owner",
                "/var/empty",
                "/usr/bin/false",
            )
        ),
    ]


@pytest.fixture
def mock_info_ret():
    return {
        "shell": "/bin/bash",
        "name": "test",
        "gid": 4376,
        "groups": ["TEST_GROUP"],
        "home": "/Users/foo",
        "fullname": "TEST USER",
        "uid": 4376,
    }


@pytest.mark.skipif(
    True, reason="Waiting on some clarifications from bug report #10594"
)
def _test_flush_dscl_cache():
    # TODO: Implement tests after clarifications come in
    pass


def test_dscl():
    """
    Tests the creation of a dscl node
    """
    mac_mock = MagicMock(
        return_value={"pid": 4948, "retcode": 0, "stderr": "", "stdout": ""}
    )
    with patch.dict(mac_user.__salt__, {"cmd.run_all": mac_mock}):
        with patch.dict(
            mac_user.__grains__,
            {"kernel": "Darwin", "osrelease": "10.9.1", "osrelease_info": (10, 9, 1)},
        ):
            assert mac_user._dscl(["username", "UniqueID", 501]) == {
                "pid": 4948,
                "retcode": 0,
                "stderr": "",
                "stdout": "",
            }


def test_first_avail_uid(mock_pwall):
    """
    Tests the availability of the next uid
    """
    with patch("pwd.getpwall", MagicMock(return_value=mock_pwall)):
        assert mac_user._first_avail_uid() == 501


# 'add' function tests: 4
# Only tested error handling
# Full functionality tests covered in integration testing


def test_add_user_exists(mock_info_ret):
    """
    Tests if the user exists or not
    """
    with patch("salt.modules.mac_user.info", MagicMock(return_value=mock_info_ret)):
        pytest.raises(CommandExecutionError, mac_user.add, "test")


def test_add_whitespace():
    """
    Tests if there is whitespace in the user name
    """
    with patch("salt.modules.mac_user.info", MagicMock(return_value={})):
        pytest.raises(SaltInvocationError, mac_user.add, "foo bar")


def test_add_uid_int():
    """
    Tests if the uid is an int
    """
    with patch("salt.modules.mac_user.info", MagicMock(return_value={})):
        pytest.raises(SaltInvocationError, mac_user.add, "foo", "foo")


def test_add_gid_int():
    """
    Tests if the gid is an int
    """
    with patch("salt.modules.mac_user.info", MagicMock(return_value={})):
        pytest.raises(SaltInvocationError, mac_user.add, "foo", 20, "foo")


# 'delete' function tests: 2
# Only tested pure logic of function
# Full functionality tests covered in integration testing


def test_delete_whitespace():
    """
    Tests if there is whitespace in the user name
    """
    pytest.raises(SaltInvocationError, mac_user.delete, "foo bar")


def test_delete_user_exists():
    """
    Tests if the user exists or not
    """
    with patch("salt.modules.mac_user.info", MagicMock(return_value={})):
        assert mac_user.delete("foo")


def test_getent(mock_pwall):
    """
    Tests the list of information for all users
    """
    with patch("pwd.getpwall", MagicMock(return_value=mock_pwall)), patch(
        "salt.modules.mac_user.list_groups", MagicMock(return_value=["TEST_GROUP"])
    ):
        ret = [
            {
                "shell": "/usr/bin/false",
                "name": "_amavisd",
                "gid": 83,
                "groups": ["TEST_GROUP"],
                "home": "/var/virusmails",
                "fullname": "AMaViS Daemon",
                "uid": 83,
            },
            {
                "shell": "/usr/bin/false",
                "name": "_appleevents",
                "gid": 55,
                "groups": ["TEST_GROUP"],
                "home": "/var/empty",
                "fullname": "AppleEvents Daemon",
                "uid": 55,
            },
            {
                "shell": "/usr/bin/false",
                "name": "_appowner",
                "gid": 87,
                "groups": ["TEST_GROUP"],
                "home": "/var/empty",
                "fullname": "Application Owner",
                "uid": 87,
            },
        ]
        assert mac_user.getent() == ret


# 'chuid' function tests: 3
# Only tested pure logic of function
# Full functionality tests covered in integration testing


def test_chuid_int():
    """
    Tests if the uid is an int
    """
    pytest.raises(SaltInvocationError, mac_user.chuid, "foo", "foo")


def test_chuid_user_exists():
    """
    Tests if the user exists or not
    """
    with patch("salt.modules.mac_user.info", MagicMock(return_value={})):
        pytest.raises(CommandExecutionError, mac_user.chuid, "foo", 4376)


def test_chuid_same_uid(mock_info_ret):
    """
    Tests if the user's uid is the same as as the argument
    """
    with patch("salt.modules.mac_user.info", MagicMock(return_value=mock_info_ret)):
        assert mac_user.chuid("foo", 4376)


# 'chgid' function tests: 3
# Only tested pure logic of function
# Full functionality tests covered in integration testing


def test_chgid_int():
    """
    Tests if the gid is an int
    """
    pytest.raises(SaltInvocationError, mac_user.chgid, "foo", "foo")


def test_chgid_user_exists():
    """
    Tests if the user exists or not
    """
    with patch("salt.modules.mac_user.info", MagicMock(return_value={})):
        pytest.raises(CommandExecutionError, mac_user.chgid, "foo", 4376)


def test_chgid_same_gid(mock_info_ret):
    """
    Tests if the user's gid is the same as as the argument
    """
    with patch("salt.modules.mac_user.info", MagicMock(return_value=mock_info_ret)):
        assert mac_user.chgid("foo", 4376)


# 'chshell' function tests: 2
# Only tested pure logic of function
# Full functionality tests covered in integration testing


def test_chshell_user_exists():
    """
    Tests if the user exists or not
    """
    with patch("salt.modules.mac_user.info", MagicMock(return_value={})):
        pytest.raises(CommandExecutionError, mac_user.chshell, "foo", "/bin/bash")


def test_chshell_same_shell(mock_info_ret):
    """
    Tests if the user's shell is the same as the argument
    """
    with patch("salt.modules.mac_user.info", MagicMock(return_value=mock_info_ret)):
        assert mac_user.chshell("foo", "/bin/bash")


# 'chhome' function tests: 2
# Only tested pure logic of function
# Full functionality tests covered in integration testing


def test_chhome_user_exists():
    """
    Test if the user exists or not
    """
    with patch("salt.modules.mac_user.info", MagicMock(return_value={})):
        pytest.raises(CommandExecutionError, mac_user.chhome, "foo", "/Users/foo")


def test_chhome_same_home(mock_info_ret):
    """
    Tests if the user's home is the same as the argument
    """
    with patch("salt.modules.mac_user.info", MagicMock(return_value=mock_info_ret)):
        assert mac_user.chhome("foo", "/Users/foo")


# 'chfullname' function tests: 2
# Only tested pure logic of function
# Full functionality tests covered in integration testing


def test_chfullname_user_exists():
    """
    Tests if the user exists or not
    """
    with patch("salt.modules.mac_user.info", MagicMock(return_value={})):
        pytest.raises(CommandExecutionError, mac_user.chfullname, "test", "TEST USER")


def test_chfullname_same_name(mock_info_ret):
    """
    Tests if the user's full name is the same as the argument
    """
    with patch("salt.modules.mac_user.info", MagicMock(return_value=mock_info_ret)):
        assert mac_user.chfullname("test", "TEST USER")


# 'chgroups' function tests: 3
# Only tested pure logic of function
# Full functionality tests covered in integration testing


def test_chgroups_user_exists():
    """
    Tests if the user exists or not
    """
    with patch("salt.modules.mac_user.info", MagicMock(return_value={})):
        pytest.raises(CommandExecutionError, mac_user.chgroups, "foo", "wheel,root")


def test_chgroups_bad_groups(mock_info_ret):
    """
    Test if there is white space in groups argument
    """
    with patch("salt.modules.mac_user.info", MagicMock(return_value=mock_info_ret)):
        pytest.raises(SaltInvocationError, mac_user.chgroups, "test", "bad group")


def test_chgroups_same_desired(mock_info_ret):
    """
    Tests if the user's list of groups is the same as the arguments
    """
    mock_primary = MagicMock(return_value="wheel")
    with patch.dict(mac_user.__salt__, {"file.gid_to_group": mock_primary}), patch(
        "salt.modules.mac_user.info", MagicMock(return_value=mock_info_ret)
    ), patch(
        "salt.modules.mac_user.list_groups", MagicMock(return_value=("wheel", "root"))
    ):
        assert mac_user.chgroups("test", "wheel,root")


def test_info():
    """
    Tests the return of user information
    """
    mock_pwnam = pwd.struct_passwd(
        ("root", "*", 0, 0, "TEST USER", "/var/test", "/bin/bash")
    )
    ret = {
        "shell": "/bin/bash",
        "name": "root",
        "gid": 0,
        "groups": ["_TEST_GROUP"],
        "home": "/var/test",
        "fullname": "TEST USER",
        "uid": 0,
    }
    with patch("pwd.getpwall", MagicMock(return_value=[mock_pwnam])), patch(
        "salt.modules.mac_user.list_groups", MagicMock(return_value=["_TEST_GROUP"])
    ):
        assert mac_user.info("root") == ret


def test_format_info():
    """
    Tests the formatting of returned user information
    """
    data = pwd.struct_passwd(
        (
            "_TEST_GROUP",
            "*",
            83,
            83,
            "AMaViS Daemon",
            "/var/virusmails",
            "/usr/bin/false",
        )
    )
    ret = {
        "shell": "/usr/bin/false",
        "name": "_TEST_GROUP",
        "gid": 83,
        "groups": ["_TEST_GROUP"],
        "home": "/var/virusmails",
        "fullname": "AMaViS Daemon",
        "uid": 83,
    }
    with patch(
        "salt.modules.mac_user.list_groups", MagicMock(return_value=["_TEST_GROUP"])
    ):
        assert mac_user._format_info(data) == ret


def test_list_users():
    """
    Tests the list of all users
    """
    expected = ["spongebob", "patrick", "squidward"]
    mock_run = MagicMock(
        return_value={
            "pid": 4948,
            "retcode": 0,
            "stderr": "",
            "stdout": "\n".join(expected),
        }
    )
    with patch.dict(mac_user.__grains__, {"osrelease_info": (10, 9, 1)}), patch.dict(
        mac_user.__salt__, {"cmd.run_all": mock_run}
    ):
        assert mac_user.list_users() == expected
