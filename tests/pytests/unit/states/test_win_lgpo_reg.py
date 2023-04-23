import pytest

import salt.modules.win_lgpo_reg as win_lgpo_reg
import salt.states.win_lgpo_reg as lgpo_reg
import salt.utils.files
import salt.utils.win_lgpo_reg
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
        },
    }


@pytest.fixture
def empty_reg_pol():
    class_info = salt.utils.win_lgpo_reg.CLASS_INFO
    reg_pol_file = class_info["Machine"]["policy_path"]
    with salt.utils.files.fopen(reg_pol_file, "wb") as f:
        f.write(salt.utils.win_lgpo_reg.REG_POL_HEADER.encode("utf-16-le"))
    yield
    with salt.utils.files.fopen(reg_pol_file, "wb") as f:
        f.write(salt.utils.win_lgpo_reg.REG_POL_HEADER.encode("utf-16-le"))


@pytest.fixture
def reg_pol():
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
        },
        r"SOFTWARE\MyKey2": {
            "MyValue3": {
                "data": ["spongebob", "squarepants"],
                "type": "REG_MULTI_SZ",
            },
        },
    }
    win_lgpo_reg.write_reg_pol(data_to_write)
    yield
    class_info = salt.utils.win_lgpo_reg.CLASS_INFO
    reg_pol_file = class_info["Machine"]["policy_path"]
    with salt.utils.files.fopen(reg_pol_file, "wb") as f:
        f.write(salt.utils.win_lgpo_reg.REG_POL_HEADER.encode("utf-16-le"))


def test_virtual_name():
    assert lgpo_reg.__virtual__() == "lgpo_reg"


def test_value_present(empty_reg_pol):
    """
    Test value.present
    """
    result = lgpo_reg.value_present(
        name="MyValue",
        key="SOFTWARE\\MyKey",
        v_data="1",
        v_type="REG_DWORD",
    )
    expected = {
        "changes": {
            "new": {
                "name": "MyValue",
                "key": "SOFTWARE\\MyKey",
                "data": 1,
                "type": "REG_DWORD",
            },
            "old": {},
        },
        "comment": "Registry.pol value has been set",
        "name": "MyValue",
        "result": True,
    }
    assert result == expected


def test_value_present_existing_change(reg_pol):
    """
    Test value.present with existing incorrect value
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
                "name": "MyValue1",
                "key": "SOFTWARE\\MyKey1",
                "data": 2,
                "type": "REG_DWORD",
            },
            "old": {
                "name": "MyValue1",
                "key": "SOFTWARE\\MyKey1",
                "data": "squidward",
                "type": "REG_SZ",
            },
        },
        "comment": "Registry.pol value has been set",
        "name": "MyValue1",
        "result": True,
    }
    assert result == expected


def test_value_present_existing_no_change(reg_pol):
    """
    Test value.present with existing correct value
    """
    result = lgpo_reg.value_present(
        name="MyValue1",
        key="SOFTWARE\\MyKey1",
        v_data="squidward",
        v_type="REG_SZ",
    )
    expected = {
        "changes": {},
        "comment": "Registry.pol value already present",
        "name": "MyValue1",
        "result": True,
    }
    assert result == expected


def test_value_present_test_true(empty_reg_pol):
    """
    Test value.present with test=True
    """
    with patch.dict(lgpo_reg.__opts__, {"test": True}):
        result = lgpo_reg.value_present(
            name="MyValue",
            key="SOFTWARE\\MyKey",
            v_data="1",
            v_type="REG_DWORD",
        )
    expected = {
        "changes": {},
        "comment": "Registry.pol value will be set",
        "name": "MyValue",
        "result": None,
    }
    assert result == expected


def test_value_present_existing_disabled(reg_pol):
    """
    Test value.present with existing value that is disabled
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
                "data": 2,
                "key": "SOFTWARE\\MyKey1",
                "name": "MyValue2",
                "type": "REG_DWORD",
            },
            "old": {
                "data": "**del.MyValue2",
                "key": "SOFTWARE\\MyKey1",
                "name": "MyValue2",
                "type": "REG_SZ",
            },
        },
        "comment": "Registry.pol value has been set",
        "name": "MyValue2",
        "result": True,
    }
    assert result == expected


def test_value_disabled(empty_reg_pol):
    """
    Test value.disabled
    """
    result = lgpo_reg.value_disabled(
        name="MyValue1",
        key="SOFTWARE\\MyKey1",
    )
    expected = {
        "changes": {
            "new": {
                "data": "**del.MyValue1",
                "key": "SOFTWARE\\MyKey1",
                "name": "MyValue1",
                "type": "REG_SZ",
            },
            "old": {},
        },
        "comment": "Registry.pol value enabled",
        "name": "MyValue1",
        "result": True,
    }
    assert result == expected


def test_value_disabled_existing_change(reg_pol):
    """
    Test value.disabled with an existing value that is not disabled
    """
    result = lgpo_reg.value_disabled(
        name="MyValue1",
        key="SOFTWARE\\MyKey1",
    )
    expected = {
        "changes": {
            "new": {
                "data": "**del.MyValue1",
                "key": "SOFTWARE\\MyKey1",
                "name": "MyValue1",
            },
            "old": {
                "data": "squidward",
                "key": "SOFTWARE\\MyKey1",
                "name": "MyValue1",
            },
        },
        "comment": "Registry.pol value enabled",
        "name": "MyValue1",
        "result": True,
    }
    assert result == expected


def test_value_disabled_existing_no_change(reg_pol):
    """
    Test value.disabled with an existing disabled value
    """
    result = lgpo_reg.value_disabled(
        name="MyValue2",
        key="SOFTWARE\\MyKey1",
    )
    expected = {
        "changes": {},
        "comment": "Registry.pol value already disabled",
        "name": "MyValue2",
        "result": True,
    }
    assert result == expected


def test_value_disabled_test_true(empty_reg_pol):
    """
    Test value.disabled when test=True
    """
    with patch.dict(lgpo_reg.__opts__, {"test": True}):
        result = lgpo_reg.value_disabled(
            name="MyValue",
            key="SOFTWARE\\MyKey",
        )
    expected = {
        "changes": {},
        "comment": "Registry.pol value will be disabled",
        "name": "MyValue",
        "result": None,
    }
    assert result == expected


def test_value_absent(reg_pol):
    """
    Test value.absent
    """
    result = lgpo_reg.value_absent(name="MyValue1", key="SOFTWARE\\MyKey1")
    expected = {
        "changes": {
            "new": {},
            "old": {
                "data": "squidward",
                "key": "SOFTWARE\\MyKey1",
                "name": "MyValue1",
                "type": "REG_SZ",
            },
        },
        "comment": "Registry.pol value deleted",
        "name": "MyValue1",
        "result": True,
    }
    assert result == expected


def test_value_absent_no_change(empty_reg_pol):
    """
    Test value.absent when the value is already absent
    """
    result = lgpo_reg.value_absent(name="MyValue1", key="SOFTWARE\\MyKey1")
    expected = {
        "changes": {},
        "comment": "Registry.pol value already absent",
        "name": "MyValue1",
        "result": True,
    }
    assert result == expected


def test_value_absent_disabled(reg_pol):
    """
    Test value.absent when the value is disabled
    """
    result = lgpo_reg.value_absent(name="MyValue2", key="SOFTWARE\\MyKey1")
    expected = {
        "changes": {
            "new": {},
            "old": {
                "data": "**del.MyValue2",
                "key": "SOFTWARE\\MyKey1",
                "name": "MyValue2",
                "type": "REG_SZ",
            },
        },
        "comment": "Registry.pol value deleted",
        "name": "MyValue2",
        "result": True,
    }
    assert result == expected


def test_value_absent_test_true(reg_pol):
    """
    Test value.absent with test=True
    """
    with patch.dict(lgpo_reg.__opts__, {"test": True}):
        result = lgpo_reg.value_absent(name="MyValue1", key="SOFTWARE\\MyKey1")
    expected = {
        "changes": {},
        "comment": "Registry.pol value will be deleted",
        "name": "MyValue1",
        "result": None,
    }
    assert result == expected
