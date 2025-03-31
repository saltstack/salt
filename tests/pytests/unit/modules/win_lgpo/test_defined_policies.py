"""
This tests policies that are defined in the giant dictionary in the LGPO module
"""

import pytest

import salt.modules.win_file as win_file
import salt.modules.win_lgpo as win_lgpo
import salt.utils.win_reg as win_reg

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.slow_test,
]


@pytest.fixture
def configure_loader_modules(tmp_path):
    cache_dir = tmp_path / "__test_admx_policy_cache_dir"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return {
        win_lgpo: {
            "__salt__": {
                "file.file_exists": win_file.file_exists,
                "file.makedirs": win_file.makedirs_,
            },
            "__opts__": {
                "cachedir": str(cache_dir),
            },
            "__utils__": {
                "reg.set_value": win_reg.set_value,
                "reg.read_value": win_reg.read_value,
                "reg.delete_value": win_reg.delete_value,
            },
            "__context__": {},
        },
    }


@pytest.mark.destructive_test
def test_vuln_channel_allow():
    key = "SYSTEM\\CurrentControlSet\\Services\\Netlogon\\Parameters"
    vname = "VulnerableChannelAllowList"
    setting = "O:BAG:BAD:(A;;RC;;;BA)"
    win_reg.delete_value(hive="HKLM", key=key, vname=vname)
    try:
        win_lgpo.set_computer_policy(name=vname, setting=setting)
        result = win_reg.read_value(hive="HKLM", key=key, vname=vname)
        assert result["vdata"] == setting
    finally:
        win_reg.delete_value(hive="HKLM", key=key, vname=vname)


@pytest.mark.destructive_test
def test_vuln_channel_allow_not_defined():
    key = "SYSTEM\\CurrentControlSet\\Services\\Netlogon\\Parameters"
    vname = "VulnerableChannelAllowList"
    win_reg.set_value(hive="HKLM", key=key, vname=vname, vdata="junk", vtype="REG_SZ")
    try:
        win_lgpo.set_computer_policy(name=vname, setting="Not Defined")
        assert not win_reg.value_exists(hive="HKLM", key=key, vname=vname)
    finally:
        win_reg.delete_value(hive="HKLM", key=key, vname=vname)


@pytest.mark.destructive_test
def test_ldap_channel_binding_never():
    key = "SYSTEM\\CurrentControlSet\\Services\\NTDS\\Parameters"
    vname = "LdapEnforceChannelBinding"
    setting = "Never"
    win_reg.delete_value(hive="HKLM", key=key, vname=vname)
    try:
        win_lgpo.set_computer_policy(name=vname, setting=setting)
        result = win_reg.read_value(hive="HKLM", key=key, vname=vname)
        assert result["vdata"] == 0
    finally:

        win_reg.delete_value(hive="HKLM", key=key, vname=vname)


@pytest.mark.destructive_test
def test_ldap_channel_binding_when_supported():
    key = "SYSTEM\\CurrentControlSet\\Services\\NTDS\\Parameters"
    vname = "LdapEnforceChannelBinding"
    setting = "When supported"
    win_reg.delete_value(hive="HKLM", key=key, vname=vname)
    try:
        win_lgpo.set_computer_policy(name=vname, setting=setting)
        result = win_reg.read_value(hive="HKLM", key=key, vname=vname)
        assert result["vdata"] == 1
    finally:

        win_reg.delete_value(hive="HKLM", key=key, vname=vname)


@pytest.mark.destructive_test
def test_ldap_channel_binding_always():
    key = "SYSTEM\\CurrentControlSet\\Services\\NTDS\\Parameters"
    vname = "LdapEnforceChannelBinding"
    setting = "Always"
    win_reg.delete_value(hive="HKLM", key=key, vname=vname)
    try:
        win_lgpo.set_computer_policy(name=vname, setting=setting)
        result = win_reg.read_value(hive="HKLM", key=key, vname=vname)
        assert result["vdata"] == 2
    finally:

        win_reg.delete_value(hive="HKLM", key=key, vname=vname)


@pytest.mark.destructive_test
def test_ldap_channel_binding_not_defined():
    key = "SYSTEM\\CurrentControlSet\\Services\\NTDS\\Parameters"
    vname = "LdapEnforceChannelBinding"
    win_reg.set_value(hive="HKLM", key=key, vname=vname, vdata=1, vtype="REG_DWORD")
    try:
        win_lgpo.set_computer_policy(name=vname, setting="Not Defined")
        assert not win_reg.value_exists(hive="HKLM", key=key, vname=vname)
    finally:
        win_reg.delete_value(hive="HKLM", key=key, vname=vname)
