"""
integration tests for mac_power
"""

import pytest

from salt.exceptions import CommandExecutionError, SaltInvocationError

pytestmark = [
    pytest.mark.skip_if_binaries_missing("systemsetup"),
    pytest.mark.slow_test,
    pytest.mark.destructive_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.skip_unless_on_darwin,
]


@pytest.fixture(scope="module")
def power(modules):
    return modules.power


@pytest.fixture
def _reset_computer_sleep(power):
    ret = power.get_computer_sleep()
    try:
        yield
    finally:
        power.set_computer_sleep(ret)


@pytest.fixture
def _reset_display_sleep(power):
    ret = power.get_display_sleep()
    try:
        yield
    finally:
        power.set_display_sleep(ret)


@pytest.fixture
def _reset_harddisk_sleep(power):
    ret = power.get_harddisk_sleep()
    try:
        yield
    finally:
        power.set_harddisk_sleep(ret)


@pytest.fixture
def _reset_restart_power_failure(power):
    try:
        ret = power.get_restart_power_failure()
        if not isinstance(ret, bool):
            assert "Error" in ret
            pytest.skip(f"Error while calling `get_restart_power_failure()`: {ret}")
    except CommandExecutionError as exc:
        if "Not supported on this machine" in str(exc):
            pytest.skip("Restart After Power Failure: Not supported on this machine.")
    try:
        yield
    finally:
        if isinstance(ret, bool):
            if ret:
                ret = power.set_restart_power_failure("On")
                assert ret
            else:
                ret = power.set_restart_power_failure("Off")
                assert ret


@pytest.fixture
def _reset_sleep_on_power_button(power):
    try:
        ret = power.get_sleep_on_power_button()
        if not isinstance(ret, bool):
            functionality_available = False
        else:
            functionality_available = True
    except CommandExecutionError as exc:
        functionality_available = False

    if functionality_available is False:
        pytest.skip("Skipping. sleep_on_power_button unavailable.")

    try:
        yield
    finally:
        power.set_sleep_on_power_button(ret)


@pytest.fixture
def _reset_wake_on_modem(power):
    try:
        ret = power.get_wake_on_modem()
        if not isinstance(ret, bool):
            functionality_available = False
        else:
            functionality_available = True
    except CommandExecutionError as exc:
        functionality_available = False

    if functionality_available is False:
        pytest.skip("Skipping. wake_on_modem unavailable.")

    try:
        yield
    finally:
        power.set_wake_on_modem(ret)


@pytest.fixture
def _reset_wake_on_network(power):
    try:
        ret = power.get_wake_on_network()
        if not isinstance(ret, bool):
            assert "Error" in ret
            pytest.skip(f"Error while calling `get_wake_on_network()`: {ret}")
    except CommandExecutionError as exc:
        if "Not supported on this machine" in str(exc):
            pytest.skip("Wake On Network Access: Not supported on this machine")
    try:
        yield
    finally:
        if isinstance(ret, bool):
            ret = power.set_wake_on_network(ret)
            assert ret


@pytest.mark.usefixtures("_reset_computer_sleep")
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


@pytest.mark.usefixtures("_reset_display_sleep")
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


@pytest.mark.usefixtures("_reset_harddisk_sleep")
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


@pytest.mark.usefixtures("_reset_restart_power_failure")
def test_restart_power_failure(power):
    """
    Test power.get_restart_power_failure
    Test power.set_restart_power_failure
    """
    ret = power.set_restart_power_failure("On")
    assert ret

    ret = power.get_restart_power_failure()
    assert ret

    ret = power.set_restart_power_failure("Off")
    assert ret

    ret = power.get_restart_power_failure()
    assert not ret


@pytest.mark.usefixtures("_reset_sleep_on_power_button")
def test_sleep_on_power_button(power):
    """
    Test power.get_sleep_on_power_button
    Test power.set_sleep_on_power_button
    """
    ret = power.set_sleep_on_power_button("on")
    assert ret

    ret = power.get_sleep_on_power_button()
    assert ret

    ret = power.set_sleep_on_power_button("off")
    assert ret

    ret = power.get_sleep_on_power_button()
    assert not ret


@pytest.mark.usefixtures("_reset_wake_on_modem")
def test_wake_on_modem(power):
    """
    Test power.get_wake_on_modem
    Test power.set_wake_on_modem
    """
    ret = power.set_wake_on_modem("on")
    assert ret

    ret = power.get_wake_on_modem()
    assert ret

    ret = power.set_wake_on_modem("off")
    assert ret

    ret = power.get_wake_on_modem()
    assert not ret


@pytest.mark.usefixtures("_reset_wake_on_network")
def test_wake_on_network(power):
    """
    Test power.get_wake_on_network
    Test power.set_wake_on_network
    """
    ret = power.set_wake_on_network("on")
    assert ret

    ret = power.get_wake_on_network()
    assert ret

    ret = power.set_wake_on_network("off")
    assert ret

    ret = power.get_wake_on_network()
    assert not ret
