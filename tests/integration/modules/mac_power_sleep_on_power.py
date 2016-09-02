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
class MacPowerModuleTestSleepOnPowerButton(integration.ModuleCase):
    '''
    Test power.get_sleep_on_power_button
    Test power.set_sleep_on_power_button
    '''
    SLEEP_ON_BUTTON = None

    def setup(self):
        '''
        Check if function is available
        Get existing value
        '''
        # Is the function available
        ret = self.run_function('power.get_sleep_on_power_button')
        if isinstance(ret, bool):
            self.SLEEP_ON_BUTTON = self.run_function(
                'power.get_sleep_on_power_button')

    def teardown(self):
        '''
        Reset to original value
        '''
        if self.SLEEP_ON_BUTTON is not None:
            self.run_function(
                'power.set_sleep_on_power_button', [self.SLEEP_ON_BUTTON])

    def test_sleep_on_power_button(self):
        '''
        Test power.get_sleep_on_power_button
        Test power.set_sleep_on_power_button
        '''
        # If available on this system, test it
        if self.SLEEP_ON_BUTTON is None:
            # Check for not available
            ret = self.run_function('power.get_sleep_on_power_button')
            self.assertIn('Error', ret)
        else:
            self.assertTrue(
                self.run_function('power.set_sleep_on_power_button', ['on']))
            self.assertTrue(
                self.run_function('power.get_sleep_on_power_button'))
            self.assertTrue(
                self.run_function('power.set_sleep_on_power_button', ['off']))
            self.assertFalse(
                self.run_function('power.get_sleep_on_power_button'))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MacPowerModuleTestSleepOnPowerButton)
