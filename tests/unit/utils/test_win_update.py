# -*- coding: utf-8 -*-

# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Testing Libs
from tests.support.mock import patch, MagicMock
from tests.support.unit import TestCase

# Import Salt Libs
import salt.utils.win_update as win_update


# @skipIf(not salt.utils.platform.is_windows(), 'Only test on Windows systems')
class WinUpdateTestCase(TestCase):
    '''
    Test cases for salt.utils.win_update
    '''
    def test_installed_no_updates(self):
        with patch('salt.utils.winapi.Com', autospec=True), \
                patch('win32com.client.Dispatch', autospec=True), \
                patch.object(win_update.WindowsUpdateAgent, 'refresh', autospec=True):

            wua = win_update.WindowsUpdateAgent(online=False)
            wua._updates = []

            installed_updates = wua.installed()

            assert installed_updates.updates.Add.call_count == 0

    def test_installed_no_updates_installed(self):
        with patch('salt.utils.winapi.Com', autospec=True), \
                patch('win32com.client.Dispatch', autospec=True), \
                patch.object(win_update.WindowsUpdateAgent, 'refresh', autospec=True):
            wua = win_update.WindowsUpdateAgent(online=False)

            wua._updates = [
                MagicMock(IsInstalled=False),
                MagicMock(IsInstalled=False),
                MagicMock(IsInstalled=False),
            ]

            installed_updates = wua.installed()

            assert installed_updates.updates.Add.call_count == 0

    def test_installed_updates_all_installed(self):
        with patch('salt.utils.winapi.Com', autospec=True), \
                patch('win32com.client.Dispatch', autospec=True), \
                patch.object(win_update.WindowsUpdateAgent, 'refresh', autospec=True):
            wua = win_update.WindowsUpdateAgent(online=False)

            wua._updates = [
                MagicMock(IsInstalled=True),
                MagicMock(IsInstalled=True),
                MagicMock(IsInstalled=True),
            ]

            installed_updates = wua.installed()

            assert installed_updates.updates.Add.call_count == 3

    def test_installed_updates_some_installed(self):
        with patch('salt.utils.winapi.Com', autospec=True), \
                patch('win32com.client.Dispatch', autospec=True), \
                patch.object(win_update.WindowsUpdateAgent, 'refresh', autospec=True):
            wua = win_update.WindowsUpdateAgent(online=False)

            wua._updates = [
                MagicMock(IsInstalled=True),
                MagicMock(IsInstalled=False),
                MagicMock(IsInstalled=True),
                MagicMock(IsInstalled=False),
                MagicMock(IsInstalled=True),
            ]

            installed_updates = wua.installed()

            assert installed_updates.updates.Add.call_count == 3
