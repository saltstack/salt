"""
integration tests for mac_power
"""

import pytest

from tests.support.case import ModuleCase


@pytest.mark.flaky(max_runs=10)
@pytest.mark.skip_unless_on_darwin
@pytest.mark.skip_if_binaries_missing("systemsetup")
@pytest.mark.skip_if_not_root
class MacPowerModuleTest(ModuleCase):
    """
    Validate the mac_power module
    """

    def setUp(self):
        """
        Get current settings
        """
        # Get current settings
        self.COMPUTER_SLEEP = self.run_function("power.get_computer_sleep")
        self.DISPLAY_SLEEP = self.run_function("power.get_display_sleep")
        self.HARD_DISK_SLEEP = self.run_function("power.get_harddisk_sleep")

    def tearDown(self):
        """
        Reset to original settings
        """
        self.run_function("power.set_computer_sleep", [self.COMPUTER_SLEEP])
        self.run_function("power.set_display_sleep", [self.DISPLAY_SLEEP])
        self.run_function("power.set_harddisk_sleep", [self.HARD_DISK_SLEEP])

    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_computer_sleep(self):
        """
        Test power.get_computer_sleep
        Test power.set_computer_sleep
        """

        # Normal Functionality
        self.assertTrue(self.run_function("power.set_computer_sleep", [90]))
        self.assertEqual(
            self.run_function("power.get_computer_sleep"), "after 90 minutes"
        )
        self.assertTrue(self.run_function("power.set_computer_sleep", ["Off"]))
        self.assertEqual(self.run_function("power.get_computer_sleep"), "Never")

        # Test invalid input
        self.assertIn(
            "Invalid String Value for Minutes",
            self.run_function("power.set_computer_sleep", ["spongebob"]),
        )
        self.assertIn(
            "Invalid Integer Value for Minutes",
            self.run_function("power.set_computer_sleep", [0]),
        )
        self.assertIn(
            "Invalid Integer Value for Minutes",
            self.run_function("power.set_computer_sleep", [181]),
        )
        self.assertIn(
            "Invalid Boolean Value for Minutes",
            self.run_function("power.set_computer_sleep", [True]),
        )

    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_display_sleep(self):
        """
        Test power.get_display_sleep
        Test power.set_display_sleep
        """

        # Normal Functionality
        self.assertTrue(self.run_function("power.set_display_sleep", [90]))
        self.assertEqual(
            self.run_function("power.get_display_sleep"), "after 90 minutes"
        )
        self.assertTrue(self.run_function("power.set_display_sleep", ["Off"]))
        self.assertEqual(self.run_function("power.get_display_sleep"), "Never")

        # Test invalid input
        self.assertIn(
            "Invalid String Value for Minutes",
            self.run_function("power.set_display_sleep", ["spongebob"]),
        )
        self.assertIn(
            "Invalid Integer Value for Minutes",
            self.run_function("power.set_display_sleep", [0]),
        )
        self.assertIn(
            "Invalid Integer Value for Minutes",
            self.run_function("power.set_display_sleep", [181]),
        )
        self.assertIn(
            "Invalid Boolean Value for Minutes",
            self.run_function("power.set_display_sleep", [True]),
        )

    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_harddisk_sleep(self):
        """
        Test power.get_harddisk_sleep
        Test power.set_harddisk_sleep
        """

        # Normal Functionality
        self.assertTrue(self.run_function("power.set_harddisk_sleep", [90]))
        self.assertEqual(
            self.run_function("power.get_harddisk_sleep"), "after 90 minutes"
        )
        self.assertTrue(self.run_function("power.set_harddisk_sleep", ["Off"]))
        self.assertEqual(self.run_function("power.get_harddisk_sleep"), "Never")

        # Test invalid input
        self.assertIn(
            "Invalid String Value for Minutes",
            self.run_function("power.set_harddisk_sleep", ["spongebob"]),
        )
        self.assertIn(
            "Invalid Integer Value for Minutes",
            self.run_function("power.set_harddisk_sleep", [0]),
        )
        self.assertIn(
            "Invalid Integer Value for Minutes",
            self.run_function("power.set_harddisk_sleep", [181]),
        )
        self.assertIn(
            "Invalid Boolean Value for Minutes",
            self.run_function("power.set_harddisk_sleep", [True]),
        )

    @pytest.mark.slow_test
    def test_restart_freeze(self):
        """
        Test power.get_restart_freeze
        Test power.set_restart_freeze
        """
        # Normal Functionality
        self.assertTrue(self.run_function("power.set_restart_freeze", ["on"]))
        self.assertTrue(self.run_function("power.get_restart_freeze"))
        # This will return False because mac fails to actually make the change
        self.assertFalse(self.run_function("power.set_restart_freeze", ["off"]))
        # Even setting to off returns true, it actually is never set
        # This is an apple bug
        self.assertTrue(self.run_function("power.get_restart_freeze"))


@pytest.mark.flaky(max_runs=10)
@pytest.mark.skip_unless_on_darwin
@pytest.mark.skip_if_binaries_missing("systemsetup")
@pytest.mark.skip_if_not_root
class MacPowerModuleTestSleepOnPowerButton(ModuleCase):
    """
    Test power.get_sleep_on_power_button
    Test power.set_sleep_on_power_button
    """

    SLEEP_ON_BUTTON = None

    def setUp(self):
        """
        Check if function is available
        Get existing value
        """
        # Is the function available
        ret = self.run_function("power.get_sleep_on_power_button")
        if isinstance(ret, bool):
            self.SLEEP_ON_BUTTON = self.run_function("power.get_sleep_on_power_button")

    def tearDown(self):
        """
        Reset to original value
        """
        if self.SLEEP_ON_BUTTON is not None:
            self.run_function("power.set_sleep_on_power_button", [self.SLEEP_ON_BUTTON])

    @pytest.mark.slow_test
    def test_sleep_on_power_button(self):
        """
        Test power.get_sleep_on_power_button
        Test power.set_sleep_on_power_button
        """
        # If available on this system, test it
        if self.SLEEP_ON_BUTTON is None:
            # Check for not available
            ret = self.run_function("power.get_sleep_on_power_button")
            self.assertIn("Error", ret)
        else:
            self.assertTrue(
                self.run_function("power.set_sleep_on_power_button", ["on"])
            )
            self.assertTrue(self.run_function("power.get_sleep_on_power_button"))
            self.assertTrue(
                self.run_function("power.set_sleep_on_power_button", ["off"])
            )
            self.assertFalse(self.run_function("power.get_sleep_on_power_button"))


@pytest.mark.flaky(max_runs=10)
@pytest.mark.skip_unless_on_darwin
@pytest.mark.skip_if_binaries_missing("systemsetup")
@pytest.mark.skip_if_not_root
class MacPowerModuleTestRestartPowerFailure(ModuleCase):
    """
    Test power.get_restart_power_failure
    Test power.set_restart_power_failure
    """

    RESTART_POWER = None

    def setUp(self):
        """
        Check if function is available
        Get existing value
        """
        # Is the function available
        ret = self.run_function("power.get_restart_power_failure")
        if isinstance(ret, bool):
            self.RESTART_POWER = ret

    def tearDown(self):
        """
        Reset to original value
        """
        if self.RESTART_POWER is not None:
            self.run_function("power.set_sleep_on_power_button", [self.SLEEP_ON_BUTTON])

    def test_restart_power_failure(self):
        """
        Test power.get_restart_power_failure
        Test power.set_restart_power_failure
        """
        # If available on this system, test it
        if self.RESTART_POWER is None:
            # Check for not available
            ret = self.run_function("power.get_restart_power_failure")
            self.assertIn("Error", ret)
        else:
            self.assertTrue(
                self.run_function("power.set_restart_power_failure", ["on"])
            )
            self.assertTrue(self.run_function("power.get_restart_power_failure"))
            self.assertTrue(
                self.run_function("power.set_restart_power_failure", ["off"])
            )
            self.assertFalse(self.run_function("power.get_restart_power_failure"))


@pytest.mark.flaky(max_runs=10)
@pytest.mark.skip_unless_on_darwin
@pytest.mark.skip_if_binaries_missing("systemsetup")
@pytest.mark.skip_if_not_root
class MacPowerModuleTestWakeOnNet(ModuleCase):
    """
    Test power.get_wake_on_network
    Test power.set_wake_on_network
    """

    WAKE_ON_NET = None

    def setUp(self):
        """
        Check if function is available
        Get existing value
        """
        # Is the function available
        ret = self.run_function("power.get_wake_on_network")
        if isinstance(ret, bool):
            self.WAKE_ON_NET = ret

    def tearDown(self):
        """
        Reset to original value
        """
        if self.WAKE_ON_NET is not None:
            self.run_function("power.set_wake_on_network", [self.WAKE_ON_NET])

    def test_wake_on_network(self):
        """
        Test power.get_wake_on_network
        Test power.set_wake_on_network
        """
        # If available on this system, test it
        if self.WAKE_ON_NET is None:
            # Check for not available
            ret = self.run_function("power.get_wake_on_network")
            self.assertIn("Error", ret)
        else:
            self.assertTrue(self.run_function("power.set_wake_on_network", ["on"]))
            self.assertTrue(self.run_function("power.get_wake_on_network"))
            self.assertTrue(self.run_function("power.set_wake_on_network", ["off"]))
            self.assertFalse(self.run_function("power.get_wake_on_network"))


@pytest.mark.flaky(max_runs=10)
@pytest.mark.skip_unless_on_darwin
@pytest.mark.skip_if_binaries_missing("systemsetup")
@pytest.mark.skip_if_not_root
class MacPowerModuleTestWakeOnModem(ModuleCase):
    """
    Test power.get_wake_on_modem
    Test power.set_wake_on_modem
    """

    WAKE_ON_MODEM = None

    def setUp(self):
        """
        Check if function is available
        Get existing value
        """
        # Is the function available
        ret = self.run_function("power.get_wake_on_modem")
        if isinstance(ret, bool):
            self.WAKE_ON_MODEM = ret

    def tearDown(self):
        """
        Reset to original value
        """
        if self.WAKE_ON_MODEM is not None:
            self.run_function("power.set_wake_on_modem", [self.WAKE_ON_MODEM])

    def test_wake_on_modem(self):
        """
        Test power.get_wake_on_modem
        Test power.set_wake_on_modem
        """
        # If available on this system, test it
        if self.WAKE_ON_MODEM is None:
            # Check for not available
            ret = self.run_function("power.get_wake_on_modem")
            self.assertIn("Error", ret)
        else:
            self.assertTrue(self.run_function("power.set_wake_on_modem", ["on"]))
            self.assertTrue(self.run_function("power.get_wake_on_modem"))
            self.assertTrue(self.run_function("power.set_wake_on_modem", ["off"]))
            self.assertFalse(self.run_function("power.get_wake_on_modem"))
