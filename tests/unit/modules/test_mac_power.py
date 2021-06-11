"""
mac_power tests
"""

import salt.modules.mac_power as mac_power
from salt.exceptions import SaltInvocationError
from tests.support.unit import TestCase


class MacPowerTestCase(TestCase):
    """
    test mac_power execution module
    """

    def test_validate_sleep_valid_number(self):
        """
        test _validate_sleep function with valid number
        """
        self.assertEqual(mac_power._validate_sleep(179), 179)

    def test_validate_sleep_invalid_number(self):
        """
        test _validate_sleep function with invalid number
        """
        self.assertRaises(SaltInvocationError, mac_power._validate_sleep, 181)

    def test_validate_sleep_valid_string(self):
        """
        test _validate_sleep function with valid string
        """
        self.assertEqual(mac_power._validate_sleep("never"), "Never")
        self.assertEqual(mac_power._validate_sleep("off"), "Never")

    def test_validate_sleep_invalid_string(self):
        """
        test _validate_sleep function with invalid string
        """
        self.assertRaises(SaltInvocationError, mac_power._validate_sleep, "bob")

    def test_validate_sleep_bool_true(self):
        """
        test _validate_sleep function with True
        """
        self.assertRaises(SaltInvocationError, mac_power._validate_sleep, True)

    def test_validate_sleep_bool_false(self):
        """
        test _validate_sleep function with False
        """
        self.assertEqual(mac_power._validate_sleep(False), "Never")

    def test_validate_sleep_unexpected(self):
        """
        test _validate_sleep function with True
        """
        self.assertRaises(SaltInvocationError, mac_power._validate_sleep, 172.7)
