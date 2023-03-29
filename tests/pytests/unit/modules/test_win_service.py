"""
    :codeauthor: Rahul Handay <rahulha@saltstack.com>

    Test cases for salt.modules.win_service
"""

import pytest

import salt.modules.win_service as win_service
import salt.utils.path
from tests.support.mock import MagicMock, patch

try:
    import pywintypes
    import win32serviceutil

    WINAPI = True
except ImportError:
    WINAPI = False


@pytest.fixture
def configure_loader_modules():
    return {win_service: {}}


def test_get_enabled():
    """
    Test to return the enabled services
    """
    mock = MagicMock(
        return_value=[
            {"ServiceName": "spongebob"},
            {"ServiceName": "squarepants"},
            {"ServiceName": "patrick"},
        ]
    )
    with patch.object(win_service, "_get_services", mock):
        mock_info = MagicMock(
            side_effect=[
                {"StartType": "Auto"},
                {"StartType": "Manual"},
                {"StartType": "Disabled"},
            ]
        )
        with patch.object(win_service, "info", mock_info):
            assert win_service.get_enabled() == ["spongebob"]


def test_get_disabled():
    """
    Test to return the disabled services
    """
    mock = MagicMock(
        return_value=[
            {"ServiceName": "spongebob"},
            {"ServiceName": "squarepants"},
            {"ServiceName": "patrick"},
        ]
    )
    with patch.object(win_service, "_get_services", mock):
        mock_info = MagicMock(
            side_effect=[
                {"StartType": "Auto"},
                {"StartType": "Manual"},
                {"StartType": "Disabled"},
            ]
        )
        with patch.object(win_service, "info", mock_info):
            assert win_service.get_disabled() == ["patrick", "squarepants"]


def test_available():
    """
    Test to Returns ``True`` if the specified service
    is available, otherwise returns ``False``
    """
    mock = MagicMock(return_value=["c", "a", "b"])
    with patch.object(win_service, "get_all", mock):
        assert win_service.available("a")


def test_missing():
    """
    Test to the inverse of service.available
    """
    mock = MagicMock(return_value=["c", "a", "b"])
    with patch.object(win_service, "get_all", mock):
        assert win_service.missing("d")


def test_get_all():
    """
    Test to return all installed services
    """
    mock = MagicMock(
        return_value=[
            {"ServiceName": "spongebob"},
            {"ServiceName": "squarepants"},
            {"ServiceName": "patrick"},
        ]
    )
    with patch.object(win_service, "_get_services", mock):
        assert win_service.get_all() == ["patrick", "spongebob", "squarepants"]


def test_get_service_name():
    """
    Test to the Display Name is what is displayed
    in Windows when services.msc is executed.
    """
    mock = MagicMock(
        return_value=[
            {"ServiceName": "spongebob", "DisplayName": "Sponge Bob"},
            {"ServiceName": "squarepants", "DisplayName": "Square Pants"},
            {"ServiceName": "patrick", "DisplayName": "Patrick the Starfish"},
        ]
    )
    with patch.object(win_service, "_get_services", mock):
        assert win_service.get_service_name() == {
            "Patrick the Starfish": "patrick",
            "Sponge Bob": "spongebob",
            "Square Pants": "squarepants",
        }
        assert win_service.get_service_name("patrick") == {
            "Patrick the Starfish": "patrick"
        }


@pytest.mark.skipif(not WINAPI, reason="win32serviceutil not available")
@pytest.mark.slow_test
def test_start():
    """
    Test to start the specified service
    """
    mock_true = MagicMock(return_value=True)
    mock_false = MagicMock(return_value=False)
    mock_info = MagicMock(side_effect=[{"Status": "Running"}])

    with patch.object(win32serviceutil, "StartService", mock_true), patch.object(
        win_service, "disabled", mock_false
    ), patch.object(win_service, "info", mock_info):
        assert win_service.start("spongebob")

    mock_info = MagicMock(
        side_effect=[
            {"Status": "Stopped", "Status_WaitHint": 0},
            {"Status": "Start Pending", "Status_WaitHint": 0},
            {"Status": "Running"},
        ]
    )

    with patch.object(win32serviceutil, "StartService", mock_true), patch.object(
        win_service, "disabled", mock_false
    ), patch.object(win_service, "info", mock_info), patch.object(
        win_service, "status", mock_true
    ):
        assert win_service.start("spongebob")


@pytest.mark.skipif(not WINAPI, reason="pywintypes not available")
def test_start_already_running():
    """
    Test starting a service that is already running
    """
    mock_false = MagicMock(return_value=False)
    mock_error = MagicMock(
        side_effect=pywintypes.error(1056, "StartService", "Service is running")
    )
    mock_info = MagicMock(side_effect=[{"Status": "Running"}])
    with patch.object(win32serviceutil, "StartService", mock_error), patch.object(
        win_service, "disabled", mock_false
    ), patch.object(win_service, "_status_wait", mock_info):
        assert win_service.start("spongebob")


@pytest.mark.skipif(not WINAPI, reason="win32serviceutil not available")
@pytest.mark.slow_test
def test_stop():
    """
    Test to stop the specified service
    """
    mock_true = MagicMock(return_value=True)
    mock_false = MagicMock(return_value=False)
    mock_info = MagicMock(side_effect=[{"Status": "Stopped"}])

    with patch.object(win32serviceutil, "StopService", mock_true), patch.object(
        win_service, "_status_wait", mock_info
    ):
        assert win_service.stop("spongebob")

    mock_info = MagicMock(
        side_effect=[
            {"Status": "Running", "Status_WaitHint": 0},
            {"Status": "Stop Pending", "Status_WaitHint": 0},
            {"Status": "Stopped"},
        ]
    )

    with patch.object(win32serviceutil, "StopService", mock_true), patch.object(
        win_service, "info", mock_info
    ), patch.object(win_service, "status", mock_false):
        assert win_service.stop("spongebob")


@pytest.mark.skipif(not WINAPI, reason="pywintypes not available")
def test_stop_not_running():
    """
    Test stopping a service that is already stopped
    """
    mock_error = MagicMock(
        side_effect=pywintypes.error(1062, "StopService", "Service is not running")
    )
    mock_info = MagicMock(side_effect=[{"Status": "Stopped"}])
    with patch.object(win32serviceutil, "StopService", mock_error), patch.object(
        win_service, "_status_wait", mock_info
    ):
        assert win_service.stop("spongebob")


def test_restart():
    """
    Test to restart the named service
    """
    mock_true = MagicMock(return_value=True)
    with patch.object(win_service, "create_win_salt_restart_task", mock_true):
        with patch.object(win_service, "execute_salt_restart_task", mock_true):
            assert win_service.restart("salt-minion")

    with patch.object(win_service, "stop", mock_true):
        with patch.object(win_service, "start", mock_true):
            assert win_service.restart("salt")


def test_createwin_saltrestart_task():
    """
    Test to create a task in Windows task
    scheduler to enable restarting the salt-minion
    """
    cmd = salt.utils.path.which("cmd")
    mock = MagicMock()
    with patch.dict(win_service.__salt__, {"task.create_task": mock}):
        win_service.create_win_salt_restart_task()
        mock.assert_called_once_with(
            action_type="Execute",
            arguments=(
                "/c ping -n 3 127.0.0.1 && net stop salt-minion && "
                "net start salt-minion"
            ),
            cmd=cmd,
            force=True,
            name="restart-salt-minion",
            start_date="1975-01-01",
            start_time="01:00",
            trigger_type="Once",
            user_name="System",
        )


def test_execute_salt_restart_task():
    """
    Test to run the Windows Salt restart task
    """
    mock_true = MagicMock(return_value=True)
    with patch.dict(win_service.__salt__, {"task.run": mock_true}):
        assert win_service.execute_salt_restart_task()


@pytest.mark.skipif(not WINAPI, reason="win32serviceutil not available")
def test_status():
    """
    Test to return the status for a service
    """
    mock_info = MagicMock(
        side_effect=[
            {"Status": "Running"},
            {"Status": "Stop Pending"},
            {"Status": "Stopped"},
        ]
    )

    with patch.object(win_service, "info", mock_info):
        assert win_service.status("spongebob")
        assert win_service.status("patrick")
        assert not win_service.status("squidward")


def test_getsid():
    """
    Test to return the sid for this windows service
    """
    mock_info = MagicMock(
        side_effect=[{"sid": "S-1-5-80-1956725871..."}, {"sid": None}]
    )
    with patch.object(win_service, "info", mock_info):
        assert win_service.getsid("spongebob") == "S-1-5-80-1956725871..."
        assert win_service.getsid("plankton") is None


def test_enable():
    """
    Test to enable the named service to start at boot
    """
    mock_modify = MagicMock(return_value=True)
    mock_info = MagicMock(return_value={"StartType": "Auto", "StartTypeDelayed": False})
    with patch.object(win_service, "modify", mock_modify):
        with patch.object(win_service, "info", mock_info):
            assert win_service.enable("spongebob")


def test_disable():
    """
    Test to disable the named service to start at boot
    """
    mock_modify = MagicMock(return_value=True)
    mock_info = MagicMock(return_value={"StartType": "Disabled"})
    with patch.object(win_service, "modify", mock_modify):
        with patch.object(win_service, "info", mock_info):
            assert win_service.disable("spongebob")


def test_enabled():
    """
    Test to check to see if the named
    service is enabled to start on boot
    """
    mock = MagicMock(side_effect=[{"StartType": "Auto"}, {"StartType": "Disabled"}])
    with patch.object(win_service, "info", mock):
        assert win_service.enabled("spongebob")
        assert not win_service.enabled("squarepants")


def test_enabled_with_space_in_name():
    """
    Test to check to see if the named
    service is enabled to start on boot
    when have space in service name
    """
    mock = MagicMock(side_effect=[{"StartType": "Auto"}, {"StartType": "Disabled"}])
    with patch.object(win_service, "info", mock):
        assert win_service.enabled("spongebob test")
        assert not win_service.enabled("squarepants test")


def test_disabled():
    """
    Test to check to see if the named
    service is disabled to start on boot
    """
    mock = MagicMock(side_effect=[False, True])
    with patch.object(win_service, "enabled", mock):
        assert win_service.disabled("spongebob")
        assert not win_service.disabled("squarepants")


def test_cmd_quote():
    """
    Make sure the command gets quoted correctly
    """
    # Should always return command wrapped in double quotes
    expected = r'"C:\Program Files\salt\test.exe"'

    # test no quotes
    bin_path = r"C:\Program Files\salt\test.exe"
    assert win_service._cmd_quote(bin_path) == expected

    # test single quotes
    bin_path = r"'C:\Program Files\salt\test.exe'"
    assert win_service._cmd_quote(bin_path) == expected

    # test double quoted single quotes
    bin_path = "\"'C:\\Program Files\\salt\\test.exe'\""
    assert win_service._cmd_quote(bin_path) == expected

    # test single quoted, double quoted, single quotes
    bin_path = "'\"'C:\\Program Files\\salt\\test.exe'\"'"
    assert win_service._cmd_quote(bin_path) == expected
