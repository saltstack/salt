"""
:codeauthor: Shane Lee <slee@saltstack.com>
"""
import pytest

import salt.modules.win_lgpo as win_lgpo
from tests.support.mock import MagicMock, Mock, patch

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
]


def test__getAdmlDisplayName():
    display_name = "$(string.KeepAliveTime1)"
    adml_xml_data = "junk, we are mocking the return"
    obj_xpath = Mock()
    obj_xpath.text = "300000 or 5 minutes (recommended) "
    mock_xpath_obj = MagicMock(return_value=[obj_xpath])
    with patch.object(win_lgpo, "ADML_DISPLAY_NAME_XPATH", mock_xpath_obj):
        result = win_lgpo._getAdmlDisplayName(
            adml_xml_data=adml_xml_data, display_name=display_name
        )
    expected = "300000 or 5 minutes (recommended)"
    assert result == expected


def test__regexSearchKeyValueCombo_enabled():
    """
    Make sure
    """
    policy_data = (
        b"[\x00s\x00o\x00f\x00t\x00w\x00a\x00r\x00e\x00\\\x00p"
        b"\x00o\x00l\x00i\x00c\x00i\x00e\x00s\x00\\\x00m\x00i"
        b"\x00c\x00r\x00o\x00s\x00o\x00f\x00t\x00\\\x00w\x00i"
        b"\x00n\x00d\x00o\x00w\x00s\x00\\\x00w\x00i\x00n\x00d"
        b"\x00o\x00w\x00s\x00 \x00e\x00r\x00r\x00o\x00r\x00 "
        b"\x00r\x00e\x00p\x00o\x00r\x00t\x00i\x00n\x00g\x00\\"
        b"\x00c\x00o\x00n\x00s\x00e\x00n\x00t\x00\x00\x00;\x00D"
        b"\x00e\x00f\x00a\x00u\x00l\x00t\x00C\x00o\x00n\x00s"
        b"\x00e\x00n\x00t\x00\x00\x00;\x00\x01\x00\x00\x00;\x00"
        b"\x04\x00\x00\x00;\x00\x02\x00\x00\x00]\x00"
    )
    policy_regpath = (
        b"\x00s\x00o\x00f\x00t\x00w\x00a\x00r\x00e\x00\\\x00p"
        b"\x00o\x00l\x00i\x00c\x00i\x00e\x00s\x00\\\x00m\x00i"
        b"\x00c\x00r\x00o\x00s\x00o\x00f\x00t\x00\\\x00w\x00i"
        b"\x00n\x00d\x00o\x00w\x00s\x00\\\x00w\x00i\x00n\x00d"
        b"\x00o\x00w\x00s\x00 \x00e\x00r\x00r\x00o\x00r\x00 "
        b"\x00r\x00e\x00p\x00o\x00r\x00t\x00i\x00n\x00g\x00\\"
        b"\x00c\x00o\x00n\x00s\x00e\x00n\x00t\x00\x00"
    )
    policy_regkey = (
        b"\x00D\x00e\x00f\x00a\x00u\x00l\x00t\x00C\x00o\x00n"
        b"\x00s\x00e\x00n\x00t\x00\x00"
    )
    test = win_lgpo._regexSearchKeyValueCombo(
        policy_data=policy_data,
        policy_regpath=policy_regpath,
        policy_regkey=policy_regkey,
    )
    assert test == policy_data


def test__regexSearchKeyValueCombo_not_configured():
    """
    Make sure
    """
    policy_data = b""
    policy_regpath = (
        b"\x00s\x00o\x00f\x00t\x00w\x00a\x00r\x00e\x00\\\x00p"
        b"\x00o\x00l\x00i\x00c\x00i\x00e\x00s\x00\\\x00m\x00i"
        b"\x00c\x00r\x00o\x00s\x00o\x00f\x00t\x00\\\x00w\x00i"
        b"\x00n\x00d\x00o\x00w\x00s\x00\\\x00w\x00i\x00n\x00d"
        b"\x00o\x00w\x00s\x00 \x00e\x00r\x00r\x00o\x00r\x00 "
        b"\x00r\x00e\x00p\x00o\x00r\x00t\x00i\x00n\x00g\x00\\"
        b"\x00c\x00o\x00n\x00s\x00e\x00n\x00t\x00\x00"
    )
    policy_regkey = (
        b"\x00D\x00e\x00f\x00a\x00u\x00l\x00t\x00C\x00o\x00n"
        b"\x00s\x00e\x00n\x00t\x00\x00"
    )
    test = win_lgpo._regexSearchKeyValueCombo(
        policy_data=policy_data,
        policy_regpath=policy_regpath,
        policy_regkey=policy_regkey,
    )
    assert test is None


def test__regexSearchKeyValueCombo_disabled():
    """
    Make sure
    """
    policy_data = (
        b"[\x00s\x00o\x00f\x00t\x00w\x00a\x00r\x00e\x00\\\x00p"
        b"\x00o\x00l\x00i\x00c\x00i\x00e\x00s\x00\\\x00m\x00i"
        b"\x00c\x00r\x00o\x00s\x00o\x00f\x00t\x00\\\x00w\x00i"
        b"\x00n\x00d\x00o\x00w\x00s\x00\\\x00w\x00i\x00n\x00d"
        b"\x00o\x00w\x00s\x00 \x00e\x00r\x00r\x00o\x00r\x00 "
        b"\x00r\x00e\x00p\x00o\x00r\x00t\x00i\x00n\x00g\x00\\"
        b"\x00c\x00o\x00n\x00s\x00e\x00n\x00t\x00\x00\x00;\x00*"
        b"\x00*\x00d\x00e\x00l\x00.\x00D\x00e\x00f\x00a\x00u"
        b"\x00l\x00t\x00C\x00o\x00n\x00s\x00e\x00n\x00t\x00\x00"
        b"\x00;\x00\x01\x00\x00\x00;\x00\x04\x00\x00\x00;\x00 "
        b"\x00\x00\x00]\x00"
    )
    policy_regpath = (
        b"\x00s\x00o\x00f\x00t\x00w\x00a\x00r\x00e\x00\\\x00p"
        b"\x00o\x00l\x00i\x00c\x00i\x00e\x00s\x00\\\x00m\x00i"
        b"\x00c\x00r\x00o\x00s\x00o\x00f\x00t\x00\\\x00w\x00i"
        b"\x00n\x00d\x00o\x00w\x00s\x00\\\x00w\x00i\x00n\x00d"
        b"\x00o\x00w\x00s\x00 \x00e\x00r\x00r\x00o\x00r\x00 "
        b"\x00r\x00e\x00p\x00o\x00r\x00t\x00i\x00n\x00g\x00\\"
        b"\x00c\x00o\x00n\x00s\x00e\x00n\x00t\x00\x00"
    )
    policy_regkey = (
        b"\x00D\x00e\x00f\x00a\x00u\x00l\x00t\x00C\x00o\x00n"
        b"\x00s\x00e\x00n\x00t\x00\x00"
    )
    test = win_lgpo._regexSearchKeyValueCombo(
        policy_data=policy_data,
        policy_regpath=policy_regpath,
        policy_regkey=policy_regkey,
    )
    assert test == policy_data


def test__encode_string():
    """
    ``_encode_string`` should return a null terminated ``utf-16-le`` encoded
    string when a string value is passed
    """
    encoded_null = chr(0).encode("utf-16-le")
    encoded_value = b"".join(["Salt is awesome".encode("utf-16-le"), encoded_null])
    value = win_lgpo._encode_string("Salt is awesome")
    assert value == encoded_value


def test__encode_string_empty_string():
    """
    ``_encode_string`` should return an encoded null when an empty string
    value is passed
    """
    value = win_lgpo._encode_string("")
    encoded_null = chr(0).encode("utf-16-le")
    assert value == encoded_null


def test__encode_string_error():
    """
    ``_encode_string`` should raise an error if a non-string value is passed
    """
    pytest.raises(TypeError, win_lgpo._encode_string, [1])
    test_list = ["item1", "item2"]
    pytest.raises(TypeError, win_lgpo._encode_string, [test_list])
    test_dict = {"key1": "value1", "key2": "value2"}
    pytest.raises(TypeError, win_lgpo._encode_string, [test_dict])


def test__encode_string_none():
    """
    ``_encode_string`` should return an encoded null when ``None`` is passed
    """
    value = win_lgpo._encode_string(None)
    encoded_null = chr(0).encode("utf-16-le")
    assert value == encoded_null


def test__multi_string_get_transform_list():
    """
    ``_multi_string_get_transform`` should return the list when a list is
    passed
    """
    test_value = ["Spongebob", "Squarepants"]
    value = win_lgpo._policy_info._multi_string_get_transform(item=test_value)
    assert value == test_value


def test__multi_string_get_transform_none():
    """
    ``_multi_string_get_transform`` should return "Not Defined" when
    ``None`` is passed
    """
    test_value = None
    value = win_lgpo._policy_info._multi_string_get_transform(item=test_value)
    assert value == "Not Defined"


def test__multi_string_get_transform_invalid():
    """
    ``_multi_string_get_transform`` should return "Not Defined" when
    ``None`` is passed
    """
    test_value = "Some String"
    value = win_lgpo._policy_info._multi_string_get_transform(item=test_value)
    assert value == "Invalid Value"


def test__multi_string_put_transform_list():
    """
    ``_multi_string_put_transform`` should return the list when a list is
    passed
    """
    test_value = ["Spongebob", "Squarepants"]
    value = win_lgpo._policy_info._multi_string_put_transform(item=test_value)
    assert value == test_value


def test__multi_string_put_transform_none():
    """
    ``_multi_string_put_transform`` should return ``None`` when
    "Not Defined" is passed
    """
    test_value = "Not Defined"
    value = win_lgpo._policy_info._multi_string_put_transform(item=test_value)
    assert value is None


def test__multi_string_put_transform_list_from_string():
    """
    ``_multi_string_put_transform`` should return a list when a comma
    delimited string is passed
    """
    test_value = "Spongebob,Squarepants"
    value = win_lgpo._policy_info._multi_string_put_transform(item=test_value)
    assert value == ["Spongebob", "Squarepants"]


def test__multi_string_put_transform_invalid():
    """
    ``_multi_string_put_transform`` should return "Invalid" value if neither
    string nor list is passed
    """
    test_value = None
    value = win_lgpo._policy_info._multi_string_put_transform(item=test_value)
    assert value == "Invalid Value"
