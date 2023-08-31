"""
    :codeauthor: :email:`Jasper Lievisse Adriaanse <j@jasper.la>`
"""

import pytest

import salt.modules.openbsd_sysctl as openbsd_sysctl
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {openbsd_sysctl: {}}


def test_get():
    """
    Tests the return of get function
    """
    mock_cmd = MagicMock(return_value="OpenBSD")
    with patch.dict(openbsd_sysctl.__salt__, {"cmd.run": mock_cmd}):
        assert openbsd_sysctl.get("kern.ostype") == "OpenBSD"


def test_assign_cmd_failed():
    """
    Tests if the assignment was successful or not
    """
    cmd = {
        "pid": 1234,
        "retcode": 1,
        "stderr": "",
        "stdout": "kern.securelevel: 1 -> 9000",
    }
    mock_cmd = MagicMock(return_value=cmd)
    with patch.dict(openbsd_sysctl.__salt__, {"cmd.run_all": mock_cmd}):
        pytest.raises(
            CommandExecutionError, openbsd_sysctl.assign, "kern.securelevel", 9000
        )


def test_assign_cmd_eperm():
    """
    Tests if the assignment was not permitted.
    """
    cmd = {
        "pid": 1234,
        "retcode": 0,
        "stdout": "",
        "stderr": "sysctl: ddb.console: Operation not permitted",
    }
    mock_cmd = MagicMock(return_value=cmd)
    with patch.dict(openbsd_sysctl.__salt__, {"cmd.run_all": mock_cmd}):
        pytest.raises(CommandExecutionError, openbsd_sysctl.assign, "ddb.console", 1)


def test_assign():
    """
    Tests the return of successful assign function
    """
    cmd = {
        "pid": 1234,
        "retcode": 0,
        "stderr": "",
        "stdout": "net.inet.ip.forwarding: 0 -> 1",
    }
    ret = {"net.inet.ip.forwarding": "1"}
    mock_cmd = MagicMock(return_value=cmd)
    with patch.dict(openbsd_sysctl.__salt__, {"cmd.run_all": mock_cmd}):
        assert openbsd_sysctl.assign("net.inet.ip.forwarding", 1) == ret
