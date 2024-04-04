"""
    Test cases for salt.states.kernelpkg
"""

import pytest

import salt.states.kernelpkg as kernelpkg
from tests.support.mock import MagicMock, patch


@pytest.fixture
def kernel_list():
    return ["4.4.0-70-generic", "4.4.0-71-generic", "4.5.1-14-generic"]


@pytest.fixture
def state_name():
    return "kernelpkg-test"


@pytest.fixture
def configure_loader_modules():
    return {
        kernelpkg: {
            "__salt__": {
                "system.reboot": MagicMock(return_value=None),
                "kernelpkg.upgrade": MagicMock(
                    return_value={
                        "upgrades": {"kernel": {"old": "1.0.0", "new": "2.0.0"}}
                    }
                ),
                "kernelpkg.active": MagicMock(return_value=0),
                "kernelpkg.latest_installed": MagicMock(return_value=0),
            }
        }
    }


def test_latest_installed_with_changes(kernel_list, state_name):
    """
    Test - latest_installed when an upgrade is available
    """
    installed = MagicMock(return_value=kernel_list[:-1])
    upgrade = MagicMock(return_value=kernel_list[-1])
    with patch.dict(kernelpkg.__salt__, {"kernelpkg.list_installed": installed}):
        with patch.dict(kernelpkg.__salt__, {"kernelpkg.latest_available": upgrade}):
            with patch.dict(kernelpkg.__opts__, {"test": False}):
                kernelpkg.__salt__["kernelpkg.upgrade"].reset_mock()
                ret = kernelpkg.latest_installed(name=state_name)
                assert ret["name"] == state_name
                assert ret["result"]
                assert isinstance(ret["changes"], dict)
                assert isinstance(ret["comment"], str)
                kernelpkg.__salt__["kernelpkg.upgrade"].assert_called_once()

            with patch.dict(kernelpkg.__opts__, {"test": True}):
                kernelpkg.__salt__["kernelpkg.upgrade"].reset_mock()
                ret = kernelpkg.latest_installed(name=state_name)
                assert ret["name"] == state_name
                assert ret["result"] is None
                assert ret["changes"] == {}
                assert isinstance(ret["comment"], str)
                kernelpkg.__salt__["kernelpkg.upgrade"].assert_not_called()


def test_latest_installed_at_latest(kernel_list, state_name):
    """
    Test - latest_installed when no upgrade is available
    """
    installed = MagicMock(return_value=kernel_list)
    upgrade = MagicMock(return_value=kernel_list[-1])
    with patch.dict(kernelpkg.__salt__, {"kernelpkg.list_installed": installed}):
        with patch.dict(kernelpkg.__salt__, {"kernelpkg.latest_available": upgrade}):
            with patch.dict(kernelpkg.__opts__, {"test": False}):
                ret = kernelpkg.latest_installed(name=state_name)
                assert ret["name"] == state_name
                assert ret["result"]
                assert ret["changes"] == {}
                assert isinstance(ret["comment"], str)
                kernelpkg.__salt__["kernelpkg.upgrade"].assert_not_called()

            with patch.dict(kernelpkg.__opts__, {"test": True}):
                ret = kernelpkg.latest_installed(name=state_name)
                assert ret["name"] == state_name
                assert ret["result"]
                assert ret["changes"] == {}
                assert isinstance(ret["comment"], str)
                kernelpkg.__salt__["kernelpkg.upgrade"].assert_not_called()


def test_latest_active_with_changes(state_name):
    """
    Test - latest_active when a new kernel is available
    """
    reboot = MagicMock(return_value=True)
    latest = MagicMock(return_value=1)
    with patch.dict(
        kernelpkg.__salt__,
        {"kernelpkg.needs_reboot": reboot, "kernelpkg.latest_installed": latest},
    ), patch.dict(kernelpkg.__opts__, {"test": False}):
        kernelpkg.__salt__["system.reboot"].reset_mock()
        ret = kernelpkg.latest_active(name=state_name)
        assert ret["name"] == state_name
        assert ret["result"]
        assert isinstance(ret["changes"], dict)
        assert isinstance(ret["comment"], str)
        kernelpkg.__salt__["system.reboot"].assert_called_once()

        with patch.dict(kernelpkg.__opts__, {"test": True}):
            kernelpkg.__salt__["system.reboot"].reset_mock()
            ret = kernelpkg.latest_active(name=state_name)
            assert ret["name"] == state_name
            assert ret["result"] is None
            assert ret["changes"] == {"kernel": {"new": 1, "old": 0}}
            assert isinstance(ret["comment"], str)
            kernelpkg.__salt__["system.reboot"].assert_not_called()


def test_latest_active_at_latest(state_name):
    """
    Test - latest_active when the newest kernel is already active
    """
    reboot = MagicMock(return_value=False)
    with patch.dict(kernelpkg.__salt__, {"kernelpkg.needs_reboot": reboot}):
        with patch.dict(kernelpkg.__opts__, {"test": False}):
            kernelpkg.__salt__["system.reboot"].reset_mock()
            ret = kernelpkg.latest_active(name=state_name)
            assert ret["name"] == state_name
            assert ret["result"]
            assert ret["changes"] == {}
            assert isinstance(ret["comment"], str)
            kernelpkg.__salt__["system.reboot"].assert_not_called()

        with patch.dict(kernelpkg.__opts__, {"test": True}):
            kernelpkg.__salt__["system.reboot"].reset_mock()
            ret = kernelpkg.latest_active(name=state_name)
            assert ret["name"] == state_name
            assert ret["result"]
            assert ret["changes"] == {}
            assert isinstance(ret["comment"], str)
            kernelpkg.__salt__["system.reboot"].assert_not_called()


def test_latest_wait(state_name):
    """
    Test - latest_wait static results
    """
    ret = kernelpkg.latest_wait(name=state_name)
    assert ret["name"] == state_name
    assert ret["result"]
    assert ret["changes"] == {}
    assert isinstance(ret["comment"], str)
