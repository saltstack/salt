"""
Tests for utils/win_functions.py
"""
import pytest

import salt.utils.win_functions as win_functions
from tests.support.mock import MagicMock, patch

HAS_WIN32 = False
HAS_PYWIN = False

try:
    import pywintypes
    import win32net

    HAS_WIN32 = True

    class WinError(win32net.error):
        winerror = 0

    class PyWinError(pywintypes.error):
        pywinerror = 0

except ImportError:
    HAS_WIN32 = False

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.skipif(HAS_WIN32 is False, reason="Tests require win32 libraries"),
]


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


def test_get_user_groups_unavailable_dc():
    groups = ["Administrators", "Users"]
    win_error = WinError()
    win_error.winerror = 1722
    effect = [win_error, groups]
    with patch("win32net.NetUserGetLocalGroups", side_effect=effect):
        assert win_functions.get_user_groups("Administrator") == groups


def test_get_user_groups_unknown_dc():
    groups = ["Administrators", "Users"]
    win_error = WinError()
    win_error.winerror = 2453
    effect = [win_error, groups]
    with patch("win32net.NetUserGetLocalGroups", side_effect=effect):
        assert win_functions.get_user_groups("Administrator") == groups


def test_get_user_groups_missing_permission():
    groups = ["Administrators", "Users"]
    win_error = WinError()
    win_error.winerror = 5
    effect = [win_error, groups]
    with patch("win32net.NetUserGetLocalGroups", side_effect=effect):
        assert win_functions.get_user_groups("Administrator") == groups


def test_get_user_groups_error():
    win_error = WinError()
    win_error.winerror = 1927
    mock_error = MagicMock(side_effect=win_error)
    with patch("win32net.NetUserGetLocalGroups", side_effect=mock_error):
        with pytest.raises(WinError):
            win_functions.get_user_groups("Administrator")


def test_get_user_groups_local_pywin_error():
    win_error = PyWinError()
    win_error.winerror = 1355
    mock_error = MagicMock(side_effect=win_error)
    with patch("win32net.NetUserGetLocalGroups", side_effect=mock_error):
        with pytest.raises(PyWinError):
            win_functions.get_user_groups("Administrator")


def test_get_user_groups_pywin_error():
    win_error = PyWinError()
    win_error.winerror = 1355
    mock_error = MagicMock(side_effect=win_error)
    with patch("win32net.NetUserGetLocalGroups", side_effect=mock_error):
        with patch("win32net.NetUserGetGroups", side_effect=mock_error):
            with pytest.raises(PyWinError):
                win_functions.get_user_groups("Administrator")


def test_get_users_sids():
    """
    Test the get_users_sids function. We can't check the SID because that is
    unique to the system running the test.
    """
    users_pids = win_functions.get_users_sids()
    found_admin = False
    for user, pid in users_pids:
        if user == "Administrator":
            found_admin = True
    assert found_admin is True


def test_get_users_sids_unfiltered():
    """
    Test the get_users_sids function with the filter cleared. We can't check the
    SID because that is unique to the system running the test.
    """
    users_pids = win_functions.get_users_sids(exclude=[])
    found_admin = False
    found_default = False
    found_guest = False
    found_wdag = False
    for user, pid in users_pids:
        if user == "Administrator":
            found_admin = True
        if user == "DefaultAccount":
            found_default = True
        if user == "Guest":
            found_guest = True
        if user == "WDAGUtilityAccount":
            found_wdag = True
    assert found_admin is True
    assert found_default is True
    assert found_guest is True
    assert found_wdag is True
