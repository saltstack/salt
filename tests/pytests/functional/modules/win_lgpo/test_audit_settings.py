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

# nox -e pytest-zeromq-3.7(coverage=False) -- -vvv --run-slow --run-destructive tests\pytests\functional\modules\win_lgpo\test_write_regpol.py


@pytest.fixture(scope="function")
def clear_policy():
    # Ensure the policy is not set
    current = win_lgpo.get_policy("Audit Account Management", "machine")
    try:
        if current != "No auditing":
            computer_policy = {"Audit Account Management": "No auditing"}
            win_lgpo.set_(computer_policy=computer_policy)
        yield
    finally:
        if win_lgpo.get_policy("Audit Account Management", "machine") != current:
            computer_policy = {"Audit Account Management": current}
            win_lgpo.set_(computer_policy=computer_policy)


@pytest.fixture(scope="function")
def set_policy():
    # Ensure the policy is not set
    policy_name = "Audit account management"
    current = win_lgpo.get_policy(policy_name=policy_name, policy_class="machine")
    try:
        if current != "Success":
            computer_policy = {policy_name: "Success"}
            win_lgpo.set_(computer_policy=computer_policy)
        yield
    finally:
        if win_lgpo.get_policy(policy_name=policy_name, policy_class="machine") != current:
            computer_policy = {policy_name: current}
            win_lgpo.set_(computer_policy=computer_policy)


def _test_auditing(setting):
    """
    Helper function to set an audit setting and assert that it was
    successful
    """
    policy_name = "Audit account management"
    computer_policy = {policy_name: setting}
    print("PRE " * 30)
    print(win_lgpo.get_policy(policy_name, "machine"))
    print("PRE " * 30)
    win_lgpo.set_(computer_policy=computer_policy)
    result = win_lgpo.get_policy(policy_name=policy_name, policy_class="machine")
    print("POST " * 30)
    print(result)
    print("POST " * 30)
    expected = setting
    assert result == expected


def test_audit_no_auditing(set_policy):
    _test_auditing("No auditing")


def test_audit_success(clear_policy):
    _test_auditing("Success")


def test_audit_failure(clear_policy):
    _test_auditing("Failure")


def test_audit_success_and_failure(clear_policy):
    _test_auditing("Success and Failure")
