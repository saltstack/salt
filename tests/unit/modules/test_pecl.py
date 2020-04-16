# -*- coding: utf-8 -*-
"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.modules.pecl as pecl
from tests.support.mock import patch

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf


class PeclTestCase(TestCase):
    """
    Test cases for salt.modules.pecl
    """

    @skipIf(True, "FASTTEST skip")
    def test_install(self):
        """
        Test to installs one or several pecl extensions.
        """
        with patch.object(pecl, "_pecl", return_value="A"):
            self.assertEqual(pecl.install("fuse", force=True), "A")

            self.assertFalse(pecl.install("fuse"))

            with patch.object(pecl, "list_", return_value={"A": ["A", "B"]}):
                self.assertTrue(pecl.install(["A", "B"]))

    @skipIf(True, "FASTTEST skip")
    def test_uninstall(self):
        """
        Test to uninstall one or several pecl extensions.
        """
        with patch.object(pecl, "_pecl", return_value="A"):
            self.assertEqual(pecl.uninstall("fuse"), "A")

    @skipIf(True, "FASTTEST skip")
    def test_update(self):
        """
        Test to update one or several pecl extensions.
        """
        with patch.object(pecl, "_pecl", return_value="A"):
            self.assertEqual(pecl.update("fuse"), "A")

    @skipIf(True, "FASTTEST skip")
    def test_list_(self):
        """
        Test to list installed pecl extensions.
        """
        with patch.object(pecl, "_pecl", return_value="A\nB"):
            self.assertDictEqual(pecl.list_("channel"), {})
