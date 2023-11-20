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


@pytest.fixture(scope="module")
def power(modules):
    return modules.power


def test_wake_on_network(power):
    """
    Test power.get_wake_on_network
    Test power.set_wake_on_network
    """

    WAKE_ON_NET = None
    ret = power.get_wake_on_network()
    if isinstance(ret, bool):
        WAKE_ON_NET = ret

    # If available on this system, test it
    if WAKE_ON_NET is None:
        # Check for not available
        ret = power.get_wake_on_network()
        assert "Error" in ret
    else:
        ret = power.set_wake_on_network("on")
        assert ret

        ret = power.get_wake_on_network()
        assert ret

        ret = power.set_wake_on_network("off")
        assert ret

        ret = power.get_wake_on_network()
        assert not ret

        power.set_wake_on_network(WAKE_ON_NET)
