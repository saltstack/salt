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


@pytest.fixture
def reset_administrator_lockout(lgpo):
    original = lgpo.get_policy("AdministratorLockout", "machine")
    try:
        yield
    finally:
        if original in ("Enabled", "Disabled"):
            lgpo.set_computer_policy("AdministratorLockout", original)


@pytest.mark.parametrize("setting", ["Enabled", "Disabled"])
def test_administrator_lockout(lgpo, setting, reset_administrator_lockout):
    """
    Test setting AdministratorLockout by short name and reading it back.
    """
    lgpo.set_computer_policy("AdministratorLockout", setting)
    result = lgpo.get_policy("AdministratorLockout", "machine")
    assert result == setting


@pytest.mark.parametrize("setting", ["Enabled", "Disabled"])
def test_administrator_lockout_full_name(lgpo, setting, reset_administrator_lockout):
    """
    Test setting AdministratorLockout by its full policy name and reading it
    back, confirming that the long name resolves to the same policy.
    """
    lgpo.set_computer_policy("Allow Administrator account lockout", setting)
    result = lgpo.get_policy("Allow Administrator account lockout", "machine")
    assert result == setting
