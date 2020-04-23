# -*- coding: utf-8 -*-
"""
Unit Tests for the mac_desktop execution module.
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.modules.mac_desktop as mac_desktop
from salt.exceptions import CommandExecutionError

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class MacDesktopTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.mac_desktop
    """

    def setup_loader_modules(self):
        return {mac_desktop: {}}

    # 'get_output_volume' function tests: 2

    def test_get_output_volume(self):
        """
        Test if it get the output volume (range 0 to 100)
        """
        mock = MagicMock(return_value={"retcode": 0, "stdout": "25"})
        with patch.dict(mac_desktop.__salt__, {"cmd.run_all": mock}):
            self.assertEqual(mac_desktop.get_output_volume(), "25")

    def test_get_output_volume_error(self):
        """
        Tests that an error is raised when cmd.run_all errors
        """
        mock = MagicMock(return_value={"retcode": 1})
        with patch.dict(mac_desktop.__salt__, {"cmd.run_all": mock}):
            self.assertRaises(CommandExecutionError, mac_desktop.get_output_volume)

    # 'set_output_volume' function tests: 2

    def test_set_output_volume(self):
        """
        Test if it set the volume of sound (range 0 to 100)
        """
        mock = MagicMock(return_value={"retcode": 0})
        with patch.dict(mac_desktop.__salt__, {"cmd.run_all": mock}), patch(
            "salt.modules.mac_desktop.get_output_volume", MagicMock(return_value="25")
        ):
            self.assertTrue(mac_desktop.set_output_volume("25"))

    def test_set_output_volume_error(self):
        """
        Tests that an error is raised when cmd.run_all errors
        """
        mock = MagicMock(return_value={"retcode": 1})
        with patch.dict(mac_desktop.__salt__, {"cmd.run_all": mock}):
            self.assertRaises(
                CommandExecutionError, mac_desktop.set_output_volume, "25"
            )

    # 'screensaver' function tests: 2

    def test_screensaver(self):
        """
        Test if it launch the screensaver
        """
        mock = MagicMock(return_value={"retcode": 0})
        with patch.dict(mac_desktop.__salt__, {"cmd.run_all": mock}):
            self.assertTrue(mac_desktop.screensaver())

    def test_screensaver_error(self):
        """
        Tests that an error is raised when cmd.run_all errors
        """
        mock = MagicMock(return_value={"retcode": 1})
        with patch.dict(mac_desktop.__salt__, {"cmd.run_all": mock}):
            self.assertRaises(CommandExecutionError, mac_desktop.screensaver)

    # 'lock' function tests: 2

    def test_lock(self):
        """
        Test if it lock the desktop session
        """
        mock = MagicMock(return_value={"retcode": 0})
        with patch.dict(mac_desktop.__salt__, {"cmd.run_all": mock}):
            self.assertTrue(mac_desktop.lock())

    def test_lock_error(self):
        """
        Tests that an error is raised when cmd.run_all errors
        """
        mock = MagicMock(return_value={"retcode": 1})
        with patch.dict(mac_desktop.__salt__, {"cmd.run_all": mock}):
            self.assertRaises(CommandExecutionError, mac_desktop.lock)

    # 'say' function tests: 2

    def test_say(self):
        """
        Test if it says some words.
        """
        mock = MagicMock(return_value={"retcode": 0})
        with patch.dict(mac_desktop.__salt__, {"cmd.run_all": mock}):
            self.assertTrue(mac_desktop.say())

    def test_say_error(self):
        """
        Tests that an error is raised when cmd.run_all errors
        """
        mock = MagicMock(return_value={"retcode": 1})
        with patch.dict(mac_desktop.__salt__, {"cmd.run_all": mock}):
            self.assertRaises(CommandExecutionError, mac_desktop.say)
