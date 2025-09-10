"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>
"""

import logging

import pytest

import salt.modules.pw_user as pw_user
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch

pwd = pytest.importorskip(
    "pwd", reason="Tests can only run on systems with the python pwd module"
)

log = logging.getLogger(__name__)


@pytest.fixture
def configure_loader_modules():
    return {pw_user: {}}


def test_add():
    """
    Test for adding a user
    """
    with patch.dict(pw_user.__grains__, {"os_family": "RedHat"}):
        mock = MagicMock(return_value=0)
        with patch.dict(pw_user.__salt__, {"cmd.retcode": mock}):
            assert pw_user.add("a")


def test_delete():
    """
    Test for deleting a user
    """
    mock = MagicMock(return_value=0)
    with patch.dict(pw_user.__salt__, {"cmd.retcode": mock}):
        assert pw_user.delete("A")


def test_getent():
    """
    Test if user.getent already have a value
    """
    mock_user = "saltdude"

    class MockData:
        pw_name = mock_user

    with patch("pwd.getpwall", MagicMock(return_value=[MockData()])):
        with patch.dict(pw_user.__context__, {"user.getent": mock_user}):
            assert pw_user.getent() == mock_user

            with patch.object(pw_user, "info", MagicMock(return_value=mock_user)):
                assert pw_user.getent(True)[0] == mock_user


def test_chuid():
    """
    Test if user id given is same as previous id
    """
    mock = MagicMock(return_value={"uid": "A"})
    with patch.object(pw_user, "info", mock):
        assert pw_user.chuid("name", "A")

    mock = MagicMock(return_value=None)
    with patch.dict(pw_user.__salt__, {"cmd.run": mock}):
        mock = MagicMock(side_effect=[{"uid": "A"}, {"uid": "A"}])
        with patch.object(pw_user, "info", mock):
            assert not pw_user.chuid("name", "B")

    mock = MagicMock(return_value=None)
    with patch.dict(pw_user.__salt__, {"cmd.run": mock}):
        mock = MagicMock(side_effect=[{"uid": "A"}, {"uid": "B"}])
        with patch.object(pw_user, "info", mock):
            assert pw_user.chuid("name", "A")


def test_chgid():
    """
    Test if group id given is same as previous id
    """
    mock = MagicMock(return_value={"gid": 1})
    with patch.object(pw_user, "info", mock):
        assert pw_user.chgid("name", 1)

    mock = MagicMock(return_value=None)
    with patch.dict(pw_user.__salt__, {"cmd.run": mock}):
        mock = MagicMock(side_effect=[{"gid": 2}, {"gid": 2}])
        with patch.object(pw_user, "info", mock):
            assert not pw_user.chgid("name", 1)

    mock = MagicMock(return_value=None)
    with patch.dict(pw_user.__salt__, {"cmd.run": mock}):
        mock = MagicMock(side_effect=[{"gid": 1}, {"gid": 2}])
        with patch.object(pw_user, "info", mock):
            assert pw_user.chgid("name", 1)


def test_chshell():
    """
    Test if shell given is same as previous shell
    """
    mock = MagicMock(return_value={"shell": "A"})
    with patch.object(pw_user, "info", mock):
        assert pw_user.chshell("name", "A")

    mock = MagicMock(return_value=None)
    with patch.dict(pw_user.__salt__, {"cmd.run": mock}):
        mock = MagicMock(side_effect=[{"shell": "B"}, {"shell": "B"}])
        with patch.object(pw_user, "info", mock):
            assert not pw_user.chshell("name", "A")

    mock = MagicMock(return_value=None)
    with patch.dict(pw_user.__salt__, {"cmd.run": mock}):
        mock = MagicMock(side_effect=[{"shell": "A"}, {"shell": "B"}])
        with patch.object(pw_user, "info", mock):
            assert pw_user.chshell("name", "A")


def test_chhome():
    """
    Test if home directory given is same as previous home directory
    """
    mock = MagicMock(return_value={"home": "A"})
    with patch.object(pw_user, "info", mock):
        assert pw_user.chhome("name", "A")

    mock = MagicMock(return_value=None)
    with patch.dict(pw_user.__salt__, {"cmd.run": mock}):
        mock = MagicMock(side_effect=[{"home": "B"}, {"home": "B"}])
        with patch.object(pw_user, "info", mock):
            assert not pw_user.chhome("name", "A")

    mock = MagicMock(return_value=None)
    with patch.dict(pw_user.__salt__, {"cmd.run": mock}):
        mock = MagicMock(side_effect=[{"home": "A"}, {"home": "B"}])
        with patch.object(pw_user, "info", mock):
            assert pw_user.chhome("name", "A")


def test_chgroups():
    """
    Test if no group needs to be added
    """
    mock = MagicMock(return_value=False)
    with patch.dict(pw_user.__salt__, {"cmd.retcode": mock}):
        mock = MagicMock(return_value=["a", "b", "c", "d"])
        with patch.object(pw_user, "list_groups", mock):
            assert pw_user.chgroups("name", "a, b, c, d")

    mock = MagicMock(return_value=False)
    with patch.dict(pw_user.__salt__, {"cmd.retcode": mock}):
        mock = MagicMock(return_value=["a", "b"])
        with patch.object(pw_user, "list_groups", mock):
            assert pw_user.chgroups("name", "a, b, c")


def test_chfullname():
    """
    Change the user's Full Name
    """
    mock = MagicMock(return_value=False)
    with patch.object(pw_user, "_get_gecos", mock):
        assert not pw_user.chfullname("name", "fullname")

    mock = MagicMock(return_value={"fullname": "fullname"})
    with patch.object(pw_user, "_get_gecos", mock):
        assert pw_user.chfullname("name", "fullname")

    mock = MagicMock(return_value={"fullname": "Unicøde name ①③②"})
    with patch.object(pw_user, "_get_gecos", mock):
        assert pw_user.chfullname("name", "Unicøde name ①③②")

    mock = MagicMock(return_value={"fullname": "fullname"})
    with patch.object(pw_user, "_get_gecos", mock):
        mock = MagicMock(return_value=None)
        with patch.dict(pw_user.__salt__, {"cmd.run": mock}):
            mock = MagicMock(return_value={"fullname": "fullname2"})
            with patch.object(pw_user, "info", mock):
                assert not pw_user.chfullname("name", "fullname1")

    mock = MagicMock(return_value={"fullname": "fullname2"})
    with patch.object(pw_user, "_get_gecos", mock):
        mock = MagicMock(return_value=None)
        with patch.dict(pw_user.__salt__, {"cmd.run": mock}):
            mock = MagicMock(return_value={"fullname": "fullname2"})
            with patch.object(pw_user, "info", mock):
                assert not pw_user.chfullname("name", "fullname1")


def test_chroomnumber():
    """
    Change the user's Room Number
    """
    mock = MagicMock(return_value=False)
    with patch.object(pw_user, "_get_gecos", mock):
        assert not pw_user.chroomnumber("name", 1)

    mock = MagicMock(return_value={"roomnumber": "Unicøde room ①③②"})
    with patch.object(pw_user, "_get_gecos", mock):
        assert pw_user.chroomnumber("name", "Unicøde room ①③②")

    mock = MagicMock(return_value={"roomnumber": "1"})
    with patch.object(pw_user, "_get_gecos", mock):
        assert pw_user.chroomnumber("name", 1)

    mock = MagicMock(return_value={"roomnumber": "2"})
    with patch.object(pw_user, "_get_gecos", mock):
        mock = MagicMock(return_value=None)
        with patch.dict(pw_user.__salt__, {"cmd.run": mock}):
            mock = MagicMock(return_value={"roomnumber": "3"})
            with patch.object(pw_user, "info", mock):
                assert not pw_user.chroomnumber("name", 1)

    mock = MagicMock(return_value={"roomnumber": "3"})
    with patch.object(pw_user, "_get_gecos", mock):
        mock = MagicMock(return_value=None)
        with patch.dict(pw_user.__salt__, {"cmd.run": mock}):
            mock = MagicMock(return_value={"roomnumber": "3"})
            with patch.object(pw_user, "info", mock):
                assert not pw_user.chroomnumber("name", 1)


def test_chworkphone():
    """
    Change the user's Work Phone
    """
    mock = MagicMock(return_value=False)
    with patch.object(pw_user, "_get_gecos", mock):
        assert not pw_user.chworkphone("name", 1)

    mock = MagicMock(return_value={"workphone": "1"})
    with patch.object(pw_user, "_get_gecos", mock):
        assert pw_user.chworkphone("name", 1)

    mock = MagicMock(return_value={"workphone": "Unicøde phone number ①③②"})
    with patch.object(pw_user, "_get_gecos", mock):
        assert pw_user.chworkphone("name", "Unicøde phone number ①③②")

    mock = MagicMock(return_value={"workphone": "2"})
    with patch.object(pw_user, "_get_gecos", mock):
        mock = MagicMock(return_value=None)
        with patch.dict(pw_user.__salt__, {"cmd.run": mock}):
            mock = MagicMock(return_value={"workphone": "3"})
            with patch.object(pw_user, "info", mock):
                assert not pw_user.chworkphone("name", 1)

    mock = MagicMock(return_value={"workphone": "3"})
    with patch.object(pw_user, "_get_gecos", mock):
        mock = MagicMock(return_value=None)
        with patch.dict(pw_user.__salt__, {"cmd.run": mock}):
            mock = MagicMock(return_value={"workphone": "3"})
            with patch.object(pw_user, "info", mock):
                assert not pw_user.chworkphone("name", 1)


def test_chhomephone():
    """
    Change the user's Home Phone
    """
    mock = MagicMock(return_value=False)
    with patch.object(pw_user, "_get_gecos", mock):
        assert not pw_user.chhomephone("name", 1)

    mock = MagicMock(return_value={"homephone": "1"})
    with patch.object(pw_user, "_get_gecos", mock):
        assert pw_user.chhomephone("name", 1)

    mock = MagicMock(return_value={"homephone": "Unicøde phone number ①③②"})
    with patch.object(pw_user, "_get_gecos", mock):
        assert pw_user.chhomephone("name", "Unicøde phone number ①③②")

    mock = MagicMock(return_value={"homephone": "2"})
    with patch.object(pw_user, "_get_gecos", mock):
        mock = MagicMock(return_value=None)
        with patch.dict(pw_user.__salt__, {"cmd.run": mock}):
            mock = MagicMock(return_value={"homephone": "3"})
            with patch.object(pw_user, "info", mock):
                assert not pw_user.chhomephone("name", 1)

    mock = MagicMock(return_value={"homephone": "3"})
    with patch.object(pw_user, "_get_gecos", mock):
        mock = MagicMock(return_value=None)
        with patch.dict(pw_user.__salt__, {"cmd.run": mock}):
            mock = MagicMock(return_value={"homephone": "3"})
            with patch.object(pw_user, "info", mock):
                assert not pw_user.chhomephone("name", 1)


def test_info():
    """
    Return user information
    """
    assert pw_user.info("name") == {}

    mock = MagicMock(
        return_value=pwd.struct_passwd(
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
    )
    with patch.object(pwd, "getpwnam", mock):
        mock = MagicMock(return_value="Group Name")
        with patch.object(pw_user, "list_groups", mock):
            assert pw_user.info("name")["name"] == "_TEST_GROUP"


def test_list_groups():
    """
    Return a list of groups the named user belongs to
    """
    mock_group = "saltgroup"

    with patch("salt.utils.user.get_group_list", MagicMock(return_value=[mock_group])):
        assert pw_user.list_groups("name") == [mock_group]


def test_list_users():
    """
    Return a list of all users
    """
    mock_user = "saltdude"

    class MockData:
        pw_name = mock_user

    with patch("pwd.getpwall", MagicMock(return_value=[MockData()])):
        assert pw_user.list_users() == [mock_user]


def test_rename():
    """
    Change the username for a named user
    """
    mock = MagicMock(return_value=False)
    with patch.object(pw_user, "info", mock):
        pytest.raises(CommandExecutionError, pw_user.rename, "name", 1)

    mock = MagicMock(return_value=True)
    with patch.object(pw_user, "info", mock):
        pytest.raises(CommandExecutionError, pw_user.rename, "name", 1)

    mock = MagicMock(return_value=None)
    with patch.dict(pw_user.__salt__, {"cmd.run": mock}):
        mock = MagicMock(side_effect=[{"name": ""}, False, {"name": "name"}])
        with patch.object(pw_user, "info", mock):
            assert pw_user.rename("name", "name")

    mock = MagicMock(return_value=None)
    with patch.dict(pw_user.__salt__, {"cmd.run": mock}):
        mock = MagicMock(side_effect=[{"name": ""}, False, {"name": ""}])
        with patch.object(pw_user, "info", mock):
            assert not pw_user.rename("name", "name")
