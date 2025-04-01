"""
    Test cases for salt.modules.win_licence
"""

import pytest

import salt.modules.win_license as win_license
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {win_license: {}}


def test_installed():
    """
    Test to see if the given license key is installed
    """
    mock = MagicMock(return_value="Partial Product Key: ABCDE")
    with patch.dict(win_license.__salt__, {"cmd.run": mock}):
        out = win_license.installed("AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE")
        mock.assert_called_once_with(r"cscript C:\Windows\System32\slmgr.vbs /dli")
        assert out


def test_installed_diff():
    """
    Test to see if the given license key is installed when the key is different
    """
    mock = MagicMock(return_value="Partial Product Key: 12345")
    with patch.dict(win_license.__salt__, {"cmd.run": mock}):
        out = win_license.installed("AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE")
        mock.assert_called_once_with(r"cscript C:\Windows\System32\slmgr.vbs /dli")
        assert not out


def test_install():
    """
    Test installing the given product key
    """
    mock = MagicMock()
    with patch.dict(win_license.__salt__, {"cmd.run": mock}):
        win_license.install("AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE")
        mock.assert_called_once_with(
            r"cscript C:\Windows\System32\slmgr.vbs /ipk "
            "AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE"
        )


def test_uninstall():
    """
    Test uninstalling the given product key
    """
    mock = MagicMock()
    with patch.dict(win_license.__salt__, {"cmd.run": mock}):
        win_license.uninstall()
        mock.assert_called_once_with(r"cscript C:\Windows\System32\slmgr.vbs /upk")


def test_activate():
    """
    Test activating the current product key
    """
    mock = MagicMock()
    with patch.dict(win_license.__salt__, {"cmd.run": mock}):
        win_license.activate()
        mock.assert_called_once_with(r"cscript C:\Windows\System32\slmgr.vbs /ato")


def test_licensed():
    """
    Test checking if the minion is licensed
    """
    mock = MagicMock(return_value="License Status: Licensed")
    with patch.dict(win_license.__salt__, {"cmd.run": mock}):
        win_license.licensed()
        mock.assert_called_once_with(r"cscript C:\Windows\System32\slmgr.vbs /dli")


def test_info():
    """
    Test getting the info about the current license key
    """
    expected = {
        "description": "Prof",
        "licensed": True,
        "name": "Win7",
        "partial_key": "12345",
    }

    mock = MagicMock(
        return_value=(
            "Name: Win7\r\nDescription: Prof\r\nPartial Product Key: 12345\r\n"
            "License Status: Licensed"
        )
    )
    with patch.dict(win_license.__salt__, {"cmd.run": mock}):
        out = win_license.info()
        mock.assert_called_once_with(r"cscript C:\Windows\System32\slmgr.vbs /dli")
        assert out == expected
