import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.slow_test,
]


@pytest.fixture(scope="module")
def lgpo(modules):
    return modules.lgpo


def test_hierarchical_return(lgpo):
    result = lgpo.get_policy(
        policy_name="Calculator",
        policy_class="Machine",
        hierarchical_return=True,
    )
    result = result["Administrative Templates"]
    result = result["Windows Components"]
    result = result["Microsoft User Experience Virtualization"]
    result = result["Applications"]
    result = result["Calculator"]
    assert result in ("Enabled", "Disabled", "Not Configured")


def test_return_value_only_false(lgpo):
    result = lgpo.get_policy(
        policy_name="Calculator",
        policy_class="Machine",
        return_value_only=False,
    )
    assert result[
        r"Windows Components\Microsoft User Experience Virtualization\Applications\Calculator"
    ] in ("Enabled", "Disabled", "Not Configured")


def test_return_full_policy_names_false(lgpo):
    result = lgpo.get_policy(
        policy_name="Calculator",
        policy_class="Machine",
        return_full_policy_names=False,
        return_value_only=False,
    )
    assert result["Calculator"] in ("Enabled", "Disabled", "Not Configured")


def test_61860_calculator(lgpo):
    result = lgpo.get_policy(policy_name="Calculator", policy_class="Machine")
    # Any of the following are valid settings. We're only making sure it doesn't
    # throw a stacktrace
    assert result in ("Enabled", "Disabled", "Not Configured")
