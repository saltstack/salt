import pytest
import salt.modules.mac_assistive as assistive
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {assistive: {}}


def test_install_assistive_bundle():
    """
    Test installing a bundle ID as being allowed to run with assistive access
    """
    mock_ret = MagicMock(return_value={"retcode": 0})
    with patch.dict(assistive.__salt__, {"cmd.run_all": mock_ret}):
        with patch.dict(assistive.__grains__, {"osrelease": "10.11.3"}):
            assert assistive.install("foo")


def test_install_assistive_error():
    """
    Test installing a bundle ID as being allowed to run with assistive access
    """
    mock_ret = MagicMock(return_value={"retcode": 1})
    with patch.dict(assistive.__salt__, {"cmd.run_all": mock_ret}):
        with patch.dict(assistive.__grains__, {"osrelease": "10.11.3"}):
            pytest.raises(CommandExecutionError, assistive.install, "foo")


def test_installed_bundle():
    """
    Test checking to see if a bundle id is installed as being able to use assistive access
    """
    with patch(
        "salt.modules.mac_assistive._get_assistive_access",
        MagicMock(return_value=[("foo", 0)]),
    ):
        assert assistive.installed("foo")


def test_installed_bundle_not():
    """
    Test checking to see if a bundle id is installed as being able to use assistive access
    """
    with patch(
        "salt.modules.mac_assistive._get_assistive_access",
        MagicMock(return_value=[]),
    ):
        assert not assistive.installed("foo")


def test_enable_assistive():
    """
    Test enabling a bundle ID as being allowed to run with assistive access
    """
    mock_ret = MagicMock(return_value={"retcode": 0})
    with patch.dict(assistive.__salt__, {"cmd.run_all": mock_ret}), patch(
        "salt.modules.mac_assistive._get_assistive_access",
        MagicMock(return_value=[("foo", 0)]),
    ):
        assert assistive.enable("foo", True)


def test_enable_error():
    """
    Test enabled a bundle ID that throws a command error
    """
    mock_ret = MagicMock(return_value={"retcode": 1})
    with patch.dict(assistive.__salt__, {"cmd.run_all": mock_ret}), patch(
        "salt.modules.mac_assistive._get_assistive_access",
        MagicMock(return_value=[("foo", 0)]),
    ):
        pytest.raises(CommandExecutionError, assistive.enable, "foo")


def test_enable_false():
    """
    Test return of enable function when app isn't found.
    """
    with patch(
        "salt.modules.mac_assistive._get_assistive_access",
        MagicMock(return_value=[]),
    ):
        assert not assistive.enable("foo")


def test_enabled_assistive():
    """
    Test enabling a bundle ID as being allowed to run with assistive access
    """
    with patch(
        "salt.modules.mac_assistive._get_assistive_access",
        MagicMock(return_value=[("foo", "1")]),
    ):
        assert assistive.enabled("foo")


def test_enabled_assistive_false():
    """
    Test if a bundle ID is disabled for assistive access
    """
    with patch(
        "salt.modules.mac_assistive._get_assistive_access",
        MagicMock(return_value=[]),
    ):
        assert not assistive.enabled("foo")


def test_remove_assistive():
    """
    Test removing an assitive bundle.
    """
    mock_ret = MagicMock(return_value={"retcode": 0})
    with patch.dict(assistive.__salt__, {"cmd.run_all": mock_ret}):
        assert assistive.remove("foo")


def test_remove_assistive_error():
    """
    Test removing an assitive bundle.
    """
    mock_ret = MagicMock(return_value={"retcode": 1})
    with patch.dict(assistive.__salt__, {"cmd.run_all": mock_ret}):
        pytest.raises(CommandExecutionError, assistive.remove, "foo")


def test_get_assistive_access():
    """
    Test if a bundle ID is enabled for assistive access
    """
    mock_out = (
        "kTCCServiceAccessibility|/bin/bash|1|1|1|\n"
        "kTCCServiceAccessibility|/usr/bin/osascript|1|1|1|"
    )
    mock_ret = MagicMock(return_value={"retcode": 0, "stdout": mock_out})
    expected = [("/bin/bash", "1"), ("/usr/bin/osascript", "1")]
    with patch.dict(assistive.__salt__, {"cmd.run_all": mock_ret}):
        assert assistive._get_assistive_access() == expected


def test_get_assistive_access_error():
    """
    Test a CommandExecutionError is raised when something goes wrong.
    """
    mock_ret = MagicMock(return_value={"retcode": 1})
    with patch.dict(assistive.__salt__, {"cmd.run_all": mock_ret}):
        pytest.raises(CommandExecutionError, assistive._get_assistive_access)
