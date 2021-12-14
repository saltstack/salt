import os
import tempfile

import pytest
import salt.utils.platform
import salt.utils.win_dacl as win_dacl
import salt.utils.win_reg as win_reg
from salt.exceptions import CommandExecutionError
from tests.support.helpers import TstSuiteLoggingHandler, random_string
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import patch
from tests.support.unit import TestCase, skipIf

try:
    import pywintypes
    import win32security

    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

FAKE_KEY = "SOFTWARE\\{}".format(random_string("SaltTesting-", lowercase=False))


@skipIf(not HAS_WIN32, "Requires pywin32")
@skipIf(not salt.utils.platform.is_windows(), "System is not Windows")
class WinDaclTestCase(TestCase):
    """
    Test cases for salt.utils.win_dacl in the registry
    """

    def test_get_sid_string(self):
        """
        Validate getting a pysid object from a name
        """
        sid_obj = win_dacl.get_sid("Administrators")
        self.assertTrue(isinstance(sid_obj, pywintypes.SIDType))
        self.assertEqual(
            win32security.LookupAccountSid(None, sid_obj)[0], "Administrators"
        )

    def test_get_sid_sid_string(self):
        """
        Validate getting a pysid object from a SID string
        """
        sid_obj = win_dacl.get_sid("S-1-5-32-544")
        self.assertTrue(isinstance(sid_obj, pywintypes.SIDType))
        self.assertEqual(
            win32security.LookupAccountSid(None, sid_obj)[0], "Administrators"
        )

    def test_get_sid_string_name(self):
        """
        Validate getting a pysid object from a SID string
        """
        sid_obj = win_dacl.get_sid("Administrators")
        self.assertTrue(isinstance(sid_obj, pywintypes.SIDType))
        self.assertEqual(win_dacl.get_sid_string(sid_obj), "S-1-5-32-544")

    def test_get_sid_string_none(self):
        """
        Validate getting a pysid object from None (NULL SID)
        """
        sid_obj = win_dacl.get_sid(None)
        self.assertTrue(isinstance(sid_obj, pywintypes.SIDType))
        self.assertEqual(win_dacl.get_sid_string(sid_obj), "S-1-0-0")

    def test_get_name_odd_case(self):
        """
        Test get_name by passing a name with inconsistent case characters.
        Should return the name in the correct case
        """
        # Case
        self.assertEqual(win_dacl.get_name("adMiniStrAtorS"), "Administrators")

    def test_get_name_using_sid(self):
        """
        Test get_name passing a SID String. Should return the string name
        """
        # SID String
        self.assertEqual(win_dacl.get_name("S-1-5-32-544"), "Administrators")

    def test_get_name_using_sid_object(self):
        """
        Test get_name passing a SID Object. Should return the string name
        """
        # SID Object
        sid_obj = win_dacl.get_sid("Administrators")
        self.assertTrue(isinstance(sid_obj, pywintypes.SIDType))
        self.assertEqual(win_dacl.get_name(sid_obj), "Administrators")

    def test_get_name_capability_sid(self):
        """
        Test get_name with a compatibility SID. Should return `None` as we want
        to ignore these SIDs
        """
        cap_sid = "S-1-15-3-1024-1065365936-1281604716-3511738428-1654721687-432734479-3232135806-4053264122-3456934681"
        sid_obj = win32security.ConvertStringSidToSid(cap_sid)
        self.assertIsNone(win_dacl.get_name(sid_obj))

    def test_get_name_error(self):
        """
        Test get_name with an un mapped SID, should throw a
        CommandExecutionError
        """
        test_sid = "S-1-2-3-4"
        sid_obj = win32security.ConvertStringSidToSid(test_sid)
        with TstSuiteLoggingHandler() as handler:
            self.assertRaises(CommandExecutionError, win_dacl.get_name, sid_obj)
            expected_message = 'ERROR:Error resolving "PySID:S-1-2-3-4"'
            self.assertIn(expected_message, handler.messages[0])


@skipIf(not HAS_WIN32, "Requires pywin32")
@skipIf(not salt.utils.platform.is_windows(), "System is not Windows")
class WinDaclRegTestCase(TestCase, LoaderModuleMockMixin):
    obj_name = "HKLM\\" + FAKE_KEY
    obj_type = "registry"
    """
    Test cases for salt.utils.win_dacl in the registry
    """

    def setup_loader_modules(self):
        return {win_dacl: {}}

    def setUp(self):
        self.assertTrue(
            win_reg.set_value(
                hive="HKLM", key=FAKE_KEY, vname="fake_name", vdata="fake_data"
            )
        )

    def tearDown(self):
        win_reg.delete_key_recursive(hive="HKLM", key=FAKE_KEY)

    @pytest.mark.destructive_test
    def test_owner(self):
        """
        Test the set_owner function
        Test the get_owner function
        """
        self.assertTrue(
            win_dacl.set_owner(
                obj_name=self.obj_name,
                principal="Backup Operators",
                obj_type=self.obj_type,
            )
        )
        self.assertEqual(
            win_dacl.get_owner(obj_name=self.obj_name, obj_type=self.obj_type),
            "Backup Operators",
        )

    @pytest.mark.destructive_test
    def test_primary_group(self):
        """
        Test the set_primary_group function
        Test the get_primary_group function
        """
        self.assertTrue(
            win_dacl.set_primary_group(
                obj_name=self.obj_name,
                principal="Backup Operators",
                obj_type=self.obj_type,
            )
        )
        self.assertEqual(
            win_dacl.get_primary_group(obj_name=self.obj_name, obj_type=self.obj_type),
            "Backup Operators",
        )

    @pytest.mark.destructive_test
    def test_set_permissions(self):
        """
        Test the set_permissions function
        """
        self.assertTrue(
            win_dacl.set_permissions(
                obj_name=self.obj_name,
                principal="Backup Operators",
                permissions="full_control",
                access_mode="grant",
                obj_type=self.obj_type,
                reset_perms=False,
                protected=None,
            )
        )
        expected = {
            "Not Inherited": {
                "Backup Operators": {
                    "grant": {
                        "applies to": "This key and subkeys",
                        "permissions": "Full Control",
                    }
                }
            }
        }
        self.assertEqual(
            win_dacl.get_permissions(
                obj_name=self.obj_name,
                principal="Backup Operators",
                obj_type=self.obj_type,
            ),
            expected,
        )

    @pytest.mark.destructive_test
    def test_get_permissions(self):
        """
        Test the get_permissions function
        """
        self.assertTrue(
            win_dacl.set_permissions(
                obj_name=self.obj_name,
                principal="Backup Operators",
                permissions="full_control",
                access_mode="grant",
                obj_type=self.obj_type,
                reset_perms=False,
                protected=None,
            )
        )
        expected = {
            "Not Inherited": {
                "Backup Operators": {
                    "grant": {
                        "applies to": "This key and subkeys",
                        "permissions": "Full Control",
                    }
                }
            }
        }
        self.assertEqual(
            win_dacl.get_permissions(
                obj_name=self.obj_name,
                principal="Backup Operators",
                obj_type=self.obj_type,
            ),
            expected,
        )

    @pytest.mark.destructive_test
    def test_has_permission(self):
        """
        Test the has_permission function
        """
        self.assertTrue(
            win_dacl.set_permissions(
                obj_name=self.obj_name,
                principal="Backup Operators",
                permissions="full_control",
                access_mode="grant",
                obj_type=self.obj_type,
                reset_perms=False,
                protected=None,
            )
        )
        # Test has_permission exact
        self.assertTrue(
            win_dacl.has_permission(
                obj_name=self.obj_name,
                principal="Backup Operators",
                permission="full_control",
                access_mode="grant",
                obj_type=self.obj_type,
                exact=True,
            )
        )
        # Test has_permission contains
        self.assertTrue(
            win_dacl.has_permission(
                obj_name=self.obj_name,
                principal="Backup Operators",
                permission="read",
                access_mode="grant",
                obj_type=self.obj_type,
                exact=False,
            )
        )

    @pytest.mark.destructive_test
    def test_rm_permissions(self):
        """
        Test the rm_permissions function
        """
        self.assertTrue(
            win_dacl.set_permissions(
                obj_name=self.obj_name,
                principal="Backup Operators",
                permissions="full_control",
                access_mode="grant",
                obj_type=self.obj_type,
                reset_perms=False,
                protected=None,
            )
        )
        self.assertTrue(
            win_dacl.rm_permissions(
                obj_name=self.obj_name,
                principal="Backup Operators",
                obj_type=self.obj_type,
            )
        )
        self.assertEqual(
            win_dacl.get_permissions(
                obj_name=self.obj_name,
                principal="Backup Operators",
                obj_type=self.obj_type,
            ),
            {},
        )

    @pytest.mark.destructive_test
    def test_inheritance(self):
        """
        Test the set_inheritance function
        Test the get_inheritance function
        """
        self.assertTrue(
            win_dacl.set_inheritance(
                obj_name=self.obj_name,
                enabled=True,
                obj_type=self.obj_type,
                clear=False,
            )
        )
        self.assertTrue(
            win_dacl.get_inheritance(obj_name=self.obj_name, obj_type=self.obj_type)
        )
        self.assertTrue(
            win_dacl.set_inheritance(
                obj_name=self.obj_name,
                enabled=False,
                obj_type=self.obj_type,
                clear=False,
            )
        )
        self.assertFalse(
            win_dacl.get_inheritance(obj_name=self.obj_name, obj_type=self.obj_type)
        )

    @pytest.mark.destructive_test
    def test_check_perms(self):
        """
        Test the check_perms function
        """
        with patch.dict(win_dacl.__opts__, {"test": False}):
            result = win_dacl.check_perms(
                obj_name=self.obj_name,
                obj_type=self.obj_type,
                ret={},
                owner="Users",
                grant_perms={"Backup Operators": {"perms": "read"}},
                deny_perms={
                    "Backup Operators": {"perms": ["delete"]},
                    "NETWORK SERVICE": {
                        "perms": ["delete", "set_value", "write_dac", "write_owner"]
                    },
                },
                inheritance=True,
                reset=False,
            )

        expected = {
            "changes": {
                "owner": "Users",
                "grant_perms": {"Backup Operators": {"permissions": "read"}},
                "deny_perms": {
                    "Backup Operators": {"permissions": ["delete"]},
                    "NETWORK SERVICE": {
                        "permissions": [
                            "delete",
                            "set_value",
                            "write_dac",
                            "write_owner",
                        ]
                    },
                },
            },
            "comment": "",
            "name": self.obj_name,
            "result": True,
        }
        self.assertDictEqual(result, expected)

        expected = {
            "Not Inherited": {
                "Backup Operators": {
                    "grant": {
                        "applies to": "This key and subkeys",
                        "permissions": "Read",
                    },
                    "deny": {
                        "applies to": "This key and subkeys",
                        "permissions": ["Delete"],
                    },
                }
            }
        }
        self.assertDictEqual(
            win_dacl.get_permissions(
                obj_name=self.obj_name,
                principal="Backup Operators",
                obj_type=self.obj_type,
            ),
            expected,
        )

        expected = {
            "Not Inherited": {
                "NETWORK SERVICE": {
                    "deny": {
                        "applies to": "This key and subkeys",
                        "permissions": [
                            "Delete",
                            "Set Value",
                            "Write DAC",
                            "Write Owner",
                        ],
                    }
                }
            }
        }
        self.assertDictEqual(
            win_dacl.get_permissions(
                obj_name=self.obj_name,
                principal="NETWORK SERVICE",
                obj_type=self.obj_type,
            ),
            expected,
        )

        self.assertEqual(
            win_dacl.get_owner(obj_name=self.obj_name, obj_type=self.obj_type), "Users"
        )

    @pytest.mark.destructive_test
    def test_check_perms_test_true(self):
        """
        Test the check_perms function
        """
        with patch.dict(win_dacl.__opts__, {"test": True}):
            result = win_dacl.check_perms(
                obj_name=self.obj_name,
                obj_type=self.obj_type,
                ret=None,
                owner="Users",
                grant_perms={"Backup Operators": {"perms": "read"}},
                deny_perms={
                    "NETWORK SERVICE": {
                        "perms": ["delete", "set_value", "write_dac", "write_owner"]
                    },
                    "Backup Operators": {"perms": ["delete"]},
                },
                inheritance=True,
                reset=False,
            )

        expected = {
            "changes": {
                "owner": "Users",
                "grant_perms": {"Backup Operators": {"permissions": "read"}},
                "deny_perms": {
                    "Backup Operators": {"permissions": ["delete"]},
                    "NETWORK SERVICE": {
                        "permissions": [
                            "delete",
                            "set_value",
                            "write_dac",
                            "write_owner",
                        ]
                    },
                },
            },
            "comment": "",
            "name": self.obj_name,
            "result": None,
        }
        self.assertDictEqual(result, expected)

        self.assertNotEqual(
            win_dacl.get_owner(obj_name=self.obj_name, obj_type=self.obj_type), "Users"
        )

        self.assertEqual(
            win_dacl.get_permissions(
                obj_name=self.obj_name,
                principal="Backup Operators",
                obj_type=self.obj_type,
            ),
            {},
        )

    def test_set_perms(self):
        """
        Test the set_perms function
        """
        result = win_dacl.set_perms(
            obj_name=self.obj_name,
            obj_type=self.obj_type,
            grant_perms={"Backup Operators": {"perms": "read"}},
            deny_perms={
                "NETWORK SERVICE": {
                    "perms": ["delete", "set_value", "write_dac", "write_owner"]
                }
            },
            inheritance=True,
            reset=False,
        )

        expected = {
            "deny": {
                "NETWORK SERVICE": {
                    "perms": ["delete", "set_value", "write_dac", "write_owner"]
                }
            },
            "grant": {"Backup Operators": {"perms": "read"}},
        }

        self.assertDictEqual(result, expected)


@skipIf(not HAS_WIN32, "Requires pywin32")
@skipIf(not salt.utils.platform.is_windows(), "System is not Windows")
class WinDaclFileTestCase(TestCase, LoaderModuleMockMixin):
    obj_name = ""
    obj_type = "file"
    """
    Test cases for salt.utils.win_dacl in the file system
    """

    def setup_loader_modules(self):
        return {win_dacl: {}}

    def setUp(self):
        config_file_fd, self.obj_name = tempfile.mkstemp(
            prefix="SaltTesting-", suffix="txt"
        )
        os.close(config_file_fd)

    def tearDown(self):
        os.remove(self.obj_name)

    @pytest.mark.destructive_test
    def test_owner(self):
        """
        Test the set_owner function
        Test the get_owner function
        """
        self.assertTrue(
            win_dacl.set_owner(
                obj_name=self.obj_name,
                principal="Backup Operators",
                obj_type=self.obj_type,
            )
        )
        self.assertEqual(
            win_dacl.get_owner(obj_name=self.obj_name, obj_type=self.obj_type),
            "Backup Operators",
        )

    @pytest.mark.destructive_test
    def test_primary_group(self):
        """
        Test the set_primary_group function
        Test the get_primary_group function
        """
        self.assertTrue(
            win_dacl.set_primary_group(
                obj_name=self.obj_name,
                principal="Backup Operators",
                obj_type=self.obj_type,
            )
        )
        self.assertEqual(
            win_dacl.get_primary_group(obj_name=self.obj_name, obj_type=self.obj_type),
            "Backup Operators",
        )

    @pytest.mark.destructive_test
    def test_set_permissions(self):
        """
        Test the set_permissions function
        """
        self.assertTrue(
            win_dacl.set_permissions(
                obj_name=self.obj_name,
                principal="Backup Operators",
                permissions="full_control",
                access_mode="grant",
                obj_type=self.obj_type,
                reset_perms=False,
                protected=None,
            )
        )
        expected = {
            "Not Inherited": {
                "Backup Operators": {
                    "grant": {
                        "applies to": "Not Inherited (file)",
                        "permissions": "Full control",
                    }
                }
            }
        }
        self.assertEqual(
            win_dacl.get_permissions(
                obj_name=self.obj_name,
                principal="Backup Operators",
                obj_type=self.obj_type,
            ),
            expected,
        )

    @pytest.mark.destructive_test
    def test_get_permissions(self):
        """
        Test the get_permissions function
        """
        self.assertTrue(
            win_dacl.set_permissions(
                obj_name=self.obj_name,
                principal="Backup Operators",
                permissions="full_control",
                access_mode="grant",
                obj_type=self.obj_type,
                reset_perms=False,
                protected=None,
            )
        )
        expected = {
            "Not Inherited": {
                "Backup Operators": {
                    "grant": {
                        "applies to": "Not Inherited (file)",
                        "permissions": "Full control",
                    }
                }
            }
        }
        self.assertEqual(
            win_dacl.get_permissions(
                obj_name=self.obj_name,
                principal="Backup Operators",
                obj_type=self.obj_type,
            ),
            expected,
        )

    @pytest.mark.destructive_test
    def test_has_permission(self):
        """
        Test the has_permission function
        """
        self.assertTrue(
            win_dacl.set_permissions(
                obj_name=self.obj_name,
                principal="Backup Operators",
                permissions="full_control",
                access_mode="grant",
                obj_type=self.obj_type,
                reset_perms=False,
                protected=None,
            )
        )
        # Test has_permission exact
        self.assertTrue(
            win_dacl.has_permission(
                obj_name=self.obj_name,
                principal="Backup Operators",
                permission="full_control",
                access_mode="grant",
                obj_type=self.obj_type,
                exact=True,
            )
        )
        # Test has_permission contains
        self.assertTrue(
            win_dacl.has_permission(
                obj_name=self.obj_name,
                principal="Backup Operators",
                permission="read",
                access_mode="grant",
                obj_type=self.obj_type,
                exact=False,
            )
        )

    @pytest.mark.destructive_test
    def test_rm_permissions(self):
        """
        Test the rm_permissions function
        """
        self.assertTrue(
            win_dacl.set_permissions(
                obj_name=self.obj_name,
                principal="Backup Operators",
                permissions="full_control",
                access_mode="grant",
                obj_type=self.obj_type,
                reset_perms=False,
                protected=None,
            )
        )
        self.assertTrue(
            win_dacl.rm_permissions(
                obj_name=self.obj_name,
                principal="Backup Operators",
                obj_type=self.obj_type,
            )
        )
        self.assertEqual(
            win_dacl.get_permissions(
                obj_name=self.obj_name,
                principal="Backup Operators",
                obj_type=self.obj_type,
            ),
            {},
        )

    @pytest.mark.destructive_test
    def test_inheritance(self):
        """
        Test the set_inheritance function
        Test the get_inheritance function
        """
        self.assertTrue(
            win_dacl.set_inheritance(
                obj_name=self.obj_name,
                enabled=True,
                obj_type=self.obj_type,
                clear=False,
            )
        )
        self.assertTrue(
            win_dacl.get_inheritance(obj_name=self.obj_name, obj_type=self.obj_type)
        )
        self.assertTrue(
            win_dacl.set_inheritance(
                obj_name=self.obj_name,
                enabled=False,
                obj_type=self.obj_type,
                clear=False,
            )
        )
        self.assertFalse(
            win_dacl.get_inheritance(obj_name=self.obj_name, obj_type=self.obj_type)
        )

    @pytest.mark.destructive_test
    def test_check_perms(self):
        """
        Test the check_perms function
        """
        with patch.dict(win_dacl.__opts__, {"test": False}):
            result = win_dacl.check_perms(
                obj_name=self.obj_name,
                obj_type=self.obj_type,
                ret={},
                owner="Users",
                grant_perms={"Backup Operators": {"perms": "read"}},
                deny_perms={
                    "Backup Operators": {"perms": ["delete"]},
                    "NETWORK SERVICE": {
                        "perms": [
                            "delete",
                            "change_permissions",
                            "write_attributes",
                            "write_data",
                        ]
                    },
                },
                inheritance=True,
                reset=False,
            )

        expected = {
            "changes": {
                "owner": "Users",
                "grant_perms": {"Backup Operators": {"permissions": "read"}},
                "deny_perms": {
                    "Backup Operators": {"permissions": ["delete"]},
                    "NETWORK SERVICE": {
                        "permissions": [
                            "delete",
                            "change_permissions",
                            "write_attributes",
                            "write_data",
                        ]
                    },
                },
            },
            "comment": "",
            "name": self.obj_name,
            "result": True,
        }
        self.assertDictEqual(result, expected)

        expected = {
            "Not Inherited": {
                "Backup Operators": {
                    "grant": {
                        "applies to": "Not Inherited (file)",
                        "permissions": "Read",
                    },
                    "deny": {
                        "applies to": "Not Inherited (file)",
                        "permissions": ["Delete"],
                    },
                }
            }
        }
        self.assertDictEqual(
            win_dacl.get_permissions(
                obj_name=self.obj_name,
                principal="Backup Operators",
                obj_type=self.obj_type,
            ),
            expected,
        )

        expected = {
            "Not Inherited": {
                "NETWORK SERVICE": {
                    "deny": {
                        "applies to": "Not Inherited (file)",
                        "permissions": [
                            "Change permissions",
                            "Create files / write data",
                            "Delete",
                            "Write attributes",
                        ],
                    }
                }
            }
        }
        self.assertDictEqual(
            win_dacl.get_permissions(
                obj_name=self.obj_name,
                principal="NETWORK SERVICE",
                obj_type=self.obj_type,
            ),
            expected,
        )

        self.assertEqual(
            win_dacl.get_owner(obj_name=self.obj_name, obj_type=self.obj_type), "Users"
        )

    @pytest.mark.destructive_test
    def test_check_perms_test_true(self):
        """
        Test the check_perms function
        """
        with patch.dict(win_dacl.__opts__, {"test": True}):
            result = win_dacl.check_perms(
                obj_name=self.obj_name,
                obj_type=self.obj_type,
                ret=None,
                owner="Users",
                grant_perms={"Backup Operators": {"perms": "read"}},
                deny_perms={
                    "NETWORK SERVICE": {
                        "perms": ["delete", "set_value", "write_dac", "write_owner"]
                    },
                    "Backup Operators": {"perms": ["delete"]},
                },
                inheritance=True,
                reset=False,
            )

        expected = {
            "changes": {
                "owner": "Users",
                "grant_perms": {"Backup Operators": {"permissions": "read"}},
                "deny_perms": {
                    "Backup Operators": {"permissions": ["delete"]},
                    "NETWORK SERVICE": {
                        "permissions": [
                            "delete",
                            "set_value",
                            "write_dac",
                            "write_owner",
                        ]
                    },
                },
            },
            "comment": "",
            "name": self.obj_name,
            "result": None,
        }
        self.assertDictEqual(result, expected)

        self.assertNotEqual(
            win_dacl.get_owner(obj_name=self.obj_name, obj_type=self.obj_type), "Users"
        )

        self.assertEqual(
            win_dacl.get_permissions(
                obj_name=self.obj_name,
                principal="Backup Operators",
                obj_type=self.obj_type,
            ),
            {},
        )

    def test_set_perms(self):
        """
        Test the set_perms function
        """
        result = win_dacl.set_perms(
            obj_name=self.obj_name,
            obj_type=self.obj_type,
            grant_perms={"Backup Operators": {"perms": "read"}},
            deny_perms={
                "NETWORK SERVICE": {
                    "perms": [
                        "delete",
                        "change_permissions",
                        "write_attributes",
                        "write_data",
                    ]
                }
            },
            inheritance=True,
            reset=False,
        )

        expected = {
            "deny": {
                "NETWORK SERVICE": {
                    "perms": [
                        "delete",
                        "change_permissions",
                        "write_attributes",
                        "write_data",
                    ]
                }
            },
            "grant": {"Backup Operators": {"perms": "read"}},
        }

        self.assertDictEqual(result, expected)
