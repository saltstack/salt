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


@pytest.fixture(scope="function")
def disable_legacy_auditing():
    # To test and use these policy settings we have to set one of the policies to Disabled
    # Location: Windows Settings -> Security Settings -> Local Policies -> Security Options
    # Policy: "Audit: Force audit policy subcategory settings..."
    # Short Name: SceNoApplyLegacyAuditPolicy
    test_setting = "Enabled"
    pre_setting = win_lgpo.get_policy(policy_name="SceNoApplyLegacyAuditPolicy", policy_class="machine")
    try:
        if pre_setting != test_setting:
            win_lgpo.set_computer_policy(name="SceNoApplyLegacyAuditPolicy", setting=test_setting)
            assert win_lgpo.get_policy(policy_name="SceNoApplyLegacyAuditPolicy", policy_class="machine") == test_setting
        yield
    finally:
        if win_lgpo.get_policy(policy_name="SceNoApplyLegacyAuditPolicy", policy_class="machine") != pre_setting:
            win_lgpo.set_computer_policy(name="SceNoApplyLegacyAuditPolicy", setting=pre_setting)


@pytest.fixture(scope="function")
def clear_policy():
    # Ensure the policy is not set
    test_setting = "No Auditing"
    pre_setting = win_lgpo.get_policy(
        policy_name="Audit User Account Management", policy_class="machine"
    )
    try:
        if pre_setting != test_setting:
            win_lgpo.set_computer_policy(name="Audit User Account Management", setting=test_setting)
            assert (
                win_lgpo.get_policy(policy_name="Audit User Account Management", policy_class="machine") == test_setting
            )
        yield
    finally:
        if (
            win_lgpo.get_policy(
                policy_name="Audit User Account Management", policy_class="machine"
            )
            != pre_setting
        ):
            win_lgpo.set_computer_policy(name="Audit User Account Management", setting=pre_setting)


@pytest.fixture(scope="function")
def set_policy():
    # Ensure the policy is set
    test_setting = "Success"
    pre_setting = win_lgpo.get_policy(
        policy_name="Audit User Account Management", policy_class="machine"
    )
    try:
        if pre_setting != test_setting:
            win_lgpo.set_computer_policy(name="Audit User Account Management", setting=test_setting)
            assert (
                win_lgpo.get_policy(
                    policy_name="Audit User Account Management", policy_class="machine"
                )
                == test_setting
            )
        yield
    finally:
        if (
            win_lgpo.get_policy(
                policy_name="Audit User Account Management", policy_class="machine"
            )
            != pre_setting
        ):
            win_lgpo.set_computer_policy(name="Audit User Account Management", setting=pre_setting)


def _test_adv_auditing(setting):
    """
    Helper function to set an audit setting and assert that it was successful
    """
    win_lgpo.set_computer_policy(name="Audit User Account Management", setting=setting)
    result = win_lgpo.get_policy(policy_name="Audit User Account Management", policy_class="machine")
    assert result == setting


def test_adv_audit_module_no_auditing(disable_legacy_auditing, set_policy):
    _test_adv_auditing("No Auditing")


def test_adv_audit_module_success(disable_legacy_auditing, clear_policy):
    _test_adv_auditing("Success")


def test_adv_audit_module_failure(disable_legacy_auditing, clear_policy):
    _test_adv_auditing("Failure")


def test_adv_audit_module_success_and_failure(disable_legacy_auditing, clear_policy):
    _test_adv_auditing("Success and Failure")
