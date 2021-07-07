import pytest
import salt.loader
import salt.modules.win_lgpo as win_lgpo

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.destructive_test,
]


@pytest.fixture
def configure_loader_modules(minion_opts, modules):
    return {
        win_lgpo: {
            "__opts__": minion_opts,
            "__salt__": modules,
            "__utils__": salt.loader.utils(minion_opts),
            "__context__": {},
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


@pytest.fixture(scope="function")
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


@pytest.fixture(scope="function")
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


def _test_adv_auditing(setting, expected):
    """
    Helper function to set an audit setting and assert that it was successful
    """
    win_lgpo.set_computer_policy(name="Audit User Account Management", setting=setting)
    # Clear the context so we're getting the actual settings from the machine
    result = win_lgpo._get_advaudit_value("Audit User Account Management", refresh=True)
    assert result == expected


def test_no_auditing(disable_legacy_auditing, set_policy):
    _test_adv_auditing("No Auditing", "0")


def test_success(disable_legacy_auditing, clear_policy):
    _test_adv_auditing("Success", "1")


def test_failure(disable_legacy_auditing, clear_policy):
    _test_adv_auditing("Failure", "2")


def test_success_and_failure(disable_legacy_auditing, clear_policy):
    _test_adv_auditing("Success and Failure", "3")
