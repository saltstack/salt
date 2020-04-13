# -*- coding: utf-8 -*-
"""
Tests for the Reg State
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import Salt libs
import salt.utils.platform
import salt.utils.win_reg as reg

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.helpers import destructiveTest, generate_random_name
from tests.support.mixins import SaltReturnAssertsMixin
from tests.support.unit import skipIf

log = logging.getLogger(__name__)

__testcontext__ = {}

UNICODE_VALUE_NAME = "Unicode Key \N{TRADE MARK SIGN}"
UNICODE_VALUE = (
    "Unicode Value " "\N{COPYRIGHT SIGN},\N{TRADE MARK SIGN},\N{REGISTERED SIGN}"
)
FAKE_KEY = "SOFTWARE\\{0}".format(generate_random_name("SaltTesting-"))


@destructiveTest
@skipIf(not salt.utils.platform.is_windows(), "Windows Specific Test")
class RegTest(ModuleCase, SaltReturnAssertsMixin):
    """
    Reg state module tests
    These tests are destructive as the modify the registry
    """

    def tearDown(self):
        reg.delete_key_recursive(hive="HKLM", key=FAKE_KEY)
        reg.delete_key_recursive(hive="HKLM", key=FAKE_KEY, use_32bit_registry=True)

    def test_present_reg_sz(self):
        """
        Testing reg.present with REG_SZ
        """
        log.debug("Testing reg.present with REG_SZ")
        # default type is 'REG_SZ'
        # Does the state return the correct data
        ret = self.run_state(
            "reg.present",
            name="HKLM\\{0}".format(FAKE_KEY),
            vname="test_reg_sz",
            vdata="fake string data",
        )
        expected = {
            "reg": {
                "Added": {
                    "Entry": "test_reg_sz",
                    "Inheritance": True,
                    "Key": "HKLM\\{0}".format(FAKE_KEY),
                    "Owner": None,
                    "Perms": {"Deny": None, "Grant": None},
                    "Value": "fake string data",
                }
            }
        }
        self.assertSaltStateChangesEqual(ret, expected)

        # Is the value actually set
        ret = reg.read_value(hive="HKLM", key=FAKE_KEY, vname="test_reg_sz")
        expected = {
            "vtype": "REG_SZ",
            "vname": "test_reg_sz",
            "success": True,
            "hive": "HKLM",
            "vdata": "fake string data",
            "key": FAKE_KEY,
        }
        self.assertEqual(ret, expected)

    def test_present_reg_sz_unicode_value(self):
        """
        Testing reg.present with REG_SZ and a unicode value
        """
        log.debug("Testing reg.present with REG_SZ and a unicode value")
        # default type is 'REG_SZ'
        # Does the state return the correct data
        ret = self.run_state(
            "reg.present",
            name="HKLM\\{0}".format(FAKE_KEY),
            vname="test_reg_sz",
            vdata=UNICODE_VALUE,
        )
        expected = {
            "reg": {
                "Added": {
                    "Entry": "test_reg_sz",
                    "Inheritance": True,
                    "Key": "HKLM\\{0}".format(FAKE_KEY),
                    "Owner": None,
                    "Perms": {"Deny": None, "Grant": None},
                    "Value": UNICODE_VALUE,
                }
            }
        }
        self.assertSaltStateChangesEqual(ret, expected)

        # Is the value actually set
        ret = reg.read_value(hive="HKLM", key=FAKE_KEY, vname="test_reg_sz")
        expected = {
            "vtype": "REG_SZ",
            "vname": "test_reg_sz",
            "success": True,
            "hive": "HKLM",
            "vdata": UNICODE_VALUE,
            "key": FAKE_KEY,
        }
        self.assertEqual(ret, expected)

    def test_present_reg_sz_unicode_default_value(self):
        """
        Testing reg.present with REG_SZ and a unicode default value
        """
        log.debug("Testing reg.present with REG_SZ and a unicode default value")
        # default type is 'REG_SZ'
        # Does the state return the correct data
        ret = self.run_state(
            "reg.present", name="HKLM\\{0}".format(FAKE_KEY), vdata=UNICODE_VALUE
        )
        expected = {
            "reg": {
                "Added": {
                    "Entry": "(Default)",
                    "Inheritance": True,
                    "Key": "HKLM\\{0}".format(FAKE_KEY),
                    "Owner": None,
                    "Perms": {"Deny": None, "Grant": None},
                    "Value": UNICODE_VALUE,
                }
            }
        }
        self.assertSaltStateChangesEqual(ret, expected)

        # Is the value actually set
        ret = reg.read_value(hive="HKLM", key=FAKE_KEY)

        expected = {
            "vtype": "REG_SZ",
            "vname": "(Default)",
            "success": True,
            "hive": "HKLM",
            "vdata": UNICODE_VALUE,
            "key": FAKE_KEY,
        }
        self.assertEqual(ret, expected)

    def test_present_reg_sz_unicode_value_name(self):
        """
        Testing reg.present with REG_SZ and a unicode value name
        """
        log.debug("Testing reg.present with REG_SZ and a unicode value name")
        # default type is 'REG_SZ'
        # Does the state return the correct data
        ret = self.run_state(
            "reg.present",
            name="HKLM\\{0}".format(FAKE_KEY),
            vname=UNICODE_VALUE_NAME,
            vdata="fake string data",
        )
        expected = {
            "reg": {
                "Added": {
                    "Entry": UNICODE_VALUE_NAME,
                    "Inheritance": True,
                    "Key": "HKLM\\{0}".format(FAKE_KEY),
                    "Owner": None,
                    "Perms": {"Deny": None, "Grant": None},
                    "Value": "fake string data",
                }
            }
        }
        self.assertSaltStateChangesEqual(ret, expected)

        # Is the value actually set
        ret = reg.read_value(hive="HKLM", key=FAKE_KEY, vname=UNICODE_VALUE_NAME)

        expected = {
            "vtype": "REG_SZ",
            "vname": UNICODE_VALUE_NAME,
            "success": True,
            "hive": "HKLM",
            "vdata": "fake string data",
            "key": FAKE_KEY,
        }
        self.assertEqual(ret, expected)

    def test_present_reg_binary(self):
        """
        Testing reg.present with REG_BINARY
        """
        test_data = "Salty Test"
        log.debug("Testing reg.present with REG_BINARY")
        # default type is 'REG_SZ'
        # Does the state return the correct data
        ret = self.run_state(
            "reg.present",
            name="HKLM\\{0}".format(FAKE_KEY),
            vname="test_reg_binary",
            vtype="REG_BINARY",
            vdata=test_data,
        )
        expected = {
            "reg": {
                "Added": {
                    "Entry": "test_reg_binary",
                    "Inheritance": True,
                    "Key": "HKLM\\{0}".format(FAKE_KEY),
                    "Owner": None,
                    "Perms": {"Deny": None, "Grant": None},
                    "Value": test_data,
                }
            }
        }
        self.assertSaltStateChangesEqual(ret, expected)

        # Is the value actually set
        ret = reg.read_value(hive="HKLM", key=FAKE_KEY, vname="test_reg_binary")
        expected = {
            "vtype": "REG_BINARY",
            "vname": "test_reg_binary",
            "success": True,
            "hive": "HKLM",
            "vdata": test_data.encode("utf-8"),
            "key": FAKE_KEY,
        }
        self.assertEqual(ret, expected)

    def test_present_reg_multi_sz(self):
        """
        Testing reg.present with REG_MULTI_SZ
        """
        log.debug("Testing reg.present with REG_MULTI_SZ")
        # default type is 'REG_SZ'
        # Does the state return the correct data
        ret = self.run_state(
            "reg.present",
            name="HKLM\\{0}".format(FAKE_KEY),
            vname="test_reg_multi_sz",
            vtype="REG_MULTI_SZ",
            vdata=["item1", "item2"],
        )
        expected = {
            "reg": {
                "Added": {
                    "Entry": "test_reg_multi_sz",
                    "Inheritance": True,
                    "Key": "HKLM\\{0}".format(FAKE_KEY),
                    "Owner": None,
                    "Perms": {"Deny": None, "Grant": None},
                    "Value": ["item1", "item2"],
                }
            }
        }
        self.assertSaltStateChangesEqual(ret, expected)

        # Is the value actually set
        ret = reg.read_value(hive="HKLM", key=FAKE_KEY, vname="test_reg_multi_sz")
        expected = {
            "vtype": "REG_MULTI_SZ",
            "vname": "test_reg_multi_sz",
            "success": True,
            "hive": "HKLM",
            "vdata": ["item1", "item2"],
            "key": FAKE_KEY,
        }
        self.assertEqual(ret, expected)

    def test_present_32_bit(self):
        """
        Testing reg.present with REG_SZ using 32bit registry
        """
        log.debug("Testing reg.present with REG_SZ using 32bit registry")
        # default type is 'REG_SZ'
        # Does the state return the correct data
        ret = self.run_state(
            "reg.present",
            name="HKLM\\{0}".format(FAKE_KEY),
            vname="test_reg_sz",
            vdata="fake string data",
            use_32bit_registry=True,
        )

        expected = {
            "reg": {
                "Added": {
                    "Entry": "test_reg_sz",
                    "Inheritance": True,
                    "Key": "HKLM\\{0}".format(FAKE_KEY),
                    "Owner": None,
                    "Perms": {"Deny": None, "Grant": None},
                    "Value": "fake string data",
                }
            }
        }
        self.assertSaltStateChangesEqual(ret, expected)

        # Is the value actually set
        ret = reg.read_value(
            hive="HKLM", key=FAKE_KEY, vname="test_reg_sz", use_32bit_registry=True
        )
        expected = {
            "vtype": "REG_SZ",
            "vname": "test_reg_sz",
            "success": True,
            "hive": "HKLM",
            "vdata": "fake string data",
            "key": FAKE_KEY,
        }
        self.assertEqual(ret, expected)
