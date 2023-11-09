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


def test_sleep_on_power_button(salt_call_cli):
    """
    Test power.get_sleep_on_power_button
    Test power.set_sleep_on_power_button
    """
    SLEEP_ON_BUTTON = None

    ret = salt_call_cli.run("power.get_sleep_on_power_button")
    if isinstance(ret, bool):
        SLEEP_ON_BUTTON = salt_call_cli.run("power.get_sleep_on_power_button")

    # If available on this system, test it
    if SLEEP_ON_BUTTON is None:
        # Check for not available
        ret = salt_call_cli.run("power.get_sleep_on_power_button")
        assert "Error" in ret
    else:
        assert salt_call_cli.run("power.set_sleep_on_power_button", "on")
        assert salt_call_cli.run("power.get_sleep_on_power_button")
        assert salt_call_cli.run("power.set_sleep_on_power_button", "off")
        assert not salt_call_cli.run("power.get_sleep_on_power_button")

        salt_call_cli.run("power.set_sleep_on_power_button", SLEEP_ON_BUTTON)
