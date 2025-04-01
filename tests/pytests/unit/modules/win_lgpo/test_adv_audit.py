import logging

import pytest

import salt.modules.win_file as win_file
import salt.modules.win_lgpo as win_lgpo
import salt.utils.win_dacl as win_dacl
import salt.utils.win_lgpo_auditpol as auditpol
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.destructive_test,
    pytest.mark.slow_test,
]


@pytest.fixture
def configure_loader_modules(tmp_path):
    cachedir = tmp_path / "__test_admx_policy_cache_dir"
    cachedir.mkdir(parents=True, exist_ok=True)
    return {
        win_lgpo: {
            "__opts__": {"cachedir": cachedir},
            "__salt__": {
                "file.copy": win_file.copy,
                "file.file_exists": win_file.file_exists,
                "file.makedirs": win_file.makedirs_,
                "file.remove": win_file.remove,
                "file.write": win_file.write,
            },
            "__utils__": {
                "auditpol.get_auditpol_dump": auditpol.get_auditpol_dump,
                "auditpol.set_setting": auditpol.set_setting,
            },
        },
        auditpol: {
            "__context__": {},
        },
        win_file: {
            "__utils__": {
                "dacl.set_perms": win_dacl.set_perms,
            },
        },
    }


@pytest.fixture(scope="module")
def disable_legacy_auditing():
    # To test and use these policy settings we have to set one of the policies to Enabled
    # Location: Windows Settings -> Security Settings -> Local Policies -> Security Options
    # Policy: "Audit: Force audit policy subcategory settings..."
    # Short Name: SceNoApplyLegacyAuditPolicy
    from tests.support.sminion import create_sminion

    salt_minion = create_sminion()
    test_setting = "Enabled"
    pre_security_setting = salt_minion.functions.lgpo.get_policy(
        policy_name="SceNoApplyLegacyAuditPolicy", policy_class="machine"
    )
    pre_audit_setting = salt_minion.functions.lgpo.get_policy(
        policy_name="Audit User Account Management", policy_class="machine"
    )
    try:
        if pre_security_setting != test_setting:
            salt_minion.functions.lgpo.set_computer_policy(
                name="SceNoApplyLegacyAuditPolicy", setting=test_setting
            )
            assert (
                salt_minion.functions.lgpo.get_policy(
                    policy_name="SceNoApplyLegacyAuditPolicy", policy_class="machine"
                )
                == test_setting
            )
        yield
    finally:
        salt_minion.functions.lgpo.set_computer_policy(
            name="SceNoApplyLegacyAuditPolicy", setting=pre_security_setting
        )
        salt_minion.functions.lgpo.set_computer_policy(
            name="Audit User Account Management", setting=pre_audit_setting
        )


@pytest.fixture
def clear_policy():
    # Ensure the policy is not set
    test_setting = "No Auditing"
    win_lgpo.set_computer_policy(
        name="Audit User Account Management", setting=test_setting
    )
    assert (
        win_lgpo.get_policy(
            policy_name="Audit User Account Management", policy_class="machine"
        )
        == test_setting
    )


@pytest.fixture
def set_policy():
    # Ensure the policy is set
    test_setting = "Success"
    win_lgpo.set_computer_policy(
        name="Audit User Account Management", setting=test_setting
    )
    assert (
        win_lgpo.get_policy(
            policy_name="Audit User Account Management", policy_class="machine"
        )
        == test_setting
    )


@pytest.mark.parametrize(
    "setting, expected",
    [
        ("No Auditing", "0"),
        ("Success", "1"),
        ("Failure", "2"),
        ("Success and Failure", "3"),
    ],
)
def test_get_value(setting, expected):
    """
    Helper function to set an audit setting and assert that it was successful
    """
    win_lgpo.set_computer_policy(name="Audit User Account Management", setting=setting)
    # Clear the context so we're getting the actual settings from the machine
    result = win_lgpo._get_advaudit_value("Audit User Account Management", refresh=True)
    assert result == expected


def test_get_defaults():
    patch_context = patch.dict(win_lgpo.__context__, {})
    patch_salt = patch.dict(
        win_lgpo.__utils__, {"auditpol.get_auditpol_dump": auditpol.get_auditpol_dump}
    )
    with patch_context, patch_salt:
        assert "Machine Name" in win_lgpo._get_advaudit_defaults("fieldnames")

    audit_defaults = {"junk": "defaults"}
    patch_context = patch.dict(
        win_lgpo.__context__, {"lgpo.audit_defaults": audit_defaults}
    )
    with patch_context, patch_salt:
        assert win_lgpo._get_advaudit_defaults() == audit_defaults


def test_set_value_error():
    mock_set_file_data = MagicMock(return_value=False)
    with patch.object(win_lgpo, "_set_advaudit_file_data", mock_set_file_data):
        with pytest.raises(CommandExecutionError):
            win_lgpo._set_advaudit_value("Audit User Account Management", "None")


def test_set_value_log_messages(caplog):
    mock_set_file_data = MagicMock(return_value=True)
    mock_set_pol_data = MagicMock(return_value=False)
    mock_context = {"lgpo.adv_audit_data": {"test_option": "test_value"}}
    with caplog.at_level(logging.DEBUG):
        with patch.object(
            win_lgpo, "_set_advaudit_file_data", mock_set_file_data
        ), patch.object(
            win_lgpo, "_set_advaudit_pol_data", mock_set_pol_data
        ), patch.dict(
            win_lgpo.__context__, mock_context
        ):
            win_lgpo._set_advaudit_value("test_option", None)
            assert "Failed to apply audit setting:" in caplog.text
        assert "LGPO: Removing Advanced Audit data:" in caplog.text
