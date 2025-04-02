"""
integration tests for mac_system
"""

import logging

import pytest
from saltfactories.utils import random_string

from salt.exceptions import CommandExecutionError, SaltInvocationError

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.skip_unless_on_darwin,
    pytest.mark.skip_if_binaries_missing("systemsetup"),
]


@pytest.fixture
def service(modules):
    return modules.service


@pytest.fixture
def system(modules):
    return modules.system


@pytest.fixture
def _remote_login_cleanup(system, grains):
    if grains["osmajorrelease"] >= 13:
        pytest.skip("SKipping until we figure out how to have full dist access")

    remote_login_enabled = system.get_remote_login()
    try:
        yield
    finally:
        if system.get_remote_login() != remote_login_enabled:
            system.set_remote_login(remote_login_enabled)


@pytest.fixture
def _remote_events_cleanup(system, grains):
    if grains["osmajorrelease"] >= 13:
        pytest.skip("SKipping until we figure out how to have full dist access")

    remote_events_enabled = system.get_remote_events()
    try:
        yield
    finally:
        if system.get_remote_events() != remote_events_enabled:
            system.set_remote_events(remote_events_enabled)


@pytest.fixture
def subnet_name(system):
    subnet_name = system.get_subnet_name()
    try:
        yield random_string("subnet-", lowercase=False)
    finally:
        if system.get_subnet_name() != subnet_name:
            system.set_subnet_name(subnet_name)


@pytest.fixture
def _keyboard_cleanup(system):
    keyboard_disabled = system.get_disable_keyboard_on_lock()
    try:
        yield
    finally:
        if system.get_disable_keyboard_on_lock() != keyboard_disabled:
            system.set_disable_keyboard_on_lock(keyboard_disabled)


@pytest.fixture
def computer_name(system):
    computer_name = system.get_computer_name()
    try:
        yield random_string("cmptr-", lowercase=False)
    finally:
        if system.get_computer_name() != computer_name:
            system.set_computer_name(computer_name)


@pytest.mark.usefixtures("_remote_login_cleanup")
def test_get_set_remote_login(system):
    """
    Test system.get_remote_login
    Test system.set_remote_login
    """
    # Normal Functionality
    ret = system.set_remote_login(True)
    assert ret

    ret = system.get_remote_login()
    assert ret

    ret = system.set_remote_login(False)
    assert ret

    ret = system.get_remote_login()
    assert not ret

    # Test valid input
    ret = system.set_remote_login(True)
    assert ret

    ret = system.set_remote_login(False)
    assert ret

    ret = system.set_remote_login("yes")
    assert ret

    ret = system.set_remote_login("no")
    assert ret

    ret = system.set_remote_login("On")
    assert ret

    ret = system.set_remote_login("Off")
    assert ret

    ret = system.set_remote_login(1)
    assert ret

    ret = system.set_remote_login(0)
    assert ret

    # Test invalid input
    with pytest.raises(SaltInvocationError) as exc:
        system.set_remote_login("spongebob")
        assert "Invalid String Value for Enabled" in str(exc.value)


@pytest.mark.skip_initial_gh_actions_failure
@pytest.mark.usefixtures("_remote_events_cleanup")
def test_get_set_remote_events(system):
    """
    Test system.get_remote_events
    Test system.set_remote_events
    """
    # Normal Functionality
    ret = system.set_remote_events(True)
    assert ret

    ret = system.get_remote_events()
    assert ret

    ret = system.set_remote_events(False)
    assert ret

    ret = not system.get_remote_events()
    assert not ret

    # Test valid input
    ret = system.set_remote_events(True)
    assert ret

    ret = system.set_remote_events(False)
    assert ret

    ret = system.set_remote_events("yes")
    assert ret

    ret = system.set_remote_events("no")
    assert ret

    ret = system.set_remote_events("On")
    assert ret

    ret = system.set_remote_events("Off")
    assert ret

    ret = system.set_remote_events(1)
    assert ret

    ret = system.set_remote_events(0)
    assert ret

    # Test invalid input
    with pytest.raises(CommandExecutionError) as exc:
        system.set_remote_events("spongebob")
        assert "Invalid String Value for Enabled" in str(exc.value)


def test_get_set_subnet_name(system, subnet_name):
    """
    Test system.get_subnet_name
    Test system.set_subnet_name
    """
    ret = system.set_subnet_name(subnet_name)
    assert ret

    ret = system.get_subnet_name()
    assert ret == subnet_name


@pytest.mark.skip_initial_gh_actions_failure
def test_get_list_startup_disk(system):
    """
    Test system.get_startup_disk
    Test system.list_startup_disks
    Don't know how to test system.set_startup_disk as there's usually only
    one startup disk available on a system
    """
    # Test list and get
    ret = system.list_startup_disks()
    assert isinstance(ret, list)

    startup_disk = system.get_startup_disk()
    assert startup_disk in ret

    # Test passing set a bad disk
    with pytest.raises(SaltInvocationError) as exc:
        system.set_startup_disk("spongebob")
        assert "Invalid value passed for path." in str(exc.value)


@pytest.mark.skip(reason="Skip this test until mac fixes it.")
def test_get_set_restart_delay(system):
    """
    Test system.get_restart_delay
    Test system.set_restart_delay
    system.set_restart_delay does not work due to an apple bug, see docs
    may need to disable this test as we can't control the delay value
    """
    # Normal Functionality
    ret = system.set_restart_delay(90)
    assert ret

    ret = system.get_restart_delay()
    assert ret == "90 seconds"

    # Pass set bad value for seconds
    with pytest.raises(CommandExecutionError) as exc:
        system.set_restart_delay(70)
        assert "Invalid value passed for seconds." in str(exc.value)


@pytest.mark.usefixtures("_keyboard_cleanup")
def test_get_set_disable_keyboard_on_lock(system):
    """
    Test system.get_disable_keyboard_on_lock
    Test system.set_disable_keyboard_on_lock
    """
    # Normal Functionality
    ret = system.set_disable_keyboard_on_lock(True)
    assert ret

    ret = system.get_disable_keyboard_on_lock()
    assert ret

    ret = system.set_disable_keyboard_on_lock(False)
    assert ret

    ret = system.get_disable_keyboard_on_lock()
    assert not ret

    # Test valid input
    ret = system.set_disable_keyboard_on_lock(True)
    assert ret

    ret = system.set_disable_keyboard_on_lock(False)
    assert ret

    ret = system.set_disable_keyboard_on_lock("yes")
    assert ret

    ret = system.set_disable_keyboard_on_lock("no")
    assert ret

    ret = system.set_disable_keyboard_on_lock("On")
    assert ret

    ret = system.set_disable_keyboard_on_lock("Off")
    assert ret

    ret = system.set_disable_keyboard_on_lock(1)
    assert ret

    ret = system.set_disable_keyboard_on_lock(0)
    assert ret

    # Test invalid input
    with pytest.raises(SaltInvocationError) as exc:
        system.set_disable_keyboard_on_lock("spongebob")
        assert "Invalid String Value for Enabled" in str(exc.value)


@pytest.mark.skip(reason="Skip this test until mac fixes it.")
def test_get_set_boot_arch(system):
    """
    Test system.get_boot_arch
    Test system.set_boot_arch
    system.set_boot_arch does not work due to an apple bug, see docs
    may need to disable this test as we can't set the boot architecture
    """
    # Normal Functionality
    ret = system.set_boot_arch("i386")
    assert ret

    ret = system.get_boot_arch()
    assert ret == "i386"

    ret = system.set_boot_arch("default")
    assert ret

    ret = system.get_boot_arch()
    assert ret == "default"

    # Test invalid input
    with pytest.raises(CommandExecutionError) as exc:
        system.set_boot_arch("spongebob")
        assert "Invalid value passed for arch" in str(exc.value)


# A similar test used to be skipped on py3 due to 'hanging', if we see
# something similar again we may want to skip this gain until we
# investigate
# @pytest.mark.skipif(salt.utils.platform.is_darwin() and six.PY3, reason='This test hangs on OS X on Py3.  Skipping until #53566 is merged.')
@pytest.mark.destructive_test
def test_get_set_computer_name(system, computer_name):
    """
    Test system.get_computer_name
    Test system.set_computer_name
    """
    current_computer_name = system.get_computer_name()
    assert current_computer_name
    assert current_computer_name != computer_name

    ret = system.set_computer_name(computer_name)
    assert ret

    ret = system.get_computer_name()
    assert ret == computer_name
