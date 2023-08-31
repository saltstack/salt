import re

import pytest

import salt.modules.win_file as win_file
from salt.exceptions import CommandExecutionError

pytestmark = [pytest.mark.windows_whitelisted, pytest.mark.skip_unless_on_windows]


def test__get_version_os():
    expected = ["32-bit Windows", "Windows NT"]
    result = win_file._get_version_os(0x00040004)
    assert result == expected


def test__get_version_type_application():
    expected = "Application"
    result = win_file._get_version_type(1, 0)
    assert result == expected


def test__get_version_type_driver():
    expected = "Printer Driver"
    result = win_file._get_version_type(3, 1)
    assert result == expected


def test__get_version_type_font():
    expected = "TrueType Font"
    result = win_file._get_version_type(4, 3)
    assert result == expected


def test__get_version_type_virtual_device():
    expected = "Virtual Device: 12345"
    result = win_file._get_version_type(5, 12345)
    assert result == expected


def test__get_version_exe():
    result = win_file._get_version(r"C:\Windows\notepad.exe")
    regex = re.compile(r"\d+.\d+.\d+.\d+")
    assert regex.search(result)


def test__get_version_dll():
    result = win_file._get_version(r"C:\Windows\System32\FirewallAPI.dll")
    regex = re.compile(r"\d+.\d+.\d+.\d+")
    assert regex.search(result)


def test__get_version_sys():
    result = win_file._get_version(r"C:\Windows\System32\drivers\netio.sys")
    regex = re.compile(r"\d+.\d+.\d+.\d+")
    assert regex.search(result)


def test_version_missing_file():
    with pytest.raises(CommandExecutionError):
        win_file.version("C:\\Windows\\bogus.exe")


def test_version_missing_directory():
    with pytest.raises(CommandExecutionError):
        win_file.version("C:\\Windows\\System32")


def test_version_details_missing_file():
    with pytest.raises(CommandExecutionError):
        win_file.version_details("C:\\Windows\\bogus.exe")


def test_version_details_missing_directory():
    with pytest.raises(CommandExecutionError):
        win_file.version_details("C:\\Windows\\System32")


def test_version_details_exe():
    result = win_file.version_details(r"C:\Windows\notepad.exe")
    assert result["FileDescription"] == "Notepad"
    assert result["FileType"] == "Application"
    assert result["OperatingSystem"] == ["32-bit Windows", "Windows NT"]
    regex = re.compile(r"\d+.\d+.\d+.\d+")
    assert regex.search(result["ProductVersion"])
    assert regex.search(result["Version"])


def test_version_details_dll():
    result = win_file.version_details(r"C:\Windows\System32\FirewallAPI.dll")
    assert "Firewall API" in result["FileDescription"]
    assert result["FileType"] == "DLL"
    assert result["OperatingSystem"] == ["32-bit Windows", "Windows NT"]
    regex = re.compile(r"\d+.\d+.\d+.\d+")
    assert regex.search(result["ProductVersion"])
    assert regex.search(result["Version"])


def test_version_details_sys():
    result = win_file.version_details(r"C:\Windows\System32\drivers\netio.sys")
    assert result["FileDescription"] == "Network I/O Subsystem"
    assert result["FileType"] == "Network Driver"
    assert result["OperatingSystem"] == ["32-bit Windows", "Windows NT"]
    regex = re.compile(r"\d+.\d+.\d+.\d+")
    assert regex.search(result["ProductVersion"])
    assert regex.search(result["Version"])
