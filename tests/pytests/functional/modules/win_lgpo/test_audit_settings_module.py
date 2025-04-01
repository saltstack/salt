import os

import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.destructive_test,
    pytest.mark.slow_test,
]


@pytest.fixture(scope="module")
def lgpo(modules):
    return modules.lgpo


@pytest.fixture(scope="module")
def enable_legacy_auditing(lgpo):
    # To test and use these policy settings we have to disable adv auditing
    # Location: Windows Settings -> Security Settings -> Local Policies -> Security Options
    # Policy: "Audit: Force audit policy subcategory settings..."
    # Short Name: SceNoApplyLegacyAuditPolicy
    try:
        lgpo.set_computer_policy("SceNoApplyLegacyAuditPolicy", "Disabled")
        lgpo.set_computer_policy("Audit account management", "No auditing")
        check = lgpo.get_policy("SceNoApplyLegacyAuditPolicy", "machine")
        assert check == "Disabled"
        check = lgpo.get_policy("Audit account management", "machine")
        assert check == "No auditing"
        yield
    finally:
        lgpo.set_computer_policy("SceNoApplyLegacyAuditPolicy", "Not Defined")
        lgpo.set_computer_policy("Audit account management", "Not Defined")


@pytest.fixture(scope="module")
def clean_adv_audit():
    # An `audit.csv` file will cause these tests to fail. Delete the `audit.csv`
    # files from the following locations:
    # - C:\Windows\security\audit
    # - C:\Windows\System32\GroupPolicy\Machine\Microsoft\Windows NT\Audit
    win_dir = os.environ.get("WINDIR")
    audit_csv_files = [
        rf"{win_dir}\security\audit\audit.csv",
        r"{}\System32\GroupPolicy\Machine\Microsoft\Windows NT\Audit\audit.csv".format(
            win_dir
        ),
    ]
    for audit_file in audit_csv_files:
        if os.path.exists(audit_file):
            os.remove(audit_file)
    yield


@pytest.fixture(scope="module")
def legacy_auditing_not_defined(lgpo):
    try:
        lgpo.set_computer_policy("SceNoApplyLegacyAuditPolicy", "Not Defined")
        check = lgpo.get_policy("SceNoApplyLegacyAuditPolicy", "machine")
        assert check == "Not Defined"
        yield
    finally:
        lgpo.set_computer_policy("SceNoApplyLegacyAuditPolicy", "Not Defined")


@pytest.mark.parametrize(
    "setting", ["No auditing", "Success", "Failure", "Success, Failure"]
)
def test_auditing(lgpo, setting, enable_legacy_auditing, clean_adv_audit):
    """
    Helper function to set an audit setting and assert that it was successful
    """
    lgpo.set_computer_policy("Audit account management", setting)
    result = lgpo.get_policy("Audit account management", "machine")
    assert result == setting


@pytest.mark.parametrize(
    "setting_name,setting",
    [
        ("Audit account management", "Success"),
        ("Audit Account Management", "Failure"),
    ],
)
def test_auditing_case_names(
    lgpo, setting_name, setting, enable_legacy_auditing, clean_adv_audit
):
    """
    Helper function to set an audit setting and assert that it was successful
    """
    lgpo.set_computer_policy(setting_name, setting)
    result = lgpo.get_policy(setting_name, "machine")
    assert result == setting


@pytest.mark.parametrize("setting", ["Enabled", "Disabled"])
def test_enable_legacy_audit_policy(
    lgpo, setting, legacy_auditing_not_defined, clean_adv_audit
):
    lgpo.set_computer_policy("SceNoApplyLegacyAuditPolicy", setting)
    result = lgpo.get_policy("SceNoApplyLegacyAuditPolicy", "machine")
    assert result == setting
