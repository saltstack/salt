# -*- coding: utf-8 -*-
'''
integration tests for mac_power
'''

# Import python libs
from __future__ import absolute_import, print_function
from six import string_types

# Import Salt Testing libs
from salttesting import skipIf
from salttesting.helpers import ensure_in_syspath, destructiveTest
ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils

@skipIf(not salt.utils.is_darwin()
        or not salt.utils.which('systemsetup')
        or salt.utils.get_uid(salt.utils.get_user()) != 0, 'Test requirements not met')
class MacPowerModuleTest(integration.ModuleCase):
    '''
    Validate the mac_power module
    '''
    COMPUTER_SLEEP = None
    DISPLAY_SLEEP = None
    HARD_DISK_SLEEP = None
    WAKE_ON_MODEM = None
    WAKE_ON_NET = None
    RESTART_POWER = None
    SLEEP_ON_BUTTON = None
    WAKE_ON_MOD_AVAIL = None
    WAKE_ON_NET_AVAIL = None
    RESTART_POW_AVAIL = None
    SLEEP_ON_POW_AVAIL = None

    def __init__(self, arg):
        super(self.__class__, self).__init__(arg)
        # Determine if these functions are available
        # This is necessary because they may not be available if this test is run
        # on a laptop vs a desktop or in a vm
        if self.RESTART_POW_AVAIL is None:
            self.RESTART_POW_AVAIL = True
            ret = self.run_function('power.get_restart_power_failure')
            if isinstance(ret, string_types) and 'Error' in ret:
                self.RESTART_POW_AVAIL = False
        if self.SLEEP_ON_POW_AVAIL is None:
            self.SLEEP_ON_POW_AVAIL = True
            ret = self.run_function('power.get_sleep_on_power_button')
            if isinstance(ret, string_types) and 'Error' in ret:
                self.SLEEP_ON_POW_AVAIL = False
        if self.WAKE_ON_NET_AVAIL is None:
            self.WAKE_ON_NET_AVAIL = True
            ret = self.run_function('power.get_wake_on_network')
            if isinstance(ret, string_types) and 'Error' in ret:
                self.WAKE_ON_NET_AVAIL = False
        if self.WAKE_ON_MOD_AVAIL is None:
            self.WAKE_ON_MOD_AVAIL = True
            ret = self.run_function('power.get_wake_on_modem')
            if isinstance(ret, string_types) and 'Error' in ret:
                self.WAKE_ON_MOD_AVAIL = False

    def setUp(self):
        '''
        Get current settings
        '''
        # Get current settings
        if self.COMPUTER_SLEEP is None:
            self.COMPUTER_SLEEP = self.run_function('power.get_computer_sleep')
        if self.DISPLAY_SLEEP is None:
            self.DISPLAY_SLEEP = self.run_function('power.get_display_sleep')
        if self.HARD_DISK_SLEEP is None:
            self.HARD_DISK_SLEEP = self.run_function('power.get_harddisk_sleep')
        if self.WAKE_ON_MOD_AVAIL:
            if self.WAKE_ON_MODEM is None:
                self.WAKE_ON_MODEM = self.run_function('power.get_wake_on_modem')
        if self.WAKE_ON_NET_AVAIL:
            if self.WAKE_ON_NET is None:
                self.WAKE_ON_NET = self.run_function('power.get_wake_on_network')
        if self.RESTART_POW_AVAIL:
            if self.RESTART_POWER is None:
                self.RESTART_POWER = self.run_function('power.get_restart_power_failure')
        if self.SLEEP_ON_POW_AVAIL:
            if self.SLEEP_ON_BUTTON is None:
                self.SLEEP_ON_BUTTON = self.run_function('power.get_sleep_on_power_button')

    def tearDown(self):
        '''
        Reset to original settings
        '''
        self.run_function('power.set_computer_sleep', [self.COMPUTER_SLEEP])
        self.run_function('power.set_display_sleep', [self.DISPLAY_SLEEP])
        self.run_function('power.set_harddisk_sleep', [self.HARD_DISK_SLEEP])
        if self.WAKE_ON_MOD_AVAIL:
            self.run_function('power.set_wake_on_modem', [self.WAKE_ON_MODEM])
        if self.WAKE_ON_NET_AVAIL:
            self.run_function('power.set_wake_on_network', [self.WAKE_ON_NET])
        if self.RESTART_POW_AVAIL:
            self.run_function('power.set_restart_power_failure',
                              [self.RESTART_POWER])
        if self.SLEEP_ON_POW_AVAIL:
            self.run_function('power.set_sleep_on_power_button',
                              [self.SLEEP_ON_BUTTON])

    @destructiveTest
    def test_computer_sleep(self):
        '''
        Test power.get_computer_sleep
        Test power.set_computer_sleep
        '''

        # Normal Functionality
        self.assertTrue(self.run_function('power.set_computer_sleep', [90]))
        self.assertEqual(
            self.run_function('power.get_computer_sleep'), 'after 90 minutes')
        self.assertTrue(self.run_function('power.set_computer_sleep', ['Off']))
        self.assertEqual(self.run_function('power.get_computer_sleep'), 'Never')

        # Test invalid input
        self.assertIn(
            'Invalid String Value for Minutes',
            self.run_function('power.set_computer_sleep', ['spongebob']))
        self.assertIn(
            'Invalid Integer Value for Minutes',
            self.run_function('power.set_computer_sleep', [0]))
        self.assertIn(
            'Invalid Integer Value for Minutes',
            self.run_function('power.set_computer_sleep', [181]))
        self.assertIn(
            'Invalid Boolean Value for Minutes',
            self.run_function('power.set_computer_sleep', [True]))

    @destructiveTest
    def test_display_sleep(self):
        '''
        Test power.get_display_sleep
        Test power.set_display_sleep
        '''

        # Normal Functionality
        self.assertTrue(self.run_function('power.set_display_sleep', [90]))
        self.assertEqual(
            self.run_function('power.get_display_sleep'), 'after 90 minutes')
        self.assertTrue(self.run_function('power.set_display_sleep', ['Off']))
        self.assertEqual(self.run_function('power.get_display_sleep'), 'Never')

        # Test invalid input
        self.assertIn(
            'Invalid String Value for Minutes',
            self.run_function('power.set_display_sleep', ['spongebob']))
        self.assertIn(
            'Invalid Integer Value for Minutes',
            self.run_function('power.set_display_sleep', [0]))
        self.assertIn(
            'Invalid Integer Value for Minutes',
            self.run_function('power.set_display_sleep', [181]))
        self.assertIn(
            'Invalid Boolean Value for Minutes',
            self.run_function('power.set_display_sleep', [True]))

    @destructiveTest
    def test_harddisk_sleep(self):
        '''
        Test power.get_harddisk_sleep
        Test power.set_harddisk_sleep
        '''

        # Normal Functionality
        self.assertTrue(self.run_function('power.set_harddisk_sleep', [90]))
        self.assertEqual(
            self.run_function('power.get_harddisk_sleep'), 'after 90 minutes')
        self.assertTrue(self.run_function('power.set_harddisk_sleep', ['Off']))
        self.assertEqual(self.run_function('power.get_harddisk_sleep'), 'Never')

        # Test invalid input
        self.assertIn(
            'Invalid String Value for Minutes',
            self.run_function('power.set_harddisk_sleep', ['spongebob']))
        self.assertIn(
            'Invalid Integer Value for Minutes',
            self.run_function('power.set_harddisk_sleep', [0]))
        self.assertIn(
            'Invalid Integer Value for Minutes',
            self.run_function('power.set_harddisk_sleep', [181]))
        self.assertIn(
            'Invalid Boolean Value for Minutes',
            self.run_function('power.set_harddisk_sleep', [True]))

    def test_wake_on_modem(self):
        '''
        Test power.get_wake_on_modem
        Test power.set_wake_on_modem
        '''
        # If available on this system, test it
        if self.WAKE_ON_MOD_AVAIL:
            self.assertTrue(
                    self.run_function('power.set_wake_on_modem', ['on']))
            self.assertTrue(self.run_function('power.get_wake_on_modem'))
            self.assertTrue(
                    self.run_function('power.set_wake_on_modem', ['off']))
            self.assertFalse(self.run_function('power.get_wake_on_modem'))
        else:
            # Check for failure if not a desktop
            ret = self.run_function('power.get_wake_on_modem')
            self.assertIn('Error', ret)

    def test_wake_on_network(self):
        '''
        Test power.get_wake_on_network
        Test power.set_wake_on_network
        '''
        # If available on this system, test it
        if self.WAKE_ON_NET_AVAIL:
            self.assertTrue(
                    self.run_function('power.set_wake_on_network', ['on']))
            self.assertTrue(self.run_function('power.get_wake_on_network'))
            self.assertTrue(
                    self.run_function('power.set_wake_on_network', ['off']))
            self.assertFalse(self.run_function('power.get_wake_on_network'))
        else:
            # Check for failure if not a desktop
            ret = self.run_function('power.get_wake_on_network')
            self.assertIn('Error', ret)

    def test_restart_power_failure(self):
        '''
        Test power.get_restart_power_failure
        Test power.set_restart_power_failure
        '''
        # If available on this system, test it
        if self.RESTART_POW_AVAIL:
            self.assertTrue(
                self.run_function('power.set_restart_power_failure', ['on']))
            self.assertTrue(
                self.run_function('power.get_restart_power_failure'))
            self.assertTrue(
                self.run_function('power.set_restart_power_failure', ['off']))
            self.assertFalse(
                self.run_function('power.get_restart_power_failure'))
        else:
            # Check for failure if not a desktop
            ret = self.run_function('power.get_restart_power_failure')
            self.assertIn('Error', ret)

    def test_restart_freeze(self):
        '''
        Test power.get_restart_freeze
        Test power.set_restart_freeze
        '''
        # Normal Functionality
        self.assertTrue(self.run_function('power.set_restart_freeze', ['on']))
        self.assertTrue(self.run_function('power.get_restart_freeze'))
        # This will return False because mac fails to actually make the change
        self.assertFalse(
	    self.run_function('power.set_restart_freeze', ['off']))
        # Even setting to off returns true, it actually is never set
        # This is an apple bug
        self.assertTrue(self.run_function('power.get_restart_freeze'))

    def test_sleep_on_power_button(self):
        '''
        Test power.get_sleep_on_power_button
        Test power.set_sleep_on_power_button
        '''
        # If available on this system, test it
        if self.SLEEP_ON_POW_AVAIL:
            self.assertTrue(
                self.run_function('power.set_sleep_on_power_button', ['on']))
            self.assertTrue(
                self.run_function('power.get_sleep_on_power_button'))
            self.assertTrue(
                self.run_function('power.set_sleep_on_power_button', ['off']))
            self.assertFalse(
                self.run_function('power.get_sleep_on_power_button'))
        else:
            ret = self.run_function('power.get_sleep_on_power_button')
            self.assertIn('Error', ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MacPowerModuleTest)
