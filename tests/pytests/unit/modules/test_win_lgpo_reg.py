import pathlib
import sys

import pytest

import salt.modules.win_file as win_file
import salt.modules.win_lgpo_reg as lgpo_reg
import salt.utils.files
import salt.utils.win_dacl
import salt.utils.win_lgpo_reg
import salt.utils.win_reg
from salt.exceptions import SaltInvocationError
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.destructive_test,
]


@pytest.fixture
def configure_loader_modules():
    return {
        win_file: {
            "__utils__": {
                "dacl.set_perms": salt.utils.win_dacl.set_perms,
                "dacl.set_permissions": salt.utils.win_dacl.set_permissions,
            },
        },
    }


@pytest.fixture
def empty_reg_pol_mach():
    class_info = salt.utils.win_lgpo_reg.CLASS_INFO
    reg_pol_file = pathlib.Path(class_info["Machine"]["policy_path"])
    if not reg_pol_file.parent.exists():
        reg_pol_file.parent.mkdir(parents=True)
    with salt.utils.files.fopen(str(reg_pol_file), "wb") as f:
        f.write(salt.utils.win_lgpo_reg.REG_POL_HEADER.encode("utf-16-le"))
    salt.utils.win_reg.delete_key_recursive(hive="HKLM", key="SOFTWARE\\MyKey1")
    salt.utils.win_reg.delete_key_recursive(hive="HKLM", key="SOFTWARE\\MyKey2")
    yield
    salt.utils.win_reg.delete_key_recursive(hive="HKLM", key="SOFTWARE\\MyKey1")
    salt.utils.win_reg.delete_key_recursive(hive="HKLM", key="SOFTWARE\\MyKey2")
    with salt.utils.files.fopen(str(reg_pol_file), "wb") as f:
        f.write(salt.utils.win_lgpo_reg.REG_POL_HEADER.encode("utf-16-le"))


@pytest.fixture
def empty_reg_pol_user():
    class_info = salt.utils.win_lgpo_reg.CLASS_INFO
    reg_pol_file = pathlib.Path(class_info["User"]["policy_path"])
    if not reg_pol_file.parent.exists():
        reg_pol_file.parent.mkdir(parents=True)
    with salt.utils.files.fopen(str(reg_pol_file), "wb") as f:
        f.write(salt.utils.win_lgpo_reg.REG_POL_HEADER.encode("utf-16-le"))
    salt.utils.win_reg.delete_key_recursive(hive="HKCU", key="SOFTWARE\\MyKey1")
    salt.utils.win_reg.delete_key_recursive(hive="HKCU", key="SOFTWARE\\MyKey2")
    yield
    salt.utils.win_reg.delete_key_recursive(hive="HKCU", key="SOFTWARE\\MyKey1")
    salt.utils.win_reg.delete_key_recursive(hive="HKCU", key="SOFTWARE\\MyKey2")
    with salt.utils.files.fopen(str(reg_pol_file), "wb") as f:
        f.write(salt.utils.win_lgpo_reg.REG_POL_HEADER.encode("utf-16-le"))


@pytest.fixture
def pol_data_mach():
    return {
        "SOFTWARE\\MyKey1": {
            "MyValue1": {"data": "squidward", "type": "REG_SZ"},
            "**del.MyValue2": {"data": " ", "type": "REG_SZ"},
            "MyValue3.exe": {"data": "dot_value", "type": "REG_SZ"},
        },
        "SOFTWARE\\MyKey2": {
            "MyValue3": {"data": ["spongebob", "squarepants"], "type": "REG_MULTI_SZ"},
        },
    }


@pytest.fixture
def reg_pol_mach(pol_data_mach):
    lgpo_reg.write_reg_pol(pol_data_mach)
    salt.utils.win_reg.set_value(
        hive="HKLM",
        key="SOFTWARE\\MyKey1",
        vname="MyValue1",
        vdata="squidward",
        vtype="REG_SZ",
    )
    assert salt.utils.win_reg.value_exists(
        hive="HKLM", key="SOFTWARE\\MyKey1", vname="MyValue1"
    )
    salt.utils.win_reg.set_value(
        hive="HKLM",
        key="SOFTWARE\\MyKey1",
        vname="MyValue3.exe",
        vdata="dot_value",
        vtype="REG_SZ",
    )
    assert salt.utils.win_reg.value_exists(
        hive="HKLM", key="SOFTWARE\\MyKey1", vname="MyValue3.exe"
    )
    salt.utils.win_reg.set_value(
        hive="HKLM",
        key="SOFTWARE\\MyKey2",
        vname="MyValue3",
        vdata=["spongebob", "squarepants"],
        vtype="REG_MULTI_SZ",
    )
    assert salt.utils.win_reg.value_exists(
        hive="HKLM", key="SOFTWARE\\MyKey2", vname="MyValue3"
    )
    yield
    salt.utils.win_reg.delete_key_recursive(hive="HKLM", key="SOFTWARE\\MyKey1")
    salt.utils.win_reg.delete_key_recursive(hive="HKLM", key="SOFTWARE\\MyKey2")
    class_info = salt.utils.win_lgpo_reg.CLASS_INFO
    reg_pol_file = class_info["Machine"]["policy_path"]
    with salt.utils.files.fopen(reg_pol_file, "wb") as f:
        f.write(salt.utils.win_lgpo_reg.REG_POL_HEADER.encode("utf-16-le"))


@pytest.fixture
def pol_data_user():
    return {
        "SOFTWARE\\MyKey1": {
            "MyValue1": {"data": "squidward", "type": "REG_SZ"},
            "**del.MyValue2": {"data": " ", "type": "REG_SZ"},
            "MyValue3.exe": {"data": "dot_value", "type": "REG_SZ"},
        },
        "SOFTWARE\\MyKey2": {
            "MyValue3": {"data": ["spongebob", "squarepants"], "type": "REG_MULTI_SZ"},
        },
    }


@pytest.fixture
def reg_pol_user(pol_data_user):
    lgpo_reg.write_reg_pol(pol_data_user, policy_class="User")
    salt.utils.win_reg.set_value(
        hive="HKCU",
        key="SOFTWARE\\MyKey1",
        vname="MyValue1",
        vdata="squidward",
        vtype="REG_SZ",
    )
    assert salt.utils.win_reg.value_exists(
        hive="HKCU", key="SOFTWARE\\MyKey1", vname="MyValue1"
    )
    salt.utils.win_reg.set_value(
        hive="HKCU",
        key="SOFTWARE\\MyKey1",
        vname="MyValue3.exe",
        vdata="dot_value",
        vtype="REG_SZ",
    )
    assert salt.utils.win_reg.value_exists(
        hive="HKCU", key="SOFTWARE\\MyKey1", vname="MyValue3.exe"
    )
    salt.utils.win_reg.set_value(
        hive="HKCU",
        key="SOFTWARE\\MyKey2",
        vname="MyValue3",
        vdata=["spongebob", "squarepants"],
        vtype="REG_MULTI_SZ",
    )
    assert salt.utils.win_reg.value_exists(
        hive="HKCU", key="SOFTWARE\\MyKey2", vname="MyValue3"
    )
    yield
    salt.utils.win_reg.delete_key_recursive(hive="HKCU", key="SOFTWARE\\MyKey1")
    salt.utils.win_reg.delete_key_recursive(hive="HKCU", key="SOFTWARE\\MyKey2")
    assert not salt.utils.win_reg.key_exists(hive="HKCU", key="SOFTWARE\\MyKey1")
    assert not salt.utils.win_reg.key_exists(hive="HKCU", key="SOFTWARE\\MyKey2")
    class_info = salt.utils.win_lgpo_reg.CLASS_INFO
    reg_pol_file = class_info["User"]["policy_path"]
    with salt.utils.files.fopen(reg_pol_file, "wb") as f:
        f.write(salt.utils.win_lgpo_reg.REG_POL_HEADER.encode("utf-16-le"))


def test_invalid_policy_class_delete_value():
    pytest.raises(
        SaltInvocationError,
        lgpo_reg.delete_value,
        key="",
        v_name="",
        policy_class="Invalid",
    )


def test_invalid_policy_class_disable_value():
    pytest.raises(
        SaltInvocationError,
        lgpo_reg.disable_value,
        key="",
        v_name="",
        policy_class="Invalid",
    )


def test_invalid_policy_class_get_key():
    pytest.raises(SaltInvocationError, lgpo_reg.get_key, key="", policy_class="Invalid")


def test_invalid_policy_class_get_value():
    pytest.raises(
        SaltInvocationError,
        lgpo_reg.get_value,
        key="",
        v_name="",
        policy_class="Invalid",
    )


def test_invalid_policy_class_read_reg_pol():
    pytest.raises(SaltInvocationError, lgpo_reg.read_reg_pol, policy_class="Invalid")


def test_invalid_policy_class_set_value():
    pytest.raises(
        SaltInvocationError,
        lgpo_reg.set_value,
        key="",
        v_name="",
        v_data="",
        policy_class="Invalid",
    )


def test_invalid_policy_class_write_reg_pol():
    pytest.raises(
        SaltInvocationError, lgpo_reg.write_reg_pol, data={}, policy_class="Invalid"
    )


def test_set_value_invalid_reg_type():
    pytest.raises(
        SaltInvocationError,
        lgpo_reg.set_value,
        key="",
        v_name="",
        v_data="",
        v_type="REG_INVALID",
    )


def test_set_value_invalid_reg_sz():
    pytest.raises(
        SaltInvocationError,
        lgpo_reg.set_value,
        key="",
        v_name="",
        v_data=[],
        v_type="REG_SZ",
    )


def test_set_value_invalid_reg_multi_sz():
    pytest.raises(
        SaltInvocationError,
        lgpo_reg.set_value,
        key="",
        v_name="",
        v_data=1,
        v_type="REG_MULTI_SZ",
    )


def test_set_value_invalid_reg_dword():
    pytest.raises(
        SaltInvocationError, lgpo_reg.set_value, key="", v_name="", v_data="string"
    )


def test_mach_read_reg_pol(empty_reg_pol_mach):
    expected = {}
    result = lgpo_reg.read_reg_pol()
    assert result == expected


def test_mach_write_reg_pol(empty_reg_pol_mach):
    data_to_write = {
        r"SOFTWARE\MyKey": {
            "MyValue": {
                "data": "string",
                "type": "REG_SZ",
            },
        },
    }
    lgpo_reg.write_reg_pol(data_to_write)
    result = lgpo_reg.read_reg_pol()
    assert result == data_to_write


@pytest.mark.parametrize(
    "name,expected",
    [
        ("MyValue", {}),
        ("MyValue1", {"data": "squidward", "type": "REG_SZ"}),
        ("MyValue2", {"data": "**del.MyValue2", "type": "REG_SZ"}),
        ("MyValue3.exe", {"data": "dot_value", "type": "REG_SZ"}),
    ],
)
def test_mach_get_value(reg_pol_mach, name, expected):
    result = lgpo_reg.get_value(key="SOFTWARE\\MyKey1", v_name=name)
    assert result == expected


def test_mach_get_key(reg_pol_mach):
    expected = {
        "MyValue3": {
            "data": ["spongebob", "squarepants"],
            "type": "REG_MULTI_SZ",
        },
    }
    result = lgpo_reg.get_key(key="SOFTWARE\\MyKey2")
    assert result == expected


def test_mach_set_value(empty_reg_pol_mach):
    key = "SOFTWARE\\MyKey"
    v_name = "MyValue"
    # Test command return
    result = lgpo_reg.set_value(key=key, v_name=v_name, v_data="1")
    assert result is True
    # Test value actually set in Registry.pol
    expected = {"data": 1, "type": "REG_DWORD"}
    result = lgpo_reg.get_value(key=key, v_name=v_name)
    assert result == expected
    # Test that the registry value has been set
    expected = {
        "hive": "HKLM",
        "key": key,
        "vname": v_name,
        "vdata": 1,
        "vtype": "REG_DWORD",
        "success": True,
    }
    result = salt.utils.win_reg.read_value(hive="HKLM", key=key, vname=v_name)
    assert result == expected


def test_mach_set_value_existing_change(reg_pol_mach):
    expected = {"data": 1, "type": "REG_DWORD"}
    key = "SOFTWARE\\MyKey"
    v_name = "MyValue1"
    lgpo_reg.set_value(key=key, v_name=v_name, v_data="1")
    result = lgpo_reg.get_value(key=key, v_name=v_name)
    assert result == expected
    expected = {
        "hive": "HKLM",
        "key": key,
        "vname": v_name,
        "vdata": 1,
        "vtype": "REG_DWORD",
        "success": True,
    }
    result = salt.utils.win_reg.read_value(hive="HKLM", key=key, vname=v_name)
    assert result == expected


def test_mach_set_value_existing_no_change(reg_pol_mach):
    expected = {"data": "squidward", "type": "REG_SZ"}
    key = "SOFTWARE\\MyKey"
    v_name = "MyValue1"
    lgpo_reg.set_value(key=key, v_name=v_name, v_data="squidward", v_type="REG_SZ")
    result = lgpo_reg.get_value(key=key, v_name=v_name)
    assert result == expected


def test_mach_disable_value(reg_pol_mach):
    key = "SOFTWARE\\MyKey1"
    # Test that the command completed successfully
    result = lgpo_reg.disable_value(key=key, v_name="MyValue1")
    assert result is True
    # Test that the value was actually set in Registry.pol
    expected = {
        "**del.MyValue1": {"data": " ", "type": "REG_SZ"},
        "**del.MyValue2": {"data": " ", "type": "REG_SZ"},
        "MyValue3.exe": {"data": "dot_value", "type": "REG_SZ"},
    }
    result = lgpo_reg.get_key(key=key)
    assert result == expected
    # Test that the registry value has been removed
    result = salt.utils.win_reg.value_exists(hive="HKLM", key=key, vname="MyValue1")
    assert result is False


def test_mach_disable_value_no_change(reg_pol_mach):
    expected = {
        "MyValue1": {"data": "squidward", "type": "REG_SZ"},
        "**del.MyValue2": {"data": " ", "type": "REG_SZ"},
        "MyValue3.exe": {"data": "dot_value", "type": "REG_SZ"},
    }
    key = "SOFTWARE\\MyKey1"
    lgpo_reg.disable_value(key=key, v_name="MyValue2")
    result = lgpo_reg.get_key(key=key)
    assert result == expected


def test_mach_delete_value_existing(reg_pol_mach):
    key = "SOFTWARE\\MyKey1"
    # Test that the command completes successfully
    result = lgpo_reg.delete_value(key=key, v_name="MyValue1")
    assert result is True
    # Test that the value is actually removed from Registry.pol
    expected = {
        "**del.MyValue2": {"data": " ", "type": "REG_SZ"},
        "MyValue3.exe": {"data": "dot_value", "type": "REG_SZ"},
    }
    result = lgpo_reg.get_key(key=key)
    assert result == expected
    # Test that the registry entry has been removed
    result = salt.utils.win_reg.value_exists(hive="HKLM", key=key, vname="MyValue2")
    assert result is False


def test_mach_delete_value_dot_value(reg_pol_mach):
    key = "SOFTWARE\\MyKey1"
    # Test that the command completes successfully
    result = lgpo_reg.delete_value(key=key, v_name="MyValue3.exe")
    assert result is True
    # Test that the value is actually removed from Registry.pol
    expected = {
        "MyValue1": {"data": "squidward", "type": "REG_SZ"},
        "**del.MyValue2": {"data": " ", "type": "REG_SZ"},
    }
    result = lgpo_reg.get_key(key=key)
    assert result == expected
    # Test that the registry entry has been removed
    result = salt.utils.win_reg.value_exists(hive="HKLM", key=key, vname="MyValue3.exe")
    assert result is False


def test_mach_delete_value_no_change(empty_reg_pol_mach):
    expected = {}
    key = "SOFTWARE\\MyKey1"
    lgpo_reg.delete_value(key=key, v_name="MyValue2")
    result = lgpo_reg.get_key(key=key)
    assert result == expected


def test_user_read_reg_pol(empty_reg_pol_user):
    expected = {}
    result = lgpo_reg.read_reg_pol(policy_class="User")
    assert result == expected


def test_user_write_reg_pol(empty_reg_pol_user):
    data_to_write = {
        r"SOFTWARE\MyKey": {
            "MyValue": {
                "data": "string",
                "type": "REG_SZ",
            },
        },
    }
    lgpo_reg.write_reg_pol(data_to_write, policy_class="User")
    result = lgpo_reg.read_reg_pol(policy_class="User")
    assert result == data_to_write


@pytest.mark.parametrize(
    "name,expected",
    [
        ("MyValue", {}),
        ("MyValue1", {"data": "squidward", "type": "REG_SZ"}),
        ("MyValue2", {"data": "**del.MyValue2", "type": "REG_SZ"}),
        ("MyValue3.exe", {"data": "dot_value", "type": "REG_SZ"}),
    ],
)
def test_user_get_value(reg_pol_user, name, expected):
    result = lgpo_reg.get_value(
        key="SOFTWARE\\MyKey1",
        v_name=name,
        policy_class="User",
    )
    assert result == expected


def test_user_get_key(reg_pol_user):
    expected = {
        "MyValue3": {
            "data": ["spongebob", "squarepants"],
            "type": "REG_MULTI_SZ",
        },
    }
    result = lgpo_reg.get_key(key="SOFTWARE\\MyKey2", policy_class="User")
    assert result == expected


def test_user_set_value(empty_reg_pol_user):
    key = "SOFTWARE\\MyKey"
    v_name = "MyValue"
    # Test command return
    result = lgpo_reg.set_value(
        key=key,
        v_name=v_name,
        v_data="1",
        policy_class="User",
    )
    assert result is True
    # Test value actually set in Registry.pol
    expected = {"data": 1, "type": "REG_DWORD"}
    result = lgpo_reg.get_value(key=key, v_name=v_name, policy_class="User")
    assert result == expected
    # Test that the registry value has not been set
    result = salt.utils.win_reg.value_exists(hive="HKCU", key=key, vname=v_name)
    assert result is False


def test_user_set_value_existing_change(reg_pol_user):
    expected = {"data": 1, "type": "REG_DWORD"}
    key = "SOFTWARE\\MyKey"
    v_name = "MyValue1"
    lgpo_reg.set_value(key=key, v_name=v_name, v_data="1", policy_class="User")
    result = lgpo_reg.get_value(key=key, v_name=v_name, policy_class="User")
    assert result == expected
    # Test that the registry value has not been set
    result = salt.utils.win_reg.value_exists(hive="HKCU", key=key, vname=v_name)
    assert result is False


def test_user_set_value_existing_no_change(reg_pol_user):
    expected = {"data": "squidward", "type": "REG_SZ"}
    key = "SOFTWARE\\MyKey"
    v_name = "MyValue1"
    lgpo_reg.set_value(
        key=key,
        v_name=v_name,
        v_data="squidward",
        v_type="REG_SZ",
        policy_class="User",
    )
    result = lgpo_reg.get_value(key=key, v_name=v_name, policy_class="User")
    assert result == expected


def test_user_disable_value(reg_pol_user):
    key = "SOFTWARE\\MyKey1"
    # Test that the command completed successfully
    result = lgpo_reg.disable_value(key=key, v_name="MyValue1", policy_class="User")
    assert result is True
    # Test that the value was actually set in Registry.pol
    expected = {
        "**del.MyValue1": {"data": " ", "type": "REG_SZ"},
        "**del.MyValue2": {"data": " ", "type": "REG_SZ"},
        "MyValue3.exe": {"data": "dot_value", "type": "REG_SZ"},
    }
    result = lgpo_reg.get_key(key=key, policy_class="User")
    assert result == expected
    # Test that the registry value has not been removed
    result = salt.utils.win_reg.value_exists(hive="HKCU", key=key, vname="MyValue1")
    assert result is True


def test_user_disable_value_no_change(reg_pol_user):
    expected = {
        "MyValue1": {"data": "squidward", "type": "REG_SZ"},
        "**del.MyValue2": {"data": " ", "type": "REG_SZ"},
        "MyValue3.exe": {"data": "dot_value", "type": "REG_SZ"},
    }
    key = "SOFTWARE\\MyKey1"
    lgpo_reg.disable_value(key=key, v_name="MyValue2", policy_class="User")
    result = lgpo_reg.get_key(key=key, policy_class="User")
    assert result == expected


def test_user_delete_value_existing(reg_pol_user):
    key = "SOFTWARE\\MyKey1"
    # Test that the command completes successfully
    result = lgpo_reg.delete_value(key=key, v_name="MyValue1", policy_class="User")
    assert result is True
    # Test that the value is actually removed from Registry.pol
    expected = {
        "**del.MyValue2": {"data": " ", "type": "REG_SZ"},
        "MyValue3.exe": {"data": "dot_value", "type": "REG_SZ"},
    }
    result = lgpo_reg.get_key(key=key, policy_class="User")
    assert result == expected
    # Test that the registry entry has not been removed
    result = salt.utils.win_reg.value_exists(hive="HKCU", key=key, vname="MyValue1")
    assert result is True


def test_user_delete_value_dot_value(reg_pol_user):
    key = "SOFTWARE\\MyKey1"
    # Test that the command completes successfully
    result = lgpo_reg.delete_value(key=key, v_name="MyValue3.exe", policy_class="User")
    assert result is True
    # Test that the value is actually removed from Registry.pol
    expected = {
        "MyValue1": {"data": "squidward", "type": "REG_SZ"},
        "**del.MyValue2": {"data": " ", "type": "REG_SZ"},
    }
    result = lgpo_reg.get_key(key=key, policy_class="User")
    assert result == expected
    # Test that the registry entry has not been removed
    result = salt.utils.win_reg.value_exists(hive="HKCU", key=key, vname="MyValue3.exe")
    assert result is True


def test_user_delete_value_no_change(empty_reg_pol_user):
    expected = {}
    key = "SOFTWARE\\MyKey1"
    lgpo_reg.delete_value(key=key, v_name="MyValue2", policy_class="User")
    result = lgpo_reg.get_key(key=key, policy_class="User")
    assert result == expected


@pytest.mark.parametrize(
    "key, v_name, expected",
    [
        ("SOFTWARE\\MyKey1", "MyValue", ("SOFTWARE\\MyKey1", "")),
        ("SOFTWARE\\MyKey1", "Value1", ("SOFTWARE\\MyKey1", "")),
        ("SOFTWARE\\MyKey1", "MyValue1", ("SOFTWARE\\MyKey1", "MyValue1")),
        ("SOFTWARE\\MyKey1", "MyValue2", ("SOFTWARE\\MyKey1", "**del.MyValue2")),
        ("SOFTWARE\\MyKey1", "MyValue3.exe", ("SOFTWARE\\MyKey1", "MyValue3.exe")),
    ],
)
def test__find_value(pol_data_mach, key, v_name, expected):
    result = lgpo_reg._find_value(pol_data=pol_data_mach, key=key, v_name=v_name)
    assert result == expected


# ---------------------------------------------------------------------------
# get_rsop_value tests
# ---------------------------------------------------------------------------


def test_get_rsop_value_wmi_unavailable():
    """When the wmi module is not importable, return empty dict."""
    with patch.dict(sys.modules, {"wmi": None}):
        result = lgpo_reg.get_rsop_value(key="SOFTWARE\\MyKey", v_name="MyValue")
    assert result == {}


def test_get_rsop_value_not_found():
    """When WMI returns no RSoP results, return empty dict."""
    wmi_mod = MagicMock()
    wmi_mod.WMI.return_value.query.return_value = []
    with patch.dict(sys.modules, {"wmi": wmi_mod}):
        result = lgpo_reg.get_rsop_value(key="SOFTWARE\\MyKey", v_name="MyValue")
    assert result == {}


def test_get_rsop_value_local_gpo():
    """When the winning GPO is the local policy, domain_managed should be False."""
    mock_setting = MagicMock()
    mock_setting.GPOID = lgpo_reg.LOCAL_POLICY_GPO_ID
    mock_setting.ValueType = 4  # REG_DWORD
    mock_setting.Value = 1
    mock_setting.Precedence = 1

    wmi_mod = MagicMock()
    conn = MagicMock()
    wmi_mod.WMI.return_value = conn
    # First call: RSOP_RegistryPolicySetting; second call: RSOP_GPO (not found)
    conn.query.side_effect = [[mock_setting], []]

    with patch.dict(sys.modules, {"wmi": wmi_mod}):
        result = lgpo_reg.get_rsop_value(key="SOFTWARE\\MyKey", v_name="MyValue")

    assert result["domain_managed"] is False
    assert result["gpo_id"] == lgpo_reg.LOCAL_POLICY_GPO_ID
    assert result["type"] == "REG_DWORD"
    assert result["data"] == 1


def test_get_rsop_value_domain_gpo():
    """When the winning GPO is a domain GPO, domain_managed should be True."""
    domain_gpo_id = "{12345678-1234-1234-1234-123456789012}"
    domain_gpo_name = "Default Domain Policy"

    mock_setting = MagicMock()
    mock_setting.GPOID = domain_gpo_id
    mock_setting.ValueType = 4  # REG_DWORD
    mock_setting.Value = 3
    mock_setting.Precedence = 1

    mock_gpo = MagicMock()
    mock_gpo.Name = domain_gpo_name

    wmi_mod = MagicMock()
    conn = MagicMock()
    wmi_mod.WMI.return_value = conn
    conn.query.side_effect = [[mock_setting], [mock_gpo]]

    with patch.dict(sys.modules, {"wmi": wmi_mod}):
        result = lgpo_reg.get_rsop_value(key="SOFTWARE\\MyKey", v_name="MyValue")

    assert result["domain_managed"] is True
    assert result["gpo_id"] == domain_gpo_id
    assert result["gpo_name"] == domain_gpo_name
    assert result["precedence"] == 1


# ---------------------------------------------------------------------------
# Module-level domain GPO log.warning tests
# ---------------------------------------------------------------------------


def test_set_value_warns_on_domain_gpo(empty_reg_pol_mach):
    """set_value should log.warning when a domain GPO manages the key/value."""
    domain_rsop = {
        "domain_managed": True,
        "gpo_name": "Default Domain Policy",
        "gpo_id": "{12345678-1234-1234-1234-123456789012}",
    }
    with patch.object(lgpo_reg, "get_rsop_value", return_value=domain_rsop), patch(
        "salt.modules.win_lgpo_reg.log"
    ) as mock_log:
        lgpo_reg.set_value(key="SOFTWARE\\MyKey1", v_name="MyValue", v_data=1)
    mock_log.warning.assert_called_once()
    assert "Domain GPO" in mock_log.warning.call_args[0][0]


def test_set_value_no_warn_local_gpo(empty_reg_pol_mach):
    """set_value should NOT log.warning when a local GPO manages the key/value."""
    with patch.object(
        lgpo_reg, "get_rsop_value", return_value={"domain_managed": False}
    ), patch("salt.modules.win_lgpo_reg.log") as mock_log:
        lgpo_reg.set_value(key="SOFTWARE\\MyKey1", v_name="MyValue", v_data=1)
    mock_log.warning.assert_not_called()


def test_disable_value_warns_on_domain_gpo(reg_pol_mach):
    """disable_value should log.warning when a domain GPO manages the key/value."""
    domain_rsop = {
        "domain_managed": True,
        "gpo_name": "Default Domain Policy",
        "gpo_id": "{12345678-1234-1234-1234-123456789012}",
    }
    with patch.object(lgpo_reg, "get_rsop_value", return_value=domain_rsop), patch(
        "salt.modules.win_lgpo_reg.log"
    ) as mock_log:
        lgpo_reg.disable_value(key="SOFTWARE\\MyKey1", v_name="MyValue1")
    mock_log.warning.assert_called_once()


def test_delete_value_warns_on_domain_gpo(reg_pol_mach):
    """delete_value should log.warning when a domain GPO manages the key/value."""
    domain_rsop = {
        "domain_managed": True,
        "gpo_name": "Default Domain Policy",
        "gpo_id": "{12345678-1234-1234-1234-123456789012}",
    }
    with patch.object(lgpo_reg, "get_rsop_value", return_value=domain_rsop), patch(
        "salt.modules.win_lgpo_reg.log"
    ) as mock_log:
        lgpo_reg.delete_value(key="SOFTWARE\\MyKey1", v_name="MyValue1")
    mock_log.warning.assert_called_once()


# ---------------------------------------------------------------------------
# _policy_lock integration — verify each RMW function acquires the lock
# ---------------------------------------------------------------------------


@pytest.fixture
def _mock_rmw():
    """Patch out read/write and _policy_lock so RMW functions run without I/O."""
    from contextlib import contextmanager

    lock_calls = []

    @contextmanager
    def fake_lock(machine=True):
        lock_calls.append(machine)
        yield

    with patch(
        "salt.utils.win_lgpo_reg._policy_lock", side_effect=fake_lock
    ), patch.object(lgpo_reg, "read_reg_pol", return_value={}), patch.object(
        lgpo_reg, "write_reg_pol", return_value=True
    ):
        yield lock_calls


def test_set_value_acquires_machine_lock(_mock_rmw):
    """set_value acquires the machine critical section for policy_class=Machine."""
    lgpo_reg.set_value(
        key="SOFTWARE\\MyKey",
        v_name="MyVal",
        v_data=1,
        v_type="REG_DWORD",
        policy_class="Machine",
    )
    assert _mock_rmw == [True]


def test_set_value_acquires_user_lock(_mock_rmw):
    """set_value acquires the user critical section for policy_class=User."""
    lgpo_reg.set_value(
        key="SOFTWARE\\MyKey",
        v_name="MyVal",
        v_data="x",
        v_type="REG_SZ",
        policy_class="User",
    )
    assert _mock_rmw == [False]


def test_disable_value_acquires_machine_lock(_mock_rmw):
    """disable_value acquires the machine critical section."""
    lgpo_reg.disable_value(
        key="SOFTWARE\\MyKey", v_name="MyVal", policy_class="Machine"
    )
    assert _mock_rmw == [True]


def test_disable_value_acquires_user_lock(_mock_rmw):
    """disable_value acquires the user critical section."""
    lgpo_reg.disable_value(key="SOFTWARE\\MyKey", v_name="MyVal", policy_class="User")
    assert _mock_rmw == [False]


def test_delete_value_acquires_machine_lock(_mock_rmw):
    """delete_value acquires the machine critical section."""
    lgpo_reg.delete_value(key="SOFTWARE\\MyKey", v_name="MyVal", policy_class="Machine")
    assert _mock_rmw == [True]


def test_delete_value_acquires_user_lock(_mock_rmw):
    """delete_value acquires the user critical section."""
    lgpo_reg.delete_value(key="SOFTWARE\\MyKey", v_name="MyVal", policy_class="User")
    assert _mock_rmw == [False]
