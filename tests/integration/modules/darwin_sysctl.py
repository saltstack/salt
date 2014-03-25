# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@satlstack.com>`
'''

# Import Python Libs
import os
import random

# Import Salt Libs
import integration
from salt.exceptions import CommandExecutionError

# Import Salt Testing Libs
from salttesting import skipIf
from salttesting.helpers import (
    destructiveTest,
    ensure_in_syspath,
    requires_system_grains
)
ensure_in_syspath('../../')

# Module Variables
ASSIGN_CMD = 'net.inet.icmp.icmplim'


class DarwinSysctlModuleTest(integration.ModuleCase):
    '''
    Integration tests for the darwin_sysctl module
    '''

    def setUp(self):
        '''
        Sets up the test requirements
        '''
        super(DarwinSysctlModuleTest, self).setUp()
        os_grain = self.run_function('grains.item', ['kernel'])
        if os_grain['kernel'] not in 'Darwin':
            self.skipTest(
                'Test not applicable to \'{kernel}\' kernel'.format(
                    **os_grain
                )
            )
        self.val = self.run_function('sysctl.get', [ASSIGN_CMD])

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'You must be logged in as root to run this test')
    @requires_system_grains
    def test_assign(self, grains=None):
        '''
        Tests assigning a single sysctl parameter
        '''
        try:
            rand = random.randint(0, 500)
            while rand == self.val:
                rand = random.randint(0, 500)
            self.run_function('sysctl.assign', [ASSIGN_CMD, rand])
            info = int(self.run_function('sysctl.get', [ASSIGN_CMD]))
            try:
                self.assertEqual(rand, info)
            except AssertionError:
                self.run_function('sysctl.assign', [ASSIGN_CMD, self.val])
                raise
        except CommandExecutionError:
            self.run_function('sysctl.assign', [ASSIGN_CMD, self.val])
            raise

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'You must be logged in as root to run this test')
    @requires_system_grains
    def tearDown(self, grains=None):
        '''
        Clean up after tests
        '''
        self.run_function('sysctl.assign', [ASSIGN_CMD, self.val])


if __name__ == '__main__':
    from integration import run_tests
    run_tests(DarwinSysctlModuleTest)
