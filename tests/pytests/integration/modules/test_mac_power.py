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


@pytest.fixture(scope="function", autouse=True)
def _setup_teardown_vars(salt_call_cli):
    computer_sleep = salt_call_cli.run("power.get_computer_sleep")
    display_sleep = salt_call_cli.run("power.get_display_sleep")
    hard_disk_sleep = salt_call_cli.run("power.get_harddisk_sleep")
    try:
        yield
    finally:
        salt_call_cli.run("power.set_computer_sleep", computer_sleep)
        salt_call_cli.run("power.set_display_sleep", display_sleep)
        salt_call_cli.run("power.set_harddisk_sleep", hard_disk_sleep)


def test_computer_sleep(salt_call_cli):
    """
    Test power.get_computer_sleep
    Test power.set_computer_sleep
    """

    # Normal Functionality
    ret = salt_call_cli.run("power.set_computer_sleep", 90)
    assert ret.data

    ret = salt_call_cli.run("power.get_computer_sleep")
    assert ret.data == "after 90 minutes"

    ret = salt_call_cli.run("power.set_computer_sleep", "Off")
    assert ret.data

    ret = salt_call_cli.run("power.get_computer_sleep")
    assert ret.data == "Never"

    # Test invalid input
    ret = salt_call_cli.run("power.set_computer_sleep", "spongebob")
    assert "Invalid String Value for Minutes" in ret.stderr

    ret = salt_call_cli.run("power.set_computer_sleep", 0)
    assert "Invalid Integer Value for Minutes" in ret.stderr

    ret = salt_call_cli.run("power.set_computer_sleep", 181)
    assert "Invalid Integer Value for Minutes" in ret.stderr

    ret = salt_call_cli.run("power.set_computer_sleep", True)
    assert "Invalid Boolean Value for Minutes" in ret.stderr


def test_display_sleep(salt_call_cli):
    """
    Test power.get_display_sleep
    Test power.set_display_sleep
    """

    # Normal Functionality
    ret = salt_call_cli.run("power.set_display_sleep", 90)
    assert ret.data

    ret = salt_call_cli.run("power.get_display_sleep")
    assert ret.data == "after 90 minutes"

    ret = salt_call_cli.run("power.set_display_sleep", "Off")
    assert ret.data

    ret = salt_call_cli.run("power.get_display_sleep")
    assert ret.data == "Never"

    # Test invalid input
    ret = salt_call_cli.run("power.set_display_sleep", "spongebob")
    assert "Invalid String Value for Minutes" in ret.stderr

    ret = salt_call_cli.run("power.set_display_sleep", 0)
    assert "Invalid Integer Value for Minutes" in ret.stderr

    ret = salt_call_cli.run("power.set_display_sleep", 181)
    assert "Invalid Integer Value for Minutes" in ret.stderr

    ret = salt_call_cli.run("power.set_display_sleep", True)
    assert "Invalid Boolean Value for Minutes" in ret.stderr


def test_harddisk_sleep(salt_call_cli):
    """
    Test power.get_harddisk_sleep
    Test power.set_harddisk_sleep
    """

    # Normal Functionality
    ret = salt_call_cli.run("power.set_harddisk_sleep", 90)
    assert ret.data

    ret = salt_call_cli.run("power.get_harddisk_sleep")
    assert ret.data == "after 90 minutes"

    ret = salt_call_cli.run("power.set_harddisk_sleep", "Off")
    assert ret.data

    ret = salt_call_cli.run("power.get_harddisk_sleep")
    assert ret.data == "Never"

    # Test invalid input
    ret = salt_call_cli.run("power.set_harddisk_sleep", "spongebob")
    assert "Invalid String Value for Minutes" in ret.stderr

    ret = salt_call_cli.run("power.set_harddisk_sleep", 0)
    assert "Invalid Integer Value for Minutes" in ret.stderr

    ret = salt_call_cli.run("power.set_harddisk_sleep", 181)
    assert "Invalid Integer Value for Minutes" in ret.stderr

    ret = salt_call_cli.run("power.set_harddisk_sleep", True)
    assert "Invalid Boolean Value for Minutes" in ret.stderr


def test_restart_freeze(salt_call_cli):
    """
    Test power.get_restart_freeze
    Test power.set_restart_freeze
    """
    # Normal Functionality
    ret = salt_call_cli.run("power.set_restart_freeze", "on")
    assert ret.data

    ret = salt_call_cli.run("power.get_restart_freeze")
    assert ret.data

    # This will return False because mac fails to actually make the change
    ret = salt_call_cli.run("power.set_restart_freeze", "off")
    assert not ret.data

    # Even setting to off returns true, it actually is never set
    # This is an apple bug
    ret = salt_call_cli.run("power.get_restart_freeze")
    assert ret.data
