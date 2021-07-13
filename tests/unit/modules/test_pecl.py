"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""


import salt.modules.pecl as pecl
from tests.support.mock import patch
from tests.support.unit import TestCase


class PeclTestCase(TestCase):
    """
    Test cases for salt.modules.pecl
    """

    def test_install(self):
        """
        Test to installs one or several pecl extensions.
        """
        with patch.object(pecl, "_pecl", return_value="A"):
            self.assertEqual(pecl.install("fuse", force=True), "A")

            self.assertFalse(pecl.install("fuse"))

            with patch.object(pecl, "list_", return_value={"A": ["A", "B"]}):
                self.assertTrue(pecl.install(["A", "B"]))

    def test_uninstall(self):
        """
        Test to uninstall one or several pecl extensions.
        """
        with patch.object(pecl, "_pecl", return_value="A"):
            self.assertEqual(pecl.uninstall("fuse"), "A")

    def test_update(self):
        """
        Test to update one or several pecl extensions.
        """
        with patch.object(pecl, "_pecl", return_value="A"):
            self.assertEqual(pecl.update("fuse"), "A")

    def test_list_(self):
        """
        Test to list installed pecl extensions.
        """
        with patch.object(pecl, "_pecl", return_value="A\nB"):
            self.assertDictEqual(pecl.list_("channel"), {})
