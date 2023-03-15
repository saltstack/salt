"""
Test the win_wusa execution module
"""

import pytest

import salt.modules.win_wusa as win_wusa
from salt.exceptions import CommandExecutionError
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


@pytest.mark.skip_unless_on_windows
class WinWusaTestCase(TestCase, LoaderModuleMockMixin):
    """
    test the functions in the win_wusa execution module
    """

    def setup_loader_modules(self):
        return {win_wusa: {}}

    def test_is_installed_false(self):
        """
        test is_installed function when the KB is not installed
        """
        mock_retcode = MagicMock(return_value=1)
        with patch.dict(win_wusa.__salt__, {"cmd.retcode": mock_retcode}):
            self.assertFalse(win_wusa.is_installed("KB123456"))

    def test_is_installed_true(self):
        """
        test is_installed function when the KB is installed
        """
        mock_retcode = MagicMock(return_value=0)
        with patch.dict(win_wusa.__salt__, {"cmd.retcode": mock_retcode}):
            self.assertTrue(win_wusa.is_installed("KB123456"))

    def test_list(self):
        """
        test list function
        """
        ret = {
            "pid": 1,
            "retcode": 0,
            "stderr": "",
            "stdout": '[{"HotFixID": "KB123456"}, {"HotFixID": "KB123457"}]',
        }
        mock_all = MagicMock(return_value=ret)
        with patch.dict(win_wusa.__salt__, {"cmd.run_all": mock_all}):
            expected = ["KB123456", "KB123457"]
            returned = win_wusa.list()
            self.assertListEqual(expected, returned)

    def test_install(self):
        """
        test install function
        """
        mock_retcode = MagicMock(return_value=0)
        path = "C:\\KB123456.msu"
        with patch.dict(win_wusa.__salt__, {"cmd.retcode": mock_retcode}):
            self.assertTrue(win_wusa.install(path))
        mock_retcode.assert_called_once_with(
            ["wusa.exe", path, "/quiet", "/norestart"], ignore_retcode=True
        )

    def test_install_restart(self):
        """
        test install function with restart=True
        """
        mock_retcode = MagicMock(return_value=0)
        path = "C:\\KB123456.msu"
        with patch.dict(win_wusa.__salt__, {"cmd.retcode": mock_retcode}):
            self.assertTrue(win_wusa.install(path, restart=True))
        mock_retcode.assert_called_once_with(
            ["wusa.exe", path, "/quiet", "/forcerestart"], ignore_retcode=True
        )

    def test_install_already_installed(self):
        """
        test install function when KB already installed
        """
        retcode = 2359302
        mock_retcode = MagicMock(return_value=retcode)
        path = "C:\\KB123456.msu"
        name = "KB123456.msu"
        with patch.dict(win_wusa.__salt__, {"cmd.retcode": mock_retcode}):
            with self.assertRaises(CommandExecutionError) as excinfo:
                win_wusa.install(path)
        mock_retcode.assert_called_once_with(
            ["wusa.exe", path, "/quiet", "/norestart"], ignore_retcode=True
        )
        self.assertEqual(
            "{} is already installed. Additional info follows:\n\n{}".format(
                name, retcode
            ),
            excinfo.exception.strerror,
        )

    def test_install_reboot_needed(self):
        """
        test install function when KB need a reboot
        """
        retcode = 3010
        mock_retcode = MagicMock(return_value=retcode)
        path = "C:\\KB123456.msu"
        name = "KB123456.msu"
        with patch.dict(win_wusa.__salt__, {"cmd.retcode": mock_retcode}):
            with self.assertRaises(CommandExecutionError) as excinfo:
                win_wusa.install(path)
        mock_retcode.assert_called_once_with(
            ["wusa.exe", path, "/quiet", "/norestart"], ignore_retcode=True
        )
        self.assertEqual(
            "{} correctly installed but server reboot is needed to complete"
            " installation. Additional info follows:\n\n{}".format(name, retcode),
            excinfo.exception.strerror,
        )

    def test_install_error_87(self):
        """
        test install function when error 87 returned
        """
        retcode = 87
        mock_retcode = MagicMock(return_value=retcode)
        path = "C:\\KB123456.msu"
        with patch.dict(win_wusa.__salt__, {"cmd.retcode": mock_retcode}):
            with self.assertRaises(CommandExecutionError) as excinfo:
                win_wusa.install(path)
        mock_retcode.assert_called_once_with(
            ["wusa.exe", path, "/quiet", "/norestart"], ignore_retcode=True
        )
        self.assertEqual(
            "Unknown error. Additional info follows:\n\n{}".format(retcode),
            excinfo.exception.strerror,
        )

    def test_install_error_other(self):
        """
        test install function on other unknown error
        """
        mock_retcode = MagicMock(return_value=1234)
        path = "C:\\KB123456.msu"
        with patch.dict(win_wusa.__salt__, {"cmd.retcode": mock_retcode}):
            with self.assertRaises(CommandExecutionError) as excinfo:
                win_wusa.install(path)
        mock_retcode.assert_called_once_with(
            ["wusa.exe", path, "/quiet", "/norestart"], ignore_retcode=True
        )
        self.assertEqual("Unknown error: 1234", excinfo.exception.strerror)

    def test_uninstall_kb(self):
        """
        test uninstall function passing kb name
        """
        mock_retcode = MagicMock(return_value=0)
        kb = "KB123456"
        with patch.dict(win_wusa.__salt__, {"cmd.retcode": mock_retcode}), patch(
            "os.path.exists", MagicMock(return_value=False)
        ):
            self.assertTrue(win_wusa.uninstall(kb))
        mock_retcode.assert_called_once_with(
            [
                "wusa.exe",
                "/uninstall",
                "/quiet",
                "/kb:{}".format(kb[2:]),
                "/norestart",
            ],
            ignore_retcode=True,
        )

    def test_uninstall_path(self):
        """
        test uninstall function passing full path to .msu file
        """
        mock_retcode = MagicMock(return_value=0)
        path = "C:\\KB123456.msu"
        with patch.dict(win_wusa.__salt__, {"cmd.retcode": mock_retcode}), patch(
            "os.path.exists", MagicMock(return_value=True)
        ):
            self.assertTrue(win_wusa.uninstall(path))
        mock_retcode.assert_called_once_with(
            ["wusa.exe", "/uninstall", "/quiet", path, "/norestart"],
            ignore_retcode=True,
        )

    def test_uninstall_path_restart(self):
        """
        test uninstall function with full path and restart=True
        """
        mock_retcode = MagicMock(return_value=0)
        path = "C:\\KB123456.msu"
        with patch.dict(win_wusa.__salt__, {"cmd.retcode": mock_retcode}), patch(
            "os.path.exists", MagicMock(return_value=True)
        ):
            self.assertTrue(win_wusa.uninstall(path, restart=True))
        mock_retcode.assert_called_once_with(
            ["wusa.exe", "/uninstall", "/quiet", path, "/forcerestart"],
            ignore_retcode=True,
        )

    def test_uninstall_already_uninstalled(self):
        """
        test uninstall function when KB already uninstalled
        """
        retcode = 2359303
        mock_retcode = MagicMock(return_value=retcode)
        kb = "KB123456"
        with patch.dict(win_wusa.__salt__, {"cmd.retcode": mock_retcode}):
            with self.assertRaises(CommandExecutionError) as excinfo:
                win_wusa.uninstall(kb)
        mock_retcode.assert_called_once_with(
            [
                "wusa.exe",
                "/uninstall",
                "/quiet",
                "/kb:{}".format(kb[2:]),
                "/norestart",
            ],
            ignore_retcode=True,
        )
        self.assertEqual(
            "{} not installed. Additional info follows:\n\n{}".format(kb, retcode),
            excinfo.exception.strerror,
        )

    def test_uninstall_path_error_other(self):
        """
        test uninstall function with unknown error
        """
        mock_retcode = MagicMock(return_value=1234)
        path = "C:\\KB123456.msu"
        with patch.dict(win_wusa.__salt__, {"cmd.retcode": mock_retcode}), patch(
            "os.path.exists", MagicMock(return_value=True)
        ), self.assertRaises(CommandExecutionError) as excinfo:
            win_wusa.uninstall(path)
        mock_retcode.assert_called_once_with(
            ["wusa.exe", "/uninstall", "/quiet", path, "/norestart"],
            ignore_retcode=True,
        )
        self.assertEqual("Unknown error: 1234", excinfo.exception.strerror)
