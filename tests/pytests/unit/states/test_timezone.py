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
    Test to set the timezone for the system.
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
    ):
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
