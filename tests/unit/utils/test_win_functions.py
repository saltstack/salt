# -*- coding: utf-8 -*-

# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.utils.platform
import salt.utils.win_functions as win_functions


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

    @skipIf(not salt.utils.platform.is_windows(), 'WinDLL only available on Windows')
    def test_broadcast_setting_change(self):
        '''
            Test to rehash the Environment variables
        '''
        self.assertTrue(win_functions.broadcast_setting_change())
