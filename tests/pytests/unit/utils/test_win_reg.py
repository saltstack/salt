import pytest
from saltfactories.utils import random_string

import salt.utils.stringutils
import salt.utils.win_reg as win_reg
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch

try:
    import win32api

except ImportError:
    pass

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
]


@pytest.fixture
def fake_key():
    return "SOFTWARE\\{}".format(random_string("SaltTesting-", lowercase=False))


@pytest.fixture
def unicode_key():
    return "Unicode Key \N{TRADE MARK SIGN}"


@pytest.fixture
def unicode_value():
    return "Unicode Value \N{COPYRIGHT SIGN},\N{TRADE MARK SIGN},\N{REGISTERED SIGN}"


def test_broadcast_change_success():
    """
    Tests the broadcast_change function
    """
    with patch("win32gui.SendMessageTimeout", return_value=("", 0)):
        assert win_reg.broadcast_change()


def test_broadcast_change_fail():
    """
    Tests the broadcast_change function failure
    """
    with patch("win32gui.SendMessageTimeout", return_value=("", 1)):
        assert not win_reg.broadcast_change()


def test_key_exists_existing():
    """
    Tests the key_exists function using a well known registry key
    """
    assert win_reg.key_exists(hive="HKLM", key="SOFTWARE\\Microsoft")


def test_key_exists_non_existing():
    """
    Tests the key_exists function using a non existing registry key
    """
    assert not win_reg.key_exists(hive="HKLM", key="SOFTWARE\\FakeKey")


def test_key_exists_invalid_hive():
    """
    Tests the key_exists function using an invalid hive
    """
    pytest.raises(
        CommandExecutionError,
        win_reg.key_exists,
        hive="BADHIVE",
        key="SOFTWARE\\Microsoft",
    )


def test_key_exists_unknown_key_error():
    """
    Tests the key_exists function with an unknown key error
    """
    mock_error = MagicMock(
        side_effect=win32api.error(123, "RegOpenKeyEx", "Unknown error")
    )
    with patch("salt.utils.win_reg.win32api.RegOpenKeyEx", mock_error):
        pytest.raises(
            win32api.error,
            win_reg.key_exists,
            hive="HKLM",
            key="SOFTWARE\\Microsoft",
        )


def test_value_exists_existing():
    """
    Tests the value_exists function using a well known registry key
    """
    assert win_reg.value_exists(
        hive="HKLM",
        key="SOFTWARE\\Microsoft\\Windows\\CurrentVersion",
        vname="CommonFilesDir",
    )


def test_value_exists_non_existing():
    """
    Tests the value_exists function using a non existing registry key
    """
    assert not win_reg.value_exists(
        hive="HKLM",
        key="SOFTWARE\\Microsoft\\Windows\\CurrentVersion",
        vname="NonExistingValueName",
    )


def test_value_exists_invalid_hive():
    """
    Tests the value_exists function using an invalid hive
    """
    pytest.raises(
        CommandExecutionError,
        win_reg.value_exists,
        hive="BADHIVE",
        key="SOFTWARE\\Microsoft\\Windows\\CurrentVersion",
        vname="CommonFilesDir",
    )


def test_value_exists_key_not_exist():
    """
    Tests the value_exists function when the key does not exist
    """
    mock_error = MagicMock(
        side_effect=win32api.error(2, "RegOpenKeyEx", "Unknown error")
    )
    with patch("salt.utils.win_reg.win32api.RegOpenKeyEx", mock_error):
        assert not win_reg.value_exists(
            hive="HKLM",
            key="SOFTWARE\\Microsoft\\Windows\\CurrentVersion",
            vname="CommonFilesDir",
        )


def test_value_exists_unknown_key_error():
    """
    Tests the value_exists function with an unknown error when opening the
    key
    """
    mock_error = MagicMock(
        side_effect=win32api.error(123, "RegOpenKeyEx", "Unknown error")
    )
    with patch("salt.utils.win_reg.win32api.RegOpenKeyEx", mock_error):
        pytest.raises(
            win32api.error,
            win_reg.value_exists,
            hive="HKLM",
            key="SOFTWARE\\Microsoft\\Windows\\CurrentVersion",
            vname="CommonFilesDir",
        )


def test_value_exists_empty_default_value():
    """
    Tests the value_exists function when querying the default value
    """
    mock_error = MagicMock(
        side_effect=win32api.error(2, "RegQueryValueEx", "Empty Value")
    )
    with patch("salt.utils.win_reg.win32api.RegQueryValueEx", mock_error):
        assert win_reg.value_exists(
            hive="HKLM",
            key="SOFTWARE\\Microsoft\\Windows\\CurrentVersion",
            vname=None,
        )


def test_value_exists_no_vname():
    """
    Tests the value_exists function when the vname does not exist
    """
    mock_error = MagicMock(
        side_effect=win32api.error(123, "RegQueryValueEx", "Empty Value")
    )
    with patch("salt.utils.win_reg.win32api.RegQueryValueEx", mock_error):
        assert not win_reg.value_exists(
            hive="HKLM",
            key="SOFTWARE\\Microsoft\\Windows\\CurrentVersion",
            vname="NonExistingValuePair",
        )


def test_list_keys_existing():
    """
    Test the list_keys function using a well known registry key
    """
    assert "Microsoft" in win_reg.list_keys(hive="HKLM", key="SOFTWARE")


def test_list_keys_non_existing(fake_key):
    """
    Test the list_keys function using a non existing registry key
    """
    expected = (False, f"Cannot find key: HKLM\\{fake_key}")
    assert win_reg.list_keys(hive="HKLM", key=fake_key) == expected


def test_list_keys_access_denied(fake_key):
    """
    Test the list_keys function using a registry key when access is denied
    """
    expected = (False, f"Access is denied: HKLM\\{fake_key}")
    mock_error = MagicMock(
        side_effect=win32api.error(5, "RegOpenKeyEx", "Access is denied")
    )
    with patch("salt.utils.win_reg.win32api.RegOpenKeyEx", mock_error):
        assert win_reg.list_keys(hive="HKLM", key=fake_key) == expected


def test_list_keys_invalid_hive():
    """
    Test the list_keys function when passing an invalid hive
    """
    pytest.raises(
        CommandExecutionError,
        win_reg.list_keys,
        hive="BADHIVE",
        key="SOFTWARE\\Microsoft",
    )


def test_list_keys_unknown_key_error():
    """
    Tests the list_keys function with an unknown key error
    """
    mock_error = MagicMock(
        side_effect=win32api.error(123, "RegOpenKeyEx", "Unknown error")
    )
    with patch("salt.utils.win_reg.win32api.RegOpenKeyEx", mock_error):
        pytest.raises(
            win32api.error,
            win_reg.list_keys,
            hive="HKLM",
            key="SOFTWARE\\Microsoft",
        )


def test_list_values_existing():
    """
    Test the list_values function using a well known registry key
    """
    values = win_reg.list_values(
        hive="HKLM", key="SOFTWARE\\Microsoft\\Windows\\CurrentVersion"
    )
    keys = []
    for value in values:
        keys.append(value["vname"])
    assert "ProgramFilesDir" in keys


def test_list_values_non_existing(fake_key):
    """
    Test the list_values function using a non existing registry key
    """
    expected = (False, f"Cannot find key: HKLM\\{fake_key}")
    assert win_reg.list_values(hive="HKLM", key=fake_key) == expected


def test_list_values_access_denied(fake_key):
    """
    Test the list_values function using a registry key when access is denied
    """
    expected = (False, f"Access is denied: HKLM\\{fake_key}")
    mock_error = MagicMock(
        side_effect=win32api.error(5, "RegOpenKeyEx", "Access is denied")
    )
    with patch("salt.utils.win_reg.win32api.RegOpenKeyEx", mock_error):
        assert win_reg.list_values(hive="HKLM", key=fake_key) == expected


def test_list_values_invalid_hive():
    """
    Test the list_values function when passing an invalid hive
    """
    pytest.raises(
        CommandExecutionError,
        win_reg.list_values,
        hive="BADHIVE",
        key="SOFTWARE\\Microsoft",
    )


def test_list_values_unknown_key_error():
    """
    Tests the list_values function with an unknown key error
    """
    mock_error = MagicMock(
        side_effect=win32api.error(123, "RegOpenKeyEx", "Unknown error")
    )
    with patch("salt.utils.win_reg.win32api.RegOpenKeyEx", mock_error):
        pytest.raises(
            win32api.error,
            win_reg.list_values,
            hive="HKLM",
            key="SOFTWARE\\Microsoft",
        )


def test_read_value_existing():
    """
    Test the read_value function using a well known registry value
    """
    ret = win_reg.read_value(
        hive="HKLM",
        key="SOFTWARE\\Microsoft\\Windows\\CurrentVersion",
        vname="ProgramFilesPath",
    )
    assert ret["vdata"] == "%ProgramFiles%"


def test_read_value_default():
    """
    Test the read_value function reading the default value using a well
    known registry key
    """
    ret = win_reg.read_value(
        hive="HKLM", key="SOFTWARE\\Microsoft\\Windows\\CurrentVersion"
    )
    assert ret["vdata"] == "(value not set)"


def test_read_value_non_existing():
    """
    Test the read_value function using a non existing value pair
    """
    expected = {
        "comment": (
            "Cannot find fake_name in HKLM\\SOFTWARE\\Microsoft\\"
            "Windows\\CurrentVersion"
        ),
        "vdata": None,
        "vtype": None,
        "vname": "fake_name",
        "success": False,
        "hive": "HKLM",
        "key": "SOFTWARE\\Microsoft\\Windows\\CurrentVersion",
    }
    assert (
        win_reg.read_value(
            hive="HKLM",
            key="SOFTWARE\\Microsoft\\Windows\\CurrentVersion",
            vname="fake_name",
        )
        == expected
    )


def test_read_value_non_existing_key(fake_key):
    """
    Test the read_value function using a non existing registry key
    """
    expected = {
        "comment": f"Cannot find key: HKLM\\{fake_key}",
        "vdata": None,
        "vtype": None,
        "vname": "fake_name",
        "success": False,
        "hive": "HKLM",
        "key": fake_key,
    }
    assert win_reg.read_value(hive="HKLM", key=fake_key, vname="fake_name") == expected


def test_read_value_access_denied(fake_key):
    """
    Test the read_value function using a registry key when access is denied
    """
    expected = {
        "comment": f"Access is denied: HKLM\\{fake_key}",
        "vdata": None,
        "vtype": None,
        "vname": "fake_name",
        "success": False,
        "hive": "HKLM",
        "key": fake_key,
    }
    mock_error = MagicMock(
        side_effect=win32api.error(5, "RegOpenKeyEx", "Access is denied")
    )
    with patch("salt.utils.win_reg.win32api.RegOpenKeyEx", mock_error):
        assert (
            win_reg.read_value(hive="HKLM", key=fake_key, vname="fake_name") == expected
        )


def test_read_value_invalid_hive():
    """
    Test the read_value function when passing an invalid hive
    """
    pytest.raises(
        CommandExecutionError,
        win_reg.read_value,
        hive="BADHIVE",
        key="SOFTWARE\\Microsoft",
        vname="ProgramFilesPath",
    )


def test_read_value_unknown_key_error():
    """
    Tests the read_value function with an unknown key error
    """
    mock_error = MagicMock(
        side_effect=win32api.error(123, "RegOpenKeyEx", "Unknown error")
    )
    with patch("salt.utils.win_reg.win32api.RegOpenKeyEx", mock_error):
        pytest.raises(
            win32api.error,
            win_reg.read_value,
            hive="HKLM",
            key="SOFTWARE\\Microsoft\\Windows\\CurrentVersion",
            vname="ProgramFilesPath",
        )


def test_read_value_unknown_value_error():
    """
    Tests the read_value function with an unknown value error
    """
    mock_error = MagicMock(
        side_effect=win32api.error(123, "RegQueryValueEx", "Unknown error")
    )
    with patch("salt.utils.win_reg.win32api.RegQueryValueEx", mock_error):
        pytest.raises(
            win32api.error,
            win_reg.read_value,
            hive="HKLM",
            key="SOFTWARE\\Microsoft\\Windows\\CurrentVersion",
            vname="ProgramFilesPath",
        )


@pytest.mark.destructive_test
def test_read_value_multi_sz_empty_list(fake_key):
    """
    An empty REG_MULTI_SZ value should return an empty list, not None
    """
    try:
        assert win_reg.set_value(
            hive="HKLM",
            key=fake_key,
            vname="empty_list",
            vdata=[],
            vtype="REG_MULTI_SZ",
        )
        expected = {
            "hive": "HKLM",
            "key": fake_key,
            "success": True,
            "vdata": [],
            "vname": "empty_list",
            "vtype": "REG_MULTI_SZ",
        }
        assert (
            win_reg.read_value(
                hive="HKLM",
                key=fake_key,
                vname="empty_list",
            )
            == expected
        )
    finally:
        win_reg.delete_key_recursive(hive="HKLM", key=fake_key)


@pytest.mark.destructive_test
def test_set_value(fake_key):
    """
    Test the set_value function
    """
    try:
        assert win_reg.set_value(
            hive="HKLM", key=fake_key, vname="fake_name", vdata="fake_data"
        )
        expected = {
            "hive": "HKLM",
            "key": fake_key,
            "success": True,
            "vdata": "fake_data",
            "vname": "fake_name",
            "vtype": "REG_SZ",
        }
        assert (
            win_reg.read_value(hive="HKLM", key=fake_key, vname="fake_name") == expected
        )
    finally:
        win_reg.delete_key_recursive(hive="HKLM", key=fake_key)


@pytest.mark.destructive_test
def test_set_value_default(fake_key):
    """
    Test the set_value function on the default value
    """
    try:
        assert win_reg.set_value(hive="HKLM", key=fake_key, vdata="fake_default_data")
        expected = {
            "hive": "HKLM",
            "key": fake_key,
            "success": True,
            "vdata": "fake_default_data",
            "vname": "(Default)",
            "vtype": "REG_SZ",
        }
        assert win_reg.read_value(hive="HKLM", key=fake_key) == expected
    finally:
        win_reg.delete_key_recursive(hive="HKLM", key=fake_key)


@pytest.mark.destructive_test
def test_set_value_unicode_key(fake_key, unicode_key):
    """
    Test the set_value function on a unicode key
    """
    try:
        assert win_reg.set_value(
            hive="HKLM",
            key="\\".join([fake_key, unicode_key]),
            vname="fake_name",
            vdata="fake_value",
        )
        expected = {
            "hive": "HKLM",
            "key": "\\".join([fake_key, unicode_key]),
            "success": True,
            "vdata": "fake_value",
            "vname": "fake_name",
            "vtype": "REG_SZ",
        }
        assert (
            win_reg.read_value(
                hive="HKLM",
                key="\\".join([fake_key, unicode_key]),
                vname="fake_name",
            )
            == expected
        )
    finally:
        win_reg.delete_key_recursive(hive="HKLM", key=fake_key)


@pytest.mark.destructive_test
def test_set_value_unicode_value(fake_key, unicode_value):
    """
    Test the set_value function on a unicode value
    """
    try:
        assert win_reg.set_value(
            hive="HKLM", key=fake_key, vname="fake_unicode", vdata=unicode_value
        )
        expected = {
            "hive": "HKLM",
            "key": fake_key,
            "success": True,
            "vdata": unicode_value,
            "vname": "fake_unicode",
            "vtype": "REG_SZ",
        }
        assert (
            win_reg.read_value(hive="HKLM", key=fake_key, vname="fake_unicode")
            == expected
        )
    finally:
        win_reg.delete_key_recursive(hive="HKLM", key=fake_key)


@pytest.mark.destructive_test
def test_set_value_reg_dword(fake_key):
    """
    Test the set_value function on a REG_DWORD value
    """
    try:
        assert win_reg.set_value(
            hive="HKLM",
            key=fake_key,
            vname="dword_value",
            vdata=123,
            vtype="REG_DWORD",
        )
        expected = {
            "hive": "HKLM",
            "key": fake_key,
            "success": True,
            "vdata": 123,
            "vname": "dword_value",
            "vtype": "REG_DWORD",
        }
        assert (
            win_reg.read_value(hive="HKLM", key=fake_key, vname="dword_value")
            == expected
        )
    finally:
        win_reg.delete_key_recursive(hive="HKLM", key=fake_key)


@pytest.mark.destructive_test
def test_set_value_reg_qword(fake_key):
    """
    Test the set_value function on a REG_QWORD value
    """
    try:
        assert win_reg.set_value(
            hive="HKLM",
            key=fake_key,
            vname="qword_value",
            vdata=123,
            vtype="REG_QWORD",
        )
        expected = {
            "hive": "HKLM",
            "key": fake_key,
            "success": True,
            "vdata": 123,
            "vname": "qword_value",
            "vtype": "REG_QWORD",
        }
        assert (
            win_reg.read_value(hive="HKLM", key=fake_key, vname="qword_value")
            == expected
        )
    finally:
        win_reg.delete_key_recursive(hive="HKLM", key=fake_key)


def test_set_value_invalid_hive(fake_key):
    """
    Test the set_value function when passing an invalid hive
    """
    pytest.raises(
        CommandExecutionError,
        win_reg.set_value,
        hive="BADHIVE",
        key=fake_key,
        vname="fake_name",
        vdata="fake_data",
    )


def test_set_value_open_create_failure(fake_key):
    """
    Test the set_value function when there is a problem opening/creating
    the key
    """
    mock_error = MagicMock(
        side_effect=win32api.error(123, "RegCreateKeyEx", "Unknown error")
    )
    with patch("salt.utils.win_reg.win32api.RegCreateKeyEx", mock_error):
        assert not win_reg.set_value(
            hive="HKLM", key=fake_key, vname="fake_name", vdata="fake_data"
        )


def test_set_value_type_error(fake_key):
    """
    Test the set_value function when the wrong type of data is passed
    """
    mock_error = MagicMock(side_effect=TypeError("Mocked TypeError"))
    with patch("salt.utils.win_reg.win32api.RegSetValueEx", mock_error):
        assert not win_reg.set_value(
            hive="HKLM", key=fake_key, vname="fake_name", vdata="fake_data"
        )


def test_set_value_system_error(fake_key):
    """
    Test the set_value function when a SystemError occurs while setting the
    value
    """
    mock_error = MagicMock(side_effect=SystemError("Mocked SystemError"))
    with patch("salt.utils.win_reg.win32api.RegSetValueEx", mock_error):
        assert not win_reg.set_value(
            hive="HKLM", key=fake_key, vname="fake_name", vdata="fake_data"
        )


def test_set_value_value_error(fake_key):
    """
    Test the set_value function when a ValueError occurs while setting the
    value
    """
    mock_error = MagicMock(side_effect=ValueError("Mocked ValueError"))
    with patch("salt.utils.win_reg.win32api.RegSetValueEx", mock_error):
        assert not win_reg.set_value(
            hive="HKLM", key=fake_key, vname="fake_name", vdata="fake_data"
        )


def test_cast_vdata_reg_binary():
    """
    Test the cast_vdata function with REG_BINARY
    Should always return binary data
    """
    vdata = salt.utils.stringutils.to_bytes("test data")
    result = win_reg.cast_vdata(vdata=vdata, vtype="REG_BINARY")
    assert isinstance(result, bytes)

    vdata = salt.utils.stringutils.to_str("test data")
    result = win_reg.cast_vdata(vdata=vdata, vtype="REG_BINARY")
    assert isinstance(result, bytes)

    vdata = salt.utils.stringutils.to_unicode("test data")
    result = win_reg.cast_vdata(vdata=vdata, vtype="REG_BINARY")
    assert isinstance(result, bytes)


def test_cast_vdata_reg_dword():
    """
    Test the cast_vdata function with REG_DWORD
    Should always return integer
    """
    vdata = 1
    expected = 1
    result = win_reg.cast_vdata(vdata=vdata, vtype="REG_DWORD")
    assert result == expected

    vdata = "1"
    result = win_reg.cast_vdata(vdata=vdata, vtype="REG_DWORD")
    assert result == expected

    vdata = "0000001"
    result = win_reg.cast_vdata(vdata=vdata, vtype="REG_DWORD")
    assert result == expected


def test_cast_vdata_reg_expand_sz():
    """
    Test the cast_vdata function with REG_EXPAND_SZ
    Should always return unicode
    """
    vdata = salt.utils.stringutils.to_str("test data")
    result = win_reg.cast_vdata(vdata=vdata, vtype="REG_EXPAND_SZ")
    assert isinstance(result, str)

    vdata = salt.utils.stringutils.to_bytes("test data")
    result = win_reg.cast_vdata(vdata=vdata, vtype="REG_EXPAND_SZ")
    assert isinstance(result, str)


def test_cast_vdata_reg_multi_sz():
    """
    Test the cast_vdata function with REG_MULTI_SZ
    Should always return a list of unicode strings
    """
    vdata = [
        salt.utils.stringutils.to_str("test string"),
        salt.utils.stringutils.to_bytes("test bytes"),
    ]
    result = win_reg.cast_vdata(vdata=vdata, vtype="REG_MULTI_SZ")
    assert isinstance(result, list)
    for item in result:
        assert isinstance(item, str)


def test_cast_vdata_reg_qword():
    """
    Test the cast_vdata function with REG_QWORD
    Should always return a long integer
    `int` is `long` is default on Py3
    """
    vdata = 1
    result = win_reg.cast_vdata(vdata=vdata, vtype="REG_QWORD")
    assert isinstance(result, int)

    vdata = "1"
    result = win_reg.cast_vdata(vdata=vdata, vtype="REG_QWORD")
    assert isinstance(result, int)


def test_cast_vdata_reg_sz():
    """
    Test the cast_vdata function with REG_SZ
    Should always return unicode
    """
    vdata = salt.utils.stringutils.to_str("test data")
    result = win_reg.cast_vdata(vdata=vdata, vtype="REG_SZ")
    assert isinstance(result, str)

    vdata = salt.utils.stringutils.to_bytes("test data")
    result = win_reg.cast_vdata(vdata=vdata, vtype="REG_SZ")
    assert isinstance(result, str)

    vdata = None
    result = win_reg.cast_vdata(vdata=vdata, vtype="REG_SZ")
    assert isinstance(result, str)
    assert result == ""


@pytest.mark.destructive_test
def test_delete_value(fake_key):
    """
    Test the delete_value function
    """
    try:
        assert win_reg.set_value(
            hive="HKLM", key=fake_key, vname="fake_name", vdata="fake_data"
        )
        assert win_reg.delete_value(hive="HKLM", key=fake_key, vname="fake_name")
        assert not win_reg.value_exists(hive="HKLM", key=fake_key, vname="fake_name")
    finally:
        win_reg.delete_key_recursive(hive="HKLM", key=fake_key)


def test_delete_value_non_existing(fake_key):
    """
    Test the delete_value function on non existing value
    """
    mock_error = MagicMock(
        side_effect=win32api.error(2, "RegOpenKeyEx", "Unknown error")
    )
    with patch("salt.utils.win_reg.win32api.RegOpenKeyEx", mock_error):
        assert (
            win_reg.delete_value(hive="HKLM", key=fake_key, vname="fake_name") is None
        )


def test_delete_value_invalid_hive(fake_key):
    """
    Test the delete_value function when passing an invalid hive
    """
    pytest.raises(
        CommandExecutionError,
        win_reg.delete_value,
        hive="BADHIVE",
        key=fake_key,
        vname="fake_name",
    )


def test_delete_value_unknown_error(fake_key):
    """
    Test the delete_value function when there is a problem opening the key
    """
    mock_error = MagicMock(
        side_effect=win32api.error(123, "RegOpenKeyEx", "Unknown error")
    )
    with patch("salt.utils.win_reg.win32api.RegOpenKeyEx", mock_error):
        pytest.raises(
            win32api.error,
            win_reg.delete_value,
            hive="HKLM",
            key=fake_key,
            vname="fake_name",
        )


@pytest.mark.destructive_test
def test_delete_value_unicode(fake_key, unicode_value):
    """
    Test the delete_value function on a unicode value
    """
    try:
        assert win_reg.set_value(
            hive="HKLM", key=fake_key, vname="fake_unicode", vdata=unicode_value
        )
        assert win_reg.delete_value(hive="HKLM", key=fake_key, vname="fake_unicode")
        assert not win_reg.value_exists(hive="HKLM", key=fake_key, vname="fake_unicode")
    finally:
        win_reg.delete_key_recursive(hive="HKLM", key=fake_key)


@pytest.mark.destructive_test
def test_delete_value_unicode_vname(fake_key, unicode_key):
    """
    Test the delete_value function on a unicode vname
    """
    try:
        assert win_reg.set_value(
            hive="HKLM", key=fake_key, vname=unicode_key, vdata="junk data"
        )
        assert win_reg.delete_value(hive="HKLM", key=fake_key, vname=unicode_key)
        assert not win_reg.value_exists(hive="HKLM", key=fake_key, vname=unicode_key)
    finally:
        win_reg.delete_key_recursive(hive="HKLM", key=fake_key)


@pytest.mark.destructive_test
def test_delete_value_unicode_key(fake_key, unicode_key):
    """
    Test the delete_value function on a unicode key
    """
    try:
        assert win_reg.set_value(
            hive="HKLM",
            key="\\".join([fake_key, unicode_key]),
            vname="fake_name",
            vdata="junk data",
        )
        assert win_reg.delete_value(
            hive="HKLM", key="\\".join([fake_key, unicode_key]), vname="fake_name"
        )
        assert not win_reg.value_exists(
            hive="HKLM", key="\\".join([fake_key, unicode_key]), vname="fake_name"
        )
    finally:
        win_reg.delete_key_recursive(hive="HKLM", key=fake_key)


def test_delete_key_recursive_invalid_hive(fake_key):
    """
    Test the delete_key_recursive function when passing an invalid hive
    """
    pytest.raises(
        CommandExecutionError,
        win_reg.delete_key_recursive,
        hive="BADHIVE",
        key=fake_key,
    )


def test_delete_key_recursive_key_not_found(fake_key):
    """
    Test the delete_key_recursive function when the passed key to delete is
    not found.
    """
    assert not win_reg.key_exists(hive="HKLM", key=fake_key)
    assert not win_reg.delete_key_recursive(hive="HKLM", key=fake_key)


def test_delete_key_recursive_too_close():
    """
    Test the delete_key_recursive function when the passed key to delete is
    too close to root, such as
    """
    mock_true = MagicMock(return_value=True)
    with patch("salt.utils.win_reg.key_exists", mock_true):
        assert not win_reg.delete_key_recursive(hive="HKLM", key="FAKE_KEY")


@pytest.mark.destructive_test
def test_delete_key_recursive(fake_key):
    """
    Test the delete_key_recursive function
    """
    try:
        assert win_reg.set_value(
            hive="HKLM", key=fake_key, vname="fake_name", vdata="fake_value"
        )
        expected = {"Deleted": ["\\".join(["HKLM", fake_key])], "Failed": []}
        assert win_reg.delete_key_recursive(hive="HKLM", key=fake_key) == expected
        assert not win_reg.key_exists(hive="HKLM", key=fake_key)
    finally:
        win_reg.delete_key_recursive(hive="HKLM", key=fake_key)


@pytest.mark.destructive_test
def test_delete_key_recursive_failed_to_open_key(fake_key):
    """
    Test the delete_key_recursive function on failure to open the key
    """
    try:
        assert win_reg.set_value(
            hive="HKLM", key=fake_key, vname="fake_name", vdata="fake_value"
        )
        expected = {
            "Deleted": [],
            "Failed": ["\\".join(["HKLM", fake_key]) + " Failed to connect to key"],
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
            assert win_reg.delete_key_recursive(hive="HKLM", key=fake_key) == expected
    finally:
        win_reg.delete_key_recursive(hive="HKLM", key=fake_key)


@pytest.mark.destructive_test
def test_delete_key_recursive_failed_to_delete(fake_key):
    """
    Test the delete_key_recursive function on failure to delete a key
    """
    try:
        assert win_reg.set_value(
            hive="HKLM", key=fake_key, vname="fake_name", vdata="fake_value"
        )
        expected = {
            "Deleted": [],
            "Failed": ["\\".join(["HKLM", fake_key]) + " Unknown error"],
        }
        # pylint: disable=undefined-variable
        mock_error = MagicMock(side_effect=WindowsError("Unknown error"))
        # pylint: enable=undefined-variable
        with patch("salt.utils.win_reg.win32api.RegDeleteKey", mock_error):
            assert win_reg.delete_key_recursive(hive="HKLM", key=fake_key) == expected
    finally:
        win_reg.delete_key_recursive(hive="HKLM", key=fake_key)


@pytest.mark.destructive_test
def test_delete_key_recursive_unicode(fake_key, unicode_key):
    """
    Test the delete_key_recursive function on value within a unicode key
    """
    try:
        assert win_reg.set_value(
            hive="HKLM",
            key="\\".join([fake_key, unicode_key]),
            vname="fake_name",
            vdata="fake_value",
        )
        expected = {
            "Deleted": ["\\".join(["HKLM", fake_key, unicode_key])],
            "Failed": [],
        }
        assert (
            win_reg.delete_key_recursive(
                hive="HKLM", key="\\".join([fake_key, unicode_key])
            )
            == expected
        )
    finally:
        win_reg.delete_key_recursive(hive="HKLM", key=fake_key)


def test__to_unicode_int():
    """
    Test the ``_to_unicode`` function when it receives an integer value.
    Should return a unicode value, which is str in PY3.
    """
    assert isinstance(win_reg._to_unicode(1), str)
