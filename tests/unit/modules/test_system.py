# -*- coding: utf-8 -*-
"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.modules.system as system

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class SystemTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.system
    """

    def setup_loader_modules(self):
        return {system: {}}

    def test_halt(self):
        """
        Test to halt a running system
        """
        with patch.dict(system.__salt__, {"cmd.run": MagicMock(return_value="A")}):
            self.assertEqual(system.halt(), "A")

    def test_init(self):
        """
        Test to change the system runlevel on sysV compatible systems
        """
        with patch.dict(system.__salt__, {"cmd.run": MagicMock(return_value="A")}):
            self.assertEqual(system.init("r"), "A")

    def test_poweroff(self):
        """
        Test to poweroff a running system
        """
        with patch.dict(system.__salt__, {"cmd.run": MagicMock(return_value="A")}):
            self.assertEqual(system.poweroff(), "A")

    def test_reboot(self):
        """
        Test to reboot the system with shutdown -r
        """
        cmd_mock = MagicMock(return_value="A")
        with patch.dict(system.__salt__, {"cmd.run": cmd_mock}):
            self.assertEqual(system.reboot(), "A")
        cmd_mock.assert_called_with(["shutdown", "-r", "now"], python_shell=False)

    def test_reboot_with_delay(self):
        """
        Test to reboot the system using shutdown -r with a delay
        """
        cmd_mock = MagicMock(return_value="A")
        with patch.dict(system.__salt__, {"cmd.run": cmd_mock}):
            self.assertEqual(system.reboot(at_time=5), "A")
        cmd_mock.assert_called_with(["shutdown", "-r", "5"], python_shell=False)

    def test_shutdown(self):
        """
        Test to shutdown a running system
        """
        cmd_mock = MagicMock(return_value="A")
        with patch.dict(system.__salt__, {"cmd.run": cmd_mock}), patch(
            "salt.utils.platform.is_freebsd", MagicMock(return_value=False)
        ), patch("salt.utils.platform.is_netbsd", MagicMock(return_value=False)), patch(
            "salt.utils.platform.is_openbsd", MagicMock(return_value=False)
        ):
            self.assertEqual(system.shutdown(), "A")
        cmd_mock.assert_called_with(["shutdown", "-h", "now"], python_shell=False)

    def test_shutdown_freebsd(self):
        """
        Test to shutdown a running FreeBSD system
        """
        cmd_mock = MagicMock(return_value="A")
        with patch.dict(system.__salt__, {"cmd.run": cmd_mock}), patch(
            "salt.utils.platform.is_freebsd", MagicMock(return_value=True)
        ), patch("salt.utils.platform.is_netbsd", MagicMock(return_value=False)), patch(
            "salt.utils.platform.is_openbsd", MagicMock(return_value=False)
        ):
            self.assertEqual(system.shutdown(), "A")
        cmd_mock.assert_called_with(["shutdown", "-p", "now"], python_shell=False)

    def test_shutdown_netbsd(self):
        """
        Test to shutdown a running NetBSD system
        """
        cmd_mock = MagicMock(return_value="A")
        with patch.dict(system.__salt__, {"cmd.run": cmd_mock}), patch(
            "salt.utils.platform.is_freebsd", MagicMock(return_value=False)
        ), patch("salt.utils.platform.is_netbsd", MagicMock(return_value=True)), patch(
            "salt.utils.platform.is_openbsd", MagicMock(return_value=False)
        ):
            self.assertEqual(system.shutdown(), "A")
        cmd_mock.assert_called_with(["shutdown", "-p", "now"], python_shell=False)

    def test_shutdown_openbsd(self):
        """
        Test to shutdown a running OpenBSD system
        """
        cmd_mock = MagicMock(return_value="A")
        with patch.dict(system.__salt__, {"cmd.run": cmd_mock}), patch(
            "salt.utils.platform.is_freebsd", MagicMock(return_value=False)
        ), patch("salt.utils.platform.is_netbsd", MagicMock(return_value=False)), patch(
            "salt.utils.platform.is_openbsd", MagicMock(return_value=True)
        ):
            self.assertEqual(system.shutdown(), "A")
        cmd_mock.assert_called_with(["shutdown", "-p", "now"], python_shell=False)
