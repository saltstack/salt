"""
integration tests for mac_system
"""

import logging

import pytest
from tests.support.case import ModuleCase
from tests.support.helpers import random_string
from tests.support.unit import skipIf

log = logging.getLogger(__name__)


SET_COMPUTER_NAME = random_string("RS-", lowercase=False)
SET_SUBNET_NAME = random_string("RS-", lowercase=False)


@pytest.mark.flaky(max_runs=10)
@pytest.mark.skip_unless_on_darwin
@pytest.mark.usefixtures("salt_sub_minion")
@pytest.mark.skip_if_not_root
@pytest.mark.skip_if_binaries_missing("systemsetup")
class MacSystemModuleTest(ModuleCase):
    """
    Validate the mac_system module
    """

    ATRUN_ENABLED = False
    REMOTE_LOGIN_ENABLED = False
    REMOTE_EVENTS_ENABLED = False
    SUBNET_NAME = ""
    KEYBOARD_DISABLED = False

    def setUp(self):
        """
        Get current settings
        """
        self.ATRUN_ENABLED = self.run_function("service.enabled", ["com.apple.atrun"])
        self.REMOTE_LOGIN_ENABLED = self.run_function("system.get_remote_login")
        self.REMOTE_EVENTS_ENABLED = self.run_function("system.get_remote_events")
        self.SUBNET_NAME = self.run_function("system.get_subnet_name")
        self.KEYBOARD_DISABLED = self.run_function(
            "system.get_disable_keyboard_on_lock"
        )

    def tearDown(self):
        """
        Reset to original settings
        """
        if not self.ATRUN_ENABLED:
            atrun = "/System/Library/LaunchDaemons/com.apple.atrun.plist"
            self.run_function("service.stop", [atrun])

        self.run_function("system.set_remote_login", [self.REMOTE_LOGIN_ENABLED])
        self.run_function("system.set_remote_events", [self.REMOTE_EVENTS_ENABLED])
        self.run_function("system.set_subnet_name", [self.SUBNET_NAME])
        self.run_function(
            "system.set_disable_keyboard_on_lock", [self.KEYBOARD_DISABLED]
        )

    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_get_set_remote_login(self):
        """
        Test system.get_remote_login
        Test system.set_remote_login
        """
        # Normal Functionality
        self.assertTrue(self.run_function("system.set_remote_login", [True]))
        self.assertTrue(self.run_function("system.get_remote_login"))
        self.assertTrue(self.run_function("system.set_remote_login", [False]))
        self.assertFalse(self.run_function("system.get_remote_login"))

        # Test valid input
        self.assertTrue(self.run_function("system.set_remote_login", [True]))
        self.assertTrue(self.run_function("system.set_remote_login", [False]))
        self.assertTrue(self.run_function("system.set_remote_login", ["yes"]))
        self.assertTrue(self.run_function("system.set_remote_login", ["no"]))
        self.assertTrue(self.run_function("system.set_remote_login", ["On"]))
        self.assertTrue(self.run_function("system.set_remote_login", ["Off"]))
        self.assertTrue(self.run_function("system.set_remote_login", [1]))
        self.assertTrue(self.run_function("system.set_remote_login", [0]))

        # Test invalid input
        self.assertIn(
            "Invalid String Value for Enabled",
            self.run_function("system.set_remote_login", ["spongebob"]),
        )

    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_get_set_remote_events(self):
        """
        Test system.get_remote_events
        Test system.set_remote_events
        """
        # Normal Functionality
        self.assertTrue(self.run_function("system.set_remote_events", [True]))
        self.assertTrue(self.run_function("system.get_remote_events"))
        self.assertTrue(self.run_function("system.set_remote_events", [False]))
        self.assertFalse(self.run_function("system.get_remote_events"))

        # Test valid input
        self.assertTrue(self.run_function("system.set_remote_events", [True]))
        self.assertTrue(self.run_function("system.set_remote_events", [False]))
        self.assertTrue(self.run_function("system.set_remote_events", ["yes"]))
        self.assertTrue(self.run_function("system.set_remote_events", ["no"]))
        self.assertTrue(self.run_function("system.set_remote_events", ["On"]))
        self.assertTrue(self.run_function("system.set_remote_events", ["Off"]))
        self.assertTrue(self.run_function("system.set_remote_events", [1]))
        self.assertTrue(self.run_function("system.set_remote_events", [0]))

        # Test invalid input
        self.assertIn(
            "Invalid String Value for Enabled",
            self.run_function("system.set_remote_events", ["spongebob"]),
        )

    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_get_set_subnet_name(self):
        """
        Test system.get_subnet_name
        Test system.set_subnet_name
        """
        self.assertTrue(self.run_function("system.set_subnet_name", [SET_SUBNET_NAME]))
        self.assertEqual(self.run_function("system.get_subnet_name"), SET_SUBNET_NAME)

    @pytest.mark.slow_test
    def test_get_list_startup_disk(self):
        """
        Test system.get_startup_disk
        Test system.list_startup_disks
        Don't know how to test system.set_startup_disk as there's usually only
        one startup disk available on a system
        """
        # Test list and get
        ret = self.run_function("system.list_startup_disks")
        self.assertIsInstance(ret, list)
        self.assertIn(self.run_function("system.get_startup_disk"), ret)

        # Test passing set a bad disk
        self.assertIn(
            "Invalid value passed for path.",
            self.run_function("system.set_startup_disk", ["spongebob"]),
        )

    @skipIf(True, "Skip this test until mac fixes it.")
    def test_get_set_restart_delay(self):
        """
        Test system.get_restart_delay
        Test system.set_restart_delay
        system.set_restart_delay does not work due to an apple bug, see docs
        may need to disable this test as we can't control the delay value
        """
        # Normal Functionality
        self.assertTrue(self.run_function("system.set_restart_delay", [90]))
        self.assertEqual(self.run_function("system.get_restart_delay"), "90 seconds")

        # Pass set bad value for seconds
        self.assertIn(
            "Invalid value passed for seconds.",
            self.run_function("system.set_restart_delay", [70]),
        )

    @pytest.mark.slow_test
    def test_get_set_disable_keyboard_on_lock(self):
        """
        Test system.get_disable_keyboard_on_lock
        Test system.set_disable_keyboard_on_lock
        """
        # Normal Functionality
        self.assertTrue(
            self.run_function("system.set_disable_keyboard_on_lock", [True])
        )
        self.assertTrue(self.run_function("system.get_disable_keyboard_on_lock"))

        self.assertTrue(
            self.run_function("system.set_disable_keyboard_on_lock", [False])
        )
        self.assertFalse(self.run_function("system.get_disable_keyboard_on_lock"))

        # Test valid input
        self.assertTrue(
            self.run_function("system.set_disable_keyboard_on_lock", [True])
        )
        self.assertTrue(
            self.run_function("system.set_disable_keyboard_on_lock", [False])
        )
        self.assertTrue(
            self.run_function("system.set_disable_keyboard_on_lock", ["yes"])
        )
        self.assertTrue(
            self.run_function("system.set_disable_keyboard_on_lock", ["no"])
        )
        self.assertTrue(
            self.run_function("system.set_disable_keyboard_on_lock", ["On"])
        )
        self.assertTrue(
            self.run_function("system.set_disable_keyboard_on_lock", ["Off"])
        )
        self.assertTrue(self.run_function("system.set_disable_keyboard_on_lock", [1]))
        self.assertTrue(self.run_function("system.set_disable_keyboard_on_lock", [0]))

        # Test invalid input
        self.assertIn(
            "Invalid String Value for Enabled",
            self.run_function("system.set_disable_keyboard_on_lock", ["spongebob"]),
        )

    @skipIf(True, "Skip this test until mac fixes it.")
    def test_get_set_boot_arch(self):
        """
        Test system.get_boot_arch
        Test system.set_boot_arch
        system.set_boot_arch does not work due to an apple bug, see docs
        may need to disable this test as we can't set the boot architecture
        """
        # Normal Functionality
        self.assertTrue(self.run_function("system.set_boot_arch", ["i386"]))
        self.assertEqual(self.run_function("system.get_boot_arch"), "i386")
        self.assertTrue(self.run_function("system.set_boot_arch", ["default"]))
        self.assertEqual(self.run_function("system.get_boot_arch"), "default")

        # Test invalid input
        self.assertIn(
            "Invalid value passed for arch",
            self.run_function("system.set_boot_arch", ["spongebob"]),
        )


@pytest.mark.skip_unless_on_darwin
@pytest.mark.skip_if_not_root
class MacSystemComputerNameTest(ModuleCase):
    def setUp(self):
        self.COMPUTER_NAME = self.run_function("system.get_computer_name")
        self.wait_for_all_jobs()

    def tearDown(self):
        self.run_function("system.set_computer_name", [self.COMPUTER_NAME])
        self.wait_for_all_jobs()

    # A similar test used to be skipped on py3 due to 'hanging', if we see
    # something similar again we may want to skip this gain until we
    # investigate
    # @skipIf(salt.utils.platform.is_darwin() and six.PY3, 'This test hangs on OS X on Py3.  Skipping until #53566 is merged.')
    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_get_set_computer_name(self):
        """
        Test system.get_computer_name
        Test system.set_computer_name
        """
        log.debug("Set name is %s", SET_COMPUTER_NAME)
        self.assertTrue(
            self.run_function("system.set_computer_name", [SET_COMPUTER_NAME])
        )
        self.assertEqual(
            self.run_function("system.get_computer_name"), SET_COMPUTER_NAME
        )
