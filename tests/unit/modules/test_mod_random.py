"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>
"""

import salt.modules.mod_random as mod_random
import salt.utils.pycrypto
from salt.exceptions import SaltInvocationError
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import patch
from tests.support.unit import TestCase, skipIf


def _test_hashlib():
    try:
        import hashlib
    except ImportError:
        return False

    if not hasattr(hashlib, "algorithms_guaranteed"):
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

        # We're using the base64 module which does not include the trailing new line
        self.assertEqual(mod_random.str_encode("A"), "QQ==")

    def test_get_str(self):
        """
        Test for Returns a random string of the specified length.
        """
        self.assertEqual(mod_random.get_str(length=1, chars="A"), "A")
        self.assertEqual(len(mod_random.get_str(length=64)), 64)
        ret = mod_random.get_str(
            length=1,
            lowercase=False,
            uppercase=False,
            printable=False,
            whitespace=False,
            punctuation=False,
        )
        self.assertNotRegex(ret, r"^[a-zA-Z]+$", "Found invalid characters")
        self.assertRegex(ret, r"^[0-9]+$", "Not found required characters")

    def test_shadow_hash(self):
        """
        Test for Generates a salted hash suitable for /etc/shadow.
        """
        with patch.object(salt.utils.pycrypto, "gen_hash", return_value="A"):
            self.assertEqual(mod_random.shadow_hash(), "A")
