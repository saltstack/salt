import pytest

import salt.utils.files
import salt.utils.win_lgpo_reg as win_lgpo_reg
from salt.exceptions import CommandExecutionError

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
]


def test_dict_to_reg_pol_empty():
    """
    Test an empty dict. Should only contain the header
    """
    test_dict = {}
    expected = b"PReg\x01\x00\x00\x00"
    result = win_lgpo_reg.dict_to_reg_pol(test_dict)
    assert result == expected


def test_reg_pol_to_dict_empty():
    """
    Test reg pol data with nothing configured. Only the header. Should return
    an empty dict
    """
    test_data = b"PReg\x01\x00\x00\x00"
    expected = {}
    result = win_lgpo_reg.reg_pol_to_dict(test_data)
    assert result == expected


def test_reg_pol_to_dict_empty_invalid():
    """
    Test reg pol data with nothing configured. Only the header. Should return
    an empty dict
    """
    test_data = b""
    pytest.raises(CommandExecutionError, win_lgpo_reg.reg_pol_to_dict, test_data)


def test_dict_to_reg_pol_reg_sz():
    """
    Test REG_SZ type
    """
    test_dict = {
        "SOFTWARE\\MyKey": {
            "MyValue": {
                "data": "String",
                "type": "REG_SZ",
            },
        },
    }
    expected = (
        b"PReg\x01\x00\x00\x00[\x00"
        b"S\x00O\x00F\x00T\x00W\x00A\x00R\x00E\x00\\\x00M\x00y\x00K\x00e\x00y\x00\x00\x00;\x00"
        b"M\x00y\x00V\x00a\x00l\x00u\x00e\x00\x00\x00;\x00"
        b"\x01\x00\x00\x00;\x00"
        b"\x0e\x00\x00\x00;\x00"
        b"S\x00t\x00r\x00i\x00n\x00g\x00\x00\x00"
        b"]\x00"
    )
    result = win_lgpo_reg.dict_to_reg_pol(test_dict)
    assert result == expected


def test_reg_pol_to_dict_reg_sz():
    """
    Test REG_SZ type
    """
    test_data = (
        b"PReg\x01\x00\x00\x00[\x00"
        b"S\x00O\x00F\x00T\x00W\x00A\x00R\x00E\x00\\\x00M\x00y\x00K\x00e\x00y\x00\x00\x00;\x00"
        b"M\x00y\x00V\x00a\x00l\x00u\x00e\x00\x00\x00;\x00"
        b"\x01\x00\x00\x00;\x00"
        b"\x0e\x00\x00\x00;\x00"
        b"S\x00t\x00r\x00i\x00n\x00g\x00\x00\x00"
        b"]\x00"
    )
    expected = {
        "SOFTWARE\\MyKey": {
            "MyValue": {
                "data": "String",
                "type": "REG_SZ",
            },
        },
    }
    result = win_lgpo_reg.reg_pol_to_dict(test_data)
    assert result == expected


def test_dict_to_reg_pol_reg_expand_sz():
    """
    Test REG_EXPAND_SZ type
    """
    test_dict = {
        "SOFTWARE\\MyKey": {
            "MyValue": {
                "data": "%WINVER%\\String",
                "type": "REG_EXPAND_SZ",
            },
        },
    }
    expected = (
        b"PReg\x01\x00\x00\x00[\x00"
        b"S\x00O\x00F\x00T\x00W\x00A\x00R\x00E\x00\\\x00M\x00y\x00K\x00e\x00y\x00\x00\x00;\x00"
        b"M\x00y\x00V\x00a\x00l\x00u\x00e\x00\x00\x00;\x00"
        b"\x02\x00\x00\x00;\x00"
        b" \x00\x00\x00;\x00"
        b"%\x00W\x00I\x00N\x00V\x00E\x00R\x00%\x00\\\x00S\x00t\x00r\x00i\x00n\x00g\x00\x00\x00"
        b"]\x00"
    )
    result = win_lgpo_reg.dict_to_reg_pol(test_dict)
    assert result == expected


def test_reg_pol_to_dict_reg_expand_sz():
    """
    Test REG_EXPAND_SZ type
    """
    test_data = (
        b"PReg\x01\x00\x00\x00[\x00"
        b"S\x00O\x00F\x00T\x00W\x00A\x00R\x00E\x00\\\x00M\x00y\x00K\x00e\x00y\x00\x00\x00;\x00"
        b"M\x00y\x00V\x00a\x00l\x00u\x00e\x00\x00\x00;\x00"
        b"\x02\x00\x00\x00;\x00"
        b" \x00\x00\x00;\x00"
        b"%\x00W\x00I\x00N\x00V\x00E\x00R\x00%\x00\\\x00S\x00t\x00r\x00i\x00n\x00g\x00\x00\x00"
        b"]\x00"
    )
    expected = {
        "SOFTWARE\\MyKey": {
            "MyValue": {
                "data": "%WINVER%\\String",
                "type": "REG_EXPAND_SZ",
            },
        },
    }
    result = win_lgpo_reg.reg_pol_to_dict(test_data)
    assert result == expected


def test_dict_to_reg_pol_reg_dword():
    """
    Test REG_DWORD type
    """
    test_dict = {
        "SOFTWARE\\MyKey": {
            "MyValue": {
                "data": 1,
                "type": "REG_DWORD",
            },
        },
    }
    expected = (
        b"PReg\x01\x00\x00\x00[\x00"
        b"S\x00O\x00F\x00T\x00W\x00A\x00R\x00E\x00\\\x00M\x00y\x00K\x00e\x00y\x00\x00\x00;\x00"
        b"M\x00y\x00V\x00a\x00l\x00u\x00e\x00\x00\x00;\x00"
        b"\x04\x00\x00\x00;\x00"
        b"\x04\x00\x00\x00;\x00"
        b"\x01\x00\x00\x00"
        b"]\x00"
    )
    result = win_lgpo_reg.dict_to_reg_pol(test_dict)
    assert result == expected


def test_reg_pol_to_dict_reg_dword():
    """
    Test REG_DWORD type
    """
    test_data = (
        b"PReg\x01\x00\x00\x00[\x00"
        b"S\x00O\x00F\x00T\x00W\x00A\x00R\x00E\x00\\\x00M\x00y\x00K\x00e\x00y\x00\x00\x00;\x00"
        b"M\x00y\x00V\x00a\x00l\x00u\x00e\x00\x00\x00;\x00"
        b"\x04\x00\x00\x00;\x00"
        b"\x04\x00\x00\x00;\x00"
        b"\x01\x00\x00\x00"
        b"]\x00"
    )
    expected = {
        "SOFTWARE\\MyKey": {
            "MyValue": {
                "data": 1,
                "type": "REG_DWORD",
            },
        },
    }
    result = win_lgpo_reg.reg_pol_to_dict(test_data)
    assert result == expected


def test_dict_to_reg_pol_reg_multi_sz():
    """
    Test REG_MULTI_SZ type
    """
    test_dict = {
        "SOFTWARE\\MyKey": {
            "MyValue": {
                "data": ["rick", "morty"],
                "type": "REG_MULTI_SZ",
            },
        },
    }
    expected = (
        b"PReg\x01\x00\x00\x00[\x00"
        b"S\x00O\x00F\x00T\x00W\x00A\x00R\x00E\x00\\\x00M\x00y\x00K\x00e\x00y\x00\x00\x00;\x00"
        b"M\x00y\x00V\x00a\x00l\x00u\x00e\x00\x00\x00;\x00"
        b"\x07\x00\x00\x00;\x00"
        b"\x18\x00\x00\x00;\x00"
        b"r\x00i\x00c\x00k\x00\x00\x00m\x00o\x00r\x00t\x00y\x00\x00\x00\x00\x00"
        b"]\x00"
    )
    result = win_lgpo_reg.dict_to_reg_pol(test_dict)
    assert result == expected


def test_reg_pol_to_dict_reg_multi_sz():
    """
    Test REG_MULTI_SZ type
    """
    test_data = (
        b"PReg\x01\x00\x00\x00[\x00"
        b"S\x00O\x00F\x00T\x00W\x00A\x00R\x00E\x00\\\x00M\x00y\x00K\x00e\x00y\x00\x00\x00;\x00"
        b"M\x00y\x00V\x00a\x00l\x00u\x00e\x00\x00\x00;\x00"
        b"\x07\x00\x00\x00;\x00"
        b"\x18\x00\x00\x00;\x00"
        b"r\x00i\x00c\x00k\x00\x00\x00m\x00o\x00r\x00t\x00y\x00\x00\x00\x00\x00"
        b"]\x00"
    )
    expected = {
        "SOFTWARE\\MyKey": {
            "MyValue": {
                "data": ["rick", "morty"],
                "type": "REG_MULTI_SZ",
            },
        },
    }
    result = win_lgpo_reg.reg_pol_to_dict(test_data)
    assert result == expected


def test_dict_to_reg_pol_reg_multi_sz_none():
    """
    Test REG_MULTI_SZ type when the value is None
    """
    test_dict = {
        "SOFTWARE\\MyKey": {
            "MyValue": {
                "data": None,
                "type": "REG_MULTI_SZ",
            },
        },
    }
    expected = (
        b"PReg\x01\x00\x00\x00[\x00"
        b"S\x00O\x00F\x00T\x00W\x00A\x00R\x00E\x00\\\x00M\x00y\x00K\x00e\x00y\x00\x00\x00;\x00"
        b"M\x00y\x00V\x00a\x00l\x00u\x00e\x00\x00\x00;\x00"
        b"\x07\x00\x00\x00;\x00"
        b"\x02\x00\x00\x00;\x00"
        b"\x00\x00"
        b"]\x00"
    )
    result = win_lgpo_reg.dict_to_reg_pol(test_dict)
    assert result == expected


def test_dict_to_reg_pol_reg_multi_sz_empty_list():
    """
    Test REG_MULTI_SZ type when the value is an empty list
    """
    test_dict = {
        "SOFTWARE\\MyKey": {
            "MyValue": {
                "data": [],
                "type": "REG_MULTI_SZ",
            },
        },
    }
    expected = (
        b"PReg\x01\x00\x00\x00[\x00"
        b"S\x00O\x00F\x00T\x00W\x00A\x00R\x00E\x00\\\x00M\x00y\x00K\x00e\x00y\x00\x00\x00;\x00"
        b"M\x00y\x00V\x00a\x00l\x00u\x00e\x00\x00\x00;\x00"
        b"\x07\x00\x00\x00;\x00"
        b"\x02\x00\x00\x00;\x00"
        b"\x00\x00"
        b"]\x00"
    )
    result = win_lgpo_reg.dict_to_reg_pol(test_dict)
    assert result == expected


def test_dict_to_reg_pol_reg_multi_sz_empty_list_value():
    """
    Test REG_MULTI_SZ type when the value is a list with an empty value
    """
    test_dict = {
        "SOFTWARE\\MyKey": {
            "MyValue": {
                "data": [""],
                "type": "REG_MULTI_SZ",
            },
        },
    }
    expected = (
        b"PReg\x01\x00\x00\x00[\x00"
        b"S\x00O\x00F\x00T\x00W\x00A\x00R\x00E\x00\\\x00M\x00y\x00K\x00e\x00y\x00\x00\x00;\x00"
        b"M\x00y\x00V\x00a\x00l\x00u\x00e\x00\x00\x00;\x00"
        b"\x07\x00\x00\x00;\x00"
        b"\x02\x00\x00\x00;\x00"
        b"\x00\x00"
        b"]\x00"
    )
    result = win_lgpo_reg.dict_to_reg_pol(test_dict)
    assert result == expected


def test_dict_to_reg_pol_reg_multi_sz_list_single_value():
    """
    Test REG_MULTI_SZ type when the value is a list with an empty value
    """
    test_dict = {
        "SOFTWARE\\MyKey": {
            "MyValue": {
                "data": ["rick"],
                "type": "REG_MULTI_SZ",
            },
        },
    }
    expected = (
        b"PReg\x01\x00\x00\x00[\x00"
        b"S\x00O\x00F\x00T\x00W\x00A\x00R\x00E\x00\\\x00M\x00y\x00K\x00e\x00y\x00\x00\x00;\x00"
        b"M\x00y\x00V\x00a\x00l\x00u\x00e\x00\x00\x00;\x00"
        b"\x07\x00\x00\x00;\x00"
        b"\x0c\x00\x00\x00;\x00"
        b"r\x00i\x00c\x00k\x00\x00\x00\x00\x00"
        b"]\x00"
    )
    result = win_lgpo_reg.dict_to_reg_pol(test_dict)
    assert result == expected


def test_reg_pol_to_dict_reg_multi_sz_empty():
    """
    Test REG_MULTI_SZ type when the value is empty
    """
    test_data = (
        b"PReg\x01\x00\x00\x00[\x00"
        b"S\x00O\x00F\x00T\x00W\x00A\x00R\x00E\x00\\\x00M\x00y\x00K\x00e\x00y\x00\x00\x00;\x00"
        b"M\x00y\x00V\x00a\x00l\x00u\x00e\x00\x00\x00;\x00"
        b"\x07\x00\x00\x00;\x00"
        b"\x02\x00\x00\x00;\x00"
        b"\x00\x00"
        b"]\x00"
    )
    expected = {
        "SOFTWARE\\MyKey": {
            "MyValue": {
                "data": None,
                "type": "REG_MULTI_SZ",
            },
        },
    }
    result = win_lgpo_reg.reg_pol_to_dict(test_data)
    assert result == expected


def test_dict_to_reg_pol_reg_qword():
    """
    Test REG_QWORD
    """
    test_dict = {
        "SOFTWARE\\MyKey": {
            "MyValue": {
                "data": 1,
                "type": "REG_QWORD",
            },
        },
    }
    expected = (
        b"PReg\x01\x00\x00\x00[\x00"
        b"S\x00O\x00F\x00T\x00W\x00A\x00R\x00E\x00\\\x00M\x00y\x00K\x00e\x00y\x00\x00\x00;\x00"
        b"M\x00y\x00V\x00a\x00l\x00u\x00e\x00\x00\x00;\x00"
        b"\x0b\x00\x00\x00;\x00"
        b"\x08\x00\x00\x00;\x00"
        b"\x01\x00\x00\x00\x00\x00\x00\x00"
        b"]\x00"
    )
    result = win_lgpo_reg.dict_to_reg_pol(test_dict)
    assert result == expected


def test_reg_pol_to_dict_reg_qword():
    """
    Test REG_QWORD
    """
    test_data = (
        b"PReg\x01\x00\x00\x00[\x00"
        b"S\x00O\x00F\x00T\x00W\x00A\x00R\x00E\x00\\\x00M\x00y\x00K\x00e\x00y\x00\x00\x00;\x00"
        b"M\x00y\x00V\x00a\x00l\x00u\x00e\x00\x00\x00;\x00"
        b"\x0b\x00\x00\x00;\x00"
        b"\x08\x00\x00\x00;\x00"
        b"\x01\x00\x00\x00\x00\x00\x00\x00"
        b"]\x00"
    )
    expected = {
        "SOFTWARE\\MyKey": {
            "MyValue": {
                "data": 1,
                "type": "REG_QWORD",
            },
        },
    }
    result = win_lgpo_reg.reg_pol_to_dict(test_data)
    assert result == expected


def test_reg_pol_to_dict_invalid_type():
    """
    Test Invalid Registry Type
    """
    test_data = (
        b"PReg\x01\x00\x00\x00[\x00"
        b"S\x00O\x00F\x00T\x00W\x00A\x00R\x00E\x00\\\x00M\x00y\x00K\x00e\x00y\x00\x00\x00;\x00"
        b"M\x00y\x00V\x00a\x00l\x00u\x00e\x00\x00\x00;\x00"
        b"\x1b\x00\x00\x00;\x00"
        b"\x04\x00\x00\x00;\x00"
        b"\x01\x00\x00\x00"
        b"]\x00"
    )
    pytest.raises(CommandExecutionError, win_lgpo_reg.reg_pol_to_dict, test_data)


def test_dict_to_reg_pol_invalid_type():
    """
    Test Invalid Registry Type
    """
    test_dict = {
        "SOFTWARE\\MyKey": {
            "MyValue": {
                "data": 1,
                "type": "REG_INVALID_TYPE",
            },
        },
    }
    pytest.raises(CommandExecutionError, win_lgpo_reg.dict_to_reg_pol, test_dict)


def test_dict_to_reg_pol_too_big():
    """
    Test when the data exceeds 65535 characters
    """
    test_dict = {
        "SOFTWARE\\MyKey": {
            "MyValue": {
                "data": "*" * 65536,
                "type": "REG_SZ",
            },
        },
    }
    pytest.raises(CommandExecutionError, win_lgpo_reg.dict_to_reg_pol, test_dict)


def test_issue_56769_windows_line_endings():
    """
    Test that it handles a gpt.ini file with Windows-style line endings.
    Should create a gpt.ini with Windows-style line endings.
    """

    data_to_write = b"[\x00d\x00u\x00m\x00m\x00y\x00\\\x00d\x00a\x00t\x00a]\x00"
    gpt_extension = "gPCMachineExtensionNames"
    gpt_extension_guid = (
        "[{35378EAC-683F-11D2-A89A-00C04FBBCFA2}{D02B1F72-3407-48AE-BA88-E8213C6761F1}]"
    )

    gpt_ini = "\r\n".join(["[General]", "gPCMachineExtensionNames=", "Version=8", ""])
    expected = "\r\n".join(
        [
            "[General]",
            "gPCMachineExtensionNames=[{35378EAC-683F-11D2-A89A-00C04FBBCFA2}{D02B1F72-3407-48AE-BA88-E8213C6761F1}]",
            "Version=9",
            "",
        ]
    )

    with pytest.helpers.temp_file(
        "Registry.pol"
    ) as reg_pol_file, pytest.helpers.temp_file("gpt.ini") as gpt_ini_file:
        # We're using salt.utils.file.fopen here because the temp_file helper
        # doesn't preserve line endings when writing the test file
        with salt.utils.files.fopen(str(gpt_ini_file), "wb") as fp:
            fp.write(gpt_ini.encode("utf-8"))
        win_lgpo_reg.write_reg_pol_data(
            data_to_write=data_to_write,
            policy_file_path=str(reg_pol_file),
            gpt_extension=gpt_extension,
            gpt_extension_guid=gpt_extension_guid,
            gpt_ini_path=str(gpt_ini_file),
        )
        # We're using salt.utils.file.fopen here because the temp_file helper
        # doesn't preserve line endings when reading the test file
        with salt.utils.files.fopen(str(gpt_ini_file)) as fp:
            result = fp.read()

        assert result == expected


def test_issue_56769_unix_line_endings():
    """
    Test that it handles a gpt.ini file with Unix-style line endings.
    Should create a gpt.ini with Windows-style line endings.
    """

    data_to_write = b"[\x00d\x00u\x00m\x00m\x00y\x00\\\x00d\x00a\x00t\x00a]\x00"
    gpt_extension = "gPCMachineExtensionNames"
    gpt_extension_guid = (
        "[{35378EAC-683F-11D2-A89A-00C04FBBCFA2}{D02B1F72-3407-48AE-BA88-E8213C6761F1}]"
    )

    gpt_ini = "\n".join(["[General]", "gPCMachineExtensionNames=", "Version=8", ""])
    expected = "\r\n".join(
        [
            "[General]",
            "gPCMachineExtensionNames=[{35378EAC-683F-11D2-A89A-00C04FBBCFA2}{D02B1F72-3407-48AE-BA88-E8213C6761F1}]",
            "Version=9",
            "",
        ]
    )

    with pytest.helpers.temp_file(
        "Registry.pol"
    ) as reg_pol_file, pytest.helpers.temp_file("gpt.ini") as gpt_ini_file:
        # We're using salt.utils.file.fopen here because the temp_file helper
        # doesn't preserve line endings when writing the test file
        with salt.utils.files.fopen(str(gpt_ini_file), "wb") as fp:
            fp.write(gpt_ini.encode("utf-8"))
        win_lgpo_reg.write_reg_pol_data(
            data_to_write=data_to_write,
            policy_file_path=str(reg_pol_file),
            gpt_extension=gpt_extension,
            gpt_extension_guid=gpt_extension_guid,
            gpt_ini_path=str(gpt_ini_file),
        )
        # We're using salt.utils.file.fopen here because the temp_file helper
        # doesn't preserve line endings when reading the test file
        with salt.utils.files.fopen(str(gpt_ini_file)) as fp:
            result = fp.read()

        assert result == expected


def test_issue_56769_mixed_line_endings():
    """
    Test that it handles a gpt.ini file with mixed line endings.
    Should create a gpt.ini with Windows-style line endings.
    """

    data_to_write = b"[\x00d\x00u\x00m\x00m\x00y\x00\\\x00d\x00a\x00t\x00a]\x00"
    gpt_extension = "gPCMachineExtensionNames"
    gpt_extension_guid = (
        "[{35378EAC-683F-11D2-A89A-00C04FBBCFA2}{D02B1F72-3407-48AE-BA88-E8213C6761F1}]"
    )

    gpt_ini = "[General]\ngPCMachineExtensionNames=\r\nVersion=8\n"
    expected = "\r\n".join(
        [
            "[General]",
            "gPCMachineExtensionNames=[{35378EAC-683F-11D2-A89A-00C04FBBCFA2}{D02B1F72-3407-48AE-BA88-E8213C6761F1}]",
            "Version=9",
            "",
        ]
    )

    with pytest.helpers.temp_file(
        "Registry.pol"
    ) as reg_pol_file, pytest.helpers.temp_file("gpt.ini") as gpt_ini_file:
        # We're using salt.utils.file.fopen here because the temp_file helper
        # doesn't preserve line endings when writing the test file
        with salt.utils.files.fopen(str(gpt_ini_file), "wb") as fp:
            fp.write(gpt_ini.encode("utf-8"))
        win_lgpo_reg.write_reg_pol_data(
            data_to_write=data_to_write,
            policy_file_path=str(reg_pol_file),
            gpt_extension=gpt_extension,
            gpt_extension_guid=gpt_extension_guid,
            gpt_ini_path=str(gpt_ini_file),
        )
        # We're using salt.utils.file.fopen here because the temp_file helper
        # doesn't preserve line endings when reading the test file
        with salt.utils.files.fopen(str(gpt_ini_file)) as fp:
            result = fp.read()

        assert result == expected
