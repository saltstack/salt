import os

import pytest

from tests.support.mock import patch
from tests.support.unit import TestCase

try:
    import salt.utils.win_system as win_system
except Exception as exc:  # pylint: disable=broad-except
    win_system = exc


class WinSystemImportTestCase(TestCase):
    """
    Simply importing should not raise an error, especially on Linux
    """

    def test_import(self):
        if isinstance(win_system, Exception):
            raise Exception(f"Importing win_system caused traceback: {win_system}")


@pytest.mark.skip_unless_on_windows
class WinSystemTestCase(TestCase):
    """
    Test cases for salt.utils.win_system
    """

    def test_get_computer_name(self):
        """
        Should return the computer name
        """
        with patch("win32api.GetComputerNameEx", return_value="FAKENAME"):
            self.assertEqual(win_system.get_computer_name(), "FAKENAME")

    def test_get_computer_name_fail(self):
        """
        If it fails, it returns False
        """
        with patch("win32api.GetComputerNameEx", return_value=None):
            self.assertFalse(win_system.get_computer_name())

    def test_get_pending_computer_name(self):
        """
        Will return the pending computer name if one is pending
        """
        expected = "PendingName"
        patch_value = {"vdata": expected}
        with patch("salt.utils.win_reg.read_value", return_value=patch_value):
            result = win_system.get_pending_computer_name()
            self.assertEqual(expected, result)

    def test_get_pending_computer_name_none(self):
        """
        Will return the None if the pending computer is the current name
        """
        patch_value = {"vdata": os.environ.get("COMPUTERNAME")}
        with patch("salt.utils.win_reg.read_value", return_value=patch_value):
            self.assertIsNone(win_system.get_pending_computer_name())

    def test_get_pending_computer_name_false(self):
        """
        Will return False if there is no pending computer name
        """
        with patch("salt.utils.win_reg.read_value", return_value=False):
            self.assertIsNone(win_system.get_pending_computer_name())

    def test_get_pending_component_servicing(self):
        """
        If none of the keys exist, should return False
        """
        with patch("salt.utils.win_reg.key_exists", return_value=False):
            self.assertFalse(win_system.get_pending_component_servicing())

    def test_get_pending_component_servicing_true_1(self):
        """
        If the RebootPending key exists, should return True
        """
        with patch("salt.utils.win_reg.key_exists", side_effect=[True]):
            self.assertTrue(win_system.get_pending_component_servicing())

    def test_get_pending_component_servicing_true_2(self):
        """
        If the RebootInProgress key exists, should return True
        """
        with patch("salt.utils.win_reg.key_exists", side_effect=[False, True]):
            self.assertTrue(win_system.get_pending_component_servicing())

    def test_get_pending_component_servicing_true_3(self):
        """
        If the PackagesPending key exists, should return True
        """
        with patch("salt.utils.win_reg.key_exists", side_effect=[False, False, True]):
            self.assertTrue(win_system.get_pending_component_servicing())

    def test_get_pending_domain_join(self):
        """
        If none of the keys exist, should return False
        """
        with patch("salt.utils.win_reg.key_exists", return_value=False):
            self.assertFalse(win_system.get_pending_domain_join())

    def test_get_pending_domain_join_true_1(self):
        """
        If the AvoidSpnSet key exists, should return True
        """
        with patch("salt.utils.win_reg.key_exists", side_effect=[True]):
            self.assertTrue(win_system.get_pending_domain_join())

    def test_get_pending_domain_join_true_2(self):
        """
        If the JoinDomain key exists, should return True
        """
        with patch("salt.utils.win_reg.key_exists", side_effect=[False, True]):
            self.assertTrue(win_system.get_pending_domain_join())

    def test_get_pending_file_rename_false_1(self):
        """
        If none of the value names exist, should return False
        """
        patched_return = {"success": False}
        with patch("salt.utils.win_reg.read_value", return_value=patched_return):
            self.assertFalse(win_system.get_pending_file_rename())

    def test_get_pending_file_rename_false_2(self):
        """
        If one of the value names exists but is not set, should return False
        """
        patched_return = {"success": True, "vdata": "(value not set)"}
        with patch("salt.utils.win_reg.read_value", return_value=patched_return):
            self.assertFalse(win_system.get_pending_file_rename())

    def test_get_pending_file_rename_true_1(self):
        """
        If one of the value names exists and is set, should return True
        """
        patched_return = {"success": True, "vdata": "some value"}
        with patch("salt.utils.win_reg.read_value", return_value=patched_return):
            self.assertTrue(win_system.get_pending_file_rename())

    def test_get_pending_servermanager_false_1(self):
        """
        If the CurrentRebootAttempts value name does not exist, should return
        False
        """
        patched_return = {"success": False}
        with patch("salt.utils.win_reg.read_value", return_value=patched_return):
            self.assertFalse(win_system.get_pending_servermanager())

    def test_get_pending_servermanager_false_2(self):
        """
        If the CurrentRebootAttempts value name exists but is not an integer,
        should return False
        """
        patched_return = {"success": True, "vdata": "(value not set)"}
        with patch("salt.utils.win_reg.read_value", return_value=patched_return):
            self.assertFalse(win_system.get_pending_file_rename())

    def test_get_pending_servermanager_true(self):
        """
        If the CurrentRebootAttempts value name exists and is an integer,
        should return True
        """
        patched_return = {"success": True, "vdata": 1}
        with patch("salt.utils.win_reg.read_value", return_value=patched_return):
            self.assertTrue(win_system.get_pending_file_rename())

    def test_get_pending_dvd_reboot(self):
        """
        If the DVDRebootSignal value name does not exist, should return False
        """
        with patch("salt.utils.win_reg.value_exists", return_value=False):
            self.assertFalse(win_system.get_pending_dvd_reboot())

    def test_get_pending_dvd_reboot_true(self):
        """
        If the DVDRebootSignal value name exists, should return True
        """
        with patch("salt.utils.win_reg.value_exists", return_value=True):
            self.assertTrue(win_system.get_pending_dvd_reboot())

    def test_get_pending_update(self):
        """
        If none of the keys exist and there are not subkeys, should return False
        """
        with patch("salt.utils.win_reg.key_exists", return_value=False), patch(
            "salt.utils.win_reg.list_keys", return_value=[]
        ):
            self.assertFalse(win_system.get_pending_update())

    def test_get_pending_update_true_1(self):
        """
        If the RebootRequired key exists, should return True
        """
        with patch("salt.utils.win_reg.key_exists", side_effect=[True]):
            self.assertTrue(win_system.get_pending_update())

    def test_get_pending_update_true_2(self):
        """
        If the PostRebootReporting key exists, should return True
        """
        with patch("salt.utils.win_reg.key_exists", side_effect=[False, True]):
            self.assertTrue(win_system.get_pending_update())

    def test_get_reboot_required_witnessed_false_1(self):
        """
        The ``Reboot Required`` value name does not exist, should return False
        """
        patched_data = {"vdata": None}
        with patch("salt.utils.win_reg.read_value", return_value=patched_data):
            self.assertFalse(win_system.get_reboot_required_witnessed())

    def test_get_reboot_required_witnessed_false_2(self):
        """
        The ``Reboot required`` value name is set to 0, should return False
        """
        patched_data = {"vdata": 0}
        with patch("salt.utils.win_reg.read_value", return_value=patched_data):
            self.assertFalse(win_system.get_reboot_required_witnessed())

    def test_get_reboot_required_witnessed_true(self):
        """
        The ``Reboot required`` value name is set to 1, should return True
        """
        patched_data = {"vdata": 1}
        with patch("salt.utils.win_reg.read_value", return_value=patched_data):
            self.assertTrue(win_system.get_reboot_required_witnessed())

    def test_set_reboot_required_witnessed(self):
        """
        The call to ``set_value`` should return True and should be called with
        the specified parameters
        """
        with patch("salt.utils.win_reg.set_value", return_value=True) as sv:
            self.assertTrue(win_system.set_reboot_required_witnessed())
            sv.assert_called_once_with(
                hive="HKLM",
                key=win_system.MINION_VOLATILE_KEY,
                volatile=True,
                vname=win_system.REBOOT_REQUIRED_NAME,
                vdata=1,
                vtype="REG_DWORD",
            )

    def test_get_pending_update_exe_volatile_false_1(self):
        """
        If UpdateExeVolatile value name is 0, should return False
        """
        patched_data = {"success": True, "vdata": 0}
        with patch("salt.utils.win_reg.read_value", return_value=patched_data):
            self.assertFalse(win_system.get_pending_update_exe_volatile())

    def test_get_pending_update_exe_volatile_false_2(self):
        """
        If UpdateExeVolatile value name is not present, should return False
        """
        patched_data = {"success": False}
        with patch("salt.utils.win_reg.read_value", return_value=patched_data):
            self.assertFalse(win_system.get_pending_update_exe_volatile())

    def test_get_pending_update_exe_volatile_true_1(self):
        """
        If UpdateExeVolatile value name is not 0, should return True
        """
        patched_data = {"success": True, "vdata": 1}
        with patch("salt.utils.win_reg.read_value", return_value=patched_data):
            self.assertTrue(win_system.get_pending_update_exe_volatile())

    def test_get_pending_reboot(self):
        """
        If all functions return Falsy data, should return False
        """
        with patch(
            "salt.utils.win_system.get_pending_update", return_value=False
        ), patch("salt.utils.win_update.needs_reboot", return_value=False), patch(
            "salt.utils.win_system.get_pending_update_exe_volatile", return_value=False
        ), patch(
            "salt.utils.win_system.get_pending_file_rename", return_value=False
        ), patch(
            "salt.utils.win_system.get_pending_servermanager", return_value=False
        ), patch(
            "salt.utils.win_system.get_pending_component_servicing", return_value=False
        ), patch(
            "salt.utils.win_system.get_pending_dvd_reboot", return_value=False
        ), patch(
            "salt.utils.win_system.get_reboot_required_witnessed", return_value=False
        ), patch(
            "salt.utils.win_system.get_pending_computer_name", return_value=None
        ), patch(
            "salt.utils.win_system.get_pending_domain_join", return_value=False
        ):
            self.assertFalse(win_system.get_pending_reboot())

    def test_get_pending_reboot_true_1(self):
        """
        If any boolean returning functions return True, should return True
        """
        with patch(
            "salt.utils.win_system.get_pending_update", return_value=False
        ), patch("salt.utils.win_update.needs_reboot", return_value=False), patch(
            "salt.utils.win_system.get_pending_update_exe_volatile", return_value=False
        ), patch(
            "salt.utils.win_system.get_pending_file_rename", return_value=False
        ), patch(
            "salt.utils.win_system.get_pending_servermanager", return_value=False
        ), patch(
            "salt.utils.win_system.get_pending_component_servicing", return_value=False
        ), patch(
            "salt.utils.win_system.get_pending_dvd_reboot", return_value=False
        ), patch(
            "salt.utils.win_system.get_reboot_required_witnessed", return_value=False
        ), patch(
            "salt.utils.win_system.get_pending_computer_name", return_value=None
        ), patch(
            "salt.utils.win_system.get_pending_domain_join", return_value=True
        ):
            self.assertTrue(win_system.get_pending_reboot())

    def test_get_pending_reboot_true_2(self):
        """
        If a computer name is returned, should return True
        """
        with patch(
            "salt.utils.win_system.get_pending_update", return_value=False
        ), patch("salt.utils.win_update.needs_reboot", return_value=False), patch(
            "salt.utils.win_system.get_pending_update_exe_volatile", return_value=False
        ), patch(
            "salt.utils.win_system.get_pending_file_rename", return_value=False
        ), patch(
            "salt.utils.win_system.get_pending_servermanager", return_value=False
        ), patch(
            "salt.utils.win_system.get_pending_component_servicing", return_value=False
        ), patch(
            "salt.utils.win_system.get_pending_dvd_reboot", return_value=False
        ), patch(
            "salt.utils.win_system.get_reboot_required_witnessed", return_value=False
        ), patch(
            "salt.utils.win_system.get_pending_computer_name",
            return_value="pending name",
        ):
            self.assertTrue(win_system.get_pending_reboot())

    def test_get_pending_reboot_details(self):
        """
        All items False should return a dictionary with all items False
        """
        with patch(
            "salt.utils.win_system.get_pending_update", return_value=False
        ), patch("salt.utils.win_update.needs_reboot", return_value=False), patch(
            "salt.utils.win_system.get_pending_update_exe_volatile", return_value=False
        ), patch(
            "salt.utils.win_system.get_pending_file_rename", return_value=False
        ), patch(
            "salt.utils.win_system.get_pending_servermanager", return_value=False
        ), patch(
            "salt.utils.win_system.get_pending_component_servicing", return_value=False
        ), patch(
            "salt.utils.win_system.get_pending_dvd_reboot", return_value=False
        ), patch(
            "salt.utils.win_system.get_reboot_required_witnessed", return_value=False
        ), patch(
            "salt.utils.win_system.get_pending_computer_name", return_value=None
        ), patch(
            "salt.utils.win_system.get_pending_domain_join", return_value=False
        ):
            expected = {
                "Pending Component Servicing": False,
                "Pending Computer Rename": False,
                "Pending DVD Reboot": False,
                "Pending File Rename": False,
                "Pending Join Domain": False,
                "Pending ServerManager": False,
                "Pending Update": False,
                "Pending Windows Update": False,
                "Reboot Required Witnessed": False,
                "Volatile Update Exe": False,
            }
            result = win_system.get_pending_reboot_details()
            self.assertDictEqual(expected, result)

    def test_get_pending_reboot_details_true(self):
        """
        All items True should return a dictionary with all items True
        """
        with patch(
            "salt.utils.win_system.get_pending_update", return_value=True
        ), patch("salt.utils.win_update.needs_reboot", return_value=True), patch(
            "salt.utils.win_system.get_pending_update_exe_volatile", return_value=True
        ), patch(
            "salt.utils.win_system.get_pending_file_rename", return_value=True
        ), patch(
            "salt.utils.win_system.get_pending_servermanager", return_value=True
        ), patch(
            "salt.utils.win_system.get_pending_component_servicing", return_value=True
        ), patch(
            "salt.utils.win_system.get_pending_dvd_reboot", return_value=True
        ), patch(
            "salt.utils.win_system.get_reboot_required_witnessed", return_value=True
        ), patch(
            "salt.utils.win_system.get_pending_computer_name",
            return_value="pending name",
        ), patch(
            "salt.utils.win_system.get_pending_domain_join", return_value=True
        ):
            expected = {
                "Pending Component Servicing": True,
                "Pending Computer Rename": True,
                "Pending DVD Reboot": True,
                "Pending File Rename": True,
                "Pending Join Domain": True,
                "Pending ServerManager": True,
                "Pending Update": True,
                "Pending Windows Update": True,
                "Reboot Required Witnessed": True,
                "Volatile Update Exe": True,
            }
            result = win_system.get_pending_reboot_details()
            self.assertDictEqual(expected, result)
