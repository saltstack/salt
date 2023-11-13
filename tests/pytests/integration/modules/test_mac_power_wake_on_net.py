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
    if isinstance(ret.data, bool):
        WAKE_ON_NET = ret.data

    # If available on this system, test it
    if WAKE_ON_NET is None:
        # Check for not available
        ret = salt_call_cli.run("power.get_wake_on_network")
        assert "Error" in ret.data
    else:
        ret = salt_call_cli.run("power.set_wake_on_network", "on")
        assert ret.data

        ret = salt_call_cli.run("power.get_wake_on_network")
        assert ret.data

        ret = salt_call_cli.run("power.set_wake_on_network", "off")
        assert ret.data

        ret = salt_call_cli.run("power.get_wake_on_network")
        assert not ret.data

        salt_call_cli.run("power.set_wake_on_network", WAKE_ON_NET)
