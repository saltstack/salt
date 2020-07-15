# -*- coding: utf-8 -*-
"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.modules.aliases as aliases
from salt.exceptions import SaltInvocationError

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class AliasesTestCase(TestCase, LoaderModuleMockMixin):
    """
    TestCase for salt.modules.aliases module
    """

    mock_alias = [("foo", "bar@example.com", "")]
    mock_alias_mult = [
        ("foo", "bar@example.com", ""),
        ("hello", "world@earth.com, earth@world.com", ""),
    ]

    def setup_loader_modules(self):
        return {aliases: {}}

    def test_list_aliases(self):
        """
        Tests the return of a file containing one alias
        """
        with patch(
            "salt.modules.aliases.__parse_aliases",
            MagicMock(return_value=self.mock_alias),
        ):
            ret = {"foo": "bar@example.com"}
            self.assertEqual(aliases.list_aliases(), ret)

    def test_list_aliases_mult(self):
        """
        Tests the return of a file containing multiple aliases
        """
        with patch(
            "salt.modules.aliases.__parse_aliases",
            MagicMock(return_value=self.mock_alias_mult),
        ):
            ret = {
                "foo": "bar@example.com",
                "hello": "world@earth.com, earth@world.com",
            }
            self.assertEqual(aliases.list_aliases(), ret)

    def test_get_target(self):
        """
        Tests the target returned by an alias with one target
        """
        with patch(
            "salt.modules.aliases.__parse_aliases",
            MagicMock(return_value=self.mock_alias),
        ):
            ret = "bar@example.com"
            self.assertEqual(aliases.get_target("foo"), ret)

    def test_get_target_mult(self):
        """
        Tests the target returned by an alias with multiple targets
        """
        with patch(
            "salt.modules.aliases.__parse_aliases",
            MagicMock(return_value=self.mock_alias_mult),
        ):
            ret = "world@earth.com, earth@world.com"
            self.assertEqual(aliases.get_target("hello"), ret)

    def test_get_target_no_alias(self):
        """
        Tests return of an alias doesn't exist
        """
        with patch(
            "salt.modules.aliases.__parse_aliases",
            MagicMock(return_value=self.mock_alias),
        ):
            self.assertEqual(aliases.get_target("pizza"), "")

    def test_has_target(self):
        """
        Tests simple return known alias and target
        """
        with patch(
            "salt.modules.aliases.__parse_aliases",
            MagicMock(return_value=self.mock_alias),
        ):
            ret = aliases.has_target("foo", "bar@example.com")
            self.assertTrue(ret)

    def test_has_target_no_alias(self):
        """
        Tests return of empty alias and known target
        """
        with patch(
            "salt.modules.aliases.__parse_aliases",
            MagicMock(return_value=self.mock_alias),
        ):
            ret = aliases.has_target("", "bar@example.com")
            self.assertFalse(ret)

    def test_has_target_no_target(self):
        """
        Tests return of known alias and empty target
        """
        self.assertRaises(SaltInvocationError, aliases.has_target, "foo", "")

    def test_has_target_mult(self):
        """
        Tests return of multiple targets to one alias
        """
        with patch(
            "salt.modules.aliases.__parse_aliases",
            MagicMock(return_value=self.mock_alias_mult),
        ):
            ret = aliases.has_target("hello", "world@earth.com, earth@world.com")
            self.assertTrue(ret)

    def test_has_target_mult_differs(self):
        """
        Tests return of multiple targets to one alias in opposite order
        """
        with patch(
            "salt.modules.aliases.__parse_aliases",
            MagicMock(return_value=self.mock_alias_mult),
        ):
            ret = aliases.has_target("hello", "earth@world.com, world@earth.com")
            self.assertFalse(ret)

    def test_has_target_list_mult(self):
        """
        Tests return of target as same list to know alias
        """
        with patch(
            "salt.modules.aliases.__parse_aliases",
            MagicMock(return_value=self.mock_alias_mult),
        ):
            ret = aliases.has_target("hello", ["world@earth.com", "earth@world.com"])
            self.assertTrue(ret)

    def test_has_target_list_mult_differs(self):
        """
        Tests return of target as differing list to known alias
        """
        with patch(
            "salt.modules.aliases.__parse_aliases",
            MagicMock(return_value=self.mock_alias_mult),
        ):
            ret = aliases.has_target("hello", ["world@earth.com", "mars@space.com"])
            self.assertFalse(ret)

    def test_set_target_equal(self):
        """
        Tests return when target is already present
        """
        with patch(
            "salt.modules.aliases.get_target", MagicMock(return_value="bar@example.com")
        ):
            alias = "foo"
            target = "bar@example.com"
            ret = aliases.set_target(alias, target)
            self.assertTrue(ret)

    def test_set_target_empty_alias(self):
        """
        Tests return of empty alias
        """
        self.assertRaises(SaltInvocationError, aliases.set_target, "", "foo")

    def test_set_target_empty_target(self):
        """
        Tests return of known alias and empty target
        """
        self.assertRaises(SaltInvocationError, aliases.set_target, "foo", "")

    def test_rm_alias_absent(self):
        """
        Tests return when alias is not present
        """
        with patch("salt.modules.aliases.get_target", MagicMock(return_value="")):
            ret = aliases.rm_alias("foo")
            self.assertTrue(ret)
