import pathlib

import pytest

import salt.modules.win_file as file
import salt.modules.win_lgpo_reg as win_lgpo_reg
import salt.states.win_lgpo_reg as lgpo_reg
import salt.utils.files
import salt.utils.win_dacl
import salt.utils.win_lgpo_reg
import salt.utils.win_reg
from tests.support.mock import patch

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.destructive_test,
]


@pytest.fixture
def configure_loader_modules():
    return {
        lgpo_reg: {
            "__opts__": {"test": False},
            "__salt__": {
                "lgpo_reg.get_value": win_lgpo_reg.get_value,
                "lgpo_reg.set_value": win_lgpo_reg.set_value,
                "lgpo_reg.disable_value": win_lgpo_reg.disable_value,
                "lgpo_reg.delete_value": win_lgpo_reg.delete_value,
            },
            "__utils__": {
                "reg.read_value": salt.utils.win_reg.read_value,
            },
        },
        file: {
            "__utils__": {
                "dacl.set_perms": salt.utils.win_dacl.set_perms,
            },
        },
    }


@pytest.fixture
def empty_reg_pol_mach():
    class_info = salt.utils.win_lgpo_reg.CLASS_INFO
    reg_pol_file = pathlib.Path(class_info["Machine"]["policy_path"])
    reg_pol_file.parent.mkdir(parents=True, exist_ok=True)
    reg_pol_file.write_bytes(salt.utils.win_lgpo_reg.REG_POL_HEADER.encode("utf-16-le"))
    salt.utils.win_reg.delete_key_recursive(hive="HKLM", key="SOFTWARE\\MyKey1")
    salt.utils.win_reg.delete_key_recursive(hive="HKLM", key="SOFTWARE\\MyKey2")
    yield
    salt.utils.win_reg.delete_key_recursive(hive="HKLM", key="SOFTWARE\\MyKey1")
    salt.utils.win_reg.delete_key_recursive(hive="HKLM", key="SOFTWARE\\MyKey2")
    reg_pol_file.write_bytes(salt.utils.win_lgpo_reg.REG_POL_HEADER.encode("utf-16-le"))


@pytest.fixture
def empty_reg_pol_user():
    class_info = salt.utils.win_lgpo_reg.CLASS_INFO
    reg_pol_file = pathlib.Path(class_info["User"]["policy_path"])
    reg_pol_file.parent.mkdir(parents=True, exist_ok=True)
    reg_pol_file.write_bytes(salt.utils.win_lgpo_reg.REG_POL_HEADER.encode("utf-16-le"))
    salt.utils.win_reg.delete_key_recursive(hive="HKCU", key="SOFTWARE\\MyKey1")
    salt.utils.win_reg.delete_key_recursive(hive="HKCU", key="SOFTWARE\\MyKey2")
    yield
    salt.utils.win_reg.delete_key_recursive(hive="HKCU", key="SOFTWARE\\MyKey1")
    salt.utils.win_reg.delete_key_recursive(hive="HKCU", key="SOFTWARE\\MyKey2")
    reg_pol_file.write_bytes(salt.utils.win_lgpo_reg.REG_POL_HEADER.encode("utf-16-le"))


@pytest.fixture
def reg_pol_mach():
    data_to_write = {
        r"SOFTWARE\MyKey1": {
            "MyValue1": {
                "data": "squidward",
                "type": "REG_SZ",
            },
            "**del.MyValue2": {
                "data": " ",
                "type": "REG_SZ",
            },
            "MyValue3": {
                "data": 0,
                "type": "REG_DWORD",
            },
        },
        r"SOFTWARE\MyKey2": {
            "MyValue3": {
                "data": ["spongebob", "squarepants"],
                "type": "REG_MULTI_SZ",
            },
        },
    }
    win_lgpo_reg.write_reg_pol(data_to_write)
    salt.utils.win_reg.set_value(
        hive="HKLM",
        key="SOFTWARE\\MyKey1",
        vname="MyValue1",
        vdata="squidward",
        vtype="REG_SZ",
    )
    salt.utils.win_reg.set_value(
        hive="HKLM",
        key="SOFTWARE\\MyKey1",
        vname="MyValue3",
        vdata=0,
        vtype="REG_DWORD",
    )
    salt.utils.win_reg.set_value(
        hive="HKLM",
        key="SOFTWARE\\MyKey2",
        vname="MyValue3",
        vdata=["spongebob", "squarepants"],
        vtype="REG_MULTI_SZ",
    )
    yield
    salt.utils.win_reg.delete_key_recursive(hive="HKLM", key="SOFTWARE\\MyKey1")
    salt.utils.win_reg.delete_key_recursive(hive="HKLM", key="SOFTWARE\\MyKey2")
    class_info = salt.utils.win_lgpo_reg.CLASS_INFO
    reg_pol_file = class_info["Machine"]["policy_path"]
    with salt.utils.files.fopen(reg_pol_file, "wb") as f:
        f.write(salt.utils.win_lgpo_reg.REG_POL_HEADER.encode("utf-16-le"))


@pytest.fixture
def reg_pol_user():
    data_to_write = {
        r"SOFTWARE\MyKey1": {
            "MyValue1": {
                "data": "squidward",
                "type": "REG_SZ",
            },
            "**del.MyValue2": {
                "data": " ",
                "type": "REG_SZ",
            },
            "MyValue3": {
                "data": 0,
                "type": "REG_DWORD",
            },
        },
        r"SOFTWARE\MyKey2": {
            "MyValue3": {
                "data": ["spongebob", "squarepants"],
                "type": "REG_MULTI_SZ",
            },
        },
    }
    win_lgpo_reg.write_reg_pol(data_to_write, policy_class="User")
    salt.utils.win_reg.set_value(
        hive="HKCU",
        key="SOFTWARE\\MyKey1",
        vname="MyValue1",
        vdata="squidward",
        vtype="REG_SZ",
    )
    salt.utils.win_reg.set_value(
        hive="HKCU",
        key="SOFTWARE\\MyKey1",
        vname="MyValue3",
        vdata=0,
        vtype="REG_DWORD",
    )
    salt.utils.win_reg.set_value(
        hive="HKCU",
        key="SOFTWARE\\MyKey2",
        vname="MyValue3",
        vdata=["spongebob", "squarepants"],
        vtype="REG_MULTI_SZ",
    )
    yield
    salt.utils.win_reg.delete_key_recursive(hive="HKCU", key="SOFTWARE\\MyKey1")
    salt.utils.win_reg.delete_key_recursive(hive="HKCU", key="SOFTWARE\\MyKey2")
    class_info = salt.utils.win_lgpo_reg.CLASS_INFO
    reg_pol_file = class_info["User"]["policy_path"]
    with salt.utils.files.fopen(reg_pol_file, "wb") as f:
        f.write(salt.utils.win_lgpo_reg.REG_POL_HEADER.encode("utf-16-le"))


def test_virtual_name():
    assert lgpo_reg.__virtual__() == "lgpo_reg"


def test_machine_value_present(empty_reg_pol_mach):
    """
    Test value.present in Machine policy
    """
    result = lgpo_reg.value_present(
        name="MyValue",
        key="SOFTWARE\\MyKey1",
        v_data="1",
        v_type="REG_DWORD",
    )
    expected = {
        "changes": {
            "new": {
                "pol": {
                    "data": 1,
                    "type": "REG_DWORD",
                },
                "reg": {
                    "data": 1,
                    "type": "REG_DWORD",
                },
            },
            "old": {
                "pol": {},
                "reg": {},
            },
        },
        "comment": "Registry policy value has been set",
        "name": "MyValue",
        "result": True,
    }
    assert result == expected


def test_machine_value_present_similar_names(empty_reg_pol_mach):
    """
    Test value.present in Machine policy
    """
    lgpo_reg.value_present(
        name="MyValueTwo",
        key="SOFTWARE\\MyKey1",
        v_data="1",
        v_type="REG_DWORD",
    )
    lgpo_reg.value_present(
        name="MyValue",
        key="SOFTWARE\\MyKey1",
        v_data="1",
        v_type="REG_DWORD",
    )
    expected = {
        "SOFTWARE\\MyKey1": {
            "MyValue": {
                "type": "REG_DWORD",
                "data": 1,
            },
            "MyValueTwo": {
                "type": "REG_DWORD",
                "data": 1,
            },
        },
    }
    result = win_lgpo_reg.read_reg_pol(policy_class="Machine")
    assert result == expected


def test_machine_value_present_enforce(reg_pol_mach):
    """
    Issue #64222
    Test value.present in Machine policy when the registry changes after the
    state is applied. This would cause a discrepancy between the registry
    setting and the value in the registry.pol file
    """
    # reg_pol_mach has MyValue3 with REG_DWORD value of 0, let's set it to 1
    salt.utils.win_reg.set_value(
        hive="HKLM",
        key="SOFTWARE\\MyKey1",
        vname="MyValue3",
        vdata="1",
        vtype="REG_DWORD",
    )
    # Now the registry and Registry.pol file are out of sync
    result = lgpo_reg.value_present(
        name="MyValue3",
        key="SOFTWARE\\MyKey1",
        v_data="0",
        v_type="REG_DWORD",
    )
    expected = {
        "changes": {
            "new": {
                "reg": {
                    "data": 0,
                }
            },
            "old": {
                "reg": {
                    "data": 1,
                }
            },
        },
        "comment": "Registry policy value has been set",
        "name": "MyValue3",
        "result": True,
    }
    assert result == expected


def test_machine_value_present_existing_change(reg_pol_mach):
    """
    Test value.present with existing incorrect value in Machine policy
    """
    result = lgpo_reg.value_present(
        name="MyValue1",
        key="SOFTWARE\\MyKey1",
        v_data="2",
        v_type="REG_DWORD",
    )
    expected = {
        "changes": {
            "new": {
                "pol": {
                    "data": 2,
                    "type": "REG_DWORD",
                },
                "reg": {
                    "data": 2,
                    "type": "REG_DWORD",
                },
            },
            "old": {
                "pol": {
                    "data": "squidward",
                    "type": "REG_SZ",
                },
                "reg": {
                    "data": "squidward",
                    "type": "REG_SZ",
                },
            },
        },
        "comment": "Registry policy value has been set",
        "name": "MyValue1",
        "result": True,
    }
    assert result == expected


def test_machine_value_present_existing_change_dword(reg_pol_mach):
    """
    Test value.present with existing incorrect value in Machine policy
    """
    result = lgpo_reg.value_present(
        name="MyValue3",
        key="SOFTWARE\\MyKey1",
        v_data=1,
        v_type="REG_DWORD",
    )
    expected = {
        "changes": {
            "new": {
                "pol": {
                    "data": 1,
                },
                "reg": {
                    "data": 1,
                },
            },
            "old": {
                "pol": {
                    "data": 0,
                },
                "reg": {
                    "data": 0,
                },
            },
        },
        "comment": "Registry policy value has been set",
        "name": "MyValue3",
        "result": True,
    }
    assert result == expected


def test_machine_value_present_existing_no_change(reg_pol_mach):
    """
    Test value.present with existing correct value in Machine policy
    """
    result = lgpo_reg.value_present(
        name="MyValue1",
        key="SOFTWARE\\MyKey1",
        v_data="squidward",
        v_type="REG_SZ",
    )
    expected = {
        "changes": {},
        "comment": "Policy value already present\nRegistry value already present",
        "name": "MyValue1",
        "result": True,
    }
    assert result == expected


def test_machine_value_present_test_true(empty_reg_pol_mach):
    """
    Test value.present with test=True in Machine policy
    """
    with patch.dict(lgpo_reg.__opts__, {"test": True}):
        result = lgpo_reg.value_present(
            name="MyValue",
            key="SOFTWARE\\MyKey1",
            v_data="1",
            v_type="REG_DWORD",
        )
    expected = {
        "changes": {},
        "comment": "Policy value will be set\nRegistry value will be set",
        "name": "MyValue",
        "result": None,
    }
    assert result == expected


def test_machine_value_present_existing_disabled(reg_pol_mach):
    """
    Test value.present with existing value that is disabled in Machine policy
    """
    result = lgpo_reg.value_present(
        name="MyValue2",
        key="SOFTWARE\\MyKey1",
        v_data="2",
        v_type="REG_DWORD",
    )
    expected = {
        "changes": {
            "new": {
                "pol": {
                    "data": 2,
                    "type": "REG_DWORD",
                },
                "reg": {
                    "data": 2,
                    "type": "REG_DWORD",
                },
            },
            "old": {
                "pol": {
                    "data": "**del.MyValue2",
                    "type": "REG_SZ",
                },
                "reg": {},
            },
        },
        "comment": "Registry policy value has been set",
        "name": "MyValue2",
        "result": True,
    }
    assert result == expected


def test_machine_value_disabled(empty_reg_pol_mach):
    """
    Test value.disabled in Machine policy
    """
    result = lgpo_reg.value_disabled(
        name="MyValue1",
        key="SOFTWARE\\MyKey1",
    )
    expected = {
        "changes": {
            "new": {
                "pol": {
                    "data": "**del.MyValue1",
                    "type": "REG_SZ",
                },
            },
            "old": {"pol": {}},
        },
        "comment": "Registry policy value disabled",
        "name": "MyValue1",
        "result": True,
    }
    assert result == expected


def test_machine_value_disabled_existing_change(reg_pol_mach):
    """
    Test value.disabled with an existing value that is not disabled in Machine
    policy
    """
    result = lgpo_reg.value_disabled(
        name="MyValue1",
        key="SOFTWARE\\MyKey1",
    )
    expected = {
        "changes": {
            "new": {
                "pol": {
                    "data": "**del.MyValue1",
                },
                "reg": {},
            },
            "old": {
                "pol": {
                    "data": "squidward",
                },
                "reg": {"data": "squidward", "type": "REG_SZ"},
            },
        },
        "comment": "Registry policy value disabled",
        "name": "MyValue1",
        "result": True,
    }
    assert result == expected


def test_machine_value_disabled_existing_no_change(reg_pol_mach):
    """
    Test value.disabled with an existing disabled value in Machine policy
    """
    result = lgpo_reg.value_disabled(
        name="MyValue2",
        key="SOFTWARE\\MyKey1",
    )
    expected = {
        "changes": {},
        "comment": "Registry policy value already disabled",
        "name": "MyValue2",
        "result": True,
    }
    assert result == expected


def test_machine_value_disabled_test_true(empty_reg_pol_mach):
    """
    Test value.disabled when test=True in Machine policy
    """
    with patch.dict(lgpo_reg.__opts__, {"test": True}):
        result = lgpo_reg.value_disabled(
            name="MyValue",
            key="SOFTWARE\\MyKey1",
        )
    expected = {
        "changes": {},
        "comment": "Policy value will be disabled",
        "name": "MyValue",
        "result": None,
    }
    assert result == expected


def test_machine_value_absent(reg_pol_mach):
    """
    Test value.absent in Machine policy
    """
    result = lgpo_reg.value_absent(name="MyValue1", key="SOFTWARE\\MyKey1")
    expected = {
        "changes": {
            "new": {"pol": {}, "reg": {}},
            "old": {
                "pol": {
                    "data": "squidward",
                    "type": "REG_SZ",
                },
                "reg": {
                    "data": "squidward",
                    "type": "REG_SZ",
                },
            },
        },
        "comment": "Registry policy value deleted",
        "name": "MyValue1",
        "result": True,
    }
    assert result == expected


def test_machine_value_absent_no_change(empty_reg_pol_mach):
    """
    Test value.absent when the value is already absent in Machine policy
    """
    result = lgpo_reg.value_absent(name="MyValue1", key="SOFTWARE\\MyKey1")
    expected = {
        "changes": {},
        "comment": "Registry policy value already deleted",
        "name": "MyValue1",
        "result": True,
    }
    assert result == expected


def test_machine_value_absent_disabled(reg_pol_mach):
    """
    Test value.absent when the value is disabled in Machine policy
    """
    result = lgpo_reg.value_absent(name="MyValue2", key="SOFTWARE\\MyKey1")
    expected = {
        "changes": {
            "new": {"pol": {}},
            "old": {
                "pol": {
                    "data": "**del.MyValue2",
                    "type": "REG_SZ",
                },
            },
        },
        "comment": "Registry policy value deleted",
        "name": "MyValue2",
        "result": True,
    }
    assert result == expected


def test_machine_value_absent_test_true(reg_pol_mach):
    """
    Test value.absent with test=True in Machine policy
    """
    with patch.dict(lgpo_reg.__opts__, {"test": True}):
        result = lgpo_reg.value_absent(name="MyValue1", key="SOFTWARE\\MyKey1")
    expected = {
        "changes": {},
        "comment": "Policy value will be deleted\nRegistry value will be deleted",
        "name": "MyValue1",
        "result": None,
    }
    assert result == expected


def test_user_value_present(empty_reg_pol_user):
    """
    Test value.present in User policy
    """
    result = lgpo_reg.value_present(
        name="MyValue",
        key="SOFTWARE\\MyKey1",
        v_data="1",
        v_type="REG_DWORD",
        policy_class="User",
    )
    expected = {
        "changes": {
            "new": {
                "pol": {
                    "data": 1,
                    "type": "REG_DWORD",
                },
                "reg": {
                    "data": 1,
                    "type": "REG_DWORD",
                },
            },
            "old": {
                "pol": {},
                "reg": {},
            },
        },
        "comment": "Registry policy value has been set",
        "name": "MyValue",
        "result": True,
    }
    assert result == expected


def test_user_value_present_similar_names(empty_reg_pol_user):
    """
    Test value.present in User policy
    """
    lgpo_reg.value_present(
        name="MyValueTwo",
        key="SOFTWARE\\MyKey1",
        v_data="1",
        v_type="REG_DWORD",
        policy_class="User",
    )
    lgpo_reg.value_present(
        name="MyValue",
        key="SOFTWARE\\MyKey1",
        v_data="1",
        v_type="REG_DWORD",
        policy_class="User",
    )
    expected = {
        "SOFTWARE\\MyKey1": {
            "MyValue": {
                "type": "REG_DWORD",
                "data": 1,
            },
            "MyValueTwo": {
                "type": "REG_DWORD",
                "data": 1,
            },
        },
    }
    result = win_lgpo_reg.read_reg_pol(policy_class="User")
    assert result == expected


def test_user_value_present_existing_change(reg_pol_user):
    """
    Test value.present with existing incorrect value in User policy
    """
    result = lgpo_reg.value_present(
        name="MyValue1",
        key="SOFTWARE\\MyKey1",
        v_data="2",
        v_type="REG_DWORD",
        policy_class="User",
    )
    expected = {
        "changes": {
            "new": {
                "pol": {
                    "data": 2,
                    "type": "REG_DWORD",
                },
                "reg": {
                    "data": 2,
                    "type": "REG_DWORD",
                },
            },
            "old": {
                "pol": {
                    "data": "squidward",
                    "type": "REG_SZ",
                },
                "reg": {
                    "data": "squidward",
                    "type": "REG_SZ",
                },
            },
        },
        "comment": "Registry policy value has been set",
        "name": "MyValue1",
        "result": True,
    }
    assert result == expected


def test_user_value_present_existing_change_dword(reg_pol_user):
    """
    Test value.present with existing incorrect value in User policy
    """
    result = lgpo_reg.value_present(
        name="MyValue3",
        key="SOFTWARE\\MyKey1",
        v_data=1,
        v_type="REG_DWORD",
        policy_class="User",
    )
    expected = {
        "changes": {
            "new": {
                "pol": {
                    "data": 1,
                },
                "reg": {
                    "data": 1,
                },
            },
            "old": {
                "pol": {
                    "data": 0,
                },
                "reg": {
                    "data": 0,
                },
            },
        },
        "comment": "Registry policy value has been set",
        "name": "MyValue3",
        "result": True,
    }
    assert result == expected


def test_user_value_present_existing_no_change(reg_pol_user):
    """
    Test value.present with existing correct value in User policy
    """
    result = lgpo_reg.value_present(
        name="MyValue1",
        key="SOFTWARE\\MyKey1",
        v_data="squidward",
        v_type="REG_SZ",
        policy_class="User",
    )
    expected = {
        "changes": {},
        "comment": "Policy value already present\nRegistry value already present",
        "name": "MyValue1",
        "result": True,
    }
    assert result == expected


def test_user_value_present_test_true(empty_reg_pol_user):
    """
    Test value.present with test=True in User policy
    """
    with patch.dict(lgpo_reg.__opts__, {"test": True}):
        result = lgpo_reg.value_present(
            name="MyValue",
            key="SOFTWARE\\MyKey1",
            v_data="1",
            v_type="REG_DWORD",
            policy_class="User",
        )
    expected = {
        "changes": {},
        "comment": "Policy value will be set\nRegistry value will be set",
        "name": "MyValue",
        "result": None,
    }
    assert result == expected


def test_user_value_present_existing_disabled(reg_pol_user):
    """
    Test value.present with existing value that is disabled in User policy
    """
    result = lgpo_reg.value_present(
        name="MyValue2",
        key="SOFTWARE\\MyKey1",
        v_data="2",
        v_type="REG_DWORD",
        policy_class="User",
    )
    expected = {
        "changes": {
            "new": {
                "pol": {
                    "data": 2,
                    "type": "REG_DWORD",
                },
                "reg": {
                    "data": 2,
                    "type": "REG_DWORD",
                },
            },
            "old": {
                "pol": {
                    "data": "**del.MyValue2",
                    "type": "REG_SZ",
                },
                "reg": {},
            },
        },
        "comment": "Registry policy value has been set",
        "name": "MyValue2",
        "result": True,
    }
    assert result == expected


def test_user_value_disabled(empty_reg_pol_user):
    """
    Test value.disabled in User policy
    """
    result = lgpo_reg.value_disabled(
        name="MyValue1", key="SOFTWARE\\MyKey1", policy_class="User"
    )
    expected = {
        "changes": {
            "new": {
                "pol": {
                    "data": "**del.MyValue1",
                    "type": "REG_SZ",
                },
            },
            "old": {"pol": {}},
        },
        "comment": "Registry policy value disabled",
        "name": "MyValue1",
        "result": True,
    }
    assert result == expected


def test_user_value_disabled_existing_change(reg_pol_user):
    """
    Test value.disabled with an existing value that is not disabled in User
    policy
    """
    result = lgpo_reg.value_disabled(
        name="MyValue1",
        key="SOFTWARE\\MyKey1",
        policy_class="User",
    )
    expected = {
        "changes": {
            "new": {
                "pol": {
                    "data": "**del.MyValue1",
                },
                "reg": {},
            },
            "old": {
                "pol": {
                    "data": "squidward",
                },
                "reg": {
                    "data": "squidward",
                    "type": "REG_SZ",
                },
            },
        },
        "comment": "Registry policy value disabled",
        "name": "MyValue1",
        "result": True,
    }
    assert result == expected


def test_user_value_disabled_existing_no_change(reg_pol_user):
    """
    Test value.disabled with an existing disabled value in User policy
    """
    result = lgpo_reg.value_disabled(
        name="MyValue2",
        key="SOFTWARE\\MyKey1",
        policy_class="User",
    )
    expected = {
        "changes": {},
        "comment": "Registry policy value already disabled",
        "name": "MyValue2",
        "result": True,
    }
    assert result == expected


def test_user_value_disabled_test_true(empty_reg_pol_user):
    """
    Test value.disabled when test=True in User policy
    """
    with patch.dict(lgpo_reg.__opts__, {"test": True}):
        result = lgpo_reg.value_disabled(
            name="MyValue",
            key="SOFTWARE\\MyKey1",
            policy_class="User",
        )
    expected = {
        "changes": {},
        "comment": "Policy value will be disabled",
        "name": "MyValue",
        "result": None,
    }
    assert result == expected


def test_user_value_absent(reg_pol_user):
    """
    Test value.absent in User policy
    """
    result = lgpo_reg.value_absent(
        name="MyValue1",
        key="SOFTWARE\\MyKey1",
        policy_class="User",
    )
    expected = {
        "changes": {
            "new": {
                "pol": {},
                "reg": {},
            },
            "old": {
                "pol": {
                    "data": "squidward",
                    "type": "REG_SZ",
                },
                "reg": {
                    "data": "squidward",
                    "type": "REG_SZ",
                },
            },
        },
        "comment": "Registry policy value deleted",
        "name": "MyValue1",
        "result": True,
    }
    assert result == expected


def test_user_value_absent_no_change(empty_reg_pol_user):
    """
    Test value.absent when the value is already absent in User policy
    """
    result = lgpo_reg.value_absent(
        name="MyValue1",
        key="SOFTWARE\\MyKey1",
        policy_class="User",
    )
    expected = {
        "changes": {},
        "comment": "Registry policy value already deleted",
        "name": "MyValue1",
        "result": True,
    }
    assert result == expected


def test_user_value_absent_disabled(reg_pol_user):
    """
    Test value.absent when the value is disabled in User policy
    """
    result = lgpo_reg.value_absent(
        name="MyValue2",
        key="SOFTWARE\\MyKey1",
        policy_class="User",
    )
    expected = {
        "changes": {
            "new": {"pol": {}},
            "old": {
                "pol": {
                    "data": "**del.MyValue2",
                    "type": "REG_SZ",
                },
            },
        },
        "comment": "Registry policy value deleted",
        "name": "MyValue2",
        "result": True,
    }
    assert result == expected


def test_user_value_absent_test_true(reg_pol_user):
    """
    Test value.absent with test=True in User policy
    """
    with patch.dict(lgpo_reg.__opts__, {"test": True}):
        result = lgpo_reg.value_absent(
            name="MyValue1",
            key="SOFTWARE\\MyKey1",
            policy_class="User",
        )
    expected = {
        "changes": {},
        "comment": "Policy value will be deleted\nRegistry value will be deleted",
        "name": "MyValue1",
        "result": None,
    }
    assert result == expected
