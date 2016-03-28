# -*- coding: utf-8 -*-
'''
integration tests for mac_power
'''

# Import python libs
from __future__ import absolute_import, print_function

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath, destructiveTest
ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils


def disabled(f):
    def _decorator(f):
        print('{0} has been disabled'.format(f.__name__))
    return _decorator(f)


class MacPowerModuleTest(integration.ModuleCase):
    '''
    Validate the mac_power module
    '''
    COMPUTER_SLEEP = 0
    DISPLAY_SLEEP = 0
    HARD_DISK_SLEEP = 0
    WAKE_ON_MODEM = False
    WAKE_ON_NET = False
    RESTART_POWER = False
    RESTART_FREEZE = False
    SLEEP_ON_BUTTON = False

    def setUp(self):
        '''
        Get current settings
        '''
        if not salt.utils.is_darwin():
            self.skipTest('Test only available on Mac OS X')

        if not salt.utils.which('systemsetup'):
            self.skipTest('Test requires systemsetup binary')

        if salt.utils.get_uid(salt.utils.get_user()) != 0:
            self.skipTest('Test requires root')

        self.COMPUTER_SLEEP = self.run_function('power.get_computer_sleep')
        self.DISPLAY_SLEEP = self.run_function('power.get_display_sleep')
        self.HARD_DISK_SLEEP = self.run_function('power.get_harddisk_sleep')
        self.WAKE_ON_MODEM = self.run_function('power.get_wake_on_modem')
        self.WAKE_ON_NET = self.run_function('power.get_wake_on_network')
        self.RESTART_POWER = self.run_function('power.get_restart_power_failure')
        self.RESTART_FREEZE = self.run_function('power.get_restart_freeze')
        self.SLEEP_ON_BUTTON = self.run_function('power.get_sleep_on_power_button')

    def tearDown(self):
        '''
        Reset to original settings
        '''
        self.run_function('power.set_computer_sleep', [self.COMPUTER_SLEEP])
        self.run_function('power.set_display_sleep', [self.DISPLAY_SLEEP])
        self.run_function('power.set_harddisk_sleep', [self.HARD_DISK_SLEEP])
        self.run_function('power.set_wake_on_modem', [self.WAKE_ON_MODEM])
        self.run_function('power.set_wake_on_network', [self.WAKE_ON_NET])
        self.run_function('power.set_restart_power_failure',
                          [self.RESTART_POWER])
        self.run_function('power.set_restart_freeze', [self.RESTART_FREEZE])
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

    @disabled
    def test_wake_on_modem(self):
        '''
        Test power.get_wake_on_modem
        Test power.set_wake_on_modem

        Commands don't seem to be supported on el capitan. Perhaps it works on
        OS X Server or older versions
        '''
        self.assertTrue(self.run_function('power.set_wake_on_modem', ['on']))
        self.assertTrue(self.run_function('power.get_wake_on_modem'))
        self.assertTrue(self.run_function('power.set_wake_on_modem', ['off']))
        self.assertFalse(self.run_function('power.get_wake_on_modem'))

    @disabled
    def test_wake_on_network(self):
        '''
        Test power.get_wake_on_network
        Test power.set_wake_on_network

        Commands don't seem to be supported on el capitan. Perhaps it works on
        OS X Server or older versions
        '''
        self.assertTrue(self.run_function('power.set_wake_on_network', ['on']))
        self.assertTrue(self.run_function('power.get_wake_on_network'))
        self.assertTrue(self.run_function('power.set_wake_on_network', ['off']))
        self.assertFalse(self.run_function('power.get_wake_on_network'))

    @disabled
    def test_restart_power_failure(self):
        '''
        Test power.get_restart_power_failure
        Test power.set_restart_power_failure

        Commands don't seem to be supported on el capitan. Perhaps it works on
        OS X Server or older versions
        '''
        self.assertTrue(
            self.run_function('power.set_restart_power_failure', ['on']))
        self.assertTrue(self.run_function('power.get_restart_power_failure'))
        self.assertTrue(
            self.run_function('power.set_restart_power_failure', ['off']))
        self.assertFalse(self.run_function('power.get_restart_power_failure'))

    @disabled
    def test_restart_freeze(self):
        '''
        Test power.get_restart_freeze
        Test power.set_restart_freeze

        Though the set command completes successfully, the setting isn't
        actually changed
        '''
        # Normal Functionality
        self.assertTrue(self.run_function('power.set_restart_freeze', ['on']))
        self.assertTrue(self.run_function('power.get_restart_freeze'))
        self.assertTrue(self.run_function('power.set_restart_freeze', ['off']))
        self.assertFalse(self.run_function('power.get_restart_freeze'))

    @disabled
    def test_sleep_on_power_button(self):
        '''
        Test power.get_sleep_on_power_button
        Test power.set_sleep_on_power_button

        Commands don't seem to be supported on el capitan. Perhaps it works on
        OS X Server or older versions
        '''
        # Normal Functionality
        self.assertTrue(
            self.run_function('power.set_sleep_on_power_button', ['on']))
        self.assertTrue(self.run_function('power.get_sleep_on_power_button'))
        self.assertTrue(
            self.run_function('power.set_sleep_on_power_button', ['off']))
        self.assertFalse(self.run_function('power.get_sleep_on_power_button'))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MacPowerModuleTest)
