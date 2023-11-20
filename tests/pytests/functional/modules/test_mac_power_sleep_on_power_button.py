"""
integration tests for mac_power sleep_on_power_button
"""

import pytest

pytestmark = [
    pytest.mark.flaky(max_runs=10),
    pytest.mark.skip_if_binaries_missing("systemsetup"),
    pytest.mark.slow_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.skip_unless_on_darwin,
]


@pytest.fixture(scope="module")
def power(modules):
    return modules.power


def test_sleep_on_power_button(power):
    """
    Test power.get_sleep_on_power_button
    Test power.set_sleep_on_power_button
    """
    SLEEP_ON_BUTTON = None

    ret = power.get_sleep_on_power_button()
    if isinstance(ret, bool):
        SLEEP_ON_BUTTON = ret

    # If available on this system, test it
    if SLEEP_ON_BUTTON is None:
        # Check for not available
        assert "Error" in ret
    else:
        ret = power.set_sleep_on_power_button("on")
        assert ret

        ret = power.get_sleep_on_power_button()
        assert ret

        ret = power.set_sleep_on_power_button("off")
        assert ret

        ret = power.get_sleep_on_power_button()
        assert not ret

        power.set_sleep_on_power_button(SLEEP_ON_BUTTON)
