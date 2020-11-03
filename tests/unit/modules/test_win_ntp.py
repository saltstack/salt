# -*- coding: utf-8 -*-
"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.modules.win_ntp as win_ntp

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class WinNtpTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.win_ntp
    """

    def setup_loader_modules(self):
        return {win_ntp: {}}

    # 'set_servers' function tests: 1

    def test_set_servers(self):
        """
        Test if it set Windows to use a list of NTP servers
        """
        # Windows Time (W32Time) service is not started
        # Windows Time (W32Time) service fails to start
        mock_service = MagicMock(return_value=False)
        with patch.dict(
            win_ntp.__salt__,
            {"service.status": mock_service, "service.start": mock_service},
        ):
            self.assertFalse(win_ntp.set_servers("pool.ntp.org"))

        # Windows Time service is running
        # Fail to set NTP servers
        mock_service = MagicMock(return_value=True)
        mock_cmd = MagicMock(
            side_effect=[
                "Failure",
                "Failure",
                "Failure",
                "NtpServer: time.windows.com,0x8",
            ]
        )
        with patch.dict(
            win_ntp.__salt__, {"service.status": mock_service, "cmd.run": mock_cmd}
        ):
            self.assertFalse(win_ntp.set_servers("pool.ntp.org"))

        # Windows Time service is running
        # Successfully set NTP servers
        mock_cmd = MagicMock(
            side_effect=["Success", "Success", "Success", "NtpServer: pool.ntp.org"]
        )
        with patch.dict(
            win_ntp.__salt__,
            {
                "service.status": mock_service,
                "service.restart": mock_service,
                "cmd.run": mock_cmd,
            },
        ):
            self.assertTrue(win_ntp.set_servers("pool.ntp.org"))

    # 'get_servers' function tests: 1

    def test_get_servers(self):
        """
        Test if it get list of configured NTP servers
        """
        mock_cmd = MagicMock(side_effect=["", "NtpServer: SALT", "NtpServer"])
        with patch.dict(win_ntp.__salt__, {"cmd.run": mock_cmd}):
            self.assertFalse(win_ntp.get_servers())

            self.assertListEqual(win_ntp.get_servers(), ["SALT"])

            self.assertFalse(win_ntp.get_servers())
