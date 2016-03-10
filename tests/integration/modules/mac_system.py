# -*- coding: utf-8 -*-
'''
integration tests for mac_system
'''

# Import python libs
from __future__ import absolute_import
import random
import string

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath, destructiveTest
from salt.ext.six.moves import range
ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils

ATRUN_ENABLED = False
REMOTE_LOGIN_ENABLED = False
REMOTE_EVENTS_ENABLED = False
COMPUTER_NAME = ''
SUBNET_NAME = ''
KEYBOARD_DISABLED = False
SET_COMPUTER_NAME = __random_string()
SET_SUBNET_NAME = __random_string()


def __random_string(size=6):
    '''
    Generates a random username
    '''
    return 'RS-' + ''.join(
        random.choice(string.ascii_uppercase + string.digits)
        for x in range(size)
    )


class MacSystemModuleTest(integration.ModuleCase):
    '''
    Validate the mac_system module
    '''

    def setUp(self):
        '''
        Get current settings
        '''
        if not salt.utils.is_darwin():
            self.skipTest('Test only available on Mac OS X')

        if not salt.utils.which('systemsetup'):
            self.skipTest('Test requires systemsetup binary')

        if not salt.utils.which('launchctl'):
            self.skipTest('Test requires launchctl binary')

        if salt.utils.get_uid(salt.utils.get_user()) != 0:
            self.skipTest('Test requires root')

        ATRUN_ENABLED = self.run_function('service.enabled',
                                          ['com.apple.atrun'])
        REMOTE_LOGIN_ENABLED = self.run_function('system.get_remote_login')
        REMOTE_EVENTS_ENABLED = self.run_function('system.get_remote_events')
        COMPUTER_NAME = self.run_function('system.get_computer_name')
        SUBNET_NAME = self.run_function('system.get_subnet_name')
        KEYBOARD_DISABLED = self.run_function(
            'system.get_disable_keyboard_on_lock')

        super(MacSystemModuleTest, self).setUp()

    def tearDown(self):
        '''
        Reset to original settings
        '''
        if not ATRUN_ENABLED:
            atrun = '/System/Library/LaunchDaemons/com.apple.atrun.plist'
            self.run_function('service.stop', [atrun])

        self.run_function('system.set_remote_login', [REMOTE_LOGIN_ENABLED])
        self.run_function('system.set_remote_events', [REMOTE_EVENTS_ENABLED])
        self.run_function('system.set_computer_name', [COMPUTER_NAME])
        self.run_function('system.set_subnet_name', [SUBNET_NAME])
        self.run_function('system.set_disable_keyboard_on_lock',
                          [KEYBOARD_DISABLED])

        super(MacSystemModuleTest, self).tearDown()

    @destructiveTest
    def test_get_set_remote_login(self):
        '''
        Test system.get_remote_login
        Test system.set_remote_login
        '''
        self.run_function('system.set_remote_login', [True])
        self.assertTrue(self.run_function('system.get_remote_login'))
        self.run_function('system.set_remote_login', [False])
        self.assertFalse(self.run_function('system.get_remote_login'))

    @destructiveTest
    def test_get_set_remote_events(self):
        '''
        Test system.get_remote_events
        Test system.set_remote_events
        '''
        self.run_function('system.set_remote_events', [True])
        self.assertTrue(self.run_function('system.get_remote_events'))
        self.run_function('system.set_remote_events', [False])
        self.assertFalse(self.run_function('system.get_remote_events'))

    @destructiveTest
    def test_get_set_computer_name(self):
        '''
        Test system.get_computer_name
        Test system.set_computer_name
        '''
        self.run_function('system.set_computer_name', [SET_COMPUTER_NAME])
        self.assertEqual(
            self.run_function('system.get_computer_name'),
            SET_COMPUTER_NAME
        )

    @destructiveTest
    def test_get_set_subnet_name(self):
        '''
        Test system.get_subnet_name
        Test system.set_subnet_name
        '''
        self.run_function('system.set_subnet_name', [SET_SUBNET_NAME])
        self.assertEqual(
            self.run_function('system.get_subnet_name'),
            SET_SUBNET_NAME
        )

    def test_get_list_startup_disk(self):
        '''
        Test system.get_startup_disk
        Test system.list_startup_disks
        Don't know how to test system.set_startup_disk as there's usually only
        one startup disk available on a system
        '''
        ret = self.run_function('system.list_startup_disks')
        self.assertIn(self.run_function('system.get_startup_disk'), ret)

    def test_get_set_restart_delay(self):
        '''
        Test system.get_restart_delay
        Test system.set_restart_delay
        system.set_restart_delay does not work due to an apple bug, see docs
        may need to disable this test as we can't control the delay value
        '''
        self.assertEqual(
            self.run_function('system.get_restart_delay'),
            '0 seconds'
        )

    def test_get_set_disable_keyboard_on_lock(self):
        '''
        Test system.get_disable_keyboard_on_lock
        Test system.set_disable_keyboard_on_lock
        '''
        self.run_function('system.set_disable_keyboard_on_lock', [True])
        self.assertTrue(
            self.run_function('system.get_disable_keyboard_on_lock')
        )

        self.run_function('system.set_disable_keyboard_on_lock', [False])
        self.assertFalse(
            self.run_function('system.get_disable_keyboard_on_lock')
        )

    def test_get_set_boot_arch(self):
        '''
        Test system.get_boot_arch
        Test system.set_boot_arch
        system.set_boot_arch does not work du to an apple but, see docs
        may need to disable this test as we can't set the boot architecture
        '''
        self.assertEqual(self.run_function('system.get_boot_arch'), 'default')


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MacSystemModuleTest)
