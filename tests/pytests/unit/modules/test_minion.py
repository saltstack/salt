import os
import sys

import pytest

import salt.modules.minion as minion
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {minion: {}}


# Test command fixtures
@pytest.fixture
def sample_restart_command():
    return ["/bin/some_command", "arg1", "arg2"]


@pytest.fixture
def daemon_argv():
    return ["/usr/bin/salt-minion", "-d"]


@pytest.fixture
def regular_argv():
    return ["/usr/bin/salt-minion"]


# Helper functions for common assertions
def assert_service_restart_called(mock_salt_dict, service_name, **kwargs):
    """Helper to assert service.restart was called with expected args"""
    mock_salt_dict["service.restart"].assert_called_once_with(service_name, **kwargs)


def assert_no_service_calls(mock_service_dict, mock_kill, mock_cmd_dict):
    """Helper to assert service.restart was not called"""
    mock_service_dict["service.restart"].assert_not_called()
    mock_kill.assert_called_once()


# Mock fixtures
@pytest.fixture
def mock_system_detection():
    """Mock functions to detect systemd and Windows systems"""
    with patch("salt.modules.minion._is_systemd_system") as mock_systemd, patch(
        "salt.modules.minion._is_windows_system"
    ) as mock_windows:
        yield mock_systemd, mock_windows


@pytest.fixture
def mock_minion_kill():
    """Mock the minion.kill function"""
    ret = {"retcode": 0, "killed": 1234}
    with patch("salt.modules.minion.kill", return_value=ret) as mock_kill:
        yield mock_kill


@pytest.fixture
def mock_salt_functions():
    """Mock salt functions used in minion.restart"""
    mocks = {
        "cmd.run_all": MagicMock(),
        "service.restart": MagicMock(),
        "config.get": MagicMock(return_value=False),
    }
    with patch.dict(minion.__salt__, mocks):
        yield mocks


def test_is_systemd_systemd():
    """Test if the system is a systemd system"""
    with patch.dict(minion.__grains__, {"kernel": "Linux"}):
        with patch("salt.utils.systemd.booted", return_value=True):
            assert minion._is_systemd_system() is True
        with patch("salt.utils.systemd.booted", return_value=False):
            assert minion._is_systemd_system() is False

    with patch.dict(minion.__grains__, {"kernel": "Windows"}):
        assert minion._is_systemd_system() is False


def test_is_windows_system():
    """Test if the system is a Windows system"""
    with patch.dict(minion.__grains__, {"kernel": "Windows"}):
        assert minion._is_windows_system() is True

    with patch.dict(minion.__grains__, {"kernel": "Linux"}):
        assert minion._is_windows_system() is False


# Tests of minion.restart()


def test_minion_restart_with_custom_command(
    mock_minion_kill, mock_salt_functions, sample_restart_command
):
    """Test behavior when minion_restart_command is configured"""
    mock_salt_functions["config.get"].return_value = sample_restart_command

    minion.restart()

    # Should call minion.kill()
    mock_minion_kill.assert_called_once()

    # Should call cmd.run_all with the custom command
    mock_salt_functions["cmd.run_all"].assert_called_once_with(
        sample_restart_command, env=os.environ
    )


@pytest.mark.parametrize(
    "is_systemd,is_windows,expected_service_call",
    [
        (True, False, {"service_name": "salt-minion", "kwargs": {"no_block": True}}),
        (False, True, {"service_name": "salt-minion", "kwargs": {}}),
    ],
)
def test_minion_restart_service_systems(
    is_systemd,
    is_windows,
    expected_service_call,
    mock_system_detection,
    mock_minion_kill,
    mock_salt_functions,
):
    """Test behavior on systemd and Windows systems"""

    mock_systemd, mock_windows = mock_system_detection
    mock_systemd.return_value = is_systemd
    mock_windows.return_value = is_windows

    minion.restart()

    # Should not call minion.kill
    mock_minion_kill.assert_not_called()

    # Should not call cmd.run_all
    mock_salt_functions["cmd.run_all"].assert_not_called()

    # Should call service.restart with expected parameters
    assert_service_restart_called(
        mock_salt_functions,
        expected_service_call["service_name"],
        **expected_service_call["kwargs"]
    )


@pytest.mark.parametrize(
    "systemd_override,win_service_override",
    [
        (False, None),  # systemd=False
        (None, False),  # win_service=False
    ],
)
def test_minion_restart_service_override(
    systemd_override,
    win_service_override,
    mock_system_detection,
    mock_minion_kill,
    mock_salt_functions,
    regular_argv,
):
    """Test behavior when service parameters are explicitly disabled"""

    mock_systemd, mock_windows = mock_system_detection
    mock_systemd.return_value = True if systemd_override is not None else False
    mock_windows.return_value = True if win_service_override is not None else False

    with patch.object(sys, "argv", regular_argv):
        kwargs = {}
        if systemd_override is not None:
            kwargs["systemd"] = systemd_override
        if win_service_override is not None:
            kwargs["win_service"] = win_service_override

        minion.restart(**kwargs)

        # Should use minion.kill instead of service.restart when overridden
        mock_minion_kill.assert_called_once()
        mock_salt_functions["service.restart"].assert_not_called()


@pytest.mark.parametrize(
    "argv,should_call_cmd_run",
    [
        (["/usr/bin/salt-minion", "-d"], True),
        (["/usr/bin/salt-minion"], False),
    ],
)
def test_minion_restart_non_service_systems(
    argv,
    should_call_cmd_run,
    mock_system_detection,
    mock_minion_kill,
    mock_salt_functions,
):
    """Test behavior on non-systemd/Windows systems"""

    mock_systemd, mock_windows = mock_system_detection
    mock_systemd.return_value = False
    mock_windows.return_value = False

    with patch.object(sys, "argv", argv):
        minion.restart()

        # Should always call kill on non systemd/Windows systems and not service.restart
        mock_minion_kill.assert_called_once()
        mock_salt_functions["service.restart"].assert_not_called()

        if should_call_cmd_run:
            mock_salt_functions["cmd.run_all"].assert_called_once_with(
                argv, env=os.environ
            )
        else:
            mock_salt_functions["cmd.run_all"].assert_not_called()
