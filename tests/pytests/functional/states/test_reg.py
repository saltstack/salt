import pytest

import salt.states.reg as reg
import salt.utils.win_dacl as win_dacl
import salt.utils.win_functions as win_functions
import salt.utils.win_reg as reg_util

pytestmark = [
    pytest.mark.skip_unless_on_windows,
    pytest.mark.windows_whitelisted,
]


class RegVars:
    """
    Class for tests that require shared variables
    """

    def __init__(self):
        self.hive = "HKEY_CURRENT_USER"
        self.key = "SOFTWARE\\Salt-Testing"
        self.hive = self.hive
        self.key = self.key
        self.name = "{}\\{}".format(self.hive, self.key)
        self.vname = "version"
        self.vdata = "0.15.3"
        self.current_user = win_functions.get_current_user(with_domain=False)


# @pytest.fixture(scope="module")
# def configure_loader_modules():
#     return {
#         reg: {
#             "__opts__": {"test": False},
#             "__salt__": {},
#             "__utils__": {
#                 "reg.cast_vdata": reg_util.cast_vdata,
#                 "reg.delete_value": reg_util.delete_value,
#                 "reg.read_value": reg_util.read_value,
#                 "reg.set_value": reg_util.set_value,
#                 "dacl.check_perms": win_dacl.check_perms,
#             },
#         },
#         win_dacl: {"__opts__": {"test": False}},
#     }


@pytest.fixture(scope="function")
def reg_vars():
    return RegVars()


@pytest.fixture(scope="function")
def clean(reg_vars, modules):
    """
    Make sure the key does NOT exist
    """
    try:
        if reg_util.key_exists(hive=reg_vars.hive, key=reg_vars.key):
            reg_util.delete_key_recursive(hive=reg_vars.hive, key=reg_vars.key)
        yield
    finally:
        if reg_util.key_exists(hive=reg_vars.hive, key=reg_vars.key):
            reg_util.delete_key_recursive(hive=reg_vars.hive, key=reg_vars.key)


@pytest.fixture(scope="function")
def reset(reg_vars, modules):
    """
    Create an existing key for testing
    """
    try:
        if not reg_util.value_exists(
            hive=reg_vars.hive, key=reg_vars.key, vname=reg_vars.vname
        ):
            reg_util.set_value(
                hive=reg_vars.hive,
                key=reg_vars.key,
                vname=reg_vars.vname,
                vdata=reg_vars.vdata,
            )
        yield
    finally:
        if reg_util.key_exists(hive=reg_vars.hive, key=reg_vars.key):
            reg_util.delete_key_recursive(hive=reg_vars.hive, key=reg_vars.key)


def test_present(reg_vars, clean, states):
    """
    Test reg.present
    """
    hive_key = "\\".join([reg_vars.hive, reg_vars.key])
    expected = {
        "comment": "Added {} to {}".format(reg_vars.vname, reg_vars.name),
        "changes": {
            "new": {
                "success": True,
                "vdata": reg_vars.vdata,
                "vtype": "REG_SZ",
            },
            "old": {
                "comment": f"Cannot find key: {hive_key}",
                "success": False,
                "vdata": None,
                "vtype": None,
                },
            },
        "name": reg_vars.name,
        "result": True,
    }
    ret = states.reg.present(name=reg_vars.name, vname=reg_vars.vname, vdata=reg_vars.vdata)
    assert ret.filtered == expected

    permissions = win_dacl.get_permissions(obj_name=reg_vars.name, obj_type="registry")
    assert permissions["Not Inherited"] == {}


def test_present_set_owner(reg_vars, clean, states):
    """
    Test reg.present
    """
    states.reg.present(
        name=reg_vars.name,
        vname=reg_vars.vname,
        vdata=reg_vars.vdata,
        win_owner=reg_vars.current_user,
    )
    assert (
        win_dacl.get_owner(obj_name=reg_vars.name, obj_type="registry")
        == reg_vars.current_user
    )


def test_present_perms_no_inherit(reg_vars, clean, states):
    states.reg.present(
        name=reg_vars.name,
        vname=reg_vars.vname,
        vdata=reg_vars.vdata,
        win_inheritance=False,
    )
    assert not win_dacl.get_inheritance(obj_name=reg_vars.name, obj_type="registry")
    permissions = win_dacl.get_permissions(obj_name=reg_vars.name, obj_type="registry")
    assert permissions["Inherited"] == {}


def test_present_perms(reg_vars, clean, states):
    states.reg.present(
        name=reg_vars.name,
        vname=reg_vars.vname,
        vdata=reg_vars.vdata,
        win_perms={"Backup Operators": {"perms": "full_control"}},
        win_deny_perms={"Guest": {"perms": "full_control"}},
    )
    permissions = win_dacl.get_permissions(obj_name=reg_vars.name, obj_type="registry")
    expected = {
        "deny": {"permissions": "Full Control", "applies to": "This key and subkeys"}
    }
    assert permissions["Not Inherited"].get("Guest") == expected
    expected = {
        "grant": {"permissions": "Full Control", "applies to": "This key and subkeys"}
    }
    assert permissions["Not Inherited"].get("Backup Operators") == expected


def test_present_perms_reset(reg_vars, clean, states):
    states.reg.present(
        name=reg_vars.name,
        vname=reg_vars.vname,
        vdata=reg_vars.vdata,
        win_perms={"Everyone": {"perms": "full_control"}},
        win_deny_perms={"Guest": {"perms": "full_control"}},
        win_perms_reset=True,
    )
    permissions = win_dacl.get_permissions(obj_name=reg_vars.name, obj_type="registry")
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


def test_present_perms_reset_no_inherit(reg_vars, clean, states):
    states.reg.present(
        name=reg_vars.name,
        vname=reg_vars.vname,
        vdata=reg_vars.vdata,
        win_perms={"Everyone": {"perms": "full_control"}},
        win_deny_perms={"Guest": {"perms": "full_control"}},
        win_perms_reset=True,
        win_inheritance=False,
    )
    permissions = win_dacl.get_permissions(obj_name=reg_vars.name, obj_type="registry")
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
    assert not win_dacl.get_inheritance(obj_name=reg_vars.name, obj_type="registry")
    assert permissions["Inherited"] == {}


def test_present_string_dword(reg_vars, clean, states):
    """
    Test to set a registry entry.
    """
    vname = "dword_data"
    vdata = "00000001"
    vtype = "REG_DWORD"
    hive_key = "\\".join([reg_vars.hive, reg_vars.key])
    expected = {
        "comment": "Added {} to {}".format(vname, reg_vars.name),
        "changes": {
            "new": {
                "success": True,
                "vdata": 1,
                "vtype": vtype,
            },
            "old": {
                "comment": f"Cannot find key: {hive_key}",
                "success": False,
                "vdata": None,
                "vtype": None,
            },
        },
        "name": reg_vars.name,
        "result": True,
    }
    ret = states.reg.present(name=reg_vars.name, vname=vname, vdata=vdata, vtype=vtype)
    assert ret.filtered == expected


def test_present_string_dword_existing(reg_vars, clean, states):
    """
    Test to set a registry entry.
    """
    vname = "dword_data"
    vdata = "0000001"
    vtype = "REG_DWORD"
    # Set it first
    reg_util.set_value(
        hive=reg_vars.hive, key=reg_vars.key, vname=vname, vdata=vdata, vtype=vtype
    )
    expected = {
        "comment": "{} in {} is already present".format(vname, reg_vars.name),
        "changes": {},
        "name": reg_vars.name,
        "result": True,
    }
    ret = states.reg.present(name=reg_vars.name, vname=vname, vdata=vdata, vtype=vtype)
    assert ret.filtered == expected


def test_present_test_true(reg_vars, clean, states):
    expected = {
        "comment": "",
        "changes": {
            "reg": {
                "Will add": {
                    "Inheritance": True,
                    "Perms": {"Deny": None, "Grant": None},
                    "Value": reg_vars.vdata,
                    "Key": reg_vars.name,
                    "Owner": None,
                    "Entry": "version",
                }
            }
        },
        "name": reg_vars.name,
        "result": None,
    }
    ret = states.reg.present(name=reg_vars.name, vname=reg_vars.vname, vdata=reg_vars.vdata, test=True)
    assert ret.filtered == expected


def test_present_existing(reg_vars, reset, states):
    expected = {
        "comment": "{} in {} is already present".format(reg_vars.vname, reg_vars.name),
        "changes": {},
        "name": reg_vars.name,
        "result": True,
    }
    ret = states.reg.present(name=reg_vars.name, vname=reg_vars.vname, vdata=reg_vars.vdata)
    assert ret.filtered == expected


def test_present_existing_key_only(reg_vars, clean, states):
    """
    Test setting only a key with no value name
    """
    # Create the reg key for testing
    reg_util.set_value(hive=reg_vars.hive, key=reg_vars.key)

    expected = {
        "comment": "(Default) in {} is already present".format(reg_vars.name),
        "changes": {},
        "name": reg_vars.name,
        "result": True,
    }
    ret = states.reg.present(reg_vars.name)
    assert ret.filtered == expected


def test_present_existing_test_true(reg_vars, reset, states):
    expected = {
        "comment": "{} in {} is already present".format(reg_vars.vname, reg_vars.name),
        "changes": {},
        "name": reg_vars.name,
        "result": True,
    }
    ret = states.reg.present(
        name=reg_vars.name, vname=reg_vars.vname, vdata=reg_vars.vdata, test=True
    )
    assert ret.filtered == expected


def test_absent(reg_vars, reset, states):
    """
    Test to remove a registry entry.
    """
    hive_key = "\\".join([reg_vars.hive, reg_vars.key])
    expected = {
        "comment": "Removed {} from {}".format(reg_vars.key, reg_vars.hive),
        "changes": {
            "new": {
                "comment": f"Cannot find version in {hive_key}",
                "success": False,
                "vdata": None,
                "vtype": None,
            },
            "old": {
                "success": True,
                "vdata": "0.15.3",
                "vtype": "REG_SZ",
            },
        },
        "name": hive_key,
        "result": True,
    }
    ret = states.reg.absent(name=reg_vars.name, vname=reg_vars.vname)
    assert ret.filtered == expected


def test_absent_test_true(reg_vars, reset, states):
    expected = {
        "comment": "",
        "changes": {
            "reg": {"Will remove": {"Entry": reg_vars.vname, "Key": reg_vars.name}}
        },
        "name": reg_vars.name,
        "result": None,
    }
    ret = states.reg.absent(name=reg_vars.name, vname=reg_vars.vname, test=True)
    assert ret.filtered == expected


def test_absent_already_absent(reg_vars, clean, states):
    """
    Test to remove a registry entry.
    """
    expected = {
        "comment": "{} is already absent".format(reg_vars.name),
        "changes": {},
        "name": reg_vars.name,
        "result": True,
    }
    ret = states.reg.absent(reg_vars.name, reg_vars.vname)
    assert ret.filtered == expected


def test_absent_already_absent_test_true(reg_vars, clean, states):
    """
    Test to remove a registry entry.
    """
    expected = {
        "comment": "{} is already absent".format(reg_vars.name),
        "changes": {},
        "name": reg_vars.name,
        "result": True,
    }
    ret = states.reg.absent(name=reg_vars.name, vname=reg_vars.vname, test=True)
    assert ret.filtered == expected


def test__get_current():
    ret = reg._get_current(
        hive="HKCU", key="Environment", vname="Path", use_32bit_registry=False, all_users=False
    )
    assert ret["success"] is True
    assert ret["vdata"]


def test__get_current_all_users():
    """
    If no other users are logged in, nothing is returned
    """
    ret = reg._get_current(
        hive="HKCU", key="Environment", vname="Path", use_32bit_registry=False, all_users=True
    )
    assert ret == {}
