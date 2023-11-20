"""
integration tests for mac_power wake_on_modem
"""

import pytest

from salt.exceptions import CommandExecutionError

pytestmark = [
    pytest.mark.flaky(max_runs=10),
    pytest.mark.slow_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.skip_unless_on_darwin,
    pytest.mark.skip_if_binaries_missing("systemsetup"),
]


@pytest.fixture(scope="module")
def power(modules):
    return modules.power


def test_wake_on_modem(power):
    """
    Test power.get_wake_on_modem
    Test power.set_wake_on_modem
    """
    try:
        ret = power.get_wake_on_modem()
        if isinstance(ret, bool):
            WAKE_ON_MODEM = ret
    except CommandExecutionError as exc:
        WAKE_ON_MODEM = None

    if WAKE_ON_MODEM is None:
        # Check for not available
        pytest.skip("Skipping. wake_on_modem unavailable.")
    else:
        ret = power.set_wake_on_modem("on")
        assert ret

        ret = power.get_wake_on_modem()
        assert ret

        ret = power.set_wake_on_modem("off")
        assert ret

        ret = power.get_wake_on_modem()
        assert not ret

        power.set_wake_on_modem(WAKE_ON_MODEM)
