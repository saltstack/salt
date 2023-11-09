"""
integration tests for mac_power wake_on_network
"""

import pytest

pytestmark = [
    pytest.mark.flaky(max_runs=10),
    pytest.mark.skip_if_binaries_missing("systemsetup"),
    pytest.mark.slow_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.skip_unless_on_darwin,
]


def test_wake_on_network(salt_call_cli):
    """
    Test power.get_wake_on_network
    Test power.set_wake_on_network
    """

    WAKE_ON_NET = None
    ret = salt_call_cli.run("power.get_wake_on_network")
    if isinstance(ret, bool):
        WAKE_ON_NET = ret

    # If available on this system, test it
    if WAKE_ON_NET is None:
        # Check for not available
        ret = salt_call_cli.run("power.get_wake_on_network")
        assert "Error" in ret
    else:
        assert salt_call_cli.run("power.set_wake_on_network", "on")
        assert salt_call_cli.run("power.get_wake_on_network")
        assert salt_call_cli.run("power.set_wake_on_network", "off")
        assert not salt_call_cli.run("power.get_wake_on_network")

        salt_call_cli.run("power.set_wake_on_network", WAKE_ON_NET)
