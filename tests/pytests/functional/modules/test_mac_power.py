"""
integration tests for mac_power
"""

import pytest

from salt.exceptions import SaltInvocationError

pytestmark = [
    pytest.mark.flaky(max_runs=10),
    pytest.mark.skip_if_binaries_missing("systemsetup"),
    pytest.mark.slow_test,
    pytest.mark.destructive_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.skip_unless_on_darwin,
]


@pytest.fixture(scope="module")
def power(modules):
    return modules.power


@pytest.fixture(scope="function", autouse=True)
def _setup_teardown_vars(power):
    computer_sleep = power.get_computer_sleep()
    display_sleep = power.get_display_sleep()
    hard_disk_sleep = power.get_harddisk_sleep()
    try:
        yield
    finally:
        power.set_computer_sleep(computer_sleep)
        power.set_display_sleep(display_sleep)
        power.set_harddisk_sleep(hard_disk_sleep)


def test_computer_sleep(power):
    """
    Test power.get_computer_sleep
    Test power.set_computer_sleep
    """

    # Normal Functionality
    ret = power.set_computer_sleep(90)
    assert ret

    ret = power.get_computer_sleep()
    assert ret == "after 90 minutes"

    ret = power.set_computer_sleep("Off")
    assert ret

    ret = power.get_computer_sleep()
    assert ret == "Never"

    # Test invalid input
    with pytest.raises(SaltInvocationError) as exc:
        power.set_computer_sleep("spongebob")
        assert "Invalid String Value for Minutes" in str(exc.value)

    with pytest.raises(SaltInvocationError) as exc:
        power.set_computer_sleep(0)
        assert "Invalid Integer Value for Minutes" in str(exc.value)

    with pytest.raises(SaltInvocationError) as exc:
        power.set_computer_sleep(181)
        assert "Invalid Integer Value for Minutes" in str(exc.value)

    with pytest.raises(SaltInvocationError) as exc:
        power.set_computer_sleep(True)
        assert "Invalid Boolean Value for Minutes" in str(exc.value)


def test_display_sleep(power):
    """
    Test power.get_display_sleep
    Test power.set_display_sleep
    """

    # Normal Functionality
    ret = power.set_display_sleep(90)
    assert ret

    ret = power.get_display_sleep()
    assert ret == "after 90 minutes"

    ret = power.set_display_sleep("Off")
    assert ret

    ret = power.get_display_sleep()
    assert ret == "Never"

    # Test invalid input
    with pytest.raises(SaltInvocationError) as exc:
        power.set_display_sleep("spongebob")
        assert "Invalid String Value for Minutes" in str(exc.value)

    with pytest.raises(SaltInvocationError) as exc:
        power.set_display_sleep(0)
        assert "Invalid Integer Value for Minutes" in str(exc.value)

    with pytest.raises(SaltInvocationError) as exc:
        power.set_display_sleep(181)
        assert "Invalid Integer Value for Minutes" in str(exc.value)

    with pytest.raises(SaltInvocationError) as exc:
        power.set_display_sleep(True)
        assert "Invalid Boolean Value for Minutes" in str(exc.value)


def test_harddisk_sleep(power):
    """
    Test power.get_harddisk_sleep
    Test power.set_harddisk_sleep
    """

    # Normal Functionality
    ret = power.set_harddisk_sleep(90)
    assert ret

    ret = power.get_harddisk_sleep()
    assert ret == "after 90 minutes"

    ret = power.set_harddisk_sleep("Off")
    assert ret

    ret = power.get_harddisk_sleep()
    assert ret == "Never"

    # Test invalid input
    with pytest.raises(SaltInvocationError) as exc:
        power.set_harddisk_sleep("spongebob")
        assert "Invalid String Value for Minutes" in str(exc.value)

    with pytest.raises(SaltInvocationError) as exc:
        power.set_harddisk_sleep(0)
        assert "Invalid Integer Value for Minutes" in str(exc.value)

    with pytest.raises(SaltInvocationError) as exc:
        power.set_harddisk_sleep(181)
        assert "Invalid Integer Value for Minutes" in str(exc.value)

    with pytest.raises(SaltInvocationError) as exc:
        power.set_harddisk_sleep(True)
        assert "Invalid Boolean Value for Minutes" in str(exc.value)


def test_restart_freeze(power):
    """
    Test power.get_restart_freeze
    Test power.set_restart_freeze
    """
    # Normal Functionality
    ret = power.set_restart_freeze("on")
    assert ret

    ret = power.get_restart_freeze()
    assert ret

    # This will return False because mac fails to actually make the change
    ret = power.set_restart_freeze("off")
    assert not ret

    # Even setting to off returns true, it actually is never set
    # This is an apple bug
    ret = power.get_restart_freeze()
    assert ret
