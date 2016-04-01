# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import
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

# Import 3rd-party libs
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin


def __random_string(size=6):
    '''
    Generates a random username
    '''
    return 'RS-' + ''.join(
        random.choice(string.ascii_uppercase + string.digits)
        for x in range(size)
    )

# Create group name strings for tests
ADD_GROUP = __random_string()
DEL_GROUP = __random_string()
CHANGE_GROUP = __random_string()


class MacGroupModuleTest(integration.ModuleCase):
    '''
    Integration tests for the mac_group module
    '''

    def setUp(self):
        '''
        Sets up test requirements
        '''
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
    def test_mac_group_add(self, grains=None):
        '''
        Tests the add group function
        '''
        try:
            self.run_function('group.add', [ADD_GROUP, 3456])
            group_info = self.run_function('group.info', [ADD_GROUP])
            self.assertEqual(group_info['name'], ADD_GROUP)
        except CommandExecutionError:
            self.run_function('group.delete', [ADD_GROUP])
            raise

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'You must be logged in as root to run this test')
    @requires_system_grains
    def test_mac_group_delete(self, grains=None):
        '''
        Tests the delete group function
        '''
        # Create a group to delete - If unsuccessful, skip the test
        if self.run_function('group.add', [DEL_GROUP, 4567]) is not True:
            self.run_function('group.delete', [DEL_GROUP])
            self.skipTest('Failed to create a group to delete')

        try:
            # Now try to delete the added group
            ret = self.run_function('group.delete', [DEL_GROUP])
            self.assertTrue(ret)
        except CommandExecutionError:
            raise

    @destructiveTest
    @skipIf(os.getuid() != 0, 'You must be logged in as root to run this test')
    @requires_system_grains
    def test_mac_group_chgid(self, grains=None):
        '''
        Tests changing the group id
        '''
        # Create a group to delete - If unsuccessful, skip the test
        if self.run_function('group.add', [CHANGE_GROUP, 5678]) is not True:
            self.run_function('group.delete', [CHANGE_GROUP])
            self.skipTest('Failed to create a group to manipulate')

        try:
            self.run_function('group.chgid', [CHANGE_GROUP, 6789])
            group_info = self.run_function('group.info', [CHANGE_GROUP])
            self.assertEqual(group_info['gid'], 6789)
        except AssertionError:
            self.run_function('group.delete', [CHANGE_GROUP])
            raise

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'You must be logged in as root to run this test')
    @requires_system_grains
    def tearDown(self, grains=None):
        '''
        Clean up after tests
        '''
        # Delete ADD_GROUP
        add_info = self.run_function('group.info', [ADD_GROUP])
        if add_info:
            self.run_function('group.delete', [ADD_GROUP])

        # Delete DEL_GROUP if something failed
        del_info = self.run_function('group.info', [DEL_GROUP])
        if del_info:
            self.run_function('group.delete', [DEL_GROUP])

        # Delete CHANGE_GROUP
        change_info = self.run_function('group.info', [CHANGE_GROUP])
        if change_info:
            self.run_function('group.delete', [CHANGE_GROUP])


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MacGroupModuleTest)
