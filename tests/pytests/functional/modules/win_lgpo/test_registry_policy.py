import pytest

import salt.utils.win_reg

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.destructive_test,
]


@pytest.fixture(scope="module")
def lgpo(modules):
    return modules.lgpo


@pytest.mark.parametrize(
    "name, setting, hive, key, vname, exp_vdata, exp_vtype, exp_removed",
    [
        (
            "DisableDomainCreds",
            "Enabled",
            "HKLM",
            "SYSTEM\\CurrentControlSet\\Control\\Lsa",
            "DisableDomainCreds",
            1,
            "REG_DWORD",
            False,
        ),
        (
            "Network access: Do not allow storage of passwords and credentials for network authentication",
            "Disabled",
            "HKLM",
            "SYSTEM\\CurrentControlSet\\Control\\Lsa",
            "DisableDomainCreds",
            0,
            "REG_DWORD",
            False,
        ),
        (
            "DisableDomainCreds",
            "Not Defined",
            "HKLM",
            "SYSTEM\\CurrentControlSet\\Control\\Lsa",
            "DisableDomainCreds",
            1,
            None,
            True,
        ),
        (
            "ForceGuest",
            "Guest only - local users authenticate as Guest",
            "HKLM",
            "SYSTEM\\CurrentControlSet\\Control\\Lsa",
            "ForceGuest",
            1,
            "REG_DWORD",
            False,
        ),
        (
            "Network access: Sharing and security model for local accounts",
            "Classic - local users authenticate as themselves",
            "HKLM",
            "SYSTEM\\CurrentControlSet\\Control\\Lsa",
            "ForceGuest",
            0,
            "REG_DWORD",
            False,
        ),
        (
            "ForceGuest",
            "Not Defined",
            "HKLM",
            "SYSTEM\\CurrentControlSet\\Control\\Lsa",
            "ForceGuest",
            1,
            "REG_DWORD",
            True,
        ),
        (
            "ScRemoveOption",
            "No Action",
            "HKLM",
            "Software\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon",
            "ScRemoveOption",
            "0",
            "REG_SZ",
            False,
        ),
        (
            "Interactive logon: Smart card removal behavior",
            "Lock Workstation",
            "HKLM",
            "Software\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon",
            "ScRemoveOption",
            "1",
            "REG_SZ",
            False,
        ),
        (
            "ScRemoveOption",
            "Not Defined",
            "HKLM",
            "Software\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon",
            "ScRemoveOption",
            "0",
            "REG_SZ",
            True,
        ),
        (
            "RelaxMinimumPasswordLengthLimits",
            "Enabled",
            "HKLM",
            "SYSTEM\\CurrentControlSet\\Control\\SAM",
            "RelaxMinimumPasswordLengthLimits",
            1,
            "REG_DWORD",
            False,
        ),
        (
            "RelaxMinimumPasswordLengthLimits",
            "Disabled",
            "HKLM",
            "SYSTEM\\CurrentControlSet\\Control\\SAM",
            "RelaxMinimumPasswordLengthLimits",
            0,
            "REG_DWORD",
            False,
        ),
        (
            "RelaxMinimumPasswordLengthLimits",
            "Not Defined",
            "HKLM",
            "SYSTEM\\CurrentControlSet\\Control\\SAM",
            "RelaxMinimumPasswordLengthLimits",
            "0",
            "REG_DWORD",
            True,
        ),
    ],
)
def test_reg_policy(
    lgpo,
    name,
    setting,
    hive,
    key,
    vname,
    exp_vdata,
    exp_vtype,
    exp_removed,
):
    """
    Test registry based settings. Validates that the value is set correctly in
    the registry.

    Args:
        name (str): The name of the policy to configure
        setting (str): The setting of the policy
        hive (str): The registry hive the key is in
        key (str): The registry key the value name is in
        vname (str): The registry value name
        exp_vdata (str, int): The expected data that the value will contain
        exp_vtype (str): The registry value type (i.e. REG_SZ, REG_DWORD, etc)
        exp_removed (bool): Define if the registry value will be removed. Some
            policies delete the registry value when set to 'Not Defined'
    """
    # Set the registry based policy
    result = lgpo.set_computer_policy(name=name, setting=setting)
    assert result is True
    # Read the value from the registry
    value = salt.utils.win_reg.read_value(
        hive=hive,
        key=key,
        vname=vname,
    )
    # Some policies may remove the registry key when disabled or set to Not
    # Configured
    if exp_removed:
        assert value["success"] is False
    else:
        assert value["success"] is True
        assert value["vdata"] == exp_vdata
        if exp_vtype:
            assert value["vtype"] == exp_vtype
