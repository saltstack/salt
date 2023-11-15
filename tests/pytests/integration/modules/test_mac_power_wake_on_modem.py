"""
integration tests for mac_power wake_on_modem
"""

import pytest

pytestmark = [
    pytest.mark.flaky(max_runs=10),
    pytest.mark.slow_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.skip_unless_on_darwin,
    pytest.mark.skip_if_binaries_missing("systemsetup"),
]


def test_wake_on_modem(salt_call_cli):
    """
    Test power.get_wake_on_modem
    Test power.set_wake_on_modem
    """
    WAKE_ON_MODEM = None
    ret = salt_call_cli.run("power.get_wake_on_modem")
    if isinstance(ret.data, bool):
        WAKE_ON_MODEM = ret.data

    if WAKE_ON_MODEM is None:
        # Check for not available
        ret = salt_call_cli.run("power.get_wake_on_modem")
        assert "Error" in ret.stderr
    else:
        ret = salt_call_cli.run("power.set_wake_on_modem", "on")
        assert ret.data

        ret = salt_call_cli.run("power.get_wake_on_modem")
        assert ret.data

        ret = salt_call_cli.run("power.set_wake_on_modem", "off")
        assert ret.data

        ret = salt_call_cli.run("power.get_wake_on_modem")
        assert not ret.data

        salt_call_cli.run("power.set_wake_on_modem", WAKE_ON_MODEM)
