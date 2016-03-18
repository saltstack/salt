# -*- coding: utf-8 -*-
'''
integration tests for mac_power
'''

# Import python libs
from __future__ import absolute_import, print_function
import random
import string

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath, destructiveTest
from salt.ext.six.moves import range
ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils


def disabled(f):
    def _decorator(f):
        print('{0} has been disabled'.format(f.__name__))
    return _decorator(f)


def __random_string(size=6):
    '''
    Generates a random username
    '''
    return 'RS-' + ''.join(
        random.choice(string.ascii_uppercase + string.digits)
        for x in range(size)
    )


COMPUTER_SLEEP = 0
DISPLAY_SLEEP = 0
HARD_DISK_SLEEP = 0
WAKE_ON_MODEM = False
WAKE_ON_NET = False
RESTART_POWER = False
RESTART_FREEZE = False
SLEEP_ON_BUTTON = False


class MacPowerModuleTest(integration.ModuleCase):
    '''
    Validate the mac_power module
    '''

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

        COMPUTER_SLEEP = self.run_function('power.get_computer_sleep')
        DISPLAY_SLEEP = self.run_function('power.get_display_sleep')
        HARD_DISK_SLEEP = self.run_function('power.get_harddisk_sleep')
        WAKE_ON_MODEM = self.run_function('power.get_wake_on_modem')
        WAKE_ON_NET = self.run_function('power.get_wake_on_network')
        RESTART_POWER = self.run_function('power.get_restart_power_failure')
        RESTART_FREEZE = self.run_function('power.get_restart_freeze')
        SLEEP_ON_BUTTON = self.run_function('power.get_sleep_on_power_button')

    def tearDown(self):
        '''
        Reset to original settings
        '''
        self.run_function('power.set_computer_sleep', [COMPUTER_SLEEP])
        self.run_function('power.set_display_sleep', [DISPLAY_SLEEP])
        self.run_function('power.set_harddisk_sleep', [HARD_DISK_SLEEP])
        self.run_function('power.set_wake_on_modem', [WAKE_ON_MODEM])
        self.run_function('power.set_wake_on_network', [WAKE_ON_NET])
        self.run_function('power.set_restart_power_failure', [RESTART_POWER])
        self.run_function('power.set_restart_freeze', [RESTART_FREEZE])
        self.run_function('power.set_sleep_on_power_button', [SLEEP_ON_BUTTON])

    @destructiveTest
    def test_computer_sleep(self):
        '''
        Test power.get_computer_sleep
        Test power.set_computer_sleep
        '''

        # Normal Functionality
        self.assertTrue(self.run_function('power.set_computer_sleep', [90]))
        self.assertEqual(self.run_function('power.get_computer_sleep'), 90)
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
        self.assertEqual(self.run_function('power.get_display_sleep'), 90)
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

    def test_harddisk_sleep(self):
        '''
        Test power.get_harddisk_sleep
        Test power.set_harddisk_sleep
        '''

        # Normal Functionality
        self.assertTrue(self.run_function('power.set_harddisk_sleep', [90]))
        self.assertEqual(self.run_function('power.get_harddisk_sleep'), 90)
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

        Always returns 'Not supported on this machine'
        '''
        self.assertTrue(self.run_function('power.set_wake_on_modem', ['on']))
        self.assertTrue(self.run_function('power.set_wake_on_modem', ['on']))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MacPowerModuleTest)
