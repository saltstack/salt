"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.modules.keyboard as keyboard
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {keyboard: {}}


# 'get_sys' function tests: 1


def test_get_sys():
    """
    Test if it get current system keyboard setting
    """
    mock = MagicMock(return_value="X11 Layout=us")
    with patch.dict(keyboard.__grains__, {"os_family": "RedHat"}):
        with patch.dict(keyboard.__salt__, {"cmd.run": mock}):
            assert keyboard.get_sys() == "us"


# 'set_sys' function tests: 1


def test_set_sys():
    """
    Test if it set current system keyboard setting
    """
    mock = MagicMock(return_value="us")
    with patch.dict(keyboard.__grains__, {"os_family": "RedHat"}):
        with patch.dict(keyboard.__salt__, {"cmd.run": mock}):
            with patch.dict(keyboard.__salt__, {"file.sed": MagicMock()}):
                assert keyboard.set_sys("us") == "us"


# 'get_x' function tests: 1


def test_get_x():
    """
    Test if it get current X keyboard setting
    """
    mock = MagicMock(return_value="layout:     us")
    with patch.dict(keyboard.__salt__, {"cmd.run": mock}):
        assert keyboard.get_x() == "us"


# 'set_x' function tests: 1


def test_set_x():
    """
    Test if it set current X keyboard setting
    """
    mock = MagicMock(return_value="us")
    with patch.dict(keyboard.__salt__, {"cmd.run": mock}):
        assert keyboard.set_x("us") == "us"
