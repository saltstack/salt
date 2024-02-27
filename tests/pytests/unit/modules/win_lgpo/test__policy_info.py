import socket

import pytest

import salt.modules.cmdmod
import salt.modules.win_file
import salt.modules.win_lgpo as win_lgpo
from salt.exceptions import CommandExecutionError
from tests.support.mock import patch

try:
    import win32security as ws

    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.slow_test,
    pytest.mark.skipif(not HAS_WIN32, reason="Failed to import win32security"),
]


@pytest.fixture
def configure_loader_modules():
    return {
        win_lgpo: {
            "__salt__": {
                "cmd.run": salt.modules.cmdmod.run,
                "file.file_exists": salt.modules.win_file.file_exists,
                "file.remove": salt.modules.win_file.remove,
            },
        },
    }


@pytest.fixture(scope="module")
def pol_info():
    return win_lgpo._policy_info()


@pytest.mark.parametrize(
    "val, expected",
    (
        (0, False),
        (1, True),
        ("", False),
        ("text", True),
        ([], False),
        ([1, 2, 3], True),
    ),
)
def test_notEmpty(pol_info, val, expected):
    assert pol_info._notEmpty(val) is expected


@pytest.mark.parametrize(
    "val, expected",
    (
        (None, "Not Defined"),
        (0, 0),
        (86400, 1),
    ),
)
def test_seconds_to_days(pol_info, val, expected):
    assert pol_info._seconds_to_days(val) == expected


@pytest.mark.parametrize(
    "val, expected",
    (
        (None, "Not Defined"),
        (0, 0),
        (1, 86400),
    ),
)
def test_days_to_seconds(pol_info, val, expected):
    assert pol_info._days_to_seconds(val) == expected


@pytest.mark.parametrize(
    "val, expected",
    (
        (None, "Not Defined"),
        (0, 0),
        (60, 1),
    ),
)
def test_seconds_to_minutes(pol_info, val, expected):
    assert pol_info._seconds_to_minutes(val) == expected


@pytest.mark.parametrize(
    "val, expected",
    (
        (None, "Not Defined"),
        (0, 0),
        (1, 60),
    ),
)
def test_minutes_to_seconds(pol_info, val, expected):
    assert pol_info._minutes_to_seconds(val) == expected


def test_strip_quotes(pol_info):
    assert pol_info._strip_quotes('"spongebob"') == "spongebob"


def test_add_quotes(pol_info):
    assert pol_info._add_quotes("squarepants") == '"squarepants"'


@pytest.mark.parametrize(
    "val, expected",
    (
        (None, "Not Defined"),
        (chr(0), "Disabled"),
        (chr(1), "Enabled"),
        (chr(2), f"Invalid Value: {chr(2)!r}"),
        ("patrick", "Invalid Value"),
    ),
)
def test_binary_enable_zero_disable_one_conversion(pol_info, val, expected):
    assert pol_info._binary_enable_zero_disable_one_conversion(val) == expected


@pytest.mark.parametrize(
    "val, expected",
    (
        (None, None),
        ("Disabled", chr(0)),
        ("Enabled", chr(1)),
        ("Junk", None),
    ),
)
def test_binary_enable_zero_disable_one_reverse_conversion(pol_info, val, expected):
    assert pol_info._binary_enable_zero_disable_one_reverse_conversion(val) == expected


@pytest.mark.parametrize(
    "val, expected",
    (
        (None, "Not Defined"),
        ("0", "Administrators"),
        (0, "Administrators"),
        ("", "Administrators"),
        ("1", "Administrators and Power Users"),
        (1, "Administrators and Power Users"),
        ("2", "Administrators and Interactive Users"),
        (2, "Administrators and Interactive Users"),
        (3, "Not Defined"),
    ),
)
def test_dasd_conversion(pol_info, val, expected):
    assert pol_info._dasd_conversion(val) == expected


@pytest.mark.parametrize(
    "val, expected",
    (
        (None, "Not Defined"),
        ("Administrators", "0"),
        ("Administrators and Power Users", "1"),
        ("Administrators and Interactive Users", "2"),
        ("Not Defined", "9999"),
        ("Plankton", "Invalid Value"),
    ),
)
def test_dasd_reverse_conversion(pol_info, val, expected):
    assert pol_info._dasd_reverse_conversion(val) == expected


@pytest.mark.parametrize(
    "val, expected",
    (
        ("Not Defined", True),
        (None, False),
        (1, True),
        (3, False),
        ("spongebob", False),
    ),
)
def test_in_range_inclusive(pol_info, val, expected):
    assert pol_info._in_range_inclusive(val) == expected


@pytest.mark.parametrize(
    "val, expected",
    (
        (None, "Not Defined"),
        ("3,1,2", "Not Defined"),
        ("3,0", "Silently Succeed"),
        ("3,1", "Warn but allow installation"),
        ("3,2", "Do not allow installation"),
        ("3,Not Defined", "Not Defined"),
        ("3,spongebob", "Invalid Value"),
    ),
)
def test_driver_signing_reg_conversion(pol_info, val, expected):
    assert pol_info._driver_signing_reg_conversion(val) == expected


@pytest.mark.parametrize(
    "val, expected",
    (
        (None, "Not Defined"),
        ("Silently Succeed", "3,0"),
        ("Warn but allow installation", f"3,{chr(1)}"),
        ("Do not allow installation", f"3,{chr(2)}"),
        ("spongebob", "Invalid Value"),
    ),
)
def test_driver_signing_reg_reverse_conversion(pol_info, val, expected):
    assert pol_info._driver_signing_reg_reverse_conversion(val) == expected


# For the next 3 tests we can't use the parametrized decorator because the
# decorator is evaluated before the imports happen, so the HAS_WIN32 is ignored
# and the decorator tries to evaluate the win32security library on systems
# without pyWin32
def test_sidConversion_no_conversion(pol_info):
    val = ws.ConvertStringSidToSid("S-1-5-0")
    expected = ["S-1-5-0"]
    assert pol_info._sidConversion([val]) == expected


def test_sidConversion_everyone(pol_info):
    val = ws.ConvertStringSidToSid("S-1-1-0")
    expected = ["Everyone"]
    assert pol_info._sidConversion([val]) == expected


def test_sidConversion_administrator(pol_info):
    val = ws.LookupAccountName("", "Administrator")[0]
    expected = [f"{socket.gethostname()}\\Administrator"]
    assert pol_info._sidConversion([val]) == expected


@pytest.mark.parametrize(
    "val, expected",
    (
        (None, None),
        ("", ""),
    ),
)
def test_usernamesToSidObjects_empty_value(pol_info, val, expected):
    assert pol_info._usernamesToSidObjects(val) == expected


def test_usernamesToSidObjects_string_list(pol_info):
    val = "Administrator,Guest"
    admin_sid = ws.LookupAccountName("", "Administrator")[0]
    guest_sid = ws.LookupAccountName("", "Guest")[0]
    expected = [admin_sid, guest_sid]
    assert pol_info._usernamesToSidObjects(val) == expected


def test_usernamesToSidObjects_string_list_error(pol_info):
    val = "spongebob,squarepants"
    with pytest.raises(CommandExecutionError):
        pol_info._usernamesToSidObjects(val)


@pytest.mark.parametrize(
    "val, expected",
    (
        (None, "Not Configured"),
        ("None", "Not Configured"),
        ("true", "Run Windows PowerShell scripts first"),
        ("false", "Run Windows PowerShell scripts last"),
        ("spongebob", "Invalid Value"),
    ),
)
def test_powershell_script_order_conversion(pol_info, val, expected):
    assert pol_info._powershell_script_order_conversion(val) == expected


@pytest.mark.parametrize(
    "val, expected",
    (
        ("Not Configured", None),
        ("Run Windows PowerShell scripts first", "true"),
        ("Run Windows PowerShell scripts last", "false"),
        ("spongebob", "Invalid Value"),
    ),
)
def test_powershell_script_order_reverse_conversion(pol_info, val, expected):
    assert pol_info._powershell_script_order_reverse_conversion(val) == expected


def test_dict_lookup(pol_info):
    lookup = {
        "spongebob": "squarepants",
        "patrick": "squidward",
        "plankton": "mr.crabs",
    }
    assert pol_info._dict_lookup("spongebob", lookup=lookup) == "squarepants"
    assert (
        pol_info._dict_lookup("squarepants", lookup=lookup, value_lookup=True)
        == "spongebob"
    )
    assert pol_info._dict_lookup("homer", lookup=lookup) == "Invalid Value"
    assert (
        pol_info._dict_lookup("homer", lookup=lookup, value_lookup=True)
        == "Invalid Value"
    )
    assert pol_info._dict_lookup("homer") == "Invalid Value"


def test_dict_lookup_bitwise_add(pol_info):
    lookup = {
        0: "spongebob",
        1: "squarepants",
        2: "patrick",
    }
    assert pol_info._dict_lookup_bitwise_add("Not Defined") is None
    assert (
        pol_info._dict_lookup_bitwise_add("not a list", value_lookup=True)
        == "Invalid Value: Not a list"
    )
    assert (
        pol_info._dict_lookup_bitwise_add([], value_lookup=True)
        == "Invalid Value: No lookup passed"
    )
    assert (
        pol_info._dict_lookup_bitwise_add("not an int") == "Invalid Value: Not an int"
    )
    assert pol_info._dict_lookup_bitwise_add(0, lookup=lookup) == []
    assert (
        pol_info._dict_lookup_bitwise_add(
            ["spongebob", "squarepants"], lookup=lookup, value_lookup=True
        )
        == 1
    )
    assert pol_info._dict_lookup_bitwise_add(1, lookup=lookup) == ["squarepants"]
    assert pol_info._dict_lookup_bitwise_add(0, lookup=lookup) == []
    assert pol_info._dict_lookup_bitwise_add(0, lookup=lookup, test_zero=True) == [
        "spongebob"
    ]


@pytest.mark.parametrize(
    "val, expected",
    (
        (["list", "of", "items"], ["list", "of", "items"]),
        ("Not Defined", None),
        ("list,of,items", ["list", "of", "items"]),
        (7, "Invalid Value"),
    ),
)
def test_multi_string_put_transform(pol_info, val, expected):
    assert pol_info._multi_string_put_transform(val) == expected


@pytest.mark.parametrize(
    "val, expected",
    (
        (["list", "of", "items"], ["list", "of", "items"]),
        (None, "Not Defined"),
        ("list,of,items", "Invalid Value"),
        (7, "Invalid Value"),
    ),
)
def test_multi_string_get_transform(pol_info, val, expected):
    assert pol_info._multi_string_get_transform(val) == expected


@pytest.mark.parametrize(
    "val, expected",
    (
        ("String Item", "String Item"),
        ("Not Defined", None),
        (7, None),
    ),
)
def test_string_put_transform(pol_info, val, expected):
    assert pol_info._string_put_transform(val) == expected


def test__virtual__(pol_info):
    assert win_lgpo.__virtual__() == "lgpo"
    with patch("salt.utils.platform.is_windows", return_value=False):
        assert win_lgpo.__virtual__() == (
            False,
            "win_lgpo: Not a Windows System",
        )

    with patch.object(win_lgpo, "HAS_WINDOWS_MODULES", False):
        assert win_lgpo.__virtual__() == (
            False,
            "win_lgpo: Required modules failed to load",
        )


@pytest.mark.parametrize(
    "val, expected",
    (
        (None, b"\x00\x00"),
        ("spongebob", b"s\x00p\x00o\x00n\x00g\x00e\x00b\x00o\x00b\x00\x00\x00"),
    ),
)
def test_encode_string(val, expected):
    assert win_lgpo._encode_string(val) == expected


def test_encode_string_error():
    with pytest.raises(TypeError):
        win_lgpo._encode_string(1)
