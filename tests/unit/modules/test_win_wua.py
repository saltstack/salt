"""
Test the win_wua execution module
"""
import salt.modules.win_wua as win_wua
import salt.utils.platform
import salt.utils.win_update
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase, skipIf

UPDATES_LIST = {
    "ca3bb521-a8ea-4e26-a563-2ad6e3108b9a": {"KBs": ["KB4481252"]},
    "07609d43-d518-4e77-856e-d1b316d1b8a8": {"KBs": ["KB925673"]},
    "fbaa5360-a440-49d8-a3b6-0c4fc7ecaa19": {"KBs": ["KB4481252"]},
    "a873372b-7a5c-443c-8022-cd59a550bef4": {"KBs": ["KB3193497"]},
    "14075cbe-822e-4004-963b-f50e08d45563": {"KBs": ["KB4540723"]},
    "d931e99c-4dda-4d39-9905-0f6a73f7195f": {"KBs": ["KB3193497"]},
    "afda9e11-44a0-4602-9e9b-423af11ecaed": {"KBs": ["KB4541329"]},
    "a0f997b1-1abe-4a46-941f-b37f732f9fbd": {"KBs": ["KB3193497"]},
    "eac02b09-d745-4891-b80f-400e0e5e4b6d": {"KBs": ["KB4052623"]},
    "0689e74b-54d1-4f55-a916-96e3c737db90": {"KBs": ["KB890830"]},
}
UPDATES_SUMMARY = {"Installed": 10}


class Updates:
    @staticmethod
    def list():
        return UPDATES_LIST

    @staticmethod
    def summary():
        return UPDATES_SUMMARY


@skipIf(not salt.utils.platform.is_windows(), "System is not Windows")
class WinWuaInstalledTestCase(TestCase):
    """
    Test the functions in the win_wua.installed function
    """

    service_auto = {"StartType": "Auto"}
    service_disabled = {"StartType": "Disabled"}
    service_manual = {"StartType": "Manual"}

    def test__virtual__not_windows(self):
        """
        Test __virtual__ function on Non-Windows
        """
        with patch("salt.utils.platform.is_windows", autospec=True, return_value=False):
            expected = (False, "WUA: Only available on Windows systems")
            result = win_wua.__virtual__()
            self.assertEqual(expected, result)

    def test__virtual__missing_pywin32(self):
        """
        Test __virtual__ function when pywin32 is not installed
        """
        with patch("salt.modules.win_wua.HAS_PYWIN32", False):
            expected = (False, "WUA: Requires PyWin32 libraries")
            result = win_wua.__virtual__()
            self.assertEqual(expected, result)

    def test__virtual__wuauserv_disabled(self):
        """
        Test __virtual__ function when the wuauserv service is disabled
        """
        mock_service_info = MagicMock(
            side_effect=[
                self.service_disabled,  # wuauserv
                self.service_auto,  # msiserver
                self.service_auto,  # BITS
                self.service_auto,  # CryptSvc
                self.service_auto,  # TrustedInstaller
            ]
        )
        with patch("salt.utils.win_service.info", mock_service_info):
            expected = (
                False,
                "WUA: The Windows Update service (wuauserv) must not be disabled",
            )
            result = win_wua.__virtual__()
            self.assertEqual(expected, result)

    def test__virtual__msiserver_disabled(self):
        """
        Test __virtual__ function when the msiserver service is disabled
        """
        mock_service_info = MagicMock(
            side_effect=[
                self.service_auto,  # wuauserv
                self.service_disabled,  # msiserver
                self.service_auto,  # BITS
                self.service_auto,  # CryptSvc
                self.service_auto,  # TrustedInstaller
            ]
        )
        with patch("salt.utils.win_service.info", mock_service_info):
            expected = (
                False,
                "WUA: The Windows Installer service (msiserver) must not be disabled",
            )
            result = win_wua.__virtual__()
            self.assertEqual(expected, result)

    def test__virtual__BITS_disabled(self):
        """
        Test __virtual__ function when the BITS service is disabled
        """
        mock_service_info = MagicMock(
            side_effect=[
                self.service_auto,  # wuauserv
                self.service_auto,  # msiserver
                self.service_disabled,  # BITS
                self.service_auto,  # CryptSvc
                self.service_auto,  # TrustedInstaller
            ]
        )
        with patch("salt.utils.win_service.info", mock_service_info):
            expected = (
                False,
                "WUA: The Background Intelligent Transfer service (bits) must not be"
                " disabled",
            )
            result = win_wua.__virtual__()
            self.assertEqual(expected, result)

    def test__virtual__BITS_manual(self):
        """
        Test __virtual__ function when the BITS service is set to manual
        Should not disable the module (__virtual__ should return True)
        """
        mock_service_info = MagicMock(
            side_effect=[
                self.service_auto,  # wuauserv
                self.service_auto,  # msiserver
                self.service_manual,  # BITS
                self.service_auto,  # CryptSvc
                self.service_auto,  # TrustedInstaller
            ]
        )
        with patch("salt.utils.win_service.info", mock_service_info):
            expected = True
            result = win_wua.__virtual__()
            self.assertEqual(expected, result)

    def test__virtual__CryptSvc_disabled(self):
        """
        Test __virtual__ function when the CryptSvc service is disabled
        """
        mock_service_info = MagicMock(
            side_effect=[
                self.service_auto,  # wuauserv
                self.service_auto,  # msiserver
                self.service_auto,  # BITS
                self.service_disabled,  # CryptSvc
                self.service_auto,  # TrustedInstaller
            ]
        )
        with patch("salt.utils.win_service.info", mock_service_info):
            expected = (
                False,
                "WUA: The Cryptographic Services service (CryptSvc) must not be"
                " disabled",
            )
            result = win_wua.__virtual__()
            self.assertEqual(expected, result)

    def test__virtual__TrustedInstaller_disabled(self):
        """
        Test __virtual__ function when the TrustedInstaller service is disabled
        """
        mock_service_info = MagicMock(
            side_effect=[
                self.service_auto,  # wuauserv
                self.service_auto,  # msiserver
                self.service_auto,  # BITS
                self.service_auto,  # CryptSvc
                self.service_disabled,  # TrustedInstaller
            ]
        )
        with patch("salt.utils.win_service.info", mock_service_info):
            expected = (
                False,
                "WUA: The Windows Module Installer service (TrustedInstaller) must not"
                " be disabled",
            )
            result = win_wua.__virtual__()
            self.assertEqual(expected, result)

    def test_installed(self):
        """
        Test installed function default
        """
        expected = UPDATES_LIST
        with patch("salt.utils.winapi.Com", autospec=True), patch(
            "win32com.client.Dispatch", autospec=True
        ), patch.object(
            salt.utils.win_update.WindowsUpdateAgent, "refresh", autospec=True
        ), patch.object(
            salt.utils.win_update, "Updates", autospec=True, return_value=Updates()
        ):
            result = win_wua.installed()
            self.assertDictEqual(result, expected)

    def test_installed_summary(self):
        """
        Test installed function with summary=True
        """
        expected = UPDATES_SUMMARY
        # Remove all updates that are not installed
        with patch("salt.utils.winapi.Com", autospec=True), patch(
            "win32com.client.Dispatch", autospec=True
        ), patch.object(
            salt.utils.win_update.WindowsUpdateAgent, "refresh", autospec=True
        ), patch.object(
            salt.utils.win_update, "Updates", autospec=True, return_value=Updates()
        ):
            result = win_wua.installed(summary=True)
            self.assertDictEqual(result, expected)

    def test_installed_kbs_only(self):
        """
        Test installed function with kbs_only=True
        """
        expected = set()
        for update in UPDATES_LIST:
            expected.update(UPDATES_LIST[update]["KBs"])
        expected = sorted(expected)
        # Remove all updates that are not installed
        with patch("salt.utils.winapi.Com", autospec=True), patch(
            "win32com.client.Dispatch", autospec=True
        ), patch.object(
            salt.utils.win_update.WindowsUpdateAgent, "refresh", autospec=True
        ), patch.object(
            salt.utils.win_update, "Updates", autospec=True, return_value=Updates()
        ):
            result = win_wua.installed(kbs_only=True)
            self.assertListEqual(result, expected)
