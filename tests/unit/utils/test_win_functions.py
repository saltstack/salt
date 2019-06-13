# -*- coding: utf-8 -*-

# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import patch, MagicMock, NO_MOCK, NO_MOCK_REASON

# Import Salt Libs
import salt.utils.platform
import salt.utils.win_functions as win_functions

# Import 3rd Party Libs
try:
    import win32net
    HAS_WIN32 = True

    class WinError(win32net.error):
        winerror = 0

except ImportError:
    HAS_WIN32 = False


@skipIf(NO_MOCK, NO_MOCK_REASON)
class WinFunctionsTestCase(TestCase):
    '''
    Test cases for salt.utils.win_functions
    '''

    def test_escape_argument_simple(self):
        '''
        Test to make sure we encode simple arguments correctly
        '''
        encoded = win_functions.escape_argument('simple')

        self.assertEqual(encoded, 'simple')

    def test_escape_argument_with_space(self):
        '''
        Test to make sure we encode arguments containing spaces correctly
        '''
        encoded = win_functions.escape_argument('with space')

        self.assertEqual(encoded, '^"with space^"')

    def test_escape_argument_simple_path(self):
        '''
        Test to make sure we encode simple path arguments correctly
        '''
        encoded = win_functions.escape_argument('C:\\some\\path')

        self.assertEqual(encoded, 'C:\\some\\path')

    def test_escape_argument_path_with_space(self):
        '''
        Test to make sure we encode path arguments containing spaces correctly
        '''
        encoded = win_functions.escape_argument('C:\\Some Path\\With Spaces')

        self.assertEqual(encoded, '^"C:\\Some Path\\With Spaces^"')

    @skipIf(not salt.utils.platform.is_windows(),
            'WinDLL only available on Windows')
    def test_broadcast_setting_change(self):
        '''
            Test to rehash the Environment variables
        '''
        self.assertTrue(win_functions.broadcast_setting_change())

    @skipIf(not salt.utils.platform.is_windows(),
            'WinDLL only available on Windows')
    def test_get_user_groups(self):
        groups = ['Administrators', 'Users']
        with patch('win32net.NetUserGetLocalGroups', return_value=groups):
            ret = win_functions.get_user_groups('Administrator')
            self.assertListEqual(groups, ret)

    @skipIf(not salt.utils.platform.is_windows(),
            'WinDLL only available on Windows')
    def test_get_user_groups_sid(self):
        groups = ['Administrators', 'Users']
        expected = ['S-1-5-32-544', 'S-1-5-32-545']
        with patch('win32net.NetUserGetLocalGroups', return_value=groups):
            ret = win_functions.get_user_groups('Administrator', sid=True)
            self.assertListEqual(expected, ret)

    @skipIf(not salt.utils.platform.is_windows(),
            'WinDLL only available on Windows')
    def test_get_user_groups_system(self):
        groups = ['SYSTEM']
        with patch('win32net.NetUserGetLocalGroups', return_value=groups):
            ret = win_functions.get_user_groups('SYSTEM')
            self.assertListEqual(groups, ret)

    @skipIf(not salt.utils.platform.is_windows(),
            'WinDLL only available on Windows')
    @skipIf(not HAS_WIN32, 'Requires pywin32 libraries')
    def test_get_user_groups_missing_permission(self):
        groups = ['Administrators', 'Users']
        win_error = WinError()
        win_error.winerror = 5
        effect = [win_error, groups]
        with patch('win32net.NetUserGetLocalGroups', side_effect=effect):
            ret = win_functions.get_user_groups('Administrator')
            self.assertListEqual(groups, ret)

    @skipIf(not salt.utils.platform.is_windows(),
            'WinDLL only available on Windows')
    @skipIf(not HAS_WIN32, 'Requires pywin32 libraries')
    def test_get_user_groups_error(self):
        win_error = WinError()
        win_error.winerror = 1927
        mock_error = MagicMock(side_effect=win_error)
        with patch('win32net.NetUserGetLocalGroups', side_effect=mock_error):
            with self.assertRaises(WinError):
                win_functions.get_user_groups('Administrator')
