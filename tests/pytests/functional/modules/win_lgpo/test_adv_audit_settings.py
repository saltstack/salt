import pytest
import salt.modules.win_lgpo as win_lgpo
import salt.loader

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
]


@pytest.fixture
def configure_loader_modules(minion_opts, modules):
    return {
        win_lgpo: {
            "__opts__": minion_opts,
            "__salt__": modules,
            "__utils__": salt.loader.utils(minion_opts),
            # "__context__": {},
        },
    }


@pytest.fixture(scope="function")
def clear_policy():
    # Ensure the policy is not set
    computer_policy = {"Audit User Account Management": "No Auditing"}
    try:
        win_lgpo.set_(computer_policy=computer_policy)
    finally:
        win_lgpo.set_(computer_policy=computer_policy)


@pytest.fixture(scope="function")
def set_policy():
    # Ensure the policy is not set
    computer_policy = {"Audit User Account Management": "Success"}
    try:
        win_lgpo.set_(computer_policy=computer_policy)
    finally:
        win_lgpo.set_(computer_policy=computer_policy)


@pytest.mark.destructive_test
def test_adv_audit_no_auditing(set_policy):
    computer_policy = {"Audit User Account Management": "No Auditing"}
    win_lgpo.set_(computer_policy=computer_policy)
    result = win_lgpo.get_policy("Audit User Account Management", "machine")
    expected = "No auditing"
    assert result == expected


@pytest.mark.destructive_test
def test_adv_audit_success(clear_policy):
    computer_policy = {"Audit User Account Management": "Success"}
    win_lgpo.set_(computer_policy=computer_policy)
    result = win_lgpo.get_policy("Audit User Account Management", "machine")
    expected = "Success"
    assert result == expected


@pytest.mark.destructive_test
def test_adv_audit_failure(clear_policy):
    computer_policy = {"Audit User Account Management": "Failure"}
    win_lgpo.set_(computer_policy=computer_policy)
    result = win_lgpo.get_policy("Audit User Account Management", "machine")
    expected = "Failure"
    assert result == expected


@pytest.mark.destructive_test
def test_adv_audit_success_and_failure(clear_policy):
    computer_policy = {"Audit Adv Account Management": "Success and Failure"}
    win_lgpo.set_(computer_policy=computer_policy)
    result = win_lgpo.get_policy("Audit Adv Account Management", "machine")
    expected = "Success and Failure"
    assert result == expected
