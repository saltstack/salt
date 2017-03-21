# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch
)

# Import Salt Libs
import salt.modules.win_ntp as win_ntp

# Globals
win_ntp.__salt__ = {}

# Make sure this module runs on Windows system
IS_WIN = win_ntp.__virtual__()


@skipIf(not IS_WIN, "This test case runs only on Windows system")
class WinNtpTestCase(TestCase):
    '''
    Test cases for salt.modules.win_ntp
    '''
    # 'set_servers' function tests: 1

    def test_set_servers(self):
        '''
        Test if it set Windows to use a list of NTP servers
        '''
        mock_service = MagicMock(return_value=False)
        mock_cmd = MagicMock(return_value='Failure')
        with patch.dict(win_ntp.__salt__, {'service.status': mock_service,
                                           'service.start': mock_service,
                                           'cmd.run': mock_cmd}):
            self.assertFalse(win_ntp.set_servers('pool.ntp.org'))

        mock_service = MagicMock(return_value=True)
        mock_cmd = MagicMock(return_value='Failure')
        with patch.dict(win_ntp.__salt__, {'service.status': mock_service,
                                           'service.start': mock_service,
                                           'cmd.run': mock_cmd}):
            self.assertFalse(win_ntp.set_servers('pool.ntp.org'))

        mock_cmd = MagicMock(return_value='command completed successfully')
        with patch.dict(win_ntp.__salt__, {'service.status': mock_service,
                                           'service.start': mock_service,
                                           'service.restart': mock_service,
                                           'cmd.run': mock_cmd}):
            self.assertTrue(win_ntp.set_servers('pool.ntp.org'))

    # 'get_servers' function tests: 1

    def test_get_servers(self):
        '''
        Test if it get list of configured NTP servers
        '''
        mock_cmd = MagicMock(side_effect=['', 'NtpServer: SALT', 'NtpServer'])
        with patch.dict(win_ntp.__salt__, {'cmd.run': mock_cmd}):
            self.assertFalse(win_ntp.get_servers())

            self.assertListEqual(win_ntp.get_servers(), ['SALT'])

            self.assertFalse(win_ntp.get_servers())
