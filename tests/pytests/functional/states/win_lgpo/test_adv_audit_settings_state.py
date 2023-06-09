import pytest

import salt.utils.win_lgpo_auditpol

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.destructive_test,
    pytest.mark.slow_test,
]


@pytest.fixture(scope="module", autouse=True)
def disable_legacy_auditing(modules):
    # To test and use these policy settings we have to set one of the policies to Enabled
    # Location: Windows Settings -> Security Settings -> Local Policies -> Security Options
    # Policy: "Audit: Force audit policy subcategory settings..."
    # Short Name: SceNoApplyLegacyAuditPolicy
    test_setting = "Enabled"
    pre_security_setting = modules.lgpo.get_policy(
        policy_name="SceNoApplyLegacyAuditPolicy", policy_class="machine"
    )
    pre_audit_setting = modules.lgpo.get_policy(
        policy_name="Audit User Account Management", policy_class="machine"
    )
    try:
        if pre_security_setting != test_setting:
            modules.lgpo.set_computer_policy(
                name="SceNoApplyLegacyAuditPolicy", setting=test_setting
            )
            assert (
                modules.lgpo.get_policy(
                    policy_name="SceNoApplyLegacyAuditPolicy", policy_class="machine"
                )
                == test_setting
            )
        yield
    finally:
        modules.lgpo.set_computer_policy(
            name="SceNoApplyLegacyAuditPolicy", setting=pre_security_setting
        )
        modules.lgpo.set_computer_policy(
            name="Audit User Account Management", setting=pre_audit_setting
        )


@pytest.fixture
def clear_policy(modules):
    # Ensure the policy is not set
    test_setting = "No Auditing"
    modules.lgpo.set_computer_policy(
        name="Audit User Account Management", setting=test_setting
    )
    assert (
        modules.lgpo.get_policy(
            policy_name="Audit User Account Management", policy_class="machine"
        )
        == test_setting
    )


@pytest.fixture
def set_policy(modules):
    # Ensure the policy is set
    test_setting = "Success"
    modules.lgpo.set_computer_policy(
        name="Audit User Account Management", setting=test_setting
    )
    assert (
        modules.lgpo.get_policy(
            policy_name="Audit User Account Management", policy_class="machine"
        )
        == test_setting
    )


def _test_adv_auditing(modules, states, setting, expected):
    """
    Helper function to set an audit setting and assert that it was successful
    """
    states.lgpo.set_(
        name="Audit User Account Management", setting=setting, policy_class="machine"
    )
    # Clear the context so we're getting the actual settings from the machine
    result = salt.utils.win_lgpo_auditpol.get_advaudit_value(
        "Audit User Account Management", refresh=True
    )
    assert result == expected


@pytest.mark.usefixtures("set_policy")
def test_no_auditing(modules, states):
    _test_adv_auditing(modules, states, "No Auditing", "0")


@pytest.mark.usefixtures("clear_policy")
def test_success(modules, states):
    _test_adv_auditing(modules, states, "Success", "1")


@pytest.mark.usefixtures("clear_policy")
def test_failure(modules, states):
    _test_adv_auditing(modules, states, "Failure", "2")


@pytest.mark.usefixtures("clear_policy")
def test_success_and_failure(modules, states):
    _test_adv_auditing(modules, states, "Success and Failure", "3")
