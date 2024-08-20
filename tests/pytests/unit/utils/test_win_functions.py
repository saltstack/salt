import platform

import pytest

import salt.utils.win_functions as win_functions
from tests.support.mock import MagicMock, patch

HAS_WIN32 = False
HAS_PYWIN = False

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
]

try:
    import win32net

    HAS_WIN32 = True

    class WinError(win32net.error):
        winerror = 0

except ImportError:
    HAS_WIN32 = False

try:
    import pywintypes

    HAS_PYWIN = True

    class PyWinError(pywintypes.error):
        pywinerror = 0

except ImportError:
    HAS_PYWIN = False


# Test cases for salt.utils.win_functions.


def test_escape_argument_simple():
    """
    Test to make sure we encode simple arguments correctly
    """
    encoded = win_functions.escape_argument("simple")
    assert encoded == "simple"


def test_escape_argument_with_space():
    """
    Test to make sure we encode arguments containing spaces correctly
    """
    encoded = win_functions.escape_argument("with space")
    assert encoded == '^"with space^"'


def test_escape_argument_simple_path():
    """
    Test to make sure we encode simple path arguments correctly
    """
    encoded = win_functions.escape_argument("C:\\some\\path")
    assert encoded == "C:\\some\\path"


def test_escape_argument_path_with_space():
    """
    Test to make sure we encode path arguments containing spaces correctly
    """
    encoded = win_functions.escape_argument("C:\\Some Path\\With Spaces")
    assert encoded == '^"C:\\Some Path\\With Spaces^"'


def test_broadcast_setting_change():
    """
    Test to rehash the Environment variables
    """
    assert win_functions.broadcast_setting_change()


def test_get_user_groups():
    groups = ["Administrators", "Users"]
    with patch("win32net.NetUserGetLocalGroups", return_value=groups):
        assert win_functions.get_user_groups("Administrator") == groups


def test_get_user_groups_sid():
    groups = ["Administrators", "Users"]
    expected = ["S-1-5-32-544", "S-1-5-32-545"]
    with patch("win32net.NetUserGetLocalGroups", return_value=groups):
        assert win_functions.get_user_groups("Administrator", sid=True) == expected


def test_get_user_groups_system():
    groups = ["SYSTEM"]
    with patch("win32net.NetUserGetLocalGroups", return_value=groups):
        assert win_functions.get_user_groups("SYSTEM") == groups


@pytest.mark.skipif(not HAS_WIN32, reason="Requires Win32 libraries")
def test_get_user_groups_unavailable_dc():
    groups = ["Administrators", "Users"]
    win_error = WinError()
    win_error.winerror = 1722
    effect = [win_error, groups]
    with patch("win32net.NetUserGetLocalGroups", side_effect=effect):
        assert win_functions.get_user_groups("Administrator") == groups


@pytest.mark.skipif(not HAS_WIN32, reason="Requires Win32 libraries")
def test_get_user_groups_unknown_dc():
    groups = ["Administrators", "Users"]
    win_error = WinError()
    win_error.winerror = 2453
    effect = [win_error, groups]
    with patch("win32net.NetUserGetLocalGroups", side_effect=effect):
        assert win_functions.get_user_groups("Administrator") == groups


@pytest.mark.skipif(not HAS_WIN32, reason="Requires Win32 libraries")
def test_get_user_groups_missing_permission():
    groups = ["Administrators", "Users"]
    win_error = WinError()
    win_error.winerror = 5
    effect = [win_error, groups]
    with patch("win32net.NetUserGetLocalGroups", side_effect=effect):
        assert win_functions.get_user_groups("Administrator") == groups


@pytest.mark.skipif(not HAS_WIN32, reason="Requires Win32 libraries")
def test_get_user_groups_error():
    win_error = WinError()
    win_error.winerror = 1927
    mock_error = MagicMock(side_effect=win_error)
    with patch("win32net.NetUserGetLocalGroups", side_effect=mock_error):
        with pytest.raises(WinError):
            win_functions.get_user_groups("Administrator")


@pytest.mark.skipif(not HAS_PYWIN, reason="Requires pywintypes libraries")
def test_get_user_groups_local_pywin_error():
    win_error = PyWinError()
    win_error.winerror = 1355
    mock_error = MagicMock(side_effect=win_error)
    with patch("win32net.NetUserGetLocalGroups", side_effect=mock_error):
        with pytest.raises(PyWinError):
            win_functions.get_user_groups("Administrator")


@pytest.mark.skipif(not HAS_PYWIN, reason="Requires pywintypes libraries")
def test_get_user_groups_pywin_error():
    win_error = PyWinError()
    win_error.winerror = 1355
    mock_error = MagicMock(side_effect=win_error)
    with patch("win32net.NetUserGetLocalGroups", side_effect=mock_error):
        with patch("win32net.NetUserGetGroups", side_effect=mock_error):
            with pytest.raises(PyWinError):
                win_functions.get_user_groups("Administrator")


@pytest.mark.skipif(not HAS_PYWIN, reason="Requires pywintypes libraries")
def test_get_sam_name_lookup_fails():
    win_error = PyWinError()
    mock_error = MagicMock(side_effect=win_error)
    with patch("win32security.LookupAccountName", side_effect=mock_error):
        expected = "\\".join([platform.node()[:15].upper(), "junk"])
        result = win_functions.get_sam_name("junk")
        assert result == expected


@pytest.mark.skipif(not HAS_PYWIN, reason="Requires pywintypes libraries")
def test_get_sam_name_everyone():
    expected = "Everyone"
    result = win_functions.get_sam_name("Everyone")
    assert result == expected


@pytest.mark.skipif(not HAS_PYWIN, reason="Requires pywintypes libraries")
def test_get_sam_name():
    expected = "\\".join([platform.node()[:15], "Administrator"])
    result = win_functions.get_sam_name("Administrator")
    assert result == expected
