"""
integration tests for mac_power
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


def test_restart_power_failure(power):
    """
    Test power.get_restart_power_failure
    Test power.set_restart_power_failure
    """
    RESTART_POWER = None

    ret = power.get_restart_power_failure()
    if isinstance(ret, bool):
        RESTART_POWER = ret

    # If available on this system, test it
    if RESTART_POWER is None:
        # Check for not available
        ret = power.get_restart_power_failure()
        assert "Error" in ret
    else:
        ret = power.set_restart_power_failure("On")
        assert ret

        ret = power.get_restart_power_failure()
        assert ret

        ret = power.set_restart_power_failure("Off")
        assert ret

        ret = power.get_restart_power_failure()
        assert not ret

        power.set_sleep_on_power_button(RESTART_POWER)
