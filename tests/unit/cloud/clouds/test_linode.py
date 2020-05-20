# -*- coding: utf-8 -*-
"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""

# Import Salt Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
from salt.cloud.clouds import linode

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase


class LinodeTestCase(TestCase, LoaderModuleMockMixin):
    """
    Unit TestCase for the salt.cloud.clouds.linode module.
    """

    def setup_loader_modules(self):
        return {linode: {}}

    # _validate_name tests

    def test_validate_name_first_character_invalid(self):
        """
        Tests when name starts with an invalid character.
        """
        # Test when name begins with a hyphen
        self.assertFalse(linode._validate_name("-foo"))

        # Test when name begins with an underscore
        self.assertFalse(linode._validate_name("_foo"))

    def test_validate_name_last_character_invalid(self):
        """
        Tests when name ends with an invalid character.
        """
        # Test when name ends with a hyphen
        self.assertFalse(linode._validate_name("foo-"))

        # Test when name ends with an underscore
        self.assertFalse(linode._validate_name("foo_"))

    def test_validate_name_too_short(self):
        """
        Tests when name has less than three letters.
        """
        # Test when name is an empty string
        self.assertFalse(linode._validate_name(""))

        # Test when name is two letters long
        self.assertFalse(linode._validate_name("ab"))

        # Test when name is three letters long (valid)
        self.assertTrue(linode._validate_name("abc"))

    def test_validate_name_too_long(self):
        """
        Tests when name has more than 48 letters.
        """
        long_name = "1111-2222-3333-4444-5555-6666-7777-8888-9999-111"
        # Test when name is 48 letters long (valid)
        self.assertEqual(len(long_name), 48)
        self.assertTrue(linode._validate_name(long_name))

        # Test when name is more than 48 letters long
        long_name += "1"
        self.assertEqual(len(long_name), 49)
        self.assertFalse(linode._validate_name(long_name))

    def test_validate_name_invalid_characters(self):
        """
        Tests when name contains invalid characters.
        """
        # Test when name contains an invalid character
        self.assertFalse(linode._validate_name("foo;bar"))

        # Test when name contains non-ascii letters
        self.assertFalse(linode._validate_name("fooàààààbar"))

        # Test when name contains spaces
        self.assertFalse(linode._validate_name("foo bar"))

    def test_validate_name_valid_characters(self):
        """
        Tests when name contains valid characters.
        """
        # Test when name contains letters and numbers
        self.assertTrue(linode._validate_name("foo123bar"))

        # Test when name contains hyphens
        self.assertTrue(linode._validate_name("foo-bar"))

        # Test when name contains underscores
        self.assertTrue(linode._validate_name("foo_bar"))

        # Test when name start and end with numbers
        self.assertTrue(linode._validate_name("1foo"))
        self.assertTrue(linode._validate_name("foo0"))
