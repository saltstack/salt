# -*- coding: utf-8 -*-
"""
Validate the mac-defaults module
"""

from __future__ import absolute_import, print_function, unicode_literals

from tests.support.case import ModuleCase
from tests.support.helpers import destructiveTest, runs_on, skip_if_not_root

DEFAULT_DOMAIN = "com.apple.AppleMultitouchMouse"
DEFAULT_KEY = "MouseHorizontalScroll"
DEFAULT_VALUE = "0"


@destructiveTest
@skip_if_not_root
@runs_on(kernel="Darwin")
class MacDefaultsModuleTest(ModuleCase):
    """
    Integration tests for the mac_default module
    """

    def test_macdefaults_write_read(self):
        """
        Tests that writes and reads macdefaults
        """
        write_domain = self.run_function(
            "macdefaults.write", [DEFAULT_DOMAIN, DEFAULT_KEY, DEFAULT_VALUE]
        )
        self.assertTrue(write_domain)

        read_domain = self.run_function(
            "macdefaults.read", [DEFAULT_DOMAIN, DEFAULT_KEY]
        )
        self.assertTrue(read_domain)
        self.assertEqual(read_domain, DEFAULT_VALUE)
