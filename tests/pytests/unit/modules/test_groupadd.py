import pytest

import salt.modules.groupadd as groupadd
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch

try:
    import grp
except ImportError:
    pass


pytestmark = [
    pytest.mark.skip_on_windows,
]


@pytest.fixture
def configure_loader_modules():
    return {groupadd: {}}


def test_add():
    """
    Tests if specified group was added
    """
    with patch(
        "salt.utils.path.which",
        MagicMock(side_effect=[None, "/bin/groupadd", "/bin/groupadd"]),
    ) as which_mock:
        with pytest.raises(CommandExecutionError):
            groupadd.add("test", 100)
        which_mock.assert_called_once_with("groupadd")

        mock = MagicMock(return_value={"retcode": 0})
        with patch.dict(groupadd.__salt__, {"cmd.run_all": mock}):
            assert groupadd.add("test", 100) is True

        with patch.dict(groupadd.__grains__, {"kernel": "Linux"}):
            with patch.dict(groupadd.__salt__, {"cmd.run_all": mock}):
                assert groupadd.add("test", 100, True) is True


def test_add_local():
    """
    Tests if specified group was added with local flag
    """
    with patch(
        "salt.utils.path.which",
        MagicMock(return_value="/bin/lgroupadd"),
    ) as which_mock:
        mock = MagicMock(return_value={"retcode": 0})
        with patch.dict(groupadd.__salt__, {"cmd.run_all": mock}):
            assert groupadd.add("test", 100, local=True) is True
        which_mock.assert_called_once_with("lgroupadd")
        mock.assert_called_once_with(
            ["/bin/lgroupadd", "-g 100", "test"], python_shell=False
        )


def test_add_local_with_params():
    """
    Tests if specified group was added with local flag and extra parameters
    """
    with patch(
        "salt.utils.path.which",
        MagicMock(return_value="/bin/lgroupadd"),
    ):
        mock = MagicMock(return_value={"retcode": 0})
        with patch.dict(groupadd.__salt__, {"cmd.run_all": mock}):
            assert (
                groupadd.add("test", 100, local=True, non_unique=True, root="ignored")
                is True
            )
        mock.assert_called_once_with(
            ["/bin/lgroupadd", "-g 100", "test"], python_shell=False
        )


def test_info():
    """
    Tests the return of group information
    """
    getgrnam = grp.struct_group(("foo", "*", 20, ["test"]))
    with patch("grp.getgrnam", MagicMock(return_value=getgrnam)):
        ret = {"passwd": "*", "gid": 20, "name": "foo", "members": ["test"]}
        assert groupadd.info("foo") == ret


def test_format_info():
    """
    Tests the formatting of returned group information
    """
    group = {"passwd": "*", "gid": 0, "name": "test", "members": ["root"]}
    with patch("salt.modules.groupadd._format_info", MagicMock(return_value=group)):
        data = grp.struct_group(("wheel", "*", 0, ["root"]))
        ret = {"passwd": "*", "gid": 0, "name": "test", "members": ["root"]}
        assert groupadd._format_info(data) == ret


def test_getent():
    """
    Tests the return of information on all groups
    """
    getgrnam = grp.struct_group(("foo", "*", 20, ["test"]))
    with patch("grp.getgrall", MagicMock(return_value=[getgrnam])):
        ret = [{"passwd": "*", "gid": 20, "name": "foo", "members": ["test"]}]
        assert groupadd.getent() == ret


def test_chgid_gid_same():
    """
    Tests if the group id is the same as argument
    """
    mock = MagicMock(return_value={"gid": 10})
    with patch.object(groupadd, "info", mock):
        assert groupadd.chgid("test", 10) is True


def test_chgid():
    """
    Tests the gid for a named group was changed
    """
    with patch(
        "salt.utils.path.which",
        MagicMock(side_effect=[None, "/bin/groupmod"]),
    ):
        cmd_mock = MagicMock(return_value=None)
        with patch.dict(groupadd.__salt__, {"cmd.run": cmd_mock}):
            info_mock = MagicMock(side_effect=[{"gid": 10}, {"gid": 10}, {"gid": 500}])
            with patch.object(groupadd, "info", info_mock):
                with pytest.raises(CommandExecutionError):
                    groupadd.chgid("test", 500)
                assert groupadd.chgid("test", 500) is True


def test_delete():
    """
    Tests if the specified group was deleted
    """
    with patch(
        "salt.utils.path.which",
        MagicMock(side_effect=[None, "/bin/groupdel"]),
    ) as which_mock:
        with pytest.raises(CommandExecutionError):
            groupadd.delete("test")
        which_mock.assert_called_once_with("groupdel")

        mock_ret = MagicMock(return_value={"retcode": 0})
        with patch.dict(groupadd.__salt__, {"cmd.run_all": mock_ret}):
            assert groupadd.delete("test") is True


def test_delete_local():
    """
    Tests if the specified group was deleted with a local flag
    """
    with patch(
        "salt.utils.path.which",
        MagicMock(return_value="/bin/lgroupdel"),
    ) as which_mock:
        mock = MagicMock(return_value={"retcode": 0})
        with patch.dict(groupadd.__salt__, {"cmd.run_all": mock}):
            assert groupadd.delete("test", local=True) is True
        which_mock.assert_called_once_with("lgroupdel")
        mock.assert_called_once_with(["/bin/lgroupdel", "test"], python_shell=False)


def test_delete_local_with_params():
    """
    Tests if the specified group was deleted with a local flag and params
    """
    with patch(
        "salt.utils.path.which",
        MagicMock(return_value="/bin/lgroupdel"),
    ):
        mock = MagicMock(return_value={"retcode": 0})
        with patch.dict(groupadd.__salt__, {"cmd.run_all": mock}):
            assert groupadd.delete("test", local=True, root="ignored") is True
        mock.assert_called_once_with(["/bin/lgroupdel", "test"], python_shell=False)


def test_adduser():
    """
    Tests if specified user gets added in the group.
    """
    os_version_list = [
        {
            "grains": {
                "kernel": "Linux",
                "os_family": "Suse",
                "osmajorrelease": "11",
            },
            "cmd": ["/bin/usermod", "-A", "test", "root"],
        },
        {
            "grains": {"kernel": "Linux"},
            "cmd": ["/bin/gpasswd", "--add", "root", "test"],
        },
        {
            "grains": {"kernel": "OTHERKERNEL"},
            "cmd": ["/bin/usermod", "-G", "test", "root"],
        },
    ]
    with patch(
        "salt.utils.path.which",
        MagicMock(
            side_effect=[
                "/bin/usermod",
                "/bin/gpasswd",
                "/bin/usermod",
            ]
        ),
    ):
        for os_version in os_version_list:
            mock = MagicMock(return_value={"retcode": 0})
            with patch.dict(groupadd.__grains__, os_version["grains"]), patch.dict(
                groupadd.__salt__, {"cmd.retcode": mock}
            ):
                assert groupadd.adduser("test", "root") is False
                groupadd.__salt__["cmd.retcode"].assert_called_once_with(
                    os_version["cmd"], python_shell=False
                )


def test_deluser():
    """
    Tests if specified user gets deleted from the group.
    """
    os_version_list = [
        {
            "grains": {
                "kernel": "Linux",
                "os_family": "Suse",
                "osmajorrelease": "11",
            },
            "cmd": ["/bin/usermod", "-R", "test", "root"],
        },
        {
            "grains": {"kernel": "Linux"},
            "cmd": ["/bin/gpasswd", "--del", "root", "test"],
        },
        {"grains": {"kernel": "OpenBSD"}, "cmd": ["/bin/usermod", "-S", "foo", "root"]},
    ]

    with patch(
        "salt.utils.path.which",
        MagicMock(
            side_effect=[
                "/bin/usermod",
                "/bin/gpasswd",
                "/bin/usermod",
            ]
        ),
    ):
        for os_version in os_version_list:
            mock_retcode = MagicMock(return_value=0)
            mock_stdout = MagicMock(return_value="test foo")
            mock_info = MagicMock(
                return_value={
                    "passwd": "*",
                    "gid": 0,
                    "name": "test",
                    "members": ["root"],
                }
            )

            with patch.dict(groupadd.__grains__, os_version["grains"]):
                with patch.dict(
                    groupadd.__salt__,
                    {
                        "cmd.retcode": mock_retcode,
                        "group.info": mock_info,
                        "cmd.run_stdout": mock_stdout,
                    },
                ):
                    assert groupadd.deluser("test", "root") is True
                    groupadd.__salt__["cmd.retcode"].assert_called_once_with(
                        os_version["cmd"], python_shell=False
                    )


def test_members():
    """
    Tests if members of the group, get replaced with a provided list.
    """
    os_version_list = [
        {
            "grains": {
                "kernel": "Linux",
                "os_family": "Suse",
                "osmajorrelease": "11",
            },
            "cmd": ["/bin/groupmod", "-A", "foo", "test"],
        },
        {
            "grains": {"kernel": "Linux"},
            "cmd": ["/bin/gpasswd", "--members", "foo", "test"],
        },
        {"grains": {"kernel": "OpenBSD"}, "cmd": ["/bin/usermod", "-G", "test", "foo"]},
    ]

    with patch(
        "salt.utils.path.which",
        MagicMock(
            side_effect=[
                "/bin/gpasswd",
                "/bin/groupmod",
                "/bin/gpasswd",
                "/bin/groupdel",
                "/bin/groupadd",
                "/bin/usermod",
            ]
        ),
    ):
        for os_version in os_version_list:
            mock_ret = MagicMock(return_value={"retcode": 0})
            mock_stdout = MagicMock(return_value={"cmd.run_stdout": 1})
            mock_info = MagicMock(
                return_value={
                    "passwd": "*",
                    "gid": 0,
                    "name": "test",
                    "members": ["root"],
                }
            )
            mock = MagicMock(return_value=True)

            with patch.dict(groupadd.__grains__, os_version["grains"]):
                with patch.dict(
                    groupadd.__salt__,
                    {
                        "cmd.retcode": mock_ret,
                        "group.info": mock_info,
                        "cmd.run_stdout": mock_stdout,
                        "cmd.run": mock,
                    },
                ):
                    assert groupadd.members("test", "foo") is False
                    groupadd.__salt__["cmd.retcode"].assert_called_once_with(
                        os_version["cmd"], python_shell=False
                    )
