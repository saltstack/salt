import datetime
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


def test_schedule_retry_systemd():
    """Test creating a scheduled retry for minion on Linux systems"""
    with patch("salt.modules.minion._is_systemd_system", return_value=False):
        assert minion._schedule_retry_systemd(60) is False
    with patch("salt.modules.minion._is_systemd_system", return_value=True):
        with patch("salt.utils.path.which", return_value="/usr/bin/systemd-run"):

            mock_cmd_run_all = MagicMock(return_value={"retcode": 0})
            with patch.dict(minion.__salt__, {"cmd.run_all": mock_cmd_run_all}):
                assert minion._schedule_retry_systemd(60)

                call_args = mock_cmd_run_all.call_args
                call_args_cmd = call_args[0][0]
                assert call_args_cmd[0] == "/usr/bin/systemd-run"
                assert call_args_cmd[1] == "--on-active=60"
                assert (
                    call_args_cmd[-1]
                    == "systemctl is-active salt-minion || systemctl start salt-minion"
                )


def test_schedule_retry_windows():
    """Test creating a scheduled retry for minion on Windows systems"""

    with patch("salt.modules.minion._is_windows_system", return_value=False):
        assert minion._schedule_retry_windows(60) is False

    fixed_time = datetime.datetime(2025, 1, 15, 14, 30, 0)
    expected_schedule_time = fixed_time + datetime.timedelta(seconds=60)

    with patch("salt.modules.minion._is_windows_system", return_value=True):
        with patch("salt.modules.minion.datetime") as mock_datetime:
            mock_datetime.datetime.now.return_value = fixed_time
            mock_datetime.timedelta = datetime.timedelta

            mock_create_task = MagicMock(return_value=True)

            with patch.dict(minion.__salt__, {"task.create_task": mock_create_task}):
                assert minion._schedule_retry(60)

                call_args = mock_create_task.call_args

                assert call_args.kwargs[
                    "start_date"
                ] == expected_schedule_time.strftime("%Y-%m-%d")
                assert call_args.kwargs[
                    "start_time"
                ] == expected_schedule_time.strftime("%H:%M:%S")
                assert call_args.kwargs["name"] == "retry-minion-restart"


def test_schedule_retry_invalid_delay():
    """Test _schedule_retry with invalid delay"""

    with pytest.raises(minion.CommandExecutionError):
        minion._schedule_retry("invalid_delay")


@pytest.mark.parametrize(
    "is_systemd,is_windows,expected_result,systemd_called,windows_called",
    [
        (False, False, False, False, False),  # Neither systemd nor windows
        (True, False, None, True, False),  # Systemd system
        (False, True, None, False, True),  # Windows system
    ],
    ids=["neither", "systemd", "windows"],
)
def test_schedule_retry_dispatch(
    is_systemd, is_windows, expected_result, systemd_called, windows_called
):
    """Test _schedule_retry dispatching"""

    mock_schedule_retry_systemd = MagicMock()
    mock_schedule_retry_windows = MagicMock()

    with patch(
        "salt.modules.minion._schedule_retry_systemd", mock_schedule_retry_systemd
    ), patch(
        "salt.modules.minion._schedule_retry_windows", mock_schedule_retry_windows
    ), patch(
        "salt.modules.minion._is_systemd_system", return_value=is_systemd
    ), patch(
        "salt.modules.minion._is_windows_system", return_value=is_windows
    ):
        result = minion._schedule_retry(60)

        # Check return value for the "neither" case
        if expected_result is not None:
            assert result is expected_result

        # Check mock calls
        if systemd_called:
            mock_schedule_retry_systemd.assert_called_once_with(60)
        else:
            mock_schedule_retry_systemd.assert_not_called()

        if windows_called:
            mock_schedule_retry_windows.assert_called_once_with(60)
        else:
            mock_schedule_retry_windows.assert_not_called()


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
        **expected_service_call["kwargs"],
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


@pytest.mark.parametrize(
    "is_systemd,is_windows,retry_delay",
    [
        (True, False, None),  # systemd with default delay
        (True, False, 300),  # systemd with custom delay
        (False, True, None),  # Windows with default delay
        (False, True, 60),  # Windows with custom delay
    ],
)
def test_minion_restart_with_schedule_retry_success(
    is_systemd,
    is_windows,
    retry_delay,
    mock_system_detection,
    mock_salt_functions,
):
    """Test minion.restart with schedule_retry enabled - success case"""

    mock_systemd, mock_windows = mock_system_detection
    mock_systemd.return_value = is_systemd
    mock_windows.return_value = is_windows

    # Mock _schedule_retry to return success
    mock_schedule_retry_result = {"stderr": "success output"}
    with patch(
        "salt.modules.minion._schedule_retry", return_value=mock_schedule_retry_result
    ) as mock_schedule_retry:

        result = (
            minion.restart(schedule_retry=True, retry_delay=retry_delay)
            if retry_delay is not None
            else minion.restart(schedule_retry=True)
        )
        retry_delay = retry_delay if retry_delay is not None else 180

        # Verify _schedule_retry was called with correct delay
        mock_schedule_retry.assert_called_once_with(retry_delay)

        # Verify service.restart was called
        mock_salt_functions["service.restart"].assert_called_once()

        # Verify return structure contains schedule_retry info
        assert "service_restart" in result
        assert "schedule_retry" in result["service_restart"]
        assert result["service_restart"]["schedule_retry"]["delay"] == retry_delay

        # Check systemd-specific details
        if is_systemd:
            assert "detail" in result["service_restart"]["schedule_retry"]
            assert (
                result["service_restart"]["schedule_retry"]["detail"]
                == "success output"
            )

        # Verify comment mentions the scheduled retry
        assert "comment" in result
        expected_comment = (
            f"Scheduled retry for minion restart in {retry_delay} seconds"
        )
        assert expected_comment in result["comment"]

        # Verify successful restart
        assert result["retcode"] == 0


@pytest.mark.parametrize(
    "is_systemd,is_windows",
    [
        (True, False),  # systemd
        (False, True),  # Windows
    ],
)
def test_minion_restart_with_schedule_retry_failure(
    is_systemd,
    is_windows,
    mock_system_detection,
    mock_salt_functions,
):
    """Test minion.restart with schedule_retry enabled - failure case"""

    mock_systemd, mock_windows = mock_system_detection
    mock_systemd.return_value = is_systemd
    mock_windows.return_value = is_windows

    # Mock _schedule_retry to raise an exception
    with patch(
        "salt.modules.minion._schedule_retry",
        side_effect=minion.CommandExecutionError("Failed to add retry task"),
    ) as mock_schedule_retry:

        result = minion.restart(schedule_retry=True, retry_delay=120)

        # Verify _schedule_retry was called
        mock_schedule_retry.assert_called_once_with(120)

        # Verify service.restart was not called after schedule_retry failure
        mock_salt_functions["service.restart"].assert_not_called()

        # Verify error handling
        assert result["retcode"] != 0
        assert "service_restart" in result
        assert result["service_restart"]["result"] is False
        assert "stderr" in result["service_restart"]
        assert "Failed to add retry task" in result["service_restart"]["stderr"]

        # Verify error comment
        assert "comment" in result
        assert "Adding scheduled retry failed" in result["comment"]


def test_minion_restart_without_schedule_retry(
    mock_system_detection,
    mock_salt_functions,
):
    """Test minion.restart with schedule_retry disabled (default behavior)"""

    mock_systemd, mock_windows = mock_system_detection
    mock_systemd.return_value = True
    mock_windows.return_value = False

    with patch("salt.modules.minion._schedule_retry") as mock_schedule_retry:

        result = minion.restart(schedule_retry=False)

        # Verify _schedule_retry was not called
        mock_schedule_retry.assert_not_called()

        # Verify service.restart was called normally
        mock_salt_functions["service.restart"].assert_called_once()

        # Verify no schedule_retry info in result
        assert "service_restart" in result
        assert "schedule_retry" not in result["service_restart"]

        # Verify successful restart
        assert result["retcode"] == 0


@pytest.mark.parametrize(
    "is_systemd,is_windows",
    [
        (True, False),  # systemd
        (False, True),  # Windows
    ],
)
def test_minion_restart_schedule_retry_service_restart_failure(
    is_systemd,
    is_windows,
    mock_system_detection,
    mock_salt_functions,
):
    """Test minion.restart when schedule_retry succeeds but service.restart fails"""

    mock_systemd, mock_windows = mock_system_detection
    mock_systemd.return_value = is_systemd
    mock_windows.return_value = is_windows

    # Mock successful _schedule_retry
    mock_schedule_retry_result = {"stderr": "retry scheduled"}

    # Mock service.restart to fail
    mock_salt_functions["service.restart"].side_effect = minion.CommandExecutionError(
        "Service restart failed"
    )

    with patch(
        "salt.modules.minion._schedule_retry", return_value=mock_schedule_retry_result
    ) as mock_schedule_retry:

        result = minion.restart(schedule_retry=True, retry_delay=90)

        # Verify _schedule_retry was called successfully
        mock_schedule_retry.assert_called_once_with(90)

        # Verify service.restart was attempted
        mock_salt_functions["service.restart"].assert_called_once()

        # Verify schedule_retry info is still in result despite service failure
        assert "service_restart" in result
        assert "schedule_retry" in result["service_restart"]
        assert result["service_restart"]["schedule_retry"]["delay"] == 90

        # Verify service failure is handled
        assert result["retcode"] != 0
        assert result["service_restart"]["result"] is False
        assert "Service restart failed" in result["comment"]

        # Verify schedule retry comment is still present
        assert "Scheduled retry for minion restart in 90 seconds" in result["comment"]


def test_minion_restart_schedule_retry_non_service_system(
    mock_system_detection,
    mock_salt_functions,
    mock_minion_kill,
):
    """Test that schedule_retry is ignored on non-service systems"""

    mock_systemd, mock_windows = mock_system_detection
    mock_systemd.return_value = False
    mock_windows.return_value = False

    with patch("salt.modules.minion._schedule_retry") as mock_schedule_retry:
        with patch.object(sys, "argv", ["/usr/bin/salt-minion"]):

            result = minion.restart(schedule_retry=True, retry_delay=60)

            # Verify _schedule_retry was not called on non-service systems
            mock_schedule_retry.assert_not_called()

            # Verify kill was called instead
            mock_minion_kill.assert_called_once()

            # Verify no service_restart info
            assert "service_restart" not in result or not result["service_restart"]
