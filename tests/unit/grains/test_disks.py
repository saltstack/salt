# -*- coding: utf-8 -*-
"""
    :codeauthor: :email:`Shane Lee <slee@saltstack.com>`
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import textwrap

# Import Salt Libs
import salt.grains.disks as disks

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class IscsiGrainsTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for _windows_disks grains
    """

    def setup_loader_modules(self):
        return {
            disks: {"__salt__": {}},
        }

    def test__windows_disks(self):
        """
        Test grains._windows_disks, normal return
        Should return a populated dictionary
        """
        mock_which = MagicMock(return_value="C:\\Windows\\System32\\wbem\\WMIC.exe")
        wmic_result = textwrap.dedent(
            """
            DeviceId  MediaType
            0         4
            1         0
            2         3
            3         5
        """
        )
        mock_run_all = MagicMock(return_value={"stdout": wmic_result, "retcode": 0})

        with patch("salt.utils.path.which", mock_which), patch.dict(
            disks.__salt__, {"cmd.run_all": mock_run_all}
        ):
            result = disks._windows_disks()
            expected = {
                "SSDs": ["\\\\.\\PhysicalDrive0"],
                "disks": [
                    "\\\\.\\PhysicalDrive0",
                    "\\\\.\\PhysicalDrive1",
                    "\\\\.\\PhysicalDrive2",
                    "\\\\.\\PhysicalDrive3",
                ],
            }
            self.assertDictEqual(result, expected)
            cmd = " ".join(
                [
                    "C:\\Windows\\System32\\wbem\\WMIC.exe",
                    "/namespace:\\\\root\\microsoft\\windows\\storage",
                    "path",
                    "MSFT_PhysicalDisk",
                    "get",
                    "DeviceID,MediaType",
                    "/format:table",
                ]
            )
            mock_run_all.assert_called_once_with(cmd)

    def test__windows_disks_retcode(self):
        """
        Test grains._windows_disks, retcode 1
        Should return empty lists
        """
        mock_which = MagicMock(return_value="C:\\Windows\\System32\\wbem\\WMIC.exe")
        mock_run_all = MagicMock(return_value={"stdout": "", "retcode": 1})
        with patch("salt.utils.path.which", mock_which), patch.dict(
            disks.__salt__, {"cmd.run_all": mock_run_all}
        ):
            result = disks._windows_disks()
            expected = {"SSDs": [], "disks": []}
            self.assertDictEqual(result, expected)
