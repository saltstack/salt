# -*- coding: utf-8 -*-
"""
Tests for the salt-run command
"""
from __future__ import absolute_import, print_function, unicode_literals

import pytest
from tests.support.case import ShellCase
from tests.support.unit import skipIf


@pytest.mark.windows_whitelisted
class ManageTest(ShellCase):
    """
    Test the manage runner
    """

    @skipIf(True, "SLOWTEST skip")
    def test_up(self):
        """
        manage.up
        """
        ret = self.run_run_plus("manage.up", timeout=60)
        self.assertIn("minion", ret["return"])
        self.assertIn("sub_minion", ret["return"])
        self.assertTrue(any("- minion" in out for out in ret["out"]))
        self.assertTrue(any("- sub_minion" in out for out in ret["out"]))

    @skipIf(True, "SLOWTEST skip")
    def test_down(self):
        """
        manage.down
        """
        ret = self.run_run_plus("manage.down", timeout=60)
        self.assertNotIn("minion", ret["return"])
        self.assertNotIn("sub_minion", ret["return"])
        self.assertNotIn("minion", ret["out"])
        self.assertNotIn("sub_minion", ret["out"])
