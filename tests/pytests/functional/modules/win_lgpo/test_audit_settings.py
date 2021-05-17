import pytest
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
        },
    }


@pytest.fixture(scope="module")
def enable_legacy_auditing():
    # To test and use these policy settings we have to set one of the policies to Disabled
    # Location: Windows Settings -> Security Settings -> Local Policies -> Security Options
    # Policy: "Audit: Force audit policy subcategory settings..."
    # Short Name: SceNoApplyLegacyAuditPolicy
    test_setting = "Disabled"
    pre_setting = win_lgpo.get_policy(policy_name="SceNoApplyLegacyAuditPolicy", policy_class="machine")
    try:
        if pre_setting != "Disabled":
            computer_policy = {"SceNoApplyLegacyAuditPolicy": test_setting}
            win_lgpo.set_(computer_policy=computer_policy)
            assert win_lgpo.get_policy(policy_name="SceNoApplyLegacyAuditPolicy", policy_class="machine") == test_setting
            yield
    finally:
        if win_lgpo.get_policy(policy_name="SceNoApplyLegacyAuditPolicy", policy_class="machine") != pre_setting:
            computer_policy = {"SceNoApplyLegacyAuditPolicy": pre_setting}
            win_lgpo.set_(computer_policy=computer_policy)


@pytest.fixture(scope="function")
def clear_policy():
    # Ensure the policy is not set
    test_setting = "No Auditing"
    pre_setting = win_lgpo.get_policy(policy_name="Audit account management", policy_class="machine")
    try:
        if pre_setting != test_setting:
            computer_policy = {"Audit account management": test_setting}
            win_lgpo.set_(computer_policy=computer_policy)
            assert win_lgpo.get_policy(policy_name="Audit account management", policy_class="machine") == test_setting
        yield
    finally:
        if win_lgpo.get_policy(policy_name="Audit account management", policy_class="machine") != pre_setting:
            computer_policy = {"Audit account management": pre_setting}
            win_lgpo.set_(computer_policy=computer_policy)


@pytest.fixture(scope="function")
def set_policy():
    # Ensure the policy is set
    test_setting = "Success"
    pre_setting = win_lgpo.get_policy(policy_name="Audit account management", policy_class="machine")
    try:
        if pre_setting != test_setting:
            computer_policy = {"Audit account management": test_setting}
            win_lgpo.set_(computer_policy=computer_policy)
            assert win_lgpo.get_policy(policy_name="Audit account management", policy_class="machine") == test_setting
        yield
    finally:
        if win_lgpo.get_policy(policy_name="Audit account management", policy_class="machine") != pre_setting:
            computer_policy = {"Audit account management": pre_setting}
            win_lgpo.set_(computer_policy=computer_policy)


def _test_auditing(setting):
    """
    Helper function to set an audit setting and assert that it was
    successful
    """
    computer_policy = {"Audit account management": setting}
    win_lgpo.set_(computer_policy=computer_policy)
    result = win_lgpo.get_policy(policy_name="Audit account management", policy_class="machine")
    assert result == setting


def test_audit_no_auditing(set_policy):
    _test_auditing("No Auditing")


def test_audit_success(clear_policy):
    _test_auditing("Success")


def test_audit_failure(clear_policy):
    _test_auditing("Failure")


def test_audit_success_and_failure(clear_policy):
    _test_auditing("Success and Failure")
