import pytest
import salt.states.win_powercfg as powercfg
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {powercfg: {}}


def test_set_monitor():
    """
    Test to make sure we can set the monitor timeout value
    """
    ret = {
        "changes": {"monitor": {"ac": {"new": 0, "old": 45}}},
        "comment": "Monitor timeout on AC power set to 0",
        "name": "monitor",
        "result": True,
    }
    get_monitor_side_effect = MagicMock(
        side_effect=[{"ac": 45, "dc": 22}, {"ac": 0, "dc": 22}]
    )
    with patch.dict(
        powercfg.__salt__,
        {
            "powercfg.get_monitor_timeout": get_monitor_side_effect,
            "powercfg.set_monitor_timeout": MagicMock(return_value=True),
        },
    ):
        with patch.dict(powercfg.__opts__, {"test": False}):
            assert powercfg.set_timeout("monitor", 0) == ret


def test_set_monitor_already_set():
    """
    Test to make sure we can set the monitor timeout value
    """
    ret = {
        "changes": {},
        "comment": "Monitor timeout on AC power is already set to 0",
        "name": "monitor",
        "result": True,
    }
    monitor_val = MagicMock(return_value={"ac": 0, "dc": 0})
    with patch.dict(powercfg.__salt__, {"powercfg.get_monitor_timeout": monitor_val}):
        assert powercfg.set_timeout("monitor", 0) == ret


def test_set_monitor_test_true_with_change():
    """
    Test to make sure set monitor works correctly with test=True with
    changes
    """
    ret = {
        "changes": {},
        "comment": "Monitor timeout on AC power will be set to 0",
        "name": "monitor",
        "result": None,
    }
    get_monitor_return_value = MagicMock(return_value={"ac": 45, "dc": 22})
    with patch.dict(
        powercfg.__salt__,
        {"powercfg.get_monitor_timeout": get_monitor_return_value},
    ):
        with patch.dict(powercfg.__opts__, {"test": True}):
            assert powercfg.set_timeout("monitor", 0) == ret


def test_fail_invalid_setting():
    """
    Test to make sure we can set the monitor timeout value
    """
    ret = {
        "changes": {},
        "comment": '"fakesetting" is not a valid setting',
        "name": "fakesetting",
        "result": False,
    }
    assert powercfg.set_timeout("fakesetting", 0) == ret


def test_fail_invalid_power():
    """
    Test to make sure we can set the monitor timeout value
    """
    ret = {
        "changes": {},
        "comment": '"fakepower" is not a power type',
        "name": "monitor",
        "result": False,
    }
    assert powercfg.set_timeout("monitor", 0, power="fakepower") == ret
