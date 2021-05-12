import pytest
import salt.modules.win_lgpo as win_lgpo
import salt.loader

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
def clear_policy():
    # Ensure the policy is not set
    test_setting = "No Auditing"
    pre_setting = win_lgpo.get_policy(policy_name="Audit User Account Management", policy_class="machine")
    try:
        if pre_setting != test_setting:
            computer_policy = {"Audit User Account Management": test_setting}
            win_lgpo.set_(computer_policy=computer_policy)
            assert win_lgpo.get_policy(policy_name="Audit User Account Management", policy_class="machine") == test_setting
        yield
    finally:
        if win_lgpo.get_policy(policy_name="Audit User Account Management", policy_class="machine") != pre_setting:
            computer_policy = {"Audit User Account Management": pre_setting}
            win_lgpo.set_(computer_policy=computer_policy)


@pytest.fixture(scope="function")
def set_policy():
    # Ensure the policy is set
    test_setting = "Success"
    pre_setting = win_lgpo.get_policy(policy_name="Audit User Account Management", policy_class="machine")
    try:
        if pre_setting != test_setting:
            computer_policy = {"Audit User Account Management": test_setting}
            win_lgpo.set_(computer_policy=computer_policy)
            assert win_lgpo.get_policy(policy_name="Audit User Account Management", policy_class="machine") == test_setting
        yield
    finally:
        if win_lgpo.get_policy(policy_name="Audit User Account Management", policy_class="machine") != pre_setting:
            computer_policy = {"Audit User Account Management": pre_setting}
            win_lgpo.set_(computer_policy=computer_policy)


def _test_adv_auditing(setting):
    """
    Helper function to set an audit setting and assert that it was
    successful
    """
    computer_policy = {"Audit User Account Management": setting}
    win_lgpo.set_(computer_policy=computer_policy)
    result = win_lgpo.get_policy(policy_name="Audit account management", policy_class="machine")
    assert result == setting

@pytest.mark.destructive_test
def test_adv_audit_no_auditing(set_policy):
    _test_adv_auditing("No Auditing")


@pytest.mark.destructive_test
def test_adv_audit_success(clear_policy):
    _test_adv_auditing("Success")


@pytest.mark.destructive_test
def test_adv_audit_failure(clear_policy):
    _test_adv_auditing("Failure")


@pytest.mark.destructive_test
def test_adv_audit_success_and_failure(clear_policy):
    _test_adv_auditing("Success and Failure")
