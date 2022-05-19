import pytest
import salt.modules.useradd as useradd
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {
        useradd: {
            "__grains__": {
                "kernel": "Linux",
                "osarch": "x86_64",
                "os": "CentOS",
                "os_family": "RedHat",
                "osmajorrelease": 8,
            },
            "__salt__": {},
        }
    }


def test_add():
    # command found and successful run
    mock = MagicMock(return_value={"retcode": 0})
    with patch(
        "salt.utils.path.which", MagicMock(return_value="/sbin/useradd")
    ), patch.dict(useradd.__salt__, {"cmd.run_all": mock}):
        assert useradd.add("Salt") is True
    mock.assert_called_once_with(["/sbin/useradd", "-m", "Salt"], python_shell=False)

    # command found and unsuccessful run
    mock = MagicMock(return_value={"retcode": 1})
    with patch(
        "salt.utils.path.which", MagicMock(return_value="/sbin/useradd")
    ), patch.dict(useradd.__salt__, {"cmd.run_all": mock}):
        assert useradd.add("Salt") is False
    mock.assert_called_once_with(["/sbin/useradd", "-m", "Salt"], python_shell=False)

    # command not found
    mock = MagicMock()
    with patch("salt.utils.path.which", MagicMock(return_value=None)), patch.dict(
        useradd.__salt__, {"cmd.run_all": mock}
    ):
        with pytest.raises(CommandExecutionError):
            useradd.add("Salt")
    mock.assert_not_called()


def test_delete():
    # command found and successful run
    mock = MagicMock(return_value={"retcode": 0})
    with patch(
        "salt.utils.path.which", MagicMock(return_value="/sbin/userdel")
    ), patch.dict(useradd.__salt__, {"cmd.run_all": mock}):
        assert useradd.delete("Salt") is True
    mock.assert_called_once_with(["/sbin/userdel", "Salt"], python_shell=False)

    # command found and unsuccessful run
    mock = MagicMock(return_value={"retcode": 1})
    with patch(
        "salt.utils.path.which", MagicMock(return_value="/sbin/userdel")
    ), patch.dict(useradd.__salt__, {"cmd.run_all": mock}):
        assert useradd.delete("Salt") is False
    mock.assert_called_once_with(["/sbin/userdel", "Salt"], python_shell=False)

    # command not found
    mock = MagicMock()
    with patch("salt.utils.path.which", MagicMock(return_value=None)), patch.dict(
        useradd.__salt__, {"cmd.run_all": mock}
    ):
        with pytest.raises(CommandExecutionError):
            useradd.delete("Salt")
    mock.assert_not_called()


def test_chgroups():
    # command found and successful run
    mock = MagicMock(return_value={"retcode": 0})
    with patch(
        "salt.utils.path.which", MagicMock(return_value="/sbin/usermod")
    ), patch.dict(useradd.__salt__, {"cmd.run_all": mock}):
        assert useradd.chgroups("Salt", "wheel,root") is True
    mock.assert_called_once_with(
        ["/sbin/usermod", "-G", "wheel,root", "Salt"], python_shell=False
    )

    # command found and unsuccessful run
    mock = MagicMock(return_value={"retcode": 1, "stderr": ""})
    with patch(
        "salt.utils.path.which", MagicMock(return_value="/sbin/usermod")
    ), patch.dict(useradd.__salt__, {"cmd.run_all": mock}):
        assert useradd.chgroups("Salt", "wheel,root") is False
    mock.assert_called_once_with(
        ["/sbin/usermod", "-G", "wheel,root", "Salt"], python_shell=False
    )

    # command not found
    mock = MagicMock()
    with patch("salt.utils.path.which", MagicMock(return_value=None)), patch.dict(
        useradd.__salt__, {"cmd.run_all": mock}
    ):
        with pytest.raises(CommandExecutionError):
            useradd.chgroups("Salt", "wheel,root")
    mock.assert_not_called()


def test_chloginclass():
    # only runs on OpenBSD
    assert useradd.chloginclass("Salt", "staff") is False

    with patch.dict(useradd.__grains__, {"kernel": "OpenBSD"}):
        # command found and successful run
        userinfo = ["class salt", "class staff"]
        mock = MagicMock(return_value={"retcode": 0})
        with patch(
            "salt.utils.path.which", MagicMock(return_value="/sbin/usermod")
        ), patch.dict(
            useradd.__salt__, {"cmd.run_stdout": MagicMock(side_effect=userinfo)}
        ), patch.dict(
            useradd.__salt__, {"cmd.run": mock}
        ):
            assert useradd.chloginclass("Salt", "staff") is True
        mock.assert_called_once_with(
            ["/sbin/usermod", "-L", "staff", "Salt"], python_shell=False
        )

        # command found and unsuccessful run
        userinfo = ["class salt", "class salt"]
        mock = MagicMock(return_value={"retcode": 1, "stderr": ""})
        with patch(
            "salt.utils.path.which", MagicMock(return_value="/sbin/usermod")
        ), patch.dict(
            useradd.__salt__, {"cmd.run_stdout": MagicMock(side_effect=userinfo)}
        ), patch.dict(
            useradd.__salt__, {"cmd.run": mock}
        ):
            assert useradd.chloginclass("Salt", "staff") is False
        mock.assert_called_once_with(
            ["/sbin/usermod", "-L", "staff", "Salt"], python_shell=False
        )

        # command not found
        userinfo = ["class salt"]
        mock = MagicMock()
        with patch("salt.utils.path.which", MagicMock(return_value=None)), patch.dict(
            useradd.__salt__, {"cmd.run_stdout": MagicMock(side_effect=userinfo)}
        ), patch.dict(useradd.__salt__, {"cmd.run": mock}):
            with pytest.raises(CommandExecutionError):
                useradd.chloginclass("Salt", "staff")
        mock.assert_not_called()


def test__chattrib():
    # command found and successful run
    mock = MagicMock(return_value={"retcode": 0})
    with patch(
        "salt.utils.path.which", MagicMock(return_value="/sbin/usermod")
    ), patch.object(
        useradd, "info", MagicMock(side_effect=[{"uid": 10}, {"uid": 11}])
    ), patch.dict(
        useradd.__salt__, {"cmd.run": mock}
    ):
        assert useradd._chattrib("Salt", "uid", 11, "-u") is True
    mock.assert_called_once_with(
        ["/sbin/usermod", "-u", 11, "Salt"], python_shell=False
    )

    # command found and unsuccessful run
    mock = MagicMock(return_value={"retcode": 1})
    with patch(
        "salt.utils.path.which", MagicMock(return_value="/sbin/usermod")
    ), patch.object(
        useradd, "info", MagicMock(side_effect=[{"uid": 10}, {"uid": 10}])
    ), patch.dict(
        useradd.__salt__, {"cmd.run": mock}
    ):
        assert useradd._chattrib("Salt", "uid", 11, "-u") is False
    mock.assert_called_once_with(
        ["/sbin/usermod", "-u", 11, "Salt"], python_shell=False
    )

    # command not found
    mock = MagicMock()
    with patch("salt.utils.path.which", MagicMock(return_value=None)), patch.dict(
        useradd.__salt__, {"cmd.run_all": mock}
    ):
        with pytest.raises(CommandExecutionError):
            useradd._chattrib("Salt", "uid", 11, "-u")
    mock.assert_not_called()


def test__update_gecos():
    pre_info = {"fullname": "Uli Kunkel"}
    post_info = {"fullname": "Karl Hungus"}

    # command found and successful run
    mock = MagicMock(return_value={"retcode": 0})
    with patch(
        "salt.utils.path.which", MagicMock(return_value="/sbin/usermod")
    ), patch.object(
        useradd, "_get_gecos", MagicMock(side_effect=[pre_info, post_info])
    ), patch.dict(
        useradd.__salt__, {"cmd.run": mock}
    ):
        assert useradd._update_gecos("Salt", "fullname", post_info["fullname"]) is True
    mock.assert_called_once_with(
        ["/sbin/usermod", "-c", "Karl Hungus", "Salt"], python_shell=False
    )

    # command found and unsuccessful run
    mock = MagicMock(return_value={"retcode": 1})
    with patch(
        "salt.utils.path.which", MagicMock(return_value="/sbin/usermod")
    ), patch.object(
        useradd, "_get_gecos", MagicMock(side_effect=[pre_info, pre_info])
    ), patch.dict(
        useradd.__salt__, {"cmd.run": mock}
    ):
        assert useradd._update_gecos("Salt", "fullname", post_info["fullname"]) is False
    mock.assert_called_once_with(
        ["/sbin/usermod", "-c", "Karl Hungus", "Salt"], python_shell=False
    )

    # command not found
    mock = MagicMock()
    with patch("salt.utils.path.which", MagicMock(return_value=None)), patch.object(
        useradd, "_get_gecos", MagicMock(side_effect=[pre_info, pre_info])
    ), patch.dict(useradd.__salt__, {"cmd.run": mock}):
        with pytest.raises(CommandExecutionError):
            useradd._update_gecos("Salt", "fullname", post_info["fullname"])
    mock.assert_not_called()
