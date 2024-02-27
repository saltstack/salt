"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>

    Test cases for salt.modules.launchctl
"""

import pytest

import salt.modules.launchctl_service as launchctl
import salt.utils.stringutils
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {launchctl: {}}


def test_get_all():
    """
    Test for Return all installed services
    """
    with patch.dict(
        launchctl.__salt__, {"cmd.run": MagicMock(return_value="A\tB\tC\t\n")}
    ):
        with patch.object(
            launchctl, "_available_services", return_value={"A": "a", "B": "b"}
        ):
            assert launchctl.get_all() == ["A", "B", "C"]


def test_available():
    """
    Test for Check that the given service is available.
    """
    with patch.object(launchctl, "_service_by_name", return_value=True):
        assert launchctl.available("job_label")


def test_missing():
    """
    Test for The inverse of service.available
    """
    with patch.object(launchctl, "_service_by_name", return_value=True):
        assert not launchctl.missing("job_label")


def test_status():
    """
    Test for Return the status for a service
    """
    launchctl_data = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>salt-minion</string>
    <key>LastExitStatus</key>
    <integer>0</integer>
    <key>LimitLoadToSessionType</key>
    <string>System</string>
    <key>OnDemand</key>
    <false/>
    <key>PID</key>
    <integer>71</integer>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/salt-minion</string>
    </array>
    <key>TimeOut</key>
    <integer>30</integer>
</dict>
</plist>"""
    with patch.object(
        launchctl, "_service_by_name", return_value={"plist": {"Label": "A"}}
    ):
        launchctl_data = salt.utils.stringutils.to_bytes(launchctl_data)
        with patch.object(
            launchctl, "_get_launchctl_data", return_value=launchctl_data
        ):
            assert launchctl.status("job_label")


def test_stop():
    """
    Test for Stop the specified service
    """
    with patch.object(launchctl, "_service_by_name", return_value={"file_path": "A"}):
        with patch.dict(
            launchctl.__salt__, {"cmd.retcode": MagicMock(return_value=False)}
        ):
            assert launchctl.stop("job_label")

    with patch.object(launchctl, "_service_by_name", return_value=None):
        assert not launchctl.stop("job_label")


def test_start():
    """
    Test for Start the specified service
    """
    with patch.object(launchctl, "_service_by_name", return_value={"file_path": "A"}):
        with patch.dict(
            launchctl.__salt__, {"cmd.retcode": MagicMock(return_value=False)}
        ):
            assert launchctl.start("job_label")

    with patch.object(launchctl, "_service_by_name", return_value=None):
        assert not launchctl.start("job_label")


def test_restart():
    """
    Test for Restart the named service
    """
    with patch.object(launchctl, "stop", return_value=None):
        with patch.object(launchctl, "start", return_value=True):
            assert launchctl.restart("job_label")
