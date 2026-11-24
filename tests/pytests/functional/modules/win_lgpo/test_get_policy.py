import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.slow_test,
]


@pytest.fixture(scope="module")
def lgpo(modules):
    return modules.lgpo


def _require_calculator_policy(lgpo, **kwargs):
    """
    The UE-V Calculator ADMX is not present on every Windows image (e.g.
    Windows 11 Arm64 hosted runners). Skip when the policy cannot be resolved.
    """
    result = lgpo.get_policy(policy_name="Calculator", policy_class="Machine", **kwargs)
    if result is None:
        pytest.skip("Calculator UE-V policy not present on this Windows image")
    return result


def test_hierarchical_return(lgpo):
    result = _require_calculator_policy(lgpo, hierarchical_return=True)
    result = result["Administrative Templates"]
    result = result["Windows Components"]
    result = result["Microsoft User Experience Virtualization"]
    result = result["Applications"]
    result = result["Calculator"]
    assert result in ("Enabled", "Disabled", "Not Configured")


def test_return_value_only_false(lgpo):
    result = _require_calculator_policy(lgpo, return_value_only=False)
    assert result[
        r"Windows Components\Microsoft User Experience Virtualization\Applications\Calculator"
    ] in ("Enabled", "Disabled", "Not Configured")


def test_return_full_policy_names_false(lgpo):
    result = _require_calculator_policy(
        lgpo,
        return_full_policy_names=False,
        return_value_only=False,
    )
    assert result["Calculator"] in ("Enabled", "Disabled", "Not Configured")


def test_61860_calculator(lgpo):
    result = _require_calculator_policy(lgpo)
    # Any of the following are valid settings. We're only making sure it doesn't
    # throw a stacktrace
    assert result in ("Enabled", "Disabled", "Not Configured")
