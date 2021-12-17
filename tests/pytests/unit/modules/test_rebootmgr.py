import pytest
import salt.modules.rebootmgr as rebootmgr
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {rebootmgr: {"__salt__": {}, "__utils__": {}}}


def test_version():
    """
    Test rebootmgr.version without parameters
    """
    version = "rebootmgrctl (rebootmgr) 1.3"
    salt_mock = {
        "cmd.run_all": MagicMock(return_value={"stdout": version, "retcode": 0})
    }
    with patch.dict(rebootmgr.__salt__, salt_mock):
        assert rebootmgr.version() == "1.3"
        salt_mock["cmd.run_all"].assert_called_with(["rebootmgrctl", "--version"])


def test_is_active():
    """
    Test rebootmgr.is_active without parameters
    """
    salt_mock = {"cmd.run_all": MagicMock(return_value={"stdout": None, "retcode": 0})}
    with patch.dict(rebootmgr.__salt__, salt_mock):
        assert rebootmgr.is_active()
        salt_mock["cmd.run_all"].assert_called_with(
            ["rebootmgrctl", "is_active", "--quiet"]
        )


def test_reboot():
    """
    Test rebootmgr.reboot without parameters
    """
    salt_mock = {
        "cmd.run_all": MagicMock(return_value={"stdout": "output", "retcode": 0})
    }
    with patch.dict(rebootmgr.__salt__, salt_mock):
        assert rebootmgr.reboot() == "output"
        salt_mock["cmd.run_all"].assert_called_with(["rebootmgrctl", "reboot"])


def test_reboot_order():
    """
    Test rebootmgr.reboot with order parameter
    """
    salt_mock = {
        "cmd.run_all": MagicMock(return_value={"stdout": "output", "retcode": 0})
    }
    with patch.dict(rebootmgr.__salt__, salt_mock):
        assert rebootmgr.reboot("now") == "output"
        salt_mock["cmd.run_all"].assert_called_with(["rebootmgrctl", "reboot", "now"])


def test_reboot_invalid():
    """
    Test rebootmgr.reboot with invalid parameter
    """
    salt_mock = {
        "cmd.run_all": MagicMock(return_value={"stdout": "output", "retcode": 0})
    }
    with patch.dict(rebootmgr.__salt__, salt_mock):
        with pytest.raises(CommandExecutionError):
            rebootmgr.reboot("invalid")


def test_cancel():
    """
    Test rebootmgr.cancel without parameters
    """
    salt_mock = {
        "cmd.run_all": MagicMock(return_value={"stdout": "output", "retcode": 0})
    }
    with patch.dict(rebootmgr.__salt__, salt_mock):
        assert rebootmgr.cancel() == "output"
        salt_mock["cmd.run_all"].assert_called_with(["rebootmgrctl", "cancel"])


def test_status():
    """
    Test rebootmgr.status without parameters
    """
    salt_mock = {
        "cmd.run_all": MagicMock(return_value={"stdout": "output", "retcode": 0})
    }
    with patch.dict(rebootmgr.__salt__, salt_mock):
        # 0 - No reboot requested
        assert rebootmgr.status() == 0
        salt_mock["cmd.run_all"].assert_called_with(
            ["rebootmgrctl", "status", "--quiet"]
        )


def test_set_strategy_default():
    """
    Test rebootmgr.set_strategy without parameters
    """
    salt_mock = {
        "cmd.run_all": MagicMock(return_value={"stdout": "output", "retcode": 0})
    }
    with patch.dict(rebootmgr.__salt__, salt_mock):
        assert rebootmgr.set_strategy() == "output"
        salt_mock["cmd.run_all"].assert_called_with(["rebootmgrctl", "set-strategy"])


def test_set_strategy():
    """
    Test rebootmgr.set_strategy with strategy parameter
    """
    salt_mock = {
        "cmd.run_all": MagicMock(return_value={"stdout": "output", "retcode": 0})
    }
    with patch.dict(rebootmgr.__salt__, salt_mock):
        assert rebootmgr.set_strategy("best-effort") == "output"
        salt_mock["cmd.run_all"].assert_called_with(
            ["rebootmgrctl", "set-strategy", "best-effort"]
        )


def test_set_strategy_invalid():
    """
    Test rebootmgr.strategy with invalid parameter
    """
    salt_mock = {
        "cmd.run_all": MagicMock(return_value={"stdout": "output", "retcode": 0})
    }
    with patch.dict(rebootmgr.__salt__, salt_mock):
        with pytest.raises(CommandExecutionError):
            rebootmgr.set_strategy("invalid")


def test_get_strategy():
    """
    Test rebootmgr.get_strategy without parameters
    """
    strategy = "Reboot strategy: best-effort"
    salt_mock = {
        "cmd.run_all": MagicMock(return_value={"stdout": strategy, "retcode": 0})
    }
    with patch.dict(rebootmgr.__salt__, salt_mock):
        assert rebootmgr.get_strategy() == "best-effort"
        salt_mock["cmd.run_all"].assert_called_with(["rebootmgrctl", "get-strategy"])


def test_set_window():
    """
    Test rebootmgr.set_window with parameters
    """
    salt_mock = {
        "cmd.run_all": MagicMock(return_value={"stdout": "output", "retcode": 0})
    }
    with patch.dict(rebootmgr.__salt__, salt_mock):
        assert rebootmgr.set_window("Thu,Fri 2020-*-1,5 11:12:13", "1h") == "output"
        salt_mock["cmd.run_all"].assert_called_with(
            ["rebootmgrctl", "set-window", "Thu,Fri 2020-*-1,5 11:12:13", "1h"]
        )


def test_get_window():
    """
    Test rebootmgr.get_window without parameters
    """
    window = "Maintenance window is set to *-*-* 03:30:00, lasting 01h30m."
    salt_mock = {
        "cmd.run_all": MagicMock(return_value={"stdout": window, "retcode": 0})
    }
    with patch.dict(rebootmgr.__salt__, salt_mock):
        assert rebootmgr.get_window() == {
            "time": "*-*-* 03:30:00",
            "duration": "01h30m",
        }
        salt_mock["cmd.run_all"].assert_called_with(["rebootmgrctl", "get-window"])


def test_set_group():
    """
    Test rebootmgr.set_group with parameters
    """
    salt_mock = {
        "cmd.run_all": MagicMock(return_value={"stdout": "output", "retcode": 0})
    }
    with patch.dict(rebootmgr.__salt__, salt_mock):
        assert rebootmgr.set_group("group1") == "output"
        salt_mock["cmd.run_all"].assert_called_with(
            ["rebootmgrctl", "set-group", "group1"]
        )


def test_get_group():
    """
    Test rebootmgr.get_group without parameters
    """
    group = "Etcd lock group is set to group1"
    salt_mock = {"cmd.run_all": MagicMock(return_value={"stdout": group, "retcode": 0})}
    with patch.dict(rebootmgr.__salt__, salt_mock):
        assert rebootmgr.get_group() == "group1"
        salt_mock["cmd.run_all"].assert_called_with(["rebootmgrctl", "get-group"])


def test_set_max():
    """
    Test rebootmgr.set_max with default parameters
    """
    salt_mock = {
        "cmd.run_all": MagicMock(return_value={"stdout": "output", "retcode": 0})
    }
    with patch.dict(rebootmgr.__salt__, salt_mock):
        assert rebootmgr.set_max(10) == "output"
        salt_mock["cmd.run_all"].assert_called_with(["rebootmgrctl", "set-max", 10])


def test_set_max_group():
    """
    Test rebootmgr.set_max with group parameter
    """
    salt_mock = {
        "cmd.run_all": MagicMock(return_value={"stdout": "output", "retcode": 0})
    }
    with patch.dict(rebootmgr.__salt__, salt_mock):
        assert rebootmgr.set_max(10, "group1") == "output"
        salt_mock["cmd.run_all"].assert_called_with(
            ["rebootmgrctl", "set-max", "--group", "group1", 10]
        )


def test_lock():
    """
    Test rebootmgr.lock without parameters
    """
    salt_mock = {
        "cmd.run_all": MagicMock(return_value={"stdout": "output", "retcode": 0})
    }
    with patch.dict(rebootmgr.__salt__, salt_mock):
        assert rebootmgr.lock() == "output"
        salt_mock["cmd.run_all"].assert_called_with(["rebootmgrctl", "lock"])


def test_lock_machine_id():
    """
    Test rebootmgr.lock with machine_id parameter
    """
    salt_mock = {
        "cmd.run_all": MagicMock(return_value={"stdout": "output", "retcode": 0})
    }
    with patch.dict(rebootmgr.__salt__, salt_mock):
        assert rebootmgr.lock("machine-id") == "output"
        salt_mock["cmd.run_all"].assert_called_with(
            ["rebootmgrctl", "lock", "machine-id"]
        )


def test_lock_machine_id_group():
    """
    Test rebootmgr.lock with machine_id and group parameters
    """
    salt_mock = {
        "cmd.run_all": MagicMock(return_value={"stdout": "output", "retcode": 0})
    }
    with patch.dict(rebootmgr.__salt__, salt_mock):
        assert rebootmgr.lock("machine-id", "group1") == "output"
        salt_mock["cmd.run_all"].assert_called_with(
            ["rebootmgrctl", "lock", "--group", "group1", "machine-id"]
        )


def test_unlock():
    """
    Test rebootmgr.unlock without parameters
    """
    salt_mock = {
        "cmd.run_all": MagicMock(return_value={"stdout": "output", "retcode": 0})
    }
    with patch.dict(rebootmgr.__salt__, salt_mock):
        assert rebootmgr.unlock() == "output"
        salt_mock["cmd.run_all"].assert_called_with(["rebootmgrctl", "unlock"])


def test_unlock_machine_id():
    """
    Test rebootmgr.unlock with machine_id parameter
    """
    salt_mock = {
        "cmd.run_all": MagicMock(return_value={"stdout": "output", "retcode": 0})
    }
    with patch.dict(rebootmgr.__salt__, salt_mock):
        assert rebootmgr.unlock("machine-id") == "output"
        salt_mock["cmd.run_all"].assert_called_with(
            ["rebootmgrctl", "unlock", "machine-id"]
        )


def test_unlock_machine_id_group():
    """
    Test rebootmgr.unlock with machine_id and group parameters
    """
    salt_mock = {
        "cmd.run_all": MagicMock(return_value={"stdout": "output", "retcode": 0})
    }
    with patch.dict(rebootmgr.__salt__, salt_mock):
        assert rebootmgr.unlock("machine-id", "group1") == "output"
        salt_mock["cmd.run_all"].assert_called_with(
            ["rebootmgrctl", "unlock", "--group", "group1", "machine-id"]
        )
