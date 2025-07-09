"""
    Test for salt.modules.vmctl
"""

import pytest

import salt.modules.vmctl as vmctl
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {vmctl: {}}


def test_create_disk():
    """
    Tests creating a new disk image.
    """
    ret = {}
    ret["stdout"] = "vmctl: imagefile created"
    ret["stderr"] = ""
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(vmctl.__salt__, {"cmd.run_all": mock_cmd}):
        assert vmctl.create_disk("/path/to/disk.img", "1G")


def test_load():
    """
    Tests loading a configuration file.
    """
    ret = {}
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(vmctl.__salt__, {"cmd.run_all": mock_cmd}):
        assert vmctl.load("/etc/vm.switches.conf")


def test_reload():
    """
    Tests reloading the configuration.
    """
    ret = {}
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(vmctl.__salt__, {"cmd.run_all": mock_cmd}):
        assert vmctl.reload()


def test_reset():
    """
    Tests resetting VMM.
    """
    ret = {}
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(vmctl.__salt__, {"cmd.run_all": mock_cmd}):
        res = vmctl.reset()
        mock_cmd.assert_called_once_with(
            ["vmctl", "reset"], output_loglevel="trace", python_shell=False
        )
        assert res


def test_reset_vms():
    """
    Tests resetting VMs.
    """
    ret = {}
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(vmctl.__salt__, {"cmd.run_all": mock_cmd}):
        res = vmctl.reset(vms=True)
        mock_cmd.assert_called_once_with(
            ["vmctl", "reset", "vms"], output_loglevel="trace", python_shell=False
        )
        assert res


def test_reset_switches():
    """
    Tests resetting switches.
    """
    ret = {}
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(vmctl.__salt__, {"cmd.run_all": mock_cmd}):
        res = vmctl.reset(switches=True)
        mock_cmd.assert_called_once_with(
            ["vmctl", "reset", "switches"],
            output_loglevel="trace",
            python_shell=False,
        )
        assert res


def test_reset_all():
    """
    Tests resetting all.
    """
    ret = {}
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(vmctl.__salt__, {"cmd.run_all": mock_cmd}):
        res = vmctl.reset(all=True)
        mock_cmd.assert_called_once_with(
            ["vmctl", "reset", "all"], output_loglevel="trace", python_shell=False
        )
        assert res


def test_start_existing_vm():
    """
    Tests starting a VM that is already defined.
    """
    ret = {}
    ret["stderr"] = "vmctl: started vm 4 successfully, tty /dev/ttyp4"
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    expected = {"changes": True, "console": "/dev/ttyp4"}
    with patch.dict(vmctl.__salt__, {"cmd.run_all": mock_cmd}):
        assert vmctl.start("4") == expected


def test_start_new_vm():
    """
    Tests starting a new VM.
    """
    ret = {}
    ret["stderr"] = "vmctl: started vm 4 successfully, tty /dev/ttyp4"
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    mock_status = MagicMock(return_value={})
    expected = {"changes": True, "console": "/dev/ttyp4"}
    with patch.dict(vmctl.__salt__, {"cmd.run_all": mock_cmd}):
        with patch("salt.modules.vmctl.status", mock_status):
            res = vmctl.start("web1", bootpath="/bsd.rd", nics=2, disk="/disk.img")
            mock_cmd.assert_called_once_with(
                [
                    "vmctl",
                    "start",
                    "web1",
                    "-i 2",
                    "-b",
                    "/bsd.rd",
                    "-d",
                    "/disk.img",
                ],
                output_loglevel="trace",
                python_shell=False,
            )
            assert res == expected


def test_status():
    """
    Tests getting status for all VMs.
    """
    ret = {}
    ret["stdout"] = (
        "   ID   PID VCPUS  MAXMEM  CURMEM     TTY        OWNER NAME\n"
        "    1   123     1    2.9G     150M  ttyp5       john web1 - stopping\n"
        "    2   456     1    512M     301M  ttyp4       paul web2\n"
        "    3     -     1    512M       -       -       george web3\n"
    )
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    expected = {
        "web1": {
            "curmem": "150M",
            "id": "1",
            "maxmem": "2.9G",
            "owner": "john",
            "pid": "123",
            "state": "stopping",
            "tty": "ttyp5",
            "vcpus": "1",
        },
        "web2": {
            "curmem": "301M",
            "id": "2",
            "maxmem": "512M",
            "owner": "paul",
            "pid": "456",
            "state": "running",
            "tty": "ttyp4",
            "vcpus": "1",
        },
        "web3": {
            "curmem": "-",
            "id": "3",
            "maxmem": "512M",
            "owner": "george",
            "pid": "-",
            "state": "stopped",
            "tty": "-",
            "vcpus": "1",
        },
    }
    with patch.dict(vmctl.__salt__, {"cmd.run_all": mock_cmd}):
        assert vmctl.status() == expected


def test_status_single():
    """
    Tests getting status for a single VM.
    """
    ret = {}
    ret["stdout"] = (
        "   ID   PID VCPUS  MAXMEM  CURMEM     TTY        OWNER NAME\n"
        "    1   123     1    2.9G     150M  ttyp5       ringo web4\n"
        "    2     -     1    512M       -       -       george web3\n"
    )
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    expected = {
        "web4": {
            "curmem": "150M",
            "id": "1",
            "maxmem": "2.9G",
            "owner": "ringo",
            "pid": "123",
            "state": "running",
            "tty": "ttyp5",
            "vcpus": "1",
        },
    }
    with patch.dict(vmctl.__salt__, {"cmd.run_all": mock_cmd}):
        assert vmctl.status("web4") == expected


def test_stop_when_running():
    """
    Tests stopping a VM that is running.
    """
    ret = {}
    ret["stdout"] = ""
    ret["stderr"] = "vmctl: sent request to terminate vm 14"
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(vmctl.__salt__, {"cmd.run_all": mock_cmd}):
        res = vmctl.stop("web1")
        mock_cmd.assert_called_once_with(
            ["vmctl", "stop", "web1"], output_loglevel="trace", python_shell=False
        )
        assert res["changes"]


def test_stop_when_stopped():
    """
    Tests stopping a VM that is already stopped/stopping.
    """
    ret = {}
    ret["stdout"] = ""
    ret["stderr"] = "vmctl: terminate vm command failed: Invalid argument"
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(vmctl.__salt__, {"cmd.run_all": mock_cmd}):
        res = vmctl.stop("web1")
        mock_cmd.assert_called_once_with(
            ["vmctl", "stop", "web1"], output_loglevel="trace", python_shell=False
        )
        assert not res["changes"]
