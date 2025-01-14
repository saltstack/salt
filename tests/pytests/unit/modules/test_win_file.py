import os
import re

import pytest

import salt.modules.win_file as win_file
import salt.utils.user
import salt.utils.win_dacl
from salt.exceptions import CommandExecutionError
from tests.support.mock import patch

pytestmark = [pytest.mark.windows_whitelisted, pytest.mark.skip_unless_on_windows]


@pytest.fixture
def configure_loader_modules():
    return {
        win_file: {},
        salt.utils.win_dacl: {},
    }


def test__virtual__not_windows():
    with patch("salt.utils.platform.is_windows", autospec=True, return_value=False):
        expected = (False, "Module win_file: Missing Win32 modules")
        result = win_file.__virtual__()
        assert result == expected
    with patch("salt.modules.win_file.HAS_WINDOWS_MODULES", False):
        expected = (False, "Module win_file: Missing Win32 modules")
        result = win_file.__virtual__()
        assert result == expected


def test__virtual__no_dacl():
    with patch("salt.modules.win_file.HAS_WIN_DACL", False):
        expected = (False, "Module win_file: Unable to load salt.utils.win_dacl")
        result = win_file.__virtual__()
        assert result == expected


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


def test_get_pgid_error():
    with pytest.raises(CommandExecutionError):
        win_file.get_pgid("C:\\Path\\That\\Does\\Not\\Exist.txt")


def test_get_pgid():
    """
    We can't know what this value is, so we're just making sure it found
    something
    """
    result = win_file.get_pgid(os.getenv("COMSPEC"))
    assert result != ""


def test_group_to_gid():
    with patch.dict(win_file.__opts__, {}):
        result = win_file.group_to_gid("Administrators")
    expected = "S-1-5-32-544"
    assert result == expected


def test_group_to_gid_empty():
    with patch.dict(win_file.__opts__, {}):
        result = win_file.group_to_gid("")
    expected = "S-1-5-32"
    assert result == expected


def test_uid_to_user():
    result = win_file.uid_to_user("S-1-5-32-544")
    expected = "Administrators"
    assert result == expected


def test_uid_to_user_empty():
    result = win_file.uid_to_user("")
    expected = ""
    assert result == expected


def test_user_to_uid():
    result = win_file.user_to_uid("Administrator")
    expected = salt.utils.win_dacl.get_sid_string("Administrator")
    assert result == expected


def test_user_to_uid_none():
    result = win_file.user_to_uid(None)
    expected = salt.utils.win_dacl.get_sid_string(salt.utils.user.get_user())
    assert result == expected


def test_get_uid():
    """
    We can't know what this value is, so we're just making sure it found
    something
    """
    result = win_file.get_uid(os.getenv("WINDIR"))
    assert result != ""


def test_get_uid_error():
    with pytest.raises(CommandExecutionError):
        win_file.get_uid("C:\\fake\\path")


def test_chown(tmp_path):
    test_file = tmp_path / "test_file.txt"
    test_file.touch()
    win_file.chown(path=str(test_file), user="Administrators", pgroup="Guests")
    assert win_file.get_user(str(test_file)) == "Administrators"
    assert win_file.get_pgroup(str(test_file)) == "Guests"


def test_chpgrp(tmp_path):
    test_file = tmp_path / "test_file.txt"
    test_file.touch()
    win_file.chown(path=str(test_file), user="Administrators", pgroup="Guests")
    win_file.chpgrp(path=str(test_file), group="Administrators")
    assert win_file.get_pgroup(str(test_file)) == "Administrators"


def test_stats_mode(tmp_path):
    test_file = tmp_path / "test_file.txt"
    test_file.touch()
    results = win_file.stats(str(test_file))
    assert results["mode"] == "0666"


def test_is_link_true(tmp_path):
    test_source = tmp_path / "test_source.txt"
    test_link = tmp_path / "test_link.txt"
    test_source.touch()
    test_link.symlink_to(test_source)
    results = win_file.is_link(str(test_link))
    expected = True
    assert results == expected


def test_is_link_false(tmp_path):
    test_file = tmp_path / "test_not_link.txt"
    test_file.touch()
    results = win_file.is_link(str(test_file))
    expected = False
    assert results == expected


def test_mkdir(tmp_path):
    test_dir = tmp_path / "test_dir"
    grant_perms = {"Guests": {"perms": "full_control"}}
    win_file.mkdir(
        path=str(test_dir),
        owner="Administrators",
        grant_perms=grant_perms,
    )
    owner = win_file.get_user(str(test_dir))
    assert owner == "Administrators"
    perms = salt.utils.win_dacl.get_permissions(str(test_dir))
    assert perms["Not Inherited"]["Guests"]["grant"]["permissions"] == "Full control"


def test_check_perms(tmp_path):
    test_dir = tmp_path / "test_dir"
    test_dir.mkdir()
    grant_perms = {"Guests": {"perms": "full_control"}}
    ret = {}
    with patch.dict(salt.utils.win_dacl.__opts__, {"test": False}):
        result = win_file.check_perms(
            path=str(test_dir),
            ret=ret,
            owner="Guests",
            grant_perms=grant_perms,
            inheritance=False,
        )

    expected = {
        "changes": {
            "grant_perms": {
                "Guests": {
                    "permissions": "full_control",
                },
            },
            "owner": "Guests",
        },
        "comment": "",
        "name": str(test_dir),
        "result": True,
    }

    assert result["changes"]["grant_perms"] == expected["changes"]["grant_perms"]
    owner = win_file.get_user(str(test_dir))
    assert owner == "Guests"
    perms = salt.utils.win_dacl.get_permissions(str(test_dir))
    assert perms["Not Inherited"]["Guests"]["grant"]["permissions"] == "Full control"


def test_set_perms(tmp_path):
    test_dir = tmp_path / "test_dir"
    test_dir.mkdir()
    grant_perms = {"Guests": {"perms": "full_control"}}
    win_file.set_perms(
        path=str(test_dir),
        grant_perms=grant_perms,
    )
    perms = salt.utils.win_dacl.get_permissions(str(test_dir))
    assert perms["Not Inherited"]["Guests"]["grant"]["permissions"] == "Full control"


def test_get_user():
    """
    We can't know what this value is, so we're just making sure it found
    something
    """
    result = win_file.get_user(os.getenv("WINDIR"))
    assert result != ""


def test_get_user_error():
    with pytest.raises(CommandExecutionError):
        win_file.get_user("C:\\fake\\path")


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
