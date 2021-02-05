import pytest
import salt.states.reg as reg
import salt.utils.win_dacl as win_dacl
import salt.utils.win_functions as win_functions
import salt.utils.win_reg as reg_util
from tests.support.mock import patch

CURRENT_USER = win_functions.get_current_user(with_domain=False)
HIVE = "HKEY_CURRENT_USER"
KEY = "SOFTWARE\\Salt-Testing"
NAME = HIVE + "\\" + KEY
VNAME = "version"
VDATA = "0.15.3"

pytestmark = [pytest.mark.windows_whitelisted, pytest.mark.skip_unless_on_windows]


@pytest.fixture
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


@pytest.fixture
def clean():
    if reg_util.key_exists(hive=HIVE, key=KEY):
        reg_util.delete_key_recursive(hive=HIVE, key=KEY)
    yield
    if reg_util.key_exists(hive=HIVE, key=KEY):
        reg_util.delete_key_recursive(hive=HIVE, key=KEY)


@pytest.fixture
def reset():
    # Create the reg key for testing
    if not reg_util.value_exists(hive=HIVE, key=KEY, vname=VNAME):
        reg_util.set_value(hive=HIVE, key=KEY, vname=VNAME, vdata=VDATA)
    yield


@pytest.mark.destructive_test
def test_present(clean):
    """
    Test reg.present
    """
    expected = {
        "comment": "Added {} to {}".format(VNAME, NAME),
        "changes": {
            "reg": {
                "Added": {
                    "Inheritance": True,
                    "Perms": {"Deny": None, "Grant": None},
                    "Value": VDATA,
                    "Key": NAME,
                    "Owner": None,
                    "Entry": VNAME,
                }
            }
        },
        "name": NAME,
        "result": True,
    }
    assert reg.present(name=NAME, vname=VNAME, vdata=VDATA) == expected
    permissions = win_dacl.get_permissions(obj_name=NAME, obj_type="registry")
    assert permissions["Not Inherited"] == {}


@pytest.mark.destructive_test
def test_present_set_owner(clean):
    """
    Test reg.present
    """
    reg.present(name=NAME, vname=VNAME, vdata=VDATA, win_owner=CURRENT_USER)
    assert win_dacl.get_owner(obj_name=NAME, obj_type="registry") == CURRENT_USER


@pytest.mark.destructive_test
def test_present_perms_no_inherit(clean):
    reg.present(name=NAME, vname=VNAME, vdata=VDATA, win_inheritance=False)
    assert not win_dacl.get_inheritance(obj_name=NAME, obj_type="registry")
    permissions = win_dacl.get_permissions(obj_name=NAME, obj_type="registry")
    assert permissions["Inherited"] == {}


@pytest.mark.destructive_test
def test_present_perms(clean):
    reg.present(
        name=NAME,
        vname=VNAME,
        vdata=VDATA,
        win_perms={"Backup Operators": {"perms": "full_control"}},
        win_deny_perms={"Guest": {"perms": "full_control"}},
    )
    permissions = win_dacl.get_permissions(obj_name=NAME, obj_type="registry")
    expected = {
        "deny": {"permissions": "Full Control", "applies to": "This key and subkeys"}
    }
    assert permissions["Not Inherited"].get("Guest") == expected
    expected = {
        "grant": {"permissions": "Full Control", "applies to": "This key and subkeys"}
    }
    assert permissions["Not Inherited"].get("Backup Operators") == expected


@pytest.mark.destructive_test
def test_present_perms_reset(clean):
    reg.present(
        name=NAME,
        vname=VNAME,
        vdata=VDATA,
        win_perms={"Everyone": {"perms": "full_control"}},
        win_deny_perms={"Guest": {"perms": "full_control"}},
        win_perms_reset=True,
    )
    permissions = win_dacl.get_permissions(obj_name=NAME, obj_type="registry")
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


@pytest.mark.destructive_test
def test_present_perms_reset_no_inherit(clean):
    reg.present(
        name=NAME,
        vname=VNAME,
        vdata=VDATA,
        win_perms={"Everyone": {"perms": "full_control"}},
        win_deny_perms={"Guest": {"perms": "full_control"}},
        win_perms_reset=True,
        win_inheritance=False,
    )
    permissions = win_dacl.get_permissions(obj_name=NAME, obj_type="registry")
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
    assert not win_dacl.get_inheritance(obj_name=NAME, obj_type="registry")
    assert permissions["Inherited"] == {}


@pytest.mark.destructive_test
def test_present_string_dword(clean):
    """
    Test to set a registry entry.
    """
    vname = "dword_data"
    vdata = "00000001"
    vtype = "REG_DWORD"
    expected_vdata = 1
    expected = {
        "comment": "Added {} to {}".format(vname, NAME),
        "changes": {
            "reg": {
                "Added": {
                    "Inheritance": True,
                    "Perms": {"Deny": None, "Grant": None},
                    "Value": expected_vdata,
                    "Key": NAME,
                    "Owner": None,
                    "Entry": vname,
                }
            }
        },
        "name": NAME,
        "result": True,
    }
    assert reg.present(name=NAME, vname=vname, vdata=vdata, vtype=vtype) == expected


@pytest.mark.destructive_test
def test_present_string_dword_existing(clean):
    """
    Test to set a registry entry.
    """
    vname = "dword_data"
    vdata = "0000001"
    vtype = "REG_DWORD"
    # Set it first
    reg_util.set_value(hive=HIVE, key=KEY, vname=vname, vdata=vdata, vtype=vtype)
    expected = {
        "comment": "{} in {} is already present".format(vname, NAME),
        "changes": {},
        "name": NAME,
        "result": True,
    }
    assert reg.present(name=NAME, vname=vname, vdata=vdata, vtype=vtype) == expected


def test_present_test_true(clean):
    expected = {
        "comment": "",
        "changes": {
            "reg": {
                "Will add": {
                    "Inheritance": True,
                    "Perms": {"Deny": None, "Grant": None},
                    "Value": VDATA,
                    "Key": NAME,
                    "Owner": None,
                    "Entry": "version",
                }
            }
        },
        "name": NAME,
        "result": None,
    }
    with patch.dict(reg.__opts__, {"test": True}):
        ret = reg.present(NAME, vname=VNAME, vdata=VDATA)
    assert ret == expected


def test_present_existing(reset):
    expected = {
        "comment": "{} in {} is already present".format(VNAME, NAME),
        "changes": {},
        "name": NAME,
        "result": True,
    }
    assert reg.present(name=NAME, vname=VNAME, vdata=VDATA) == expected


def test_present_existing_key_only(clean):
    """
    Test setting only a key with no value name
    """
    # Create the reg key for testing
    reg_util.set_value(hive=HIVE, key=KEY)

    expected = {
        "comment": "(Default) in {} is already present".format(NAME),
        "changes": {},
        "name": NAME,
        "result": True,
    }
    assert reg.present(NAME) == expected


def test_present_existing_test_true(reset):
    expected = {
        "comment": "{} in {} is already present".format(VNAME, NAME),
        "changes": {},
        "name": NAME,
        "result": True,
    }
    with patch.dict(reg.__opts__, {"test": True}):
        ret = reg.present(name=NAME, vname=VNAME, vdata=VDATA)
    assert ret == expected


@pytest.mark.destructive_test
def test_absent(reset):
    """
    Test to remove a registry entry.
    """
    expected = {
        "comment": "Removed {} from {}".format(KEY, HIVE),
        "changes": {"reg": {"Removed": {"Entry": VNAME, "Key": NAME}}},
        "name": NAME,
        "result": True,
    }
    assert reg.absent(NAME, VNAME) == expected


@pytest.mark.destructive_test
def test_absent_test_true(reset):
    expected = {
        "comment": "",
        "changes": {"reg": {"Will remove": {"Entry": VNAME, "Key": NAME}}},
        "name": NAME,
        "result": None,
    }
    with patch.dict(reg.__opts__, {"test": True}):
        ret = reg.absent(NAME, VNAME)
    assert ret == expected


def test_absent_already_absent(clean):
    """
    Test to remove a registry entry.
    """
    expected = {
        "comment": "{} is already absent".format(NAME),
        "changes": {},
        "name": NAME,
        "result": True,
    }
    assert reg.absent(NAME, VNAME) == expected


def test_absent_already_absent_test_true(clean):
    """
    Test to remove a registry entry.
    """
    expected = {
        "comment": "{} is already absent".format(NAME),
        "changes": {},
        "name": NAME,
        "result": True,
    }
    with patch.dict(reg.__opts__, {"test": True}):
        ret = reg.absent(NAME, VNAME)
    assert ret == expected
