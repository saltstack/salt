# -*- coding: utf-8 -*-
"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.modules.mod_random as mod_random
import salt.utils.pycrypto
from salt.exceptions import SaltInvocationError

# Import 3rd-party libs
from salt.ext import six

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import patch
from tests.support.unit import TestCase, skipIf


def _test_hashlib():
    try:
        import hashlib
    except ImportError:
        return False

    if six.PY2:
        algorithms_attr_name = "algorithms"
    else:
        algorithms_attr_name = "algorithms_guaranteed"

    if not hasattr(hashlib, algorithms_attr_name):
        return False
    else:
        return True


SUPPORTED_HASHLIB = _test_hashlib()


@skipIf(not SUPPORTED_HASHLIB, "Hashlib does not contain needed functionality")
class ModrandomTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.mod_random
    """

    def setup_loader_modules(self):
        return {mod_random: {}}

    def test_hash(self):
        """
        Test for Encodes a value with the specified encoder.
        """
        self.assertEqual(mod_random.hash("value")[0:4], "ec2c")

        self.assertRaises(SaltInvocationError, mod_random.hash, "value", "algorithm")

    def test_str_encode(self):
        """
        Test for The value to be encoded.
        """
        self.assertRaises(SaltInvocationError, mod_random.str_encode, "None", "abc")

        self.assertRaises(SaltInvocationError, mod_random.str_encode, None)

        if six.PY2:
            self.assertEqual(mod_random.str_encode("A"), "QQ==\n")
        else:
            # We're using the base64 module which does not include the trailing new line
            self.assertEqual(mod_random.str_encode("A"), "QQ==")

    def test_get_str(self):
        """
        Test for Returns a random string of the specified length.
        """
        with patch.object(salt.utils.pycrypto, "secure_password", return_value="A"):
            self.assertEqual(mod_random.get_str(), "A")

    def test_shadow_hash(self):
        """
        Test for Generates a salted hash suitable for /etc/shadow.
        """
        with patch.object(salt.utils.pycrypto, "gen_hash", return_value="A"):
            self.assertEqual(mod_random.shadow_hash(), "A")
