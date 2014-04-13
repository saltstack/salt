# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''

# Import Python Libs
import os
import random
import string

# Import Salt Testing Libs
from salttesting import skipIf
from salttesting.helpers import (
    destructiveTest,
    ensure_in_syspath,
    requires_system_grains
)
ensure_in_syspath('../../')

# Import Salt Libs
import integration
from salt.exceptions import CommandExecutionError


def __random_string(size=6):
    '''
    Generates a random username
    '''
    return 'RS-' + ''.join(
        random.choice(string.ascii_uppercase + string.digits)
        for x in range(size)
    )

# Create user strings for tests
ADD_USER = __random_string()
DEL_USER = __random_string()
CHANGE_USER = __random_string()


class MacUserModuleTest(integration.ModuleCase):
    '''
    Integration tests for the mac_user module
    '''

    def setUp(self):
        '''
        Sets up test requirements
        '''
        super(MacUserModuleTest, self).setUp()
        os_grain = self.run_function('grains.item', ['kernel'])
        if os_grain['kernel'] not in 'Darwin':
            self.skipTest(
                'Test not applicable to \'{kernel}\' kernel'.format(
                    **os_grain
                )
            )

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'You must be logged in as root to run this test')
    @requires_system_grains
    def test_mac_user_add(self, grains=None):
        '''
        Tests the add function
        '''
        try:
            self.run_function('user.add', [ADD_USER])
            user_info = self.run_function('user.info', [ADD_USER])
            self.assertEqual(ADD_USER, user_info['name'])
        except CommandExecutionError:
            self.run_function('user.delete', [ADD_USER])
            raise

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'You must be logged in as root to run this test')
    @requires_system_grains
    def test_mac_user_delete(self, grains=None):
        '''
        Tests the delete function
        '''

        # Create a user to delete - If unsuccessful, skip the test
        if self.run_function('user.add', [DEL_USER]) is not True:
            self.run_function('user.delete', [DEL_USER])
            self.skipTest('Failed to create a user to delete')

        try:
            # Now try to delete the added user
            ret = self.run_function('user.delete', [DEL_USER])
            self.assertTrue(ret)
        except CommandExecutionError:
            raise

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'You must be logged in as root to run this test')
    @requires_system_grains
    def test_mac_user_changes(self, grains=None):
        '''
        Tests mac_user functions that change user properties
        '''
        # Create a user to manipulate - if unsuccessful, skip the test
        if self.run_function('user.add', [CHANGE_USER]) is not True:
            self.run_function('user.delete', [CHANGE_USER])
            self.skipTest('Failed to create a user')

        try:
            # Test mac_user.chudi
            self.run_function('user.chuid', [CHANGE_USER, 4376])
            uid_info = self.run_function('user.info', [CHANGE_USER])
            self.assertEqual(uid_info['uid'], 4376)

            # Test mac_user.chgid
            self.run_function('user.chgid', [CHANGE_USER, 4376])
            gid_info = self.run_function('user.info', [CHANGE_USER])
            self.assertEqual(gid_info['gid'], 4376)

            # Test mac.user.chshell
            self.run_function('user.chshell', [CHANGE_USER, '/bin/zsh'])
            shell_info = self.run_function('user.info', [CHANGE_USER])
            self.assertEqual(shell_info['shell'], '/bin/zsh')

            # Test mac_user.chhome
            self.run_function('user.chhome', [CHANGE_USER, '/Users/foo'])
            home_info = self.run_function('user.info', [CHANGE_USER])
            self.assertEqual(home_info['home'], '/Users/foo')

            # Test mac_user.chfullname
            self.run_function('user.chfullname', [CHANGE_USER, 'Foo Bar'])
            fullname_info = self.run_function('user.info', [CHANGE_USER])
            self.assertEqual(fullname_info['fullname'], 'Foo Bar')

            # Test mac_user.chgroups
            self.run_function('user.chgroups', [CHANGE_USER, 'wheel'])
            groups_info = self.run_function('user.info', [CHANGE_USER])
            self.assertEqual(groups_info['groups'], ['wheel'])

        except AssertionError:
            self.run_function('user.delete', [CHANGE_USER])
            raise

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'You must be logged in as root to run this test')
    @requires_system_grains
    def tearDown(self, grains=None):
        '''
        Clean up after tests
        '''

        # Delete ADD_USER
        add_info = self.run_function('user.info', [ADD_USER])
        if add_info:
            self.run_function('user.delete', [ADD_USER])

        # Delete DEL_USER if something failed
        del_info = self.run_function('user.info', [DEL_USER])
        if del_info:
            self.run_function('user.delete', [DEL_USER])

        # Delete CHANGE_USER
        change_info = self.run_function('user.info', [CHANGE_USER])
        if change_info:
            self.run_function('user.delete', [CHANGE_USER])


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MacUserModuleTest)
