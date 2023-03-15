"""
:codeauthor: Shane Lee <slee@saltstack.com>
"""
import os

import pytest

import salt.modules.cmdmod as cmdmod
import salt.modules.win_file as win_file
import salt.modules.win_lgpo as win_lgpo
import salt.utils.win_dacl as win_dacl
import salt.utils.win_lgpo_auditpol as win_lgpo_auditpol
import salt.utils.win_reg as win_reg
from tests.support.mock import patch

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
]


@pytest.fixture
def configure_loader_modules(tmp_path):
    cachedir = tmp_path / "__test_admx_policy_cache_dir"
    cachedir.mkdir(parents=True, exist_ok=True)
    return {
        win_lgpo: {
            "__salt__": {
                "cmd.run": cmdmod.run,
                "file.file_exists": win_file.file_exists,
                "file.makedirs": win_file.makedirs_,
                "file.remove": win_file.remove,
                "file.write": win_file.write,
            },
            "__opts__": {
                "cachedir": str(cachedir),
            },
            "__utils__": {
                "auditpol.get_auditpol_dump": win_lgpo_auditpol.get_auditpol_dump,
                "reg.read_value": win_reg.read_value,
            },
        },
        win_file: {
            "__utils__": {
                "dacl.set_perms": win_dacl.set_perms,
            },
        },
    }


def _test_mechanism(policy_name):
    """
    Helper function to get current setting
    """
    policy_data = win_lgpo._policy_info()
    policy_definition = policy_data.policies["Machine"]["policies"][policy_name]
    return win_lgpo._get_policy_info_setting(policy_definition)


def test_registry():
    """
    Test getting policy value using the Registry mechanism
    """
    policy_name = "RemoteRegistryExactPaths"
    result = _test_mechanism(policy_name=policy_name)
    expected = [
        "System\\CurrentControlSet\\Control\\ProductOptions",
        "System\\CurrentControlSet\\Control\\Server Applications",
        "Software\\Microsoft\\Windows NT\\CurrentVersion",
    ]
    assert result == expected


def test_secedit():
    """
    Test getting policy value using the Secedit mechanism
    """
    policy_name = "LSAAnonymousNameLookup"
    result = _test_mechanism(policy_name=policy_name)
    expected = "Disabled"
    assert result == expected


def test_netsh():
    """
    Test getting the policy value using the NetSH mechanism
    """
    policy_name = "WfwDomainState"
    all_settings = {
        "State": "NotConfigured",
        "Inbound": "NotConfigured",
        "Outbound": "NotConfigured",
        "LocalFirewallRules": "NotConfigured",
        "LocalConSecRules": "NotConfigured",
        "InboundUserNotification": "NotConfigured",
        "RemoteManagement": "NotConfigured",
        "UnicastResponseToMulticast": "NotConfigured",
        "LogAllowedConnections": "NotConfigured",
        "LogDroppedConnections": "NotConfigured",
        "FileName": "NotConfigured",
        "MaxFileSize": "NotConfigured",
    }
    with patch("salt.utils.win_lgpo_netsh.get_all_settings", return_value=all_settings):
        result = _test_mechanism(policy_name=policy_name)
    expected = "Not configured"
    assert result == expected


@pytest.mark.destructive_test
def test_adv_audit():
    """
    Test getting the policy value using the AdvAudit mechanism
    """
    system_root = os.environ.get("SystemRoot", "C:\\Windows")
    f_audit = os.path.join(system_root, "security", "audit", "audit.csv")
    f_audit_gpo = os.path.join(
        system_root,
        "System32",
        "GroupPolicy",
        "Machine",
        "Microsoft",
        "Windows NT",
        "Audit",
        "audit.csv",
    )
    if os.path.exists(f_audit):
        os.remove(f_audit)
    if os.path.exists(f_audit_gpo):
        os.remove(f_audit_gpo)
    policy_name = "AuditCredentialValidation"
    result = _test_mechanism(policy_name=policy_name)
    expected = "Not Configured"
    assert result == expected


def test_net_user_modal():
    """
    Test getting the policy value using the NetUserModal mechanism
    """
    policy_name = "PasswordHistory"
    result = _test_mechanism(policy_name=policy_name)
    expected = 0
    assert result == expected


def test_lsa_rights():
    """
    Test getting the policy value using the LsaRights mechanism
    """
    policy_name = "SeTrustedCredManAccessPrivilege"
    result = _test_mechanism(policy_name=policy_name)
    expected = []
    assert result == expected


def test_script_ini():
    """
    Test getting the policy value using the ScriptIni value
    """
    policy_name = "StartupScripts"
    result = _test_mechanism(policy_name=policy_name)
    expected = None
    assert result == expected
