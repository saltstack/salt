"""
integration tests for mac_power
"""

import pytest

pytestmark = [
    pytest.mark.flaky(max_runs=10),
    pytest.mark.skip_if_binaries_missing("systemsetup"),
    pytest.mark.slow_test,
    pytest.mark.destructive_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.skip_unless_on_darwin,
]


@pytest.fixture(scope="function")
def setup_teardown_vars(salt_call_cli):
    COMPUTER_SLEEP = salt_call_cli.run("power.get_computer_sleep")
    DISPLAY_SLEEP = salt_call_cli.run("power.get_display_sleep")
    HARD_DISK_SLEEP = salt_call_cli.run("power.get_harddisk_sleep")
    try:
        yield
    finally:
        salt_call_cli.run("power.set_computer_sleep", COMPUTER_SLEEP)
        salt_call_cli.run("power.set_display_sleep", DISPLAY_SLEEP)
        salt_call_cli.run("power.set_harddisk_sleep", HARD_DISK_SLEEP)


def test_computer_sleep(salt_call_cli, setup_teardown_vars):
    """
    Test power.get_computer_sleep
    Test power.set_computer_sleep
    """

    # Normal Functionality
    assert salt_call_cli.run("power.set_computer_sleep", 90)
    assert salt_call_cli.run("power.get_computer_sleep") == "after 90 minutes"
    assert salt_call_cli.run("power.set_computer_sleep", "Off")
    assert salt_call_cli.run("power.get_computer_sleep") == "Never"

    # Test invalid input
    assert "Invalid String Value for Minutes" in salt_call_cli.run(
        "power.set_computer_sleep", "spongebob"
    )
    assert "Invalid Integer Value for Minutes" in salt_call_cli.run(
        "power.set_computer_sleep", 0
    )
    assert "Invalid Integer Value for Minutes" in salt_call_cli.run(
        "power.set_computer_sleep", 181
    )
    assert "Invalid Boolean Value for Minutes" in salt_call_cli.run(
        "power.set_computer_sleep", True
    )


def test_display_sleep(salt_call_cli, setup_teardown_vars):
    """
    Test power.get_display_sleep
    Test power.set_display_sleep
    """

    # Normal Functionality
    assert salt_call_cli.run("power.set_display_sleep", 90)
    assert salt_call_cli.run("power.get_display_sleep") == "after 90 minutes"
    assert salt_call_cli.run("power.set_display_sleep", "Off")
    assert salt_call_cli.run("power.get_display_sleep") == "Never"

    # Test invalid input
    assert "Invalid String Value for Minutes" in salt_call_cli.run(
        "power.set_display_sleep", "spongebob"
    )
    assert "Invalid Integer Value for Minutes" in salt_call_cli.run(
        "power.set_display_sleep", 0
    )
    assert "Invalid Integer Value for Minutes" in salt_call_cli.run(
        "power.set_display_sleep", 181
    )
    assert "Invalid Boolean Value for Minutes" in salt_call_cli.run(
        "power.set_display_sleep", True
    )


def test_harddisk_sleep(salt_call_cli, setup_teardown_vars):
    """
    Test power.get_harddisk_sleep
    Test power.set_harddisk_sleep
    """

    # Normal Functionality
    assert salt_call_cli.run("power.set_harddisk_sleep", 90)
    assert salt_call_cli.run("power.get_harddisk_sleep") == "after 90 minutes"
    assert salt_call_cli.run("power.set_harddisk_sleep", "Off")
    assert salt_call_cli.run("power.get_harddisk_sleep") == "Never"

    # Test invalid input
    assert "Invalid String Value for Minutes" in salt_call_cli.run(
        "power.set_harddisk_sleep", "spongebob"
    )
    assert "Invalid Integer Value for Minutes" in salt_call_cli.run(
        "power.set_harddisk_sleep", 0
    )
    assert "Invalid Integer Value for Minutes" in salt_call_cli.run(
        "power.set_harddisk_sleep", 181
    )
    assert "Invalid Boolean Value for Minutes" in salt_call_cli.run(
        "power.set_harddisk_sleep", True
    )


def test_restart_freeze(salt_call_cli, setup_teardown_vars):
    """
    Test power.get_restart_freeze
    Test power.set_restart_freeze
    """
    # Normal Functionality
    assert salt_call_cli.run("power.set_restart_freeze", "on")
    assert salt_call_cli.run("power.get_restart_freeze")
    # This will return False because mac fails to actually make the change
    assert not salt_call_cli.run("power.set_restart_freeze", "off")
    # Even setting to off returns true, it actually is never set
    # This is an apple bug
    assert salt_call_cli.run("power.get_restart_freeze")
