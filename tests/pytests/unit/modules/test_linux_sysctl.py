"""
Tests for salt.modules.linux_sysctl module

:codeauthor: jmoney <justin@saltstack.com>
"""

import pytest
import salt.modules.linux_sysctl as linux_sysctl
import salt.modules.systemd_service as systemd
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, mock_open, patch


@pytest.fixture
def configure_loader_modules():
    return {linux_sysctl: {}, systemd: {}}


def test_get():
    """
    Tests the return of get function
    """
    mock_cmd = MagicMock(return_value=1)
    with patch.dict(linux_sysctl.__salt__, {"cmd.run": mock_cmd}):
        assert linux_sysctl.get("net.ipv4.ip_forward") == 1


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
        with patch.dict(linux_sysctl.__salt__, {"cmd.run_all": mock_cmd}):
            with pytest.raises(CommandExecutionError):
                linux_sysctl.assign("net.ipv4.ip_forward", "backward")


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
        with patch.dict(linux_sysctl.__salt__, {"cmd.run_all": mock_cmd}):
            assert linux_sysctl.assign("net.ipv4.ip_forward", 1) == ret


def test_persist_no_conf_failure():
    """
    Tests adding of config file failure
    """
    asn_cmd = {
        "pid": 1337,
        "retcode": 0,
        "stderr": "sysctl: permission denied",
        "stdout": "",
    }
    mock_asn_cmd = MagicMock(return_value=asn_cmd)
    cmd = "sysctl -w net.ipv4.ip_forward=1"
    mock_cmd = MagicMock(return_value=cmd)
    with patch.dict(
        linux_sysctl.__salt__,
        {"cmd.run_stdout": mock_cmd, "cmd.run_all": mock_asn_cmd},
    ):
        with patch("salt.utils.files.fopen", mock_open()) as m_open:
            with pytest.raises(CommandExecutionError):
                linux_sysctl.persist("net.ipv4.ip_forward", 1, config=None)


def test_persist_no_conf_success():
    """
    Tests successful add of config file when previously not one
    """
    config = "/etc/sysctl.conf"
    with patch("os.path.isfile", MagicMock(return_value=False)), patch(
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

        with patch("salt.utils.files.fopen", mock_open()):
            with patch.dict(
                linux_sysctl.__context__, {"salt.utils.systemd.version": 232}
            ):
                with patch.dict(
                    linux_sysctl.__salt__,
                    {"cmd.run_stdout": mock_sys_cmd, "cmd.run_all": mock_asn_cmd},
                ):
                    with patch.dict(
                        systemd.__context__, {"salt.utils.systemd.booted": True}
                    ):
                        assert (
                            linux_sysctl.persist("net.ipv4.ip_forward", 1) == "Updated"
                        )
