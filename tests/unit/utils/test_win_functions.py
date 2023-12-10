import pytest

import salt.utils.win_functions as win_functions
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase

try:
    import win32net

    HAS_WIN32 = True

    class WinError(win32net.error):
        winerror = 0

except ImportError:
    HAS_WIN32 = False


class WinFunctionsTestCase(TestCase):
    """
    Test cases for salt.utils.win_functions.
    """

    def test_escape_argument_simple(self):
        """
        Test to make sure we encode simple arguments correctly
        """
        encoded = win_functions.escape_argument("simple")

        self.assertEqual(encoded, "simple")

    def test_escape_argument_with_space(self):
        """
        Test to make sure we encode arguments containing spaces correctly
        """
        encoded = win_functions.escape_argument("with space")

        self.assertEqual(encoded, '^"with space^"')

    def test_escape_argument_simple_path(self):
        """
        Test to make sure we encode simple path arguments correctly
        """
        encoded = win_functions.escape_argument("C:\\some\\path")

        self.assertEqual(encoded, "C:\\some\\path")

    def test_escape_argument_path_with_space(self):
        """
        Test to make sure we encode path arguments containing spaces correctly
        """
        encoded = win_functions.escape_argument("C:\\Some Path\\With Spaces")

        self.assertEqual(encoded, '^"C:\\Some Path\\With Spaces^"')

    @pytest.mark.skip_unless_on_windows
    def test_broadcast_setting_change(self):
        """
        Test to rehash the Environment variables
        """
        self.assertTrue(win_functions.broadcast_setting_change())

    @pytest.mark.skip_unless_on_windows
    def test_get_user_groups(self):
        groups = ["Administrators", "Users"]
        with patch("win32net.NetUserGetLocalGroups", return_value=groups):
            ret = win_functions.get_user_groups("Administrator")
            self.assertListEqual(groups, ret)

    @pytest.mark.skip_unless_on_windows
    def test_get_user_groups_sid(self):
        groups = ["Administrators", "Users"]
        expected = ["S-1-5-32-544", "S-1-5-32-545"]
        with patch("win32net.NetUserGetLocalGroups", return_value=groups):
            ret = win_functions.get_user_groups("Administrator", sid=True)
            self.assertListEqual(expected, ret)

    @pytest.mark.skip_unless_on_windows
    def test_get_user_groups_system(self):
        groups = ["SYSTEM"]
        with patch("win32net.NetUserGetLocalGroups", return_value=groups):
            ret = win_functions.get_user_groups("SYSTEM")
            self.assertListEqual(groups, ret)

    @pytest.mark.skip_unless_on_windows
    @pytest.mark.skipif(not HAS_WIN32, reason="Requires pywin32 libraries")
    def test_get_user_groups_unavailable_dc(self):
        groups = ["Administrators", "Users"]
        win_error = WinError()
        win_error.winerror = 1722
        effect = [win_error, groups]
        with patch("win32net.NetUserGetLocalGroups", side_effect=effect):
            ret = win_functions.get_user_groups("Administrator")
            self.assertListEqual(groups, ret)

    @pytest.mark.skip_unless_on_windows
    @pytest.mark.skipif(not HAS_WIN32, reason="Requires pywin32 libraries")
    def test_get_user_groups_unknown_dc(self):
        groups = ["Administrators", "Users"]
        win_error = WinError()
        win_error.winerror = 2453
        effect = [win_error, groups]
        with patch("win32net.NetUserGetLocalGroups", side_effect=effect):
            ret = win_functions.get_user_groups("Administrator")
            self.assertListEqual(groups, ret)

    @pytest.mark.skip_unless_on_windows
    @pytest.mark.skipif(not HAS_WIN32, reason="Requires pywin32 libraries")
    def test_get_user_groups_missing_permission(self):
        groups = ["Administrators", "Users"]
        win_error = WinError()
        win_error.winerror = 5
        effect = [win_error, groups]
        with patch("win32net.NetUserGetLocalGroups", side_effect=effect):
            ret = win_functions.get_user_groups("Administrator")
            self.assertListEqual(groups, ret)

    @pytest.mark.skip_unless_on_windows
    @pytest.mark.skipif(not HAS_WIN32, reason="Requires pywin32 libraries")
    def test_get_user_groups_error(self):
        win_error = WinError()
        win_error.winerror = 1927
        mock_error = MagicMock(side_effect=win_error)
        with patch("win32net.NetUserGetLocalGroups", side_effect=mock_error):
            with self.assertRaises(WinError):
                win_functions.get_user_groups("Administrator")
