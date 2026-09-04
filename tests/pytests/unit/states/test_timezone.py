"""
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
"""

import pytest

import salt.states.timezone as timezone
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {timezone: {}}


def test_system():
    """
    Test to set the timezone for the system (non-Windows / Linux path).
    """
    ret = {"name": "salt", "changes": {}, "result": True, "comment": ""}
    mock = MagicMock(side_effect=[CommandExecutionError, True, True, True])
    mock1 = MagicMock(side_effect=["local", "localtime", "localtime"])
    mock2 = MagicMock(return_value=False)
    with patch.dict(
        timezone.__salt__,
        {
            "timezone.zone_compare": mock,
            "timezone.get_hwclock": mock1,
            "timezone.set_hwclock": mock2,
        },
    ), patch("salt.utils.platform.is_windows", return_value=False):
        ret.update(
            {
                "comment": (
                    "Unable to compare desired timezone 'salt' to system timezone: "
                ),
                "result": False,
            }
        )
        assert timezone.system("salt") == ret

        ret.update(
            {
                "comment": "Timezone salt already set, UTC already set to salt",
                "result": True,
            }
        )
        assert timezone.system("salt") == ret

        with patch.dict(timezone.__opts__, {"test": True}):
            ret.update({"comment": "UTC needs to be set to True", "result": None})
            assert timezone.system("salt") == ret

        with patch.dict(timezone.__opts__, {"test": False}):
            ret.update({"comment": "Failed to set UTC to True", "result": False})
            assert timezone.system("salt") == ret


def test_system_windows():
    """
    Test that on Windows the UTC/hwclock block is skipped entirely and the
    state succeeds even when utc=True (the default).
    """
    mock_zone_compare = MagicMock(return_value=False)
    mock_get_hwclock = MagicMock(return_value="localtime")
    mock_set_hwclock = MagicMock(return_value=False)
    mock_set_zone = MagicMock(return_value=True)
    with patch.dict(
        timezone.__salt__,
        {
            "timezone.zone_compare": mock_zone_compare,
            "timezone.get_hwclock": mock_get_hwclock,
            "timezone.set_hwclock": mock_set_hwclock,
            "timezone.set_zone": mock_set_zone,
        },
    ), patch.dict(timezone.__opts__, {"test": False}), patch(
        "salt.utils.platform.is_windows", return_value=True
    ):
        ret = timezone.system("America/New_York", utc=True)
        assert ret["result"] is True
        assert ret["changes"] == {"timezone": "America/New_York"}
        mock_set_hwclock.assert_not_called()


def test_system_windows_already_set():
    """
    Test that on Windows, when the timezone is already correct, the state
    succeeds and reports already-set without touching the hwclock.
    """
    mock_zone_compare = MagicMock(return_value=True)
    mock_get_hwclock = MagicMock(return_value="localtime")
    mock_set_hwclock = MagicMock(return_value=False)
    with patch.dict(
        timezone.__salt__,
        {
            "timezone.zone_compare": mock_zone_compare,
            "timezone.get_hwclock": mock_get_hwclock,
            "timezone.set_hwclock": mock_set_hwclock,
        },
    ), patch.dict(timezone.__opts__, {"test": False}), patch(
        "salt.utils.platform.is_windows", return_value=True
    ):
        ret = timezone.system("America/New_York", utc=True)
        assert ret["result"] is True
        assert ret["changes"] == {}
        mock_set_hwclock.assert_not_called()
