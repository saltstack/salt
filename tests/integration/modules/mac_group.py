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

# Create group name strings for tests
ADD_GROUP = __random_string()


class MacGroupModuleTest(integration.ModuleCase):
    '''
    Integration tests for the mac_group module
    '''

    def setUp(self):
        '''
        Sets up test requirements
        '''
        super(MacGroupModuleTest, self).setUp()
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
        print "In Add"
        print "Add Group"
        print ADD_GROUP
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
    def tearDown(self, grains=None):
        '''
        Clean up after tests
        '''
        # Delete the added group
        add_info = self.run_function('group.info', [ADD_GROUP])
        if add_info:
            self.run_function('group.delete', [ADD_GROUP])


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MacGroupModuleTest)
