import pytest
from tests.support.mock import patch

try:
    import salt.states.reg as reg
    import salt.utils.win_dacl as win_dacl
    import salt.utils.win_functions as win_functions
    import salt.utils.win_reg as reg_util

    HAS_WIN_LIBS = True
except ImportError:
    HAS_WIN_LIBS = False

pytestmark = [
    pytest.mark.skip_unless_on_windows,
    pytest.mark.skipif(HAS_WIN_LIBS is False, reason="Windows Libraries not available"),
    pytest.mark.windows_whitelisted,
]


@pytest.fixture(scope="module")
def configure_loader_modules():
    return {
        reg: {
            "__opts__": {"test": False},
            "__salt__": {},
            "__utils__": {
                "reg.cast_vdata": reg_util.cast_vdata,
                "reg.delete_value": reg_util.delete_value,
                "reg.read_value": reg_util.read_value,
                "reg.set_value": reg_util.set_value,
                "dacl.check_perms": win_dacl.check_perms,
            },
        },
        win_dacl: {"__opts__": {"test": False}},
    }


@pytest.mark.destructive_test
class TestRegState:
    """
    Class for tests that require shared variables
    """

    hive = "HKEY_CURRENT_USER"
    key = "SOFTWARE\\Salt-Testing"
    hive = hive
    key = key
    name = "{}\\{}".format(hive, key)
    vname = "version"
    vdata = "0.15.3"
    current_user = win_functions.get_current_user(with_domain=False)

    @pytest.fixture(scope="function")
    def clean(self):
        """
        Make sure the key does NOT exist
        """
        try:
            if reg_util.key_exists(hive=self.hive, key=self.key):
                reg_util.delete_key_recursive(hive=self.hive, key=self.key)
            yield
        finally:
            if reg_util.key_exists(hive=self.hive, key=self.key):
                reg_util.delete_key_recursive(hive=self.hive, key=self.key)

    @pytest.fixture(scope="function")
    def reset(self):
        """
        Create an existing key for testing
        """
        try:
            if not reg_util.value_exists(
                hive=self.hive, key=self.key, vname=self.vname
            ):
                reg_util.set_value(
                    hive=self.hive, key=self.key, vname=self.vname, vdata=self.vdata
                )
            yield
        finally:
            if reg_util.key_exists(hive=self.hive, key=self.key):
                reg_util.delete_key_recursive(hive=self.hive, key=self.key)

    def test_present(self):
        """
        Test reg.present
        """
        expected = {
            "comment": "Added {} to {}".format(self.vname, self.name),
            "changes": {
                "reg": {
                    "Added": {
                        "Inheritance": True,
                        "Perms": {"Deny": None, "Grant": None},
                        "Value": self.vdata,
                        "Key": self.name,
                        "Owner": None,
                        "Entry": self.vname,
                    }
                }
            },
            "name": self.name,
            "result": True,
        }
        assert (
            reg.present(name=self.name, vname=self.vname, vdata=self.vdata) == expected
        )
        permissions = win_dacl.get_permissions(obj_name=self.name, obj_type="registry")
        assert permissions["Not Inherited"] == {}

    def test_present_set_owner(self, clean):
        """
        Test reg.present
        """
        reg.present(
            name=self.name,
            vname=self.vname,
            vdata=self.vdata,
            win_owner=self.current_user,
        )
        assert (
            win_dacl.get_owner(obj_name=self.name, obj_type="registry")
            == self.current_user
        )

    def test_present_perms_no_inherit(self, clean):
        reg.present(
            name=self.name, vname=self.vname, vdata=self.vdata, win_inheritance=False
        )
        assert not win_dacl.get_inheritance(obj_name=self.name, obj_type="registry")
        permissions = win_dacl.get_permissions(obj_name=self.name, obj_type="registry")
        assert permissions["Inherited"] == {}

    def test_present_perms(self, clean):
        reg.present(
            name=self.name,
            vname=self.vname,
            vdata=self.vdata,
            win_perms={"Backup Operators": {"perms": "full_control"}},
            win_deny_perms={"Guest": {"perms": "full_control"}},
        )
        permissions = win_dacl.get_permissions(obj_name=self.name, obj_type="registry")
        expected = {
            "deny": {
                "permissions": "Full Control",
                "applies to": "This key and subkeys",
            }
        }
        assert permissions["Not Inherited"].get("Guest") == expected
        expected = {
            "grant": {
                "permissions": "Full Control",
                "applies to": "This key and subkeys",
            }
        }
        assert permissions["Not Inherited"].get("Backup Operators") == expected

    def test_present_perms_reset(self, clean):
        reg.present(
            name=self.name,
            vname=self.vname,
            vdata=self.vdata,
            win_perms={"Everyone": {"perms": "full_control"}},
            win_deny_perms={"Guest": {"perms": "full_control"}},
            win_perms_reset=True,
        )
        permissions = win_dacl.get_permissions(obj_name=self.name, obj_type="registry")
        expected = {
            "Guest": {
                "deny": {
                    "permissions": "Full Control",
                    "applies to": "This key and subkeys",
                }
            },
            "Everyone": {
                "grant": {
                    "permissions": "Full Control",
                    "applies to": "This key and subkeys",
                }
            },
        }
        assert permissions["Not Inherited"] == expected

    def test_present_perms_reset_no_inherit(self, clean):
        reg.present(
            name=self.name,
            vname=self.vname,
            vdata=self.vdata,
            win_perms={"Everyone": {"perms": "full_control"}},
            win_deny_perms={"Guest": {"perms": "full_control"}},
            win_perms_reset=True,
            win_inheritance=False,
        )
        permissions = win_dacl.get_permissions(obj_name=self.name, obj_type="registry")
        expected = {
            "Guest": {
                "deny": {
                    "permissions": "Full Control",
                    "applies to": "This key and subkeys",
                }
            },
            "Everyone": {
                "grant": {
                    "permissions": "Full Control",
                    "applies to": "This key and subkeys",
                }
            },
        }
        assert permissions["Not Inherited"] == expected
        assert not win_dacl.get_inheritance(obj_name=self.name, obj_type="registry")
        assert permissions["Inherited"] == {}

    def test_present_string_dword(self, clean):
        """
        Test to set a registry entry.
        """
        vname = "dword_data"
        vdata = "00000001"
        vtype = "REG_DWORD"
        expected_vdata = 1
        expected = {
            "comment": "Added {} to {}".format(vname, self.name),
            "changes": {
                "reg": {
                    "Added": {
                        "Inheritance": True,
                        "Perms": {"Deny": None, "Grant": None},
                        "Value": expected_vdata,
                        "Key": self.name,
                        "Owner": None,
                        "Entry": vname,
                    }
                }
            },
            "name": self.name,
            "result": True,
        }
        assert (
            reg.present(name=self.name, vname=vname, vdata=vdata, vtype=vtype)
            == expected
        )

    def test_present_string_dword_existing(self, clean):
        """
        Test to set a registry entry.
        """
        vname = "dword_data"
        vdata = "0000001"
        vtype = "REG_DWORD"
        # Set it first
        reg_util.set_value(
            hive=self.hive, key=self.key, vname=vname, vdata=vdata, vtype=vtype
        )
        expected = {
            "comment": "{} in {} is already present".format(vname, self.name),
            "changes": {},
            "name": self.name,
            "result": True,
        }
        assert (
            reg.present(name=self.name, vname=vname, vdata=vdata, vtype=vtype)
            == expected
        )

    def test_present_test_true(self, clean):
        expected = {
            "comment": "",
            "changes": {
                "reg": {
                    "Will add": {
                        "Inheritance": True,
                        "Perms": {"Deny": None, "Grant": None},
                        "Value": self.vdata,
                        "Key": self.name,
                        "Owner": None,
                        "Entry": "version",
                    }
                }
            },
            "name": self.name,
            "result": None,
        }
        with patch.dict(reg.__opts__, {"test": True}):
            ret = reg.present(self.name, vname=self.vname, vdata=self.vdata)
        assert ret == expected

    def test_present_existing(self, reset):
        expected = {
            "comment": "{} in {} is already present".format(self.vname, self.name),
            "changes": {},
            "name": self.name,
            "result": True,
        }
        assert (
            reg.present(name=self.name, vname=self.vname, vdata=self.vdata) == expected
        )

    def test_present_existing_key_only(self, clean):
        """
        Test setting only a key with no value name
        """
        # Create the reg key for testing
        reg_util.set_value(hive=self.hive, key=self.key)

        expected = {
            "comment": "(Default) in {} is already present".format(self.name),
            "changes": {},
            "name": self.name,
            "result": True,
        }
        assert reg.present(self.name) == expected

    def test_present_existing_test_true(self, reset):
        expected = {
            "comment": "{} in {} is already present".format(self.vname, self.name),
            "changes": {},
            "name": self.name,
            "result": True,
        }
        with patch.dict(reg.__opts__, {"test": True}):
            ret = reg.present(name=self.name, vname=self.vname, vdata=self.vdata)
        assert ret == expected

    def test_absent(self, reset):
        """
        Test to remove a registry entry.
        """
        expected = {
            "comment": "Removed {} from {}".format(self.key, self.hive),
            "changes": {"reg": {"Removed": {"Entry": self.vname, "Key": self.name}}},
            "name": self.name,
            "result": True,
        }
        assert reg.absent(self.name, self.vname) == expected

    def test_absent_test_true(self, reset):
        expected = {
            "comment": "",
            "changes": {
                "reg": {"Will remove": {"Entry": self.vname, "Key": self.name}}
            },
            "name": self.name,
            "result": None,
        }
        with patch.dict(reg.__opts__, {"test": True}):
            ret = reg.absent(self.name, self.vname)
        assert ret == expected

    def test_absent_already_absent(self, clean):
        """
        Test to remove a registry entry.
        """
        expected = {
            "comment": "{} is already absent".format(self.name),
            "changes": {},
            "name": self.name,
            "result": True,
        }
        assert reg.absent(self.name, self.vname) == expected

    def test_absent_already_absent_test_true(self, clean):
        """
        Test to remove a registry entry.
        """
        expected = {
            "comment": "{} is already absent".format(self.name),
            "changes": {},
            "name": self.name,
            "result": True,
        }
        with patch.dict(reg.__opts__, {"test": True}):
            ret = reg.absent(self.name, self.vname)
        assert ret == expected
