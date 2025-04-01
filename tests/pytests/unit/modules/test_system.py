"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.modules.system as system
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_on_windows(reason="Skip system functions on Windows"),
]


@pytest.fixture
def configure_loader_modules():
    return {system: {}}


def test_halt():
    """
    Test to halt a running system
    """
    with patch.dict(system.__salt__, {"cmd.run": MagicMock(return_value="A")}):
        assert system.halt() == "A"


def test_init():
    """
    Test to change the system runlevel on sysV compatible systems
    """
    with patch.dict(system.__salt__, {"cmd.run": MagicMock(return_value="A")}):
        assert system.init("r") == "A"


def test_poweroff():
    """
    Test to poweroff a running system
    """
    with patch.dict(system.__salt__, {"cmd.run": MagicMock(return_value="A")}):
        assert system.poweroff() == "A"


def test_reboot():
    """
    Test to reboot the system with shutdown -r
    """
    cmd_mock = MagicMock(return_value="A")
    with patch.dict(system.__salt__, {"cmd.run": cmd_mock}):
        assert system.reboot() == "A"
    cmd_mock.assert_called_with(["shutdown", "-r", "now"], python_shell=False)


def test_reboot_with_delay():
    """
    Test to reboot the system using shutdown -r with a delay
    """
    cmd_mock = MagicMock(return_value="A")
    with patch.dict(system.__salt__, {"cmd.run": cmd_mock}):
        assert system.reboot(at_time=5) == "A"
    cmd_mock.assert_called_with(["shutdown", "-r", "5"], python_shell=False)


def test_shutdown():
    """
    Test to shutdown a running system
    """
    cmd_mock = MagicMock(return_value="A")
    with patch.dict(system.__salt__, {"cmd.run": cmd_mock}), patch(
        "salt.utils.platform.is_freebsd", MagicMock(return_value=False)
    ), patch("salt.utils.platform.is_netbsd", MagicMock(return_value=False)), patch(
        "salt.utils.platform.is_openbsd", MagicMock(return_value=False)
    ):
        assert system.shutdown() == "A"
    cmd_mock.assert_called_with(["shutdown", "-h", "now"], python_shell=False)


def test_shutdown_freebsd():
    """
    Test to shutdown a running FreeBSD system
    """
    cmd_mock = MagicMock(return_value="A")
    with patch.dict(system.__salt__, {"cmd.run": cmd_mock}), patch(
        "salt.utils.platform.is_freebsd", MagicMock(return_value=True)
    ), patch("salt.utils.platform.is_netbsd", MagicMock(return_value=False)), patch(
        "salt.utils.platform.is_openbsd", MagicMock(return_value=False)
    ):
        assert system.shutdown() == "A"
    cmd_mock.assert_called_with(["shutdown", "-p", "now"], python_shell=False)


def test_shutdown_netbsd():
    """
    Test to shutdown a running NetBSD system
    """
    cmd_mock = MagicMock(return_value="A")
    with patch.dict(system.__salt__, {"cmd.run": cmd_mock}), patch(
        "salt.utils.platform.is_freebsd", MagicMock(return_value=False)
    ), patch("salt.utils.platform.is_netbsd", MagicMock(return_value=True)), patch(
        "salt.utils.platform.is_openbsd", MagicMock(return_value=False)
    ):
        assert system.shutdown() == "A"
    cmd_mock.assert_called_with(["shutdown", "-p", "now"], python_shell=False)


def test_shutdown_openbsd():
    """
    Test to shutdown a running OpenBSD system
    """
    cmd_mock = MagicMock(return_value="A")
    with patch.dict(system.__salt__, {"cmd.run": cmd_mock}), patch(
        "salt.utils.platform.is_freebsd", MagicMock(return_value=False)
    ), patch("salt.utils.platform.is_netbsd", MagicMock(return_value=False)), patch(
        "salt.utils.platform.is_openbsd", MagicMock(return_value=True)
    ):
        assert system.shutdown() == "A"
    cmd_mock.assert_called_with(["shutdown", "-p", "now"], python_shell=False)
