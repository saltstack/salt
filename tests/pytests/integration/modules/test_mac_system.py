"""
integration tests for mac_system
"""

import logging

import pytest
from saltfactories.utils import random_string

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.flaky(max_runs=10),
    pytest.mark.slow_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.skip_unless_on_darwin,
    pytest.mark.usefixtures("salt_sub_minion"),
    pytest.mark.skip_if_binaries_missing("systemsetup"),
    pytest.mark.skip_initial_gh_actions_failure,
]


@pytest.fixture(scope="function")
def setup_teardown_vars(salt_call_cli):
    ATRUN_ENABLED = salt_call_cli.run("service.enabled", "com.apple.atrun")
    REMOTE_LOGIN_ENABLED = salt_call_cli.run("system.get_remote_login")
    REMOTE_EVENTS_ENABLED = salt_call_cli.run("system.get_remote_events")
    SUBNET_NAME = salt_call_cli.run("system.get_subnet_name")
    KEYBOARD_DISABLED = salt_call_cli.run("system.get_disable_keyboard_on_lock")

    try:
        yield
    finally:
        if not ATRUN_ENABLED:
            atrun = "/System/Library/LaunchDaemons/com.apple.atrun.plist"
            salt_call_cli.run("service.stop", atrun)

        salt_call_cli.run("system.set_remote_login", REMOTE_LOGIN_ENABLED)
        salt_call_cli.run("system.set_remote_events", REMOTE_EVENTS_ENABLED)
        salt_call_cli.run("system.set_subnet_name", SUBNET_NAME)
        salt_call_cli.run("system.set_disable_keyboard_on_lock", KEYBOARD_DISABLED)


def test_get_set_remote_login(salt_call_cli):
    """
    Test system.get_remote_login
    Test system.set_remote_login
    """
    # Normal Functionality
    assert salt_call_cli.run("system.set_remote_login", True)
    assert salt_call_cli.run("system.get_remote_login")
    assert salt_call_cli.run("system.set_remote_login", False)
    assert not salt_call_cli.run("system.get_remote_login")

    # Test valid input
    assert salt_call_cli.run("system.set_remote_login", True)
    assert salt_call_cli.run("system.set_remote_login", False)
    assert salt_call_cli.run("system.set_remote_login", "yes")
    assert salt_call_cli.run("system.set_remote_login", "no")
    assert salt_call_cli.run("system.set_remote_login", "On")
    assert salt_call_cli.run("system.set_remote_login", "Off")
    assert salt_call_cli.run("system.set_remote_login", 1)
    assert salt_call_cli.run("system.set_remote_login", 0)

    # Test invalid input
    assert "Invalid String Value for Enabled" in salt_call_cli.run(
        "system.set_remote_login", "spongebob"
    )


def test_get_set_remote_events(salt_call_cli):
    """
    Test system.get_remote_events
    Test system.set_remote_events
    """
    # Normal Functionality
    assert salt_call_cli.run("system.set_remote_events", True)
    assert salt_call_cli.run("system.get_remote_events")
    assert salt_call_cli.run("system.set_remote_events", False)
    assert not salt_call_cli.run("system.get_remote_events")

    # Test valid input
    assert salt_call_cli.run("system.set_remote_events", True)
    assert salt_call_cli.run("system.set_remote_events", False)
    assert salt_call_cli.run("system.set_remote_events", "yes")
    assert salt_call_cli.run("system.set_remote_events", "no")
    assert salt_call_cli.run("system.set_remote_events", "On")
    assert salt_call_cli.run("system.set_remote_events", "Off")
    assert salt_call_cli.run("system.set_remote_events", 1)
    assert salt_call_cli.run("system.set_remote_events", 0)

    # Test invalid input
    assert "Invalid String Value for Enabled" in salt_call_cli.run(
        "system.set_remote_events", "spongebob"
    )


def test_get_set_subnet_name(salt_call_cli):
    """
    Test system.get_subnet_name
    Test system.set_subnet_name
    """
    SET_SUBNET_NAME = random_string("RS-", lowercase=False)

    assert salt_call_cli.run("system.set_subnet_name", SET_SUBNET_NAME)
    assert salt_call_cli.run("system.get_subnet_name") == SET_SUBNET_NAME


def test_get_list_startup_disk(salt_call_cli):
    """
    Test system.get_startup_disk
    Test system.list_startup_disks
    Don't know how to test system.set_startup_disk as there's usually only
    one startup disk available on a system
    """
    # Test list and get
    ret = salt_call_cli.run("system.list_startup_disks")
    assert isinstance(ret, list)
    assert salt_call_cli.run("system.get_startup_disk") in ret

    # Test passing set a bad disk
    assert "Invalid value passed for path." in salt_call_cli.run(
        "system.set_startup_disk", "spongebob"
    )


@pytest.mark.skip(reason="Skip this test until mac fixes it.")
def test_get_set_restart_delay(salt_call_cli):
    """
    Test system.get_restart_delay
    Test system.set_restart_delay
    system.set_restart_delay does not work due to an apple bug, see docs
    may need to disable this test as we can't control the delay value
    """
    # Normal Functionality
    assert salt_call_cli.run("system.set_restart_delay", 90)
    assert salt_call_cli.run("system.get_restart_delay") == "90 seconds"

    # Pass set bad value for seconds
    assert "Invalid value passed for seconds." in salt_call_cli.run(
        "system.set_restart_delay", 70
    )


def test_get_set_disable_keyboard_on_lock(salt_call_cli):
    """
    Test system.get_disable_keyboard_on_lock
    Test system.set_disable_keyboard_on_lock
    """
    # Normal Functionality
    assert salt_call_cli.run("system.set_disable_keyboard_on_lock", True)
    assert salt_call_cli.run("system.get_disable_keyboard_on_lock")

    assert salt_call_cli.run("system.set_disable_keyboard_on_lock", False)
    assert not salt_call_cli.run("system.get_disable_keyboard_on_lock")

    # Test valid input
    assert salt_call_cli.run("system.set_disable_keyboard_on_lock", True)
    assert salt_call_cli.run("system.set_disable_keyboard_on_lock", False)
    assert salt_call_cli.run("system.set_disable_keyboard_on_lock", "yes")
    assert salt_call_cli.run("system.set_disable_keyboard_on_lock", "no")
    assert salt_call_cli.run("system.set_disable_keyboard_on_lock", "On")
    assert salt_call_cli.run("system.set_disable_keyboard_on_lock", "Off")
    assert salt_call_cli.run("system.set_disable_keyboard_on_lock", 1)
    assert salt_call_cli.run("system.set_disable_keyboard_on_lock", 0)

    # Test invalid input
    assert "Invalid String Value for Enabled" in salt_call_cli.run(
        "system.set_disable_keyboard_on_lock", "spongebob"
    )


@pytest.mark.skip(reason="Skip this test until mac fixes it.")
def test_get_set_boot_arch(salt_call_cli):
    """
    Test system.get_boot_arch
    Test system.set_boot_arch
    system.set_boot_arch does not work due to an apple bug, see docs
    may need to disable this test as we can't set the boot architecture
    """
    # Normal Functionality
    assert salt_call_cli.run("system.set_boot_arch", "i386")
    assert salt_call_cli.run("system.get_boot_arch") == "i386"
    assert salt_call_cli.run("system.set_boot_arch", "default")
    assert salt_call_cli.run("system.get_boot_arch") == "default"

    # Test invalid input
    assert "Invalid value passed for arch" in salt_call_cli.run(
        "system.set_boot_arch", "spongebob"
    )


# A similar test used to be skipped on py3 due to 'hanging', if we see
# something similar again we may want to skip this gain until we
# investigate
# @pytest.mark.skipif(salt.utils.platform.is_darwin() and six.PY3, reason='This test hangs on OS X on Py3.  Skipping until #53566 is merged.')
@pytest.mark.destructive_test
def test_get_set_computer_name(salt_call_cli):
    """
    Test system.get_computer_name
    Test system.set_computer_name
    """
    SET_COMPUTER_NAME = random_string("RS-", lowercase=False)

    COMPUTER_NAME = salt_call_cli.run("system.get_computer_name")

    log.debug("Set name is %s", SET_COMPUTER_NAME)
    assert salt_call_cli.run("system.set_computer_name", [SET_COMPUTER_NAME])
    assert salt_call_cli.run("system.get_computer_name") == SET_COMPUTER_NAME

    salt_call_cli.run("system.set_computer_name", COMPUTER_NAME)
