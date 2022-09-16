"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.states.keyboard as keyboard
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {keyboard: {}}


# 'system' function tests: 1


def test_system():
    """
    Test to set the keyboard layout for the system.
    """
    name = "salt"

    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    mock = MagicMock(side_effect=[name, "", "", ""])
    mock_t = MagicMock(side_effect=[True, False])
    with patch.dict(
        keyboard.__salt__, {"keyboard.get_sys": mock, "keyboard.set_sys": mock_t}
    ):
        comt = "System layout {} already set".format(name)
        ret.update({"comment": comt})
        assert keyboard.system(name) == ret

        with patch.dict(keyboard.__opts__, {"test": True}):
            comt = "System layout {} needs to be set".format(name)
            ret.update({"comment": comt, "result": None})
            assert keyboard.system(name) == ret

        with patch.dict(keyboard.__opts__, {"test": False}):
            comt = "Set system keyboard layout {}".format(name)
            ret.update({"comment": comt, "result": True, "changes": {"layout": name}})
            assert keyboard.system(name) == ret

            comt = "Failed to set system keyboard layout"
            ret.update({"comment": comt, "result": False, "changes": {}})
            assert keyboard.system(name) == ret


# 'xorg' function tests: 1


def test_xorg():
    """
    Test to set the keyboard layout for XOrg.
    """
    name = "salt"

    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    mock = MagicMock(side_effect=[name, "", "", ""])
    mock_t = MagicMock(side_effect=[True, False])
    with patch.dict(
        keyboard.__salt__, {"keyboard.get_x": mock, "keyboard.set_x": mock_t}
    ):
        comt = "XOrg layout {} already set".format(name)
        ret.update({"comment": comt})
        assert keyboard.xorg(name) == ret

        with patch.dict(keyboard.__opts__, {"test": True}):
            comt = "XOrg layout {} needs to be set".format(name)
            ret.update({"comment": comt, "result": None})
            assert keyboard.xorg(name) == ret

        with patch.dict(keyboard.__opts__, {"test": False}):
            comt = "Set XOrg keyboard layout {}".format(name)
            ret.update({"comment": comt, "result": True, "changes": {"layout": name}})
            assert keyboard.xorg(name) == ret

            comt = "Failed to set XOrg keyboard layout"
            ret.update({"comment": comt, "result": False, "changes": {}})
            assert keyboard.xorg(name) == ret
