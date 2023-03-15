"""
Tests for salt.modules.linux_sysctl module

:codeauthor: jmoney <justin@saltstack.com>
"""

import os

import pytest

import salt.modules.linux_sysctl as linux_sysctl
import salt.modules.systemd_service as systemd
from salt.exceptions import CommandExecutionError
from salt.utils.files import fopen
from tests.support.mock import MagicMock, mock_open, patch

pytestmark = [
    pytest.mark.skip_on_windows(reason="sysctl not available on Windows"),
]


@pytest.fixture
def configure_loader_modules():
    return {linux_sysctl: {}, systemd: {}}


def test_get():
    """
    Tests the return of get function
    """
    mock_cmd = MagicMock(return_value=1)
    which_mock = MagicMock(return_value="/usr/sbin/sysctl")
    with patch("salt.utils.path.which", which_mock):
        with patch.dict(linux_sysctl.__salt__, {"cmd.run": mock_cmd}):
            assert linux_sysctl.get("net.ipv4.ip_forward") == 1
    mock_cmd.assert_called_once_with(
        ["/usr/sbin/sysctl", "-n", "net.ipv4.ip_forward"], python_shell=False
    )


def test_show():
    """
    Tests the return of show function
    """
    mock_cmd = MagicMock(
        return_value="""\
kernel.core_pattern = |/usr/share/kdump-tools/dump-core %p %s %t %e
kernel.printk = 3 4 1 3
net.ipv4.ip_forward = 1
net.ipv4.tcp_rmem = 4096	131072	6291456
"""
    )
    which_mock = MagicMock(return_value="/usr/sbin/sysctl")
    with patch("salt.utils.path.which", which_mock):
        with patch.dict(linux_sysctl.__salt__, {"cmd.run_stdout": mock_cmd}):
            assert linux_sysctl.show() == {
                "kernel.core_pattern": "|/usr/share/kdump-tools/dump-core %p %s %t %e",
                "kernel.printk": "3 4 1 3",
                "net.ipv4.ip_forward": "1",
                "net.ipv4.tcp_rmem": "4096\t131072\t6291456",
            }
    mock_cmd.assert_called_once_with(
        ["/usr/sbin/sysctl", "-a"], output_loglevel="trace"
    )


def test_show_config_file(tmp_path):
    """
    Tests the return of show function for a given file
    """
    config = str(tmp_path / "sysctl.conf")
    with fopen(config, "w", encoding="utf-8") as config_file:
        config_file.write(
            """\
# Use dump-core from kdump-tools Debian package.
kernel.core_pattern = |/usr/share/kdump-tools/dump-core %p %s %t %e
 # Stop low-level messages on console = less logging
 kernel.printk  = 3 4 1 3

net.ipv4.ip_forward=1
net.ipv4.tcp_rmem	=	4096	131072	6291456
"""
        )
    assert linux_sysctl.show(config) == {
        "kernel.core_pattern": "|/usr/share/kdump-tools/dump-core %p %s %t %e",
        "kernel.printk": "3 4 1 3",
        "net.ipv4.ip_forward": "1",
        "net.ipv4.tcp_rmem": "4096\t131072\t6291456",
    }


def test_get_no_sysctl_binary():
    """
    Tests the failure of get function when no binary exists
    """
    with patch("salt.utils.path.which", MagicMock(return_value=None)):
        with pytest.raises(CommandExecutionError):
            linux_sysctl.get("net.ipv4.ip_forward")


def test_assign_proc_sys_failed():
    """
    Tests if /proc/sys/<kernel-subsystem> exists or not
    """
    with patch("os.path.exists", MagicMock(return_value=False)):
        cmd = {
            "pid": 1337,
            "retcode": 0,
            "stderr": "",
            "stdout": "net.ipv4.ip_forward = 1",
        }
        mock_cmd = MagicMock(return_value=cmd)
        with patch.dict(linux_sysctl.__salt__, {"cmd.run_all": mock_cmd}):
            with pytest.raises(CommandExecutionError):
                linux_sysctl.assign("net.ipv4.ip_forward", 1)
        mock_cmd.assert_not_called()


def test_assign_cmd_failed():
    """
    Tests if the assignment was successful or not
    """
    with patch("os.path.exists", MagicMock(return_value=True)):
        cmd = {
            "pid": 1337,
            "retcode": 0,
            "stderr": 'sysctl: setting key "net.ipv4.ip_forward": Invalid argument',
            "stdout": "net.ipv4.ip_forward = backward",
        }
        mock_cmd = MagicMock(return_value=cmd)
        which_mock = MagicMock(return_value="/usr/sbin/sysctl")
        with patch("salt.utils.path.which", which_mock):
            with patch.dict(linux_sysctl.__salt__, {"cmd.run_all": mock_cmd}):
                with pytest.raises(CommandExecutionError):
                    linux_sysctl.assign("net.ipv4.ip_forward", "backward")
        mock_cmd.assert_called_once_with(
            ["/usr/sbin/sysctl", "-w", "net.ipv4.ip_forward=backward"],
            python_shell=False,
        )


def test_assign_success():
    """
    Tests the return of successful assign function
    """
    with patch("os.path.exists", MagicMock(return_value=True)):
        cmd = {
            "pid": 1337,
            "retcode": 0,
            "stderr": "",
            "stdout": "net.ipv4.ip_forward = 1",
        }
        ret = {"net.ipv4.ip_forward": "1"}
        mock_cmd = MagicMock(return_value=cmd)
        which_mock = MagicMock(return_value="/usr/sbin/sysctl")
        with patch("salt.utils.path.which", which_mock):
            with patch.dict(linux_sysctl.__salt__, {"cmd.run_all": mock_cmd}):
                assert linux_sysctl.assign("net.ipv4.ip_forward", 1) == ret
        mock_cmd.assert_called_once_with(
            ["/usr/sbin/sysctl", "-w", "net.ipv4.ip_forward=1"], python_shell=False
        )


def test_sanitize_sysctl_value():
    assert (
        linux_sysctl._sanitize_sysctl_value("4096 131072  6291456")
        == "4096\t131072\t6291456"
    )


def test_sanitize_sysctl_value_int():
    assert linux_sysctl._sanitize_sysctl_value(1337) == "1337"


def test_persist_int(tmp_path):
    """
    Tests linux_sysctl.persist for an integer that is already set.
    """
    config = str(tmp_path / "sysctl.conf")
    config_file_content = "fs.suid_dumpable = 2\n"
    with fopen(config, "w", encoding="utf-8") as config_file:
        config_file.write(config_file_content)
    mock_run = MagicMock(return_value="2")
    mock_run_all = MagicMock()
    which_mock = MagicMock(return_value="/usr/sbin/sysctl")
    with patch("salt.utils.path.which", which_mock):
        with patch("os.path.exists", MagicMock(return_value=True)), patch.dict(
            linux_sysctl.__salt__, {"cmd.run": mock_run, "cmd.run_all": mock_run_all}
        ):
            assert (
                linux_sysctl.persist("fs.suid_dumpable", 2, config=config)
                == "Already set"
            )
            mock_run.assert_called_once_with(
                ["/usr/sbin/sysctl", "-n", "fs.suid_dumpable"], python_shell=False
            )
            mock_run_all.assert_not_called()
    assert os.path.isfile(config)
    with fopen(config, encoding="utf-8") as config_file:
        written = config_file.read()
    assert written == config_file_content


def test_persist_no_conf_failure():
    """
    Tests adding of config file failure
    """
    fopen_mock = MagicMock(side_effect=OSError())
    which_mock = MagicMock(return_value="/usr/sbin/sysctl")
    with patch("salt.utils.path.which", which_mock):
        with patch("os.path.isfile", MagicMock(return_value=False)), patch(
            "os.path.exists", MagicMock(return_value=False)
        ), patch("os.makedirs", MagicMock()), patch(
            "salt.utils.files.fopen", fopen_mock
        ):
            with pytest.raises(CommandExecutionError):
                linux_sysctl.persist("net.ipv4.ip_forward", 42, config=None)
    fopen_mock.called_once()


def test_persist_no_conf_success():
    """
    Tests successful add of config file when previously not one
    """
    config = "/etc/sysctl.conf"
    with patch("os.path.isfile", MagicMock(return_value=False)), patch(
        "os.path.exists", MagicMock(return_value=True)
    ), patch("salt.utils.path.which", MagicMock(return_value="/bin/sysctl")):
        asn_cmd = {
            "pid": 1337,
            "retcode": 0,
            "stderr": "",
            "stdout": "net.ipv4.ip_forward = 1",
        }
        mock_asn_cmd = MagicMock(return_value=asn_cmd)

        sys_cmd = "systemd 208\n+PAM +LIBWRAP"
        mock_sys_cmd = MagicMock(return_value=sys_cmd)

        which_mock = MagicMock(return_value="/usr/sbin/sysctl")
        with patch("salt.utils.path.which", which_mock):
            with patch("salt.utils.files.fopen", mock_open()) as m_open, patch.dict(
                linux_sysctl.__context__, {"salt.utils.systemd.version": 232}
            ), patch.dict(
                linux_sysctl.__salt__,
                {"cmd.run_stdout": mock_sys_cmd, "cmd.run_all": mock_asn_cmd},
            ), patch.dict(
                systemd.__context__,
                {"salt.utils.systemd.booted": True, "salt.utils.systemd.version": 232},
            ):
                linux_sysctl.persist("net.ipv4.ip_forward", 1, config=config)
                writes = m_open.write_calls()
                assert writes == ["#\n# Kernel sysctl configuration\n#\n"], writes
        mock_asn_cmd.assert_called_once_with(
            ["/usr/sbin/sysctl", "-w", "net.ipv4.ip_forward=1"], python_shell=False
        )


def test_persist_read_conf_success():
    """
    Tests sysctl.conf read success
    """
    with patch("os.path.isfile", MagicMock(return_value=True)), patch(
        "os.path.exists", MagicMock(return_value=True)
    ):
        asn_cmd = {
            "pid": 1337,
            "retcode": 0,
            "stderr": "",
            "stdout": "net.ipv4.ip_forward = 1",
        }
        mock_asn_cmd = MagicMock(return_value=asn_cmd)

        sys_cmd = "systemd 208\n+PAM +LIBWRAP"
        mock_sys_cmd = MagicMock(return_value=sys_cmd)

        which_mock = MagicMock(return_value="/usr/sbin/sysctl")
        with patch("salt.utils.path.which", which_mock):
            with patch("salt.utils.files.fopen", mock_open()), patch.dict(
                linux_sysctl.__context__, {"salt.utils.systemd.version": 232}
            ), patch.dict(
                linux_sysctl.__salt__,
                {"cmd.run_stdout": mock_sys_cmd, "cmd.run_all": mock_asn_cmd},
            ), patch.dict(
                systemd.__context__, {"salt.utils.systemd.booted": True}
            ):
                assert linux_sysctl.persist("net.ipv4.ip_forward", 1) == "Updated"
        mock_asn_cmd.assert_called_once_with(
            ["/usr/sbin/sysctl", "-w", "net.ipv4.ip_forward=1"], python_shell=False
        )


def test_persist_parsing_file(tmp_path):
    """
    Tests linux_sysctl.persist to correctly parse the config file.
    """
    config = str(tmp_path / "sysctl.conf")
    with fopen(config, "w", encoding="utf-8") as config_file:
        config_file.write(
            """\
# Use dump-core from kdump-tools Debian package.
kernel.core_pattern = |/usr/share/kdump-tools/dump-core %p %s %t %e
 # Stop low-level messages on console = less logging
 kernel.printk  = 3 4 1 3

 net.ipv4.ip_forward=1
net.ipv4.tcp_rmem	=	4096	131072	6291456
"""
        )
    mock_run = MagicMock()
    mock_run_all = MagicMock(
        return_value={
            "pid": 1337,
            "retcode": 0,
            "stderr": "",
            "stdout": "net.ipv4.ip_forward = 0",
        }
    )

    which_mock = MagicMock(return_value="/usr/sbin/sysctl")
    with patch("salt.utils.path.which", which_mock):
        with patch("os.path.exists", MagicMock(return_value=True)), patch.dict(
            linux_sysctl.__salt__, {"cmd.run": mock_run, "cmd.run_all": mock_run_all}
        ):
            assert (
                linux_sysctl.persist("net.ipv4.ip_forward", "0", config=config)
                == "Updated"
            )
            mock_run.assert_not_called()
            mock_run_all.assert_called_once_with(
                ["/usr/sbin/sysctl", "-w", "net.ipv4.ip_forward=0"], python_shell=False
            )
    assert os.path.isfile(config)
    with fopen(config, encoding="utf-8") as config_file:
        written = config_file.read()
    assert (
        written
        == """\
# Use dump-core from kdump-tools Debian package.
kernel.core_pattern = |/usr/share/kdump-tools/dump-core %p %s %t %e
 # Stop low-level messages on console = less logging
 kernel.printk  = 3 4 1 3

net.ipv4.ip_forward = 0
net.ipv4.tcp_rmem	=	4096	131072	6291456
"""
    )


def test_persist_value_with_spaces_already_set(tmp_path):
    """
    Tests linux_sysctl.persist for a value with spaces that is already set.
    """
    config = str(tmp_path / "existing_sysctl_with_spaces.conf")
    value = "|/usr/share/kdump-tools/dump-core %p %s %t %e"
    config_file_content = "kernel.core_pattern = {}\n".format(value)
    with fopen(config, "w", encoding="utf-8") as config_file:
        config_file.write(config_file_content)
    mock_run = MagicMock(return_value=value)
    mock_run_all = MagicMock()
    which_mock = MagicMock(return_value="/usr/sbin/sysctl")
    with patch("salt.utils.path.which", which_mock):
        with patch("os.path.exists", MagicMock(return_value=True)), patch.dict(
            linux_sysctl.__salt__, {"cmd.run": mock_run, "cmd.run_all": mock_run_all}
        ):
            assert (
                linux_sysctl.persist("kernel.core_pattern", value, config=config)
                == "Already set"
            )
            mock_run.assert_called_once_with(
                ["/usr/sbin/sysctl", "-n", "kernel.core_pattern"], python_shell=False
            )
            mock_run_all.assert_not_called()
    assert os.path.isfile(config)
    with fopen(config, encoding="utf-8") as config_file:
        written = config_file.read()
    assert written == config_file_content


def test_persist_value_with_spaces_already_configured(tmp_path):
    """
    Tests linux_sysctl.persist for a value with spaces that is only configured.
    """
    config = str(tmp_path / "existing_sysctl_with_spaces.conf")
    value = "|/usr/share/kdump-tools/dump-core %p %s %t %e"
    config_file_content = "kernel.core_pattern = {}\n".format(value)
    with fopen(config, "w", encoding="utf-8") as config_file:
        config_file.write(config_file_content)
    mock_run = MagicMock(return_value="")
    mock_run_all = MagicMock(
        return_value={
            "pid": 1337,
            "retcode": 0,
            "stderr": "",
            "stdout": "kernel.core_pattern = " + value,
        }
    )
    which_mock = MagicMock(return_value="/usr/sbin/sysctl")
    with patch("salt.utils.path.which", which_mock):
        with patch("os.path.exists", MagicMock(return_value=True)), patch.dict(
            linux_sysctl.__salt__, {"cmd.run": mock_run, "cmd.run_all": mock_run_all}
        ):
            assert (
                linux_sysctl.persist("kernel.core_pattern", value, config=config)
                == "Updated"
            )
            mock_run.assert_called_once_with(
                ["/usr/sbin/sysctl", "-n", "kernel.core_pattern"], python_shell=False
            )
            mock_run_all.assert_called_once_with(
                ["/usr/sbin/sysctl", "-w", "kernel.core_pattern=" + value],
                python_shell=False,
            )
    assert os.path.isfile(config)
    with fopen(config, encoding="utf-8") as config_file:
        written = config_file.read()
    assert written == config_file_content


def test_persist_value_with_spaces_update_config(tmp_path):
    """
    Tests linux_sysctl.persist for a value with spaces that differs from the config.
    """
    config = str(tmp_path / "existing_sysctl_with_spaces.conf")
    value = "|/usr/share/kdump-tools/dump-core %p %s %t %e"
    with fopen(config, "w", encoding="utf-8") as config_file:
        config_file.write("kernel.core_pattern =\n")
    mock_run = MagicMock()
    mock_run_all = MagicMock(
        return_value={
            "pid": 1337,
            "retcode": 0,
            "stderr": "",
            "stdout": "kernel.core_pattern = " + value,
        }
    )
    which_mock = MagicMock(return_value="/usr/sbin/sysctl")
    with patch("salt.utils.path.which", which_mock):
        with patch("os.path.exists", MagicMock(return_value=True)), patch.dict(
            linux_sysctl.__salt__, {"cmd.run": mock_run, "cmd.run_all": mock_run_all}
        ):
            assert (
                linux_sysctl.persist("kernel.core_pattern", value, config=config)
                == "Updated"
            )
            mock_run.assert_not_called()
            mock_run_all.assert_called_once_with(
                ["/usr/sbin/sysctl", "-w", "kernel.core_pattern=" + value],
                python_shell=False,
            )
    assert os.path.isfile(config)
    with fopen(config, encoding="utf-8") as config_file:
        written = config_file.read()
    assert written == "kernel.core_pattern = {}\n".format(value)


def test_persist_value_with_spaces_new_file(tmp_path):
    """
    Tests linux_sysctl.persist for a value that contains spaces.
    """
    config = str(tmp_path / "sysctl_with_spaces.conf")
    value = "|/usr/share/kdump-tools/dump-core %p %s %t %e"
    mock_run_all = MagicMock(
        return_value={
            "pid": 1337,
            "retcode": 0,
            "stderr": "",
            "stdout": "kernel.core_pattern = " + value,
        }
    )
    which_mock = MagicMock(return_value="/usr/sbin/sysctl")
    with patch("salt.utils.path.which", which_mock):
        with patch("os.path.exists", MagicMock(return_value=True)), patch.dict(
            linux_sysctl.__salt__, {"cmd.run_all": mock_run_all}
        ):
            assert (
                linux_sysctl.persist("kernel.core_pattern", value, config=config)
                == "Updated"
            )
            mock_run_all.assert_called_once_with(
                ["/usr/sbin/sysctl", "-w", "kernel.core_pattern=" + value],
                python_shell=False,
            )
    assert os.path.isfile(config)
    with fopen(config, encoding="utf-8") as config_file:
        written = config_file.read()
    assert (
        written
        == """\
#
# Kernel sysctl configuration
#
kernel.core_pattern = |/usr/share/kdump-tools/dump-core %p %s %t %e
"""
    )


def test_persist_value_with_tabs_new_file(tmp_path):
    """
    Tests linux_sysctl.persist for a value that contains tabs.
    """
    config = str(tmp_path / "sysctl_with_tabs.conf")
    value = "|/usr/share/kdump-tools/dump-core\t%p\t%s\t%t\t%e"
    mock_run_all = MagicMock(
        return_value={
            "pid": 1337,
            "retcode": 0,
            "stderr": "",
            "stdout": "kernel.core_pattern = " + value,
        }
    )
    which_mock = MagicMock(return_value="/usr/sbin/sysctl")
    with patch("salt.utils.path.which", which_mock):
        with patch("os.path.exists", MagicMock(return_value=True)), patch.dict(
            linux_sysctl.__salt__, {"cmd.run_all": mock_run_all}
        ):
            assert (
                linux_sysctl.persist("kernel.core_pattern", value, config=config)
                == "Updated"
            )
            mock_run_all.assert_called_once_with(
                ["/usr/sbin/sysctl", "-w", "kernel.core_pattern=" + value],
                python_shell=False,
            )
    assert os.path.isfile(config)
    with fopen(config, encoding="utf-8") as config_file:
        written = config_file.read()
    assert (
        written
        == """\
#
# Kernel sysctl configuration
#
kernel.core_pattern = |/usr/share/kdump-tools/dump-core	%p	%s	%t	%e
"""
    )
