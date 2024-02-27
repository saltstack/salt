"""
:codeauthor: Shane Lee <slee@saltstack.com>
"""

import pytest

import salt.modules.win_lgpo as win_lgpo

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.slow_test,
]


@pytest.fixture
def reg_pol_dword():
    data = (
        b"PReg\x01\x00\x00\x00"  # Header
        b"[\x00"  # Opening list of policies
        b"S\x00o\x00m\x00e\x00\\\x00K\x00e\x00y\x00\x00\x00;\x00"  # Key
        b"V\x00a\x00l\x00u\x00e\x00N\x00a\x00m\x00e\x00\x00\x00;\x00"  # Value
        b"\x04\x00\x00\x00;\x00"  # Reg DWord Type
        b"\x04\x00\x00\x00;\x00"  # Size
        # b"\x01\x00\x00\x00"  # Reg Dword Data
        b"\x00\x00\x00\x00"  # No Data
        b"]\x00"  # Closing list of policies
    )
    yield data


def test_get_data_from_reg_pol_data(reg_pol_dword):
    encoded_name = "ValueName".encode("utf-16-le")
    encoded_null = chr(0).encode("utf-16-le")
    encoded_semicolon = ";".encode("utf-16-le")
    encoded_type = chr(4).encode("utf-16-le")
    encoded_size = chr(4).encode("utf-16-le")
    search_string = b"".join(
        [
            encoded_semicolon,
            encoded_name,
            encoded_null,
            encoded_semicolon,
            encoded_type,
            encoded_null,
            encoded_semicolon,
            encoded_size,
            encoded_null,
        ]
    )
    result = win_lgpo._getDataFromRegPolData(
        search_string, reg_pol_dword, return_value_name=True
    )
    assert result == {"ValueName": 0}
