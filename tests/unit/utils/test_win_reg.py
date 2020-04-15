# -*- coding: utf-8 -*-

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.utils.stringutils
import salt.utils.win_reg as win_reg
from salt.exceptions import CommandExecutionError
from salt.ext import six

# Import Salt Testing Libs
from tests.support.helpers import destructiveTest, generate_random_name
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase, skipIf

try:
    import win32api

    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

UNICODE_KEY = "Unicode Key \N{TRADE MARK SIGN}"
UNICODE_VALUE = (
    "Unicode Value " "\N{COPYRIGHT SIGN},\N{TRADE MARK SIGN},\N{REGISTERED SIGN}"
)
FAKE_KEY = "\\".join(["SOFTWARE", generate_random_name("SaltTesting-")])


@skipIf(not HAS_WIN32, "Tests require win32 libraries")
class WinFunctionsTestCase(TestCase):
    """
    Test cases for salt.utils.win_reg
    """

    def test_broadcast_change_success(self):
        """
        Tests the broadcast_change function
        """
        with patch("win32gui.SendMessageTimeout", return_value=("", 0)):
            self.assertTrue(win_reg.broadcast_change())

    def test_broadcast_change_fail(self):
        """
        Tests the broadcast_change function failure
        """
        with patch("win32gui.SendMessageTimeout", return_value=("", 1)):
            self.assertFalse(win_reg.broadcast_change())

    def test_key_exists_existing(self):
        """
        Tests the key_exists function using a well known registry key
        """
        self.assertTrue(win_reg.key_exists(hive="HKLM", key="SOFTWARE\\Microsoft"))

    def test_key_exists_non_existing(self):
        """
        Tests the key_exists function using a non existing registry key
        """
        self.assertFalse(win_reg.key_exists(hive="HKLM", key=FAKE_KEY))

    def test_key_exists_invalid_hive(self):
        """
        Tests the key_exists function using an invalid hive
        """
        self.assertRaises(
            CommandExecutionError,
            win_reg.key_exists,
            hive="BADHIVE",
            key="SOFTWARE\\Microsoft",
        )

    def test_key_exists_unknown_key_error(self):
        """
        Tests the key_exists function with an unknown key error
        """
        mock_error = MagicMock(
            side_effect=win32api.error(123, "RegOpenKeyEx", "Unknown error")
        )
        with patch("salt.utils.win_reg.win32api.RegOpenKeyEx", mock_error):
            self.assertRaises(
                win32api.error,
                win_reg.key_exists,
                hive="HKLM",
                key="SOFTWARE\\Microsoft",
            )

    def test_value_exists_existing(self):
        """
        Tests the value_exists function using a well known registry key
        """
        self.assertTrue(
            win_reg.value_exists(
                hive="HKLM",
                key="SOFTWARE\\Microsoft\\Windows\\CurrentVersion",
                vname="CommonFilesDir",
            )
        )

    def test_value_exists_non_existing(self):
        """
        Tests the value_exists function using a non existing registry key
        """
        self.assertFalse(
            win_reg.value_exists(
                hive="HKLM",
                key="SOFTWARE\\Microsoft\\Windows\\CurrentVersion",
                vname="NonExistingValueName",
            )
        )

    def test_value_exists_invalid_hive(self):
        """
        Tests the value_exists function using an invalid hive
        """
        self.assertRaises(
            CommandExecutionError,
            win_reg.value_exists,
            hive="BADHIVE",
            key="SOFTWARE\\Microsoft\\Windows\\CurrentVersion",
            vname="CommonFilesDir",
        )

    def test_value_exists_key_not_exist(self):
        """
        Tests the value_exists function when the key does not exist
        """
        mock_error = MagicMock(
            side_effect=win32api.error(2, "RegOpenKeyEx", "Unknown error")
        )
        with patch("salt.utils.win_reg.win32api.RegOpenKeyEx", mock_error):
            self.assertFalse(
                win_reg.value_exists(
                    hive="HKLM",
                    key="SOFTWARE\\Microsoft\\Windows\\CurrentVersion",
                    vname="CommonFilesDir",
                )
            )

    def test_value_exists_unknown_key_error(self):
        """
        Tests the value_exists function with an unknown error when opening the
        key
        """
        mock_error = MagicMock(
            side_effect=win32api.error(123, "RegOpenKeyEx", "Unknown error")
        )
        with patch("salt.utils.win_reg.win32api.RegOpenKeyEx", mock_error):
            self.assertRaises(
                win32api.error,
                win_reg.value_exists,
                hive="HKLM",
                key="SOFTWARE\\Microsoft\\Windows\\CurrentVersion",
                vname="CommonFilesDir",
            )

    def test_value_exists_empty_default_value(self):
        """
        Tests the value_exists function when querying the default value
        """
        mock_error = MagicMock(
            side_effect=win32api.error(2, "RegQueryValueEx", "Empty Value")
        )
        with patch("salt.utils.win_reg.win32api.RegQueryValueEx", mock_error):
            self.assertTrue(
                win_reg.value_exists(
                    hive="HKLM",
                    key="SOFTWARE\\Microsoft\\Windows\\CurrentVersion",
                    vname=None,
                )
            )

    def test_value_exists_no_vname(self):
        """
        Tests the value_exists function when the vname does not exist
        """
        mock_error = MagicMock(
            side_effect=win32api.error(123, "RegQueryValueEx", "Empty Value")
        )
        with patch("salt.utils.win_reg.win32api.RegQueryValueEx", mock_error):
            self.assertFalse(
                win_reg.value_exists(
                    hive="HKLM",
                    key="SOFTWARE\\Microsoft\\Windows\\CurrentVersion",
                    vname="NonExistingValuePair",
                )
            )

    def test_list_keys_existing(self):
        """
        Test the list_keys function using a well known registry key
        """
        self.assertIn("Microsoft", win_reg.list_keys(hive="HKLM", key="SOFTWARE"))

    def test_list_keys_non_existing(self):
        """
        Test the list_keys function using a non existing registry key
        """
        expected = (False, "Cannot find key: HKLM\\{0}".format(FAKE_KEY))
        self.assertEqual(win_reg.list_keys(hive="HKLM", key=FAKE_KEY), expected)

    def test_list_keys_invalid_hive(self):
        """
        Test the list_keys function when passing an invalid hive
        """
        self.assertRaises(
            CommandExecutionError,
            win_reg.list_keys,
            hive="BADHIVE",
            key="SOFTWARE\\Microsoft",
        )

    def test_list_keys_unknown_key_error(self):
        """
        Tests the list_keys function with an unknown key error
        """
        mock_error = MagicMock(
            side_effect=win32api.error(123, "RegOpenKeyEx", "Unknown error")
        )
        with patch("salt.utils.win_reg.win32api.RegOpenKeyEx", mock_error):
            self.assertRaises(
                win32api.error,
                win_reg.list_keys,
                hive="HKLM",
                key="SOFTWARE\\Microsoft",
            )

    def test_list_values_existing(self):
        """
        Test the list_values function using a well known registry key
        """
        values = win_reg.list_values(
            hive="HKLM", key="SOFTWARE\\Microsoft\\Windows\\CurrentVersion"
        )
        keys = []
        for value in values:
            keys.append(value["vname"])
        self.assertIn("ProgramFilesDir", keys)

    def test_list_values_non_existing(self):
        """
        Test the list_values function using a non existing registry key
        """
        expected = (False, "Cannot find key: HKLM\\{0}".format(FAKE_KEY))
        self.assertEqual(win_reg.list_values(hive="HKLM", key=FAKE_KEY), expected)

    def test_list_values_invalid_hive(self):
        """
        Test the list_values function when passing an invalid hive
        """
        self.assertRaises(
            CommandExecutionError,
            win_reg.list_values,
            hive="BADHIVE",
            key="SOFTWARE\\Microsoft",
        )

    def test_list_values_unknown_key_error(self):
        """
        Tests the list_values function with an unknown key error
        """
        mock_error = MagicMock(
            side_effect=win32api.error(123, "RegOpenKeyEx", "Unknown error")
        )
        with patch("salt.utils.win_reg.win32api.RegOpenKeyEx", mock_error):
            self.assertRaises(
                win32api.error,
                win_reg.list_values,
                hive="HKLM",
                key="SOFTWARE\\Microsoft",
            )

    def test_read_value_existing(self):
        """
        Test the read_value function using a well known registry value
        """
        ret = win_reg.read_value(
            hive="HKLM",
            key="SOFTWARE\\Microsoft\\Windows\\CurrentVersion",
            vname="ProgramFilesPath",
        )
        self.assertEqual(ret["vdata"], "%ProgramFiles%")

    def test_read_value_default(self):
        """
        Test the read_value function reading the default value using a well
        known registry key
        """
        ret = win_reg.read_value(
            hive="HKLM", key="SOFTWARE\\Microsoft\\Windows\\CurrentVersion"
        )
        self.assertEqual(ret["vdata"], "(value not set)")

    def test_read_value_non_existing(self):
        """
        Test the read_value function using a non existing value pair
        """
        expected = {
            "comment": "Cannot find fake_name in HKLM\\SOFTWARE\\Microsoft\\"
            "Windows\\CurrentVersion",
            "vdata": None,
            "vname": "fake_name",
            "success": False,
            "hive": "HKLM",
            "key": "SOFTWARE\\Microsoft\\Windows\\CurrentVersion",
        }
        self.assertDictEqual(
            win_reg.read_value(
                hive="HKLM",
                key="SOFTWARE\\Microsoft\\Windows\\CurrentVersion",
                vname="fake_name",
            ),
            expected,
        )

    def test_read_value_non_existing_key(self):
        """
        Test the read_value function using a non existing registry key
        """
        expected = {
            "comment": "Cannot find key: HKLM\\{0}".format(FAKE_KEY),
            "vdata": None,
            "vname": "fake_name",
            "success": False,
            "hive": "HKLM",
            "key": FAKE_KEY,
        }
        self.assertDictEqual(
            win_reg.read_value(hive="HKLM", key=FAKE_KEY, vname="fake_name"), expected
        )

    def test_read_value_invalid_hive(self):
        """
        Test the read_value function when passing an invalid hive
        """
        self.assertRaises(
            CommandExecutionError,
            win_reg.read_value,
            hive="BADHIVE",
            key="SOFTWARE\\Microsoft",
            vname="ProgramFilesPath",
        )

    def test_read_value_unknown_key_error(self):
        """
        Tests the read_value function with an unknown key error
        """
        mock_error = MagicMock(
            side_effect=win32api.error(123, "RegOpenKeyEx", "Unknown error")
        )
        with patch("salt.utils.win_reg.win32api.RegOpenKeyEx", mock_error):
            self.assertRaises(
                win32api.error,
                win_reg.read_value,
                hive="HKLM",
                key="SOFTWARE\\Microsoft\\Windows\\CurrentVersion",
                vname="ProgramFilesPath",
            )

    def test_read_value_unknown_value_error(self):
        """
        Tests the read_value function with an unknown value error
        """
        mock_error = MagicMock(
            side_effect=win32api.error(123, "RegQueryValueEx", "Unknown error")
        )
        with patch("salt.utils.win_reg.win32api.RegQueryValueEx", mock_error):
            self.assertRaises(
                win32api.error,
                win_reg.read_value,
                hive="HKLM",
                key="SOFTWARE\\Microsoft\\Windows\\CurrentVersion",
                vname="ProgramFilesPath",
            )

    @destructiveTest
    def test_read_value_multi_sz_empty_list(self):
        """
        An empty REG_MULTI_SZ value should return an empty list, not None
        """
        try:
            self.assertTrue(
                win_reg.set_value(
                    hive="HKLM",
                    key=FAKE_KEY,
                    vname="empty_list",
                    vdata=[],
                    vtype="REG_MULTI_SZ",
                )
            )
            expected = {
                "hive": "HKLM",
                "key": FAKE_KEY,
                "success": True,
                "vdata": [],
                "vname": "empty_list",
                "vtype": "REG_MULTI_SZ",
            }
            self.assertEqual(
                win_reg.read_value(hive="HKLM", key=FAKE_KEY, vname="empty_list",),
                expected,
            )
        finally:
            win_reg.delete_key_recursive(hive="HKLM", key=FAKE_KEY)

    @destructiveTest
    def test_set_value(self):
        """
        Test the set_value function
        """
        try:
            self.assertTrue(
                win_reg.set_value(
                    hive="HKLM", key=FAKE_KEY, vname="fake_name", vdata="fake_data"
                )
            )
            expected = {
                "hive": "HKLM",
                "key": FAKE_KEY,
                "success": True,
                "vdata": "fake_data",
                "vname": "fake_name",
                "vtype": "REG_SZ",
            }
            self.assertEqual(
                win_reg.read_value(hive="HKLM", key=FAKE_KEY, vname="fake_name"),
                expected,
            )
        finally:
            win_reg.delete_key_recursive(hive="HKLM", key=FAKE_KEY)

    @destructiveTest
    def test_set_value_default(self):
        """
        Test the set_value function on the default value
        """
        try:
            self.assertTrue(
                win_reg.set_value(hive="HKLM", key=FAKE_KEY, vdata="fake_default_data")
            )
            expected = {
                "hive": "HKLM",
                "key": FAKE_KEY,
                "success": True,
                "vdata": "fake_default_data",
                "vname": "(Default)",
                "vtype": "REG_SZ",
            }
            self.assertEqual(win_reg.read_value(hive="HKLM", key=FAKE_KEY), expected)
        finally:
            win_reg.delete_key_recursive(hive="HKLM", key=FAKE_KEY)

    @destructiveTest
    def test_set_value_unicode_key(self):
        """
        Test the set_value function on a unicode key
        """
        try:
            self.assertTrue(
                win_reg.set_value(
                    hive="HKLM",
                    key="\\".join([FAKE_KEY, UNICODE_KEY]),
                    vname="fake_name",
                    vdata="fake_value",
                )
            )
            expected = {
                "hive": "HKLM",
                "key": "\\".join([FAKE_KEY, UNICODE_KEY]),
                "success": True,
                "vdata": "fake_value",
                "vname": "fake_name",
                "vtype": "REG_SZ",
            }
            self.assertEqual(
                win_reg.read_value(
                    hive="HKLM",
                    key="\\".join([FAKE_KEY, UNICODE_KEY]),
                    vname="fake_name",
                ),
                expected,
            )
        finally:
            win_reg.delete_key_recursive(hive="HKLM", key=FAKE_KEY)

    @destructiveTest
    def test_set_value_unicode_value(self):
        """
        Test the set_value function on a unicode value
        """
        try:
            self.assertTrue(
                win_reg.set_value(
                    hive="HKLM", key=FAKE_KEY, vname="fake_unicode", vdata=UNICODE_VALUE
                )
            )
            expected = {
                "hive": "HKLM",
                "key": FAKE_KEY,
                "success": True,
                "vdata": UNICODE_VALUE,
                "vname": "fake_unicode",
                "vtype": "REG_SZ",
            }
            self.assertEqual(
                win_reg.read_value(hive="HKLM", key=FAKE_KEY, vname="fake_unicode"),
                expected,
            )
        finally:
            win_reg.delete_key_recursive(hive="HKLM", key=FAKE_KEY)

    @destructiveTest
    def test_set_value_reg_dword(self):
        """
        Test the set_value function on a REG_DWORD value
        """
        try:
            self.assertTrue(
                win_reg.set_value(
                    hive="HKLM",
                    key=FAKE_KEY,
                    vname="dword_value",
                    vdata=123,
                    vtype="REG_DWORD",
                )
            )
            expected = {
                "hive": "HKLM",
                "key": FAKE_KEY,
                "success": True,
                "vdata": 123,
                "vname": "dword_value",
                "vtype": "REG_DWORD",
            }
            self.assertEqual(
                win_reg.read_value(hive="HKLM", key=FAKE_KEY, vname="dword_value"),
                expected,
            )
        finally:
            win_reg.delete_key_recursive(hive="HKLM", key=FAKE_KEY)

    @destructiveTest
    def test_set_value_reg_qword(self):
        """
        Test the set_value function on a REG_QWORD value
        """
        try:
            self.assertTrue(
                win_reg.set_value(
                    hive="HKLM",
                    key=FAKE_KEY,
                    vname="qword_value",
                    vdata=123,
                    vtype="REG_QWORD",
                )
            )
            expected = {
                "hive": "HKLM",
                "key": FAKE_KEY,
                "success": True,
                "vdata": 123,
                "vname": "qword_value",
                "vtype": "REG_QWORD",
            }
            self.assertEqual(
                win_reg.read_value(hive="HKLM", key=FAKE_KEY, vname="qword_value"),
                expected,
            )
        finally:
            win_reg.delete_key_recursive(hive="HKLM", key=FAKE_KEY)

    def test_set_value_invalid_hive(self):
        """
        Test the set_value function when passing an invalid hive
        """
        self.assertRaises(
            CommandExecutionError,
            win_reg.set_value,
            hive="BADHIVE",
            key=FAKE_KEY,
            vname="fake_name",
            vdata="fake_data",
        )

    def test_set_value_open_create_failure(self):
        """
        Test the set_value function when there is a problem opening/creating
        the key
        """
        mock_error = MagicMock(
            side_effect=win32api.error(123, "RegCreateKeyEx", "Unknown error")
        )
        with patch("salt.utils.win_reg.win32api.RegCreateKeyEx", mock_error):
            self.assertFalse(
                win_reg.set_value(
                    hive="HKLM", key=FAKE_KEY, vname="fake_name", vdata="fake_data"
                )
            )

    def test_set_value_type_error(self):
        """
        Test the set_value function when the wrong type of data is passed
        """
        mock_error = MagicMock(side_effect=TypeError("Mocked TypeError"))
        with patch("salt.utils.win_reg.win32api.RegSetValueEx", mock_error):
            self.assertFalse(
                win_reg.set_value(
                    hive="HKLM", key=FAKE_KEY, vname="fake_name", vdata="fake_data"
                )
            )

    def test_set_value_system_error(self):
        """
        Test the set_value function when a SystemError occurs while setting the
        value
        """
        mock_error = MagicMock(side_effect=SystemError("Mocked SystemError"))
        with patch("salt.utils.win_reg.win32api.RegSetValueEx", mock_error):
            self.assertFalse(
                win_reg.set_value(
                    hive="HKLM", key=FAKE_KEY, vname="fake_name", vdata="fake_data"
                )
            )

    def test_set_value_value_error(self):
        """
        Test the set_value function when a ValueError occurs while setting the
        value
        """
        mock_error = MagicMock(side_effect=ValueError("Mocked ValueError"))
        with patch("salt.utils.win_reg.win32api.RegSetValueEx", mock_error):
            self.assertFalse(
                win_reg.set_value(
                    hive="HKLM", key=FAKE_KEY, vname="fake_name", vdata="fake_data"
                )
            )

    def test_cast_vdata_reg_binary(self):
        """
        Test the cast_vdata function with REG_BINARY
        Should always return binary data
        """
        vdata = salt.utils.stringutils.to_bytes("test data")
        result = win_reg.cast_vdata(vdata=vdata, vtype="REG_BINARY")
        self.assertTrue(isinstance(result, six.binary_type))

        vdata = salt.utils.stringutils.to_str("test data")
        result = win_reg.cast_vdata(vdata=vdata, vtype="REG_BINARY")
        self.assertTrue(isinstance(result, six.binary_type))

        vdata = salt.utils.stringutils.to_unicode("test data")
        result = win_reg.cast_vdata(vdata=vdata, vtype="REG_BINARY")
        self.assertTrue(isinstance(result, six.binary_type))

    def test_cast_vdata_reg_dword(self):
        """
        Test the cast_vdata function with REG_DWORD
        Should always return integer
        """
        vdata = 1
        expected = 1
        result = win_reg.cast_vdata(vdata=vdata, vtype="REG_DWORD")
        self.assertEqual(result, expected)

        vdata = "1"
        result = win_reg.cast_vdata(vdata=vdata, vtype="REG_DWORD")
        self.assertEqual(result, expected)

        vdata = "0000001"
        result = win_reg.cast_vdata(vdata=vdata, vtype="REG_DWORD")
        self.assertEqual(result, expected)

    def test_cast_vdata_reg_expand_sz(self):
        """
        Test the cast_vdata function with REG_EXPAND_SZ
        Should always return unicode
        """
        vdata = salt.utils.stringutils.to_str("test data")
        result = win_reg.cast_vdata(vdata=vdata, vtype="REG_EXPAND_SZ")
        self.assertTrue(isinstance(result, six.text_type))

        vdata = salt.utils.stringutils.to_bytes("test data")
        result = win_reg.cast_vdata(vdata=vdata, vtype="REG_EXPAND_SZ")
        self.assertTrue(isinstance(result, six.text_type))

    def test_cast_vdata_reg_multi_sz(self):
        """
        Test the cast_vdata function with REG_MULTI_SZ
        Should always return a list of unicode strings
        """
        vdata = [
            salt.utils.stringutils.to_str("test string"),
            salt.utils.stringutils.to_bytes("test bytes"),
        ]
        result = win_reg.cast_vdata(vdata=vdata, vtype="REG_MULTI_SZ")
        self.assertTrue(isinstance(result, list))
        for item in result:
            self.assertTrue(isinstance(item, six.text_type))

    def test_cast_vdata_reg_qword(self):
        """
        Test the cast_vdata function with REG_QWORD
        Should always return a long integer
        `int` is `long` is default on Py3
        """
        vdata = 1
        result = win_reg.cast_vdata(vdata=vdata, vtype="REG_QWORD")
        if six.PY2:
            # pylint: disable=incompatible-py3-code,undefined-variable
            self.assertTrue(isinstance(result, long))
            # pylint: enable=incompatible-py3-code,undefined-variable
        else:
            self.assertTrue(isinstance(result, int))

        vdata = "1"
        result = win_reg.cast_vdata(vdata=vdata, vtype="REG_QWORD")
        if six.PY2:
            # pylint: disable=incompatible-py3-code,undefined-variable
            self.assertTrue(isinstance(result, long))
            # pylint: enable=incompatible-py3-code,undefined-variable
        else:
            self.assertTrue(isinstance(result, int))

    def test_cast_vdata_reg_sz(self):
        """
        Test the cast_vdata function with REG_SZ
        Should always return unicode
        """
        vdata = salt.utils.stringutils.to_str("test data")
        result = win_reg.cast_vdata(vdata=vdata, vtype="REG_SZ")
        self.assertTrue(isinstance(result, six.text_type))

        vdata = salt.utils.stringutils.to_bytes("test data")
        result = win_reg.cast_vdata(vdata=vdata, vtype="REG_SZ")
        self.assertTrue(isinstance(result, six.text_type))

    @destructiveTest
    def test_delete_value(self):
        """
        Test the delete_value function
        """
        try:
            self.assertTrue(
                win_reg.set_value(
                    hive="HKLM", key=FAKE_KEY, vname="fake_name", vdata="fake_data"
                )
            )
            self.assertTrue(
                win_reg.delete_value(hive="HKLM", key=FAKE_KEY, vname="fake_name")
            )
        finally:
            win_reg.delete_key_recursive(hive="HKLM", key=FAKE_KEY)

    def test_delete_value_non_existing(self):
        """
        Test the delete_value function on non existing value
        """
        mock_error = MagicMock(
            side_effect=win32api.error(2, "RegOpenKeyEx", "Unknown error")
        )
        with patch("salt.utils.win_reg.win32api.RegOpenKeyEx", mock_error):
            self.assertIsNone(
                win_reg.delete_value(hive="HKLM", key=FAKE_KEY, vname="fake_name")
            )

    def test_delete_value_invalid_hive(self):
        """
        Test the delete_value function when passing an invalid hive
        """
        self.assertRaises(
            CommandExecutionError,
            win_reg.delete_value,
            hive="BADHIVE",
            key=FAKE_KEY,
            vname="fake_name",
        )

    def test_delete_value_unknown_error(self):
        """
        Test the delete_value function when there is a problem opening the key
        """
        mock_error = MagicMock(
            side_effect=win32api.error(123, "RegOpenKeyEx", "Unknown error")
        )
        with patch("salt.utils.win_reg.win32api.RegOpenKeyEx", mock_error):
            self.assertRaises(
                win32api.error,
                win_reg.delete_value,
                hive="HKLM",
                key=FAKE_KEY,
                vname="fake_name",
            )

    @destructiveTest
    def test_delete_value_unicode(self):
        """
        Test the delete_value function on a unicode value
        """
        try:
            self.assertTrue(
                win_reg.set_value(
                    hive="HKLM", key=FAKE_KEY, vname="fake_unicode", vdata=UNICODE_VALUE
                )
            )
            self.assertTrue(
                win_reg.delete_value(hive="HKLM", key=FAKE_KEY, vname="fake_unicode")
            )
        finally:
            win_reg.delete_key_recursive(hive="HKLM", key=FAKE_KEY)

    @destructiveTest
    def test_delete_value_unicode_vname(self):
        """
        Test the delete_value function on a unicode vname
        """
        try:
            self.assertTrue(
                win_reg.set_value(
                    hive="HKLM", key=FAKE_KEY, vname=UNICODE_KEY, vdata="junk data"
                )
            )
            self.assertTrue(
                win_reg.delete_value(hive="HKLM", key=FAKE_KEY, vname=UNICODE_KEY)
            )
        finally:
            win_reg.delete_key_recursive(hive="HKLM", key=FAKE_KEY)

    @destructiveTest
    def test_delete_value_unicode_key(self):
        """
        Test the delete_value function on a unicode key
        """
        try:
            self.assertTrue(
                win_reg.set_value(
                    hive="HKLM",
                    key="\\".join([FAKE_KEY, UNICODE_KEY]),
                    vname="fake_name",
                    vdata="junk data",
                )
            )
            self.assertTrue(
                win_reg.delete_value(
                    hive="HKLM",
                    key="\\".join([FAKE_KEY, UNICODE_KEY]),
                    vname="fake_name",
                )
            )
        finally:
            win_reg.delete_key_recursive(hive="HKLM", key=FAKE_KEY)

    def test_delete_key_recursive_invalid_hive(self):
        """
        Test the delete_key_recursive function when passing an invalid hive
        """
        self.assertRaises(
            CommandExecutionError,
            win_reg.delete_key_recursive,
            hive="BADHIVE",
            key=FAKE_KEY,
        )

    def test_delete_key_recursive_key_not_found(self):
        """
        Test the delete_key_recursive function when the passed key to delete is
        not found.
        """
        self.assertFalse(win_reg.key_exists(hive="HKLM", key=FAKE_KEY))
        self.assertFalse(win_reg.delete_key_recursive(hive="HKLM", key=FAKE_KEY))

    def test_delete_key_recursive_too_close(self):
        """
        Test the delete_key_recursive function when the passed key to delete is
        too close to root, such as
        """
        mock_true = MagicMock(return_value=True)
        with patch("salt.utils.win_reg.key_exists", mock_true):
            self.assertFalse(win_reg.delete_key_recursive(hive="HKLM", key="FAKE_KEY"))

    @destructiveTest
    def test_delete_key_recursive(self):
        """
        Test the delete_key_recursive function
        """
        try:
            self.assertTrue(
                win_reg.set_value(
                    hive="HKLM", key=FAKE_KEY, vname="fake_name", vdata="fake_value"
                )
            )
            expected = {"Deleted": ["\\".join(["HKLM", FAKE_KEY])], "Failed": []}
            self.assertDictEqual(
                win_reg.delete_key_recursive(hive="HKLM", key=FAKE_KEY), expected
            )
        finally:
            win_reg.delete_key_recursive(hive="HKLM", key=FAKE_KEY)

    @destructiveTest
    def test_delete_key_recursive_failed_to_open_key(self):
        """
        Test the delete_key_recursive function on failure to open the key
        """
        try:
            self.assertTrue(
                win_reg.set_value(
                    hive="HKLM", key=FAKE_KEY, vname="fake_name", vdata="fake_value"
                )
            )
            expected = {
                "Deleted": [],
                "Failed": ["\\".join(["HKLM", FAKE_KEY]) + " Failed to connect to key"],
            }
            mock_true = MagicMock(return_value=True)
            mock_error = MagicMock(
                side_effect=[
                    1,
                    win32api.error(3, "RegOpenKeyEx", "Failed to connect to key"),
                ]
            )
            with patch("salt.utils.win_reg.key_exists", mock_true), patch(
                "salt.utils.win_reg.win32api.RegOpenKeyEx", mock_error
            ):
                self.assertDictEqual(
                    win_reg.delete_key_recursive(hive="HKLM", key=FAKE_KEY), expected
                )
        finally:
            win_reg.delete_key_recursive(hive="HKLM", key=FAKE_KEY)

    @destructiveTest
    def test_delete_key_recursive_failed_to_delete(self):
        """
        Test the delete_key_recursive function on failure to delete a key
        """
        try:
            self.assertTrue(
                win_reg.set_value(
                    hive="HKLM", key=FAKE_KEY, vname="fake_name", vdata="fake_value"
                )
            )
            expected = {
                "Deleted": [],
                "Failed": ["\\".join(["HKLM", FAKE_KEY]) + " Unknown error"],
            }
            # pylint: disable=undefined-variable
            mock_error = MagicMock(side_effect=WindowsError("Unknown error"))
            # pylint: enable=undefined-variable
            with patch("salt.utils.win_reg.win32api.RegDeleteKey", mock_error):
                self.assertDictEqual(
                    win_reg.delete_key_recursive(hive="HKLM", key=FAKE_KEY), expected
                )
        finally:
            win_reg.delete_key_recursive(hive="HKLM", key=FAKE_KEY)

    @destructiveTest
    def test_delete_key_recursive_unicode(self):
        """
        Test the delete_key_recursive function on value within a unicode key
        """
        try:
            self.assertTrue(
                win_reg.set_value(
                    hive="HKLM",
                    key="\\".join([FAKE_KEY, UNICODE_KEY]),
                    vname="fake_name",
                    vdata="fake_value",
                )
            )
            expected = {
                "Deleted": ["\\".join(["HKLM", FAKE_KEY, UNICODE_KEY])],
                "Failed": [],
            }
            self.assertDictEqual(
                win_reg.delete_key_recursive(
                    hive="HKLM", key="\\".join([FAKE_KEY, UNICODE_KEY])
                ),
                expected,
            )
        finally:
            win_reg.delete_key_recursive(hive="HKLM", key=FAKE_KEY)

    def test__to_unicode_int(self):
        """
        Test the ``_to_unicode`` function when it receives an integer value.
        Should return a unicode value, which is unicode in PY2 and str in PY3.
        """
        if six.PY3:
            self.assertTrue(isinstance(win_reg._to_unicode(1), str))
        else:
            # fmt: off
            self.assertTrue(
                isinstance(
                    win_reg._to_unicode(1),
                    unicode,  # pylint: disable=incompatible-py3-code,undefined-variable
                )
            )
            # fmt: on
