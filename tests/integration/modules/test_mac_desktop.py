# -*- coding: utf-8 -*-
"""
Integration tests for the mac_desktop execution module.
"""
from __future__ import absolute_import, print_function, unicode_literals

from salt.ext import six
from tests.support.case import ModuleCase
from tests.support.helpers import destructiveTest, runs_on, skip_if_not_root, slowTest


@destructiveTest
@skip_if_not_root
@runs_on(kernel="Darwin")
class MacDesktopTestCase(ModuleCase):
    """
    Integration tests for the mac_desktop module.
    """

    def test_get_output_volume(self):
        """
        Tests the return of get_output_volume.
        """
        ret = self.run_function("desktop.get_output_volume")
        self.assertIsNotNone(ret)

    @slowTest
    def test_set_output_volume(self):
        """
        Tests the return of set_output_volume.
        """
        current_vol = self.run_function("desktop.get_output_volume")
        to_set = 10
        if current_vol == six.text_type(to_set):
            to_set += 2
        new_vol = self.run_function(
            "desktop.set_output_volume", [six.text_type(to_set)]
        )
        check_vol = self.run_function("desktop.get_output_volume")
        self.assertEqual(new_vol, check_vol)

        # Set volume back to what it was before
        self.run_function("desktop.set_output_volume", [current_vol])

    def test_screensaver(self):
        """
        Tests the return of the screensaver function.
        """
        self.assertTrue(self.run_function("desktop.screensaver"))

    def test_lock(self):
        """
        Tests the return of the lock function.
        """
        self.assertTrue(self.run_function("desktop.lock"))

    @slowTest
    def test_say(self):
        """
        Tests the return of the say function.
        """
        self.assertTrue(self.run_function("desktop.say", ["hello", "world"]))
