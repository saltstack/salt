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


def test_restart_power_failure(salt_call_cli):
    """
    Test power.get_restart_power_failure
    Test power.set_restart_power_failure
    """
    RESTART_POWER = None

    ret = salt_call_cli.run("power.get_restart_power_failure")
    if isinstance(ret.data, bool):
        RESTART_POWER = ret.data

    # If available on this system, test it
    if RESTART_POWER is None:
        # Check for not available
        ret = salt_call_cli.run("power.get_restart_power_failure")
        assert "Error" in ret.data
    else:
        ret = salt_call_cli.run("power.set_restart_power_failure", "On")
        assert ret.data

        ret = salt_call_cli.run("power.get_restart_power_failure")
        assert ret.data

        ret = salt_call_cli.run("power.set_restart_power_failure", "Off")
        assert ret.data

        ret = salt_call_cli.run("power.get_restart_power_failure")
        assert not ret.data

        salt_call_cli.run("power.set_sleep_on_power_button", RESTART_POWER)
