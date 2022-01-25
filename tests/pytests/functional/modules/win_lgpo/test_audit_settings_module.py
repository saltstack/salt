import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.destructive_test,
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
def test_auditing(lgpo, setting, enable_legacy_auditing):
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
def test_auditing_case_names(lgpo, setting_name, setting, enable_legacy_auditing):
    """
    Helper function to set an audit setting and assert that it was successful
    """
    lgpo.set_computer_policy(setting_name, setting)
    result = lgpo.get_policy(setting_name, "machine")
    assert result == setting


@pytest.mark.parametrize("setting", ["Enabled", "Disabled"])
def test_enable_legacy_audit_policy(lgpo, setting, legacy_auditing_not_defined):
    lgpo.set_computer_policy("SceNoApplyLegacyAuditPolicy", setting)
    result = lgpo.get_policy("SceNoApplyLegacyAuditPolicy", "machine")
    assert result == setting
