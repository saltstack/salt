import os

import pytest

import salt.loader
import salt.modules.win_lgpo as win_lgpo_module
import salt.states.win_lgpo as win_lgpo_state

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.destructive_test,
]


@pytest.fixture
def configure_loader_modules(minion_opts, modules):
    utils = salt.loader.utils(minion_opts)
    return {
        win_lgpo_state: {
            "__opts__": minion_opts,
            "__salt__": modules,
            "__utils__": utils,
        },
        win_lgpo_module: {
            "__opts__": {"cachedir": minion_opts["cachedir"]},
            "__salt__": modules,
            "__utils__": utils,
        },
    }


@pytest.fixture(scope="module")
def enable_legacy_auditing():
    # To test and use these policy settings we have to set one of the policies
    # to Disabled Location:
    # Windows Settings -> Security Settings -> Local Policies -> Security Options
    # Policy: "Audit: Force audit policy subcategory settings..."
    # Short Name: SceNoApplyLegacyAuditPolicy
    from tests.support.sminion import create_sminion

    salt_minion = create_sminion()
    test_setting = "Disabled"
    pre_security_setting = salt_minion.functions.lgpo.get_policy(
        policy_name="SceNoApplyLegacyAuditPolicy", policy_class="machine"
    )
    pre_audit_setting = salt_minion.functions.lgpo.get_policy(
        policy_name="Audit Account Management", policy_class="machine"
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
            name="Audit Account Management", setting=pre_audit_setting
        )


@pytest.fixture(scope="module")
def clean_adv_audit():
    # An `audit.csv` file will cause these tests to fail. Delete the `audit.csv`
    # files from the following locations:
    # - C:\Windows\security\audit
    # - C:\Windows\System32\GroupPolicy\Machine\Microsoft\Windows NT\Audit
    win_dir = os.environ.get("WINDIR")
    audit_csv_files = [
        r"{}\security\audit\audit.csv".format(win_dir),
        r"{}\System32\GroupPolicy\Machine\Microsoft\Windows NT\Audit\audit.csv".format(
            win_dir
        ),
    ]
    for audit_file in audit_csv_files:
        if os.path.exists(audit_file):
            os.remove(audit_file)
    yield


@pytest.fixture
def clear_policy():
    # Ensure the policy is not set
    test_setting = "No auditing"
    win_lgpo_module.set_computer_policy(
        name="Audit account management", setting=test_setting
    )
    assert (
        win_lgpo_module.get_policy(
            policy_name="Audit account management", policy_class="machine"
        )
        == test_setting
    )


@pytest.fixture
def set_policy():
    # Ensure the policy is set
    test_setting = "Success"
    win_lgpo_module.set_computer_policy(
        name="Audit account management", setting=test_setting
    )
    assert (
        win_lgpo_module.get_policy(
            policy_name="Audit account management", policy_class="machine"
        )
        == test_setting
    )


def _test_auditing(setting):
    """
    Helper function to set an audit setting and assert that it was successful
    """
    computer_policy = {"Audit Account Management": setting}
    win_lgpo_state.set_(name="junk", computer_policy=computer_policy)
    # Clear the context so we're getting the actual settings from the machine
    win_lgpo_module._get_secedit_data(refresh=True)
    result = win_lgpo_module.get_policy(
        policy_name="Audit Account Management", policy_class="machine"
    )
    assert result == setting


def test_no_auditing(enable_legacy_auditing, set_policy, clean_adv_audit):
    _test_auditing("No auditing")


def test_success(enable_legacy_auditing, clear_policy, clean_adv_audit):
    _test_auditing("Success")


def test_failure(enable_legacy_auditing, clear_policy, clean_adv_audit):
    _test_auditing("Failure")


def test_success_and_failure(enable_legacy_auditing, clear_policy, clean_adv_audit):
    _test_auditing("Success, Failure")
