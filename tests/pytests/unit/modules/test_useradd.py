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
    # groups matched - no command run
    mock = MagicMock()
    with patch.object(
        useradd, "list_groups", MagicMock(return_value=["wheel", "root"])
    ), patch.dict(useradd.__salt__, {"cmd.run_all": mock}):
        assert useradd.chgroups("Salt", "wheel,root") is True
    mock.assert_not_called()

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
    with patch("salt.utils.path.which", MagicMock(return_value=None)), patch.object(
        useradd, "info", MagicMock(return_value={"uid": 10})
    ), patch.dict(useradd.__salt__, {"cmd.run_all": mock}):
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


def test_rename():
    # command not found
    with patch("salt.utils.path.which", MagicMock(return_value=None)):
        mock = MagicMock()
        with patch.object(
            useradd, "info", MagicMock(return_value={"uid": 10})
        ), patch.dict(useradd.__salt__, {"cmd.run": mock}):
            with pytest.raises(CommandExecutionError):
                useradd.rename("salt", 1)
        mock.assert_not_called()

    # command found
    with patch("salt.utils.path.which", MagicMock(return_value="/sbin/usermod")):
        mock = MagicMock(return_value=False)
        with patch.object(useradd, "info", mock):
            with pytest.raises(CommandExecutionError):
                useradd.rename("salt", 1)

        mock = MagicMock(return_value=True)
        with patch.object(useradd, "info", mock):
            with pytest.raises(CommandExecutionError):
                useradd.rename("salt", 1)

        mock = MagicMock(return_value=None)
        with patch.dict(useradd.__salt__, {"cmd.run": mock}):
            mock = MagicMock(side_effect=[False, {"name": ""}, {"name": "salt"}])
            with patch.object(useradd, "info", mock):
                assert useradd.rename("name", "salt") is True

        mock = MagicMock(return_value=None)
        with patch.dict(useradd.__salt__, {"cmd.run": mock}):
            mock = MagicMock(side_effect=[False, {"name": ""}, {"name": ""}])
            with patch.object(useradd, "info", mock):
                assert useradd.rename("salt", "salt") is False


def test_chuid():
    # command not found
    with patch("salt.utils.path.which", MagicMock(return_value=None)):
        mock = MagicMock()
        with patch.object(
            useradd, "info", MagicMock(return_value={"uid": 10})
        ), patch.dict(useradd.__salt__, {"cmd.run": mock}):
            with pytest.raises(CommandExecutionError):
                useradd.chuid("salt", 1)
        mock.assert_not_called()

    # command found
    with patch("salt.utils.path.which", MagicMock(return_value="/sbin/usermod")):
        mock = MagicMock(return_value={"uid": 11})
        with patch.object(useradd, "info", mock):
            assert useradd.chuid("name", 11) is True

        mock_run = MagicMock(return_value=None)
        with patch.dict(useradd.__salt__, {"cmd.run": mock_run}):
            mock = MagicMock(side_effect=[{"uid": 11}, {"uid": 11}])
            with patch.object(useradd, "info", mock):
                assert useradd.chuid("name", 22) is False

        with patch.dict(useradd.__salt__, {"cmd.run": mock_run}):
            mock = MagicMock(side_effect=[{"uid": 11}, {"uid": 22}])
            with patch.object(useradd, "info", mock):
                assert useradd.chuid("name", 11) is True


def test_chgid():
    # command not found
    with patch("salt.utils.path.which", MagicMock(return_value=None)):
        mock = MagicMock()
        with patch.object(
            useradd, "info", MagicMock(return_value={"gid": 10})
        ), patch.dict(useradd.__salt__, {"cmd.run": mock}):
            with pytest.raises(CommandExecutionError):
                useradd.chgid("salt", 1)
        mock.assert_not_called()

    # command found
    with patch("salt.utils.path.which", MagicMock(return_value="/sbin/usermod")):
        mock = MagicMock(return_value={"gid": 11})
        with patch.object(useradd, "info", mock):
            assert useradd.chgid("name", 11) is True

        mock_run = MagicMock(return_value=None)
        with patch.dict(useradd.__salt__, {"cmd.run": mock_run}):
            mock = MagicMock(side_effect=[{"gid": 22}, {"gid": 22}])
            with patch.object(useradd, "info", mock):
                assert useradd.chgid("name", 11) is False

        with patch.dict(useradd.__salt__, {"cmd.run": mock_run}):
            mock = MagicMock(side_effect=[{"gid": 11}, {"gid": 22}])
            with patch.object(useradd, "info", mock):
                assert useradd.chgid("name", 11) is True


def test_chshell():
    # command not found
    with patch("salt.utils.path.which", MagicMock(return_value=None)):
        mock = MagicMock()
        with patch.object(
            useradd, "info", MagicMock(return_value={"shell": "/bin/bash"})
        ), patch.dict(useradd.__salt__, {"cmd.run": mock}):
            with pytest.raises(CommandExecutionError):
                useradd.chshell("salt", "/usr/bash")
        mock.assert_not_called()

    # command found
    with patch("salt.utils.path.which", MagicMock(return_value="/sbin/usermod")):
        mock = MagicMock(return_value={"shell": "/bin/bash"})
        with patch.object(useradd, "info", mock):
            assert useradd.chshell("name", "/bin/bash") is True

        mock_run = MagicMock(return_value=None)
        with patch.dict(useradd.__salt__, {"cmd.run": mock_run}):
            mock = MagicMock(
                side_effect=[{"shell": "/bin/bash"}, {"shell": "/bin/bash"}]
            )
            with patch.object(useradd, "info", mock):
                assert useradd.chshell("name", "/usr/bash") is False

        with patch.dict(useradd.__salt__, {"cmd.run": mock_run}):
            mock = MagicMock(
                side_effect=[{"shell": "/bin/bash"}, {"shell": "/usr/bash"}]
            )
            with patch.object(useradd, "info", mock):
                assert useradd.chshell("name", "/bin/bash") is True


def test_chhome():
    # command not found
    with patch("salt.utils.path.which", MagicMock(return_value=None)):
        mock = MagicMock()
        with patch.object(
            useradd, "info", MagicMock(return_value={"home": "/root"})
        ), patch.dict(useradd.__salt__, {"cmd.run": mock}):
            with pytest.raises(CommandExecutionError):
                useradd.chhome("salt", "/user")
        mock.assert_not_called()

    # command found
    with patch("salt.utils.path.which", MagicMock(return_value="/sbin/usermod")):
        mock = MagicMock(return_value={"home": "/root"})
        with patch.object(useradd, "info", mock):
            assert useradd.chhome("name", "/root") is True

        mock = MagicMock(return_value=None)
        with patch.dict(useradd.__salt__, {"cmd.run": mock}):
            mock = MagicMock(side_effect=[{"home": "/root"}, {"home": "/root"}])
            with patch.object(useradd, "info", mock):
                assert useradd.chhome("name", "/user") is False

        mock = MagicMock(return_value=None)
        with patch.dict(useradd.__salt__, {"cmd.run": mock}):
            mock = MagicMock(side_effect=[{"home": "/root"}, {"home": "/root"}])
            with patch.object(useradd, "info", mock):
                assert useradd.chhome("name", "/root") is True


def test_chfullname():
    # command not found
    with patch("salt.utils.path.which", MagicMock(return_value=None)):
        mock = MagicMock()
        with patch.object(
            useradd, "_get_gecos", MagicMock(return_value={"fullname": "Salt"})
        ), patch.dict(useradd.__salt__, {"cmd.run": mock}):
            with pytest.raises(CommandExecutionError):
                useradd.chfullname("salt", "Saltstack")
        mock.assert_not_called()

    # command found
    with patch("salt.utils.path.which", MagicMock(return_value="/sbin/usermod")):
        mock = MagicMock(return_value=False)
        with patch.object(useradd, "_get_gecos", mock):
            assert useradd.chfullname("Salt", "SaltStack") is False

        mock = MagicMock(return_value={"fullname": "SaltStack"})
        with patch.object(useradd, "_get_gecos", mock):
            assert useradd.chfullname("Salt", "SaltStack") is True

        mock = MagicMock(return_value={"fullname": "SaltStack"})
        with patch.object(useradd, "_get_gecos", mock):
            mock = MagicMock(return_value=None)
            with patch.dict(useradd.__salt__, {"cmd.run": mock}):
                mock = MagicMock(return_value={"fullname": "SaltStack2"})
                with patch.object(useradd, "info", mock):
                    assert useradd.chfullname("Salt", "SaltStack1") is False

        mock = MagicMock(return_value={"fullname": "SaltStack2"})
        with patch.object(useradd, "_get_gecos", mock):
            mock = MagicMock(return_value=None)
            with patch.dict(useradd.__salt__, {"cmd.run": mock}):
                mock = MagicMock(return_value={"fullname": "SaltStack2"})
                with patch.object(useradd, "info", mock):
                    assert useradd.chfullname("Salt", "SaltStack1") is False


def test_chroomnumber():
    # command not found
    with patch("salt.utils.path.which", MagicMock(return_value=None)):
        mock = MagicMock()
        with patch.object(
            useradd, "_get_gecos", MagicMock(return_value={"roomnumber": "1"})
        ), patch.dict(useradd.__salt__, {"cmd.run": mock}):
            with pytest.raises(CommandExecutionError):
                useradd.chroomnumber("salt", 2)
        mock.assert_not_called()

    # command found
    with patch("salt.utils.path.which", MagicMock(return_value="/sbin/usermod")):
        mock = MagicMock(return_value=False)
        with patch.object(useradd, "_get_gecos", mock):
            assert useradd.chroomnumber("salt", 1) is False

        mock = MagicMock(return_value={"roomnumber": "1"})
        with patch.object(useradd, "_get_gecos", mock):
            assert useradd.chroomnumber("salt", 1) is True

        mock = MagicMock(return_value={"roomnumber": "2"})
        with patch.object(useradd, "_get_gecos", mock):
            mock = MagicMock(return_value=None)
            with patch.dict(useradd.__salt__, {"cmd.run": mock}):
                mock = MagicMock(return_value={"roomnumber": "3"})
                with patch.object(useradd, "info", mock):
                    assert useradd.chroomnumber("salt", 1) is False

        mock = MagicMock(return_value={"roomnumber": "3"})
        with patch.object(useradd, "_get_gecos", mock):
            mock = MagicMock(return_value=None)
            with patch.dict(useradd.__salt__, {"cmd.run": mock}):
                mock = MagicMock(return_value={"roomnumber": "3"})


def test_chworkphone():
    # command not found
    with patch("salt.utils.path.which", MagicMock(return_value=None)):
        mock = MagicMock()
        with patch.object(
            useradd, "_get_gecos", MagicMock(return_value={"workphone": "1"})
        ), patch.dict(useradd.__salt__, {"cmd.run": mock}):
            with pytest.raises(CommandExecutionError):
                useradd.chworkphone("salt", 2)
        mock.assert_not_called()

    # command found
    with patch("salt.utils.path.which", MagicMock(return_value="/sbin/usermod")):
        mock = MagicMock(return_value=False)
        with patch.object(useradd, "_get_gecos", mock):
            assert useradd.chworkphone("salt", 1) is False

        mock = MagicMock(return_value={"workphone": "1"})
        with patch.object(useradd, "_get_gecos", mock):
            assert useradd.chworkphone("salt", 1) is True

        mock = MagicMock(return_value={"workphone": "2"})
        with patch.object(useradd, "_get_gecos", mock):
            mock = MagicMock(return_value=None)
            with patch.dict(useradd.__salt__, {"cmd.run": mock}):
                mock = MagicMock(return_value={"workphone": "3"})
                with patch.object(useradd, "info", mock):
                    assert useradd.chworkphone("salt", 1) is False

        mock = MagicMock(return_value={"workphone": "3"})
        with patch.object(useradd, "_get_gecos", mock):
            mock = MagicMock(return_value=None)
            with patch.dict(useradd.__salt__, {"cmd.run": mock}):
                mock = MagicMock(return_value={"workphone": "3"})
                with patch.object(useradd, "info", mock):
                    assert useradd.chworkphone("salt", 1) is False


def test_chhomephone():
    # command not found
    with patch("salt.utils.path.which", MagicMock(return_value=None)):
        mock = MagicMock()
        with patch.object(
            useradd, "_get_gecos", MagicMock(return_value={"homephone": "1"})
        ), patch.dict(useradd.__salt__, {"cmd.run": mock}):
            with pytest.raises(CommandExecutionError):
                useradd.chhomephone("salt", 2)
        mock.assert_not_called()

    # command found
    with patch("salt.utils.path.which", MagicMock(return_value="/sbin/usermod")):
        mock = MagicMock(return_value=False)
        with patch.object(useradd, "_get_gecos", mock):
            assert useradd.chhomephone("salt", 1) is False

        mock = MagicMock(return_value={"homephone": "1"})
        with patch.object(useradd, "_get_gecos", mock):
            assert useradd.chhomephone("salt", 1) is True

        mock = MagicMock(return_value={"homephone": "2"})
        with patch.object(useradd, "_get_gecos", mock):
            mock = MagicMock(return_value=None)
            with patch.dict(useradd.__salt__, {"cmd.run": mock}):
                mock = MagicMock(return_value={"homephone": "3"})
                with patch.object(useradd, "info", mock):
                    assert useradd.chhomephone("salt", 1) is False

        mock = MagicMock(return_value={"homephone": "3"})
        with patch.object(useradd, "_get_gecos", mock):
            mock = MagicMock(return_value=None)
            with patch.dict(useradd.__salt__, {"cmd.run": mock}):
                mock = MagicMock(return_value={"homephone": "3"})
                with patch.object(useradd, "info", mock):
                    assert useradd.chhomephone("salt", 1) is False


def test_chother():
    # command not found
    with patch("salt.utils.path.which", MagicMock(return_value=None)):
        mock = MagicMock()
        with patch.object(
            useradd, "_get_gecos", MagicMock(return_value={"other": "1"})
        ), patch.dict(useradd.__salt__, {"cmd.run": mock}):
            with pytest.raises(CommandExecutionError):
                useradd.chother("salt", 2)
        mock.assert_not_called()

    # command found
    with patch("salt.utils.path.which", MagicMock(return_value="/sbin/usermod")):
        mock = MagicMock(return_value=False)
        with patch.object(useradd, "_get_gecos", mock):
            assert useradd.chother("salt", 1) is False

        mock = MagicMock(return_value={"other": "foobar"})
        with patch.object(useradd, "_get_gecos", mock):
            assert useradd.chother("salt", "foobar") is True

        mock = MagicMock(return_value={"other": "foobar2"})
        with patch.object(useradd, "_get_gecos", mock):
            mock = MagicMock(return_value=None)
            with patch.dict(useradd.__salt__, {"cmd.run": mock}):
                mock = MagicMock(return_value={"other": "foobar3"})
                with patch.object(useradd, "info", mock):
                    assert useradd.chother("salt", "foobar") is False

        mock = MagicMock(return_value={"other": "foobar3"})
        with patch.object(useradd, "_get_gecos", mock):
            mock = MagicMock(return_value=None)
            with patch.dict(useradd.__salt__, {"cmd.run": mock}):
                mock = MagicMock(return_value={"other": "foobar3"})
                with patch.object(useradd, "info", mock):
                    assert useradd.chother("salt", "foobar") is False
