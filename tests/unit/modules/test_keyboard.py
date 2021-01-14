# -*- coding: utf-8 -*-
"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.modules.keyboard as keyboard

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class KeyboardTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.keyboard
    """

    def setup_loader_modules(self):
        return {keyboard: {}}

    # 'get_sys' function tests: 1

    def test_get_sys(self):
        """
        Test if it get current system keyboard setting
        """
        mock = MagicMock(return_value="X11 Layout=us")
        with patch.dict(keyboard.__grains__, {"os_family": "RedHat"}):
            with patch.dict(keyboard.__salt__, {"cmd.run": mock}):
                self.assertEqual(keyboard.get_sys(), "us")

    # 'set_sys' function tests: 1

    def test_set_sys(self):
        """
        Test if it set current system keyboard setting
        """
        mock = MagicMock(return_value="us")
        with patch.dict(keyboard.__grains__, {"os_family": "RedHat"}):
            with patch.dict(keyboard.__salt__, {"cmd.run": mock}):
                with patch.dict(keyboard.__salt__, {"file.sed": MagicMock()}):
                    self.assertEqual(keyboard.set_sys("us"), "us")

    # 'get_x' function tests: 1

    def test_get_x(self):
        """
        Test if it get current X keyboard setting
        """
        mock = MagicMock(return_value="layout:     us")
        with patch.dict(keyboard.__salt__, {"cmd.run": mock}):
            self.assertEqual(keyboard.get_x(), "us")

    # 'set_x' function tests: 1

    def test_set_x(self):
        """
        Test if it set current X keyboard setting
        """
        mock = MagicMock(return_value="us")
        with patch.dict(keyboard.__salt__, {"cmd.run": mock}):
            self.assertEqual(keyboard.set_x("us"), "us")
