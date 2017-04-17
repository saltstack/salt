# -*- coding: utf-8 -*-
'''
Validate the mac-defaults module
'''

# Import Python Libs
from __future__ import absolute_import
import os

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

DEFAULT_DOMAIN = 'com.apple.AppleMultitouchMouse'
DEFAULT_KEY = 'MouseHorizontalScroll'
DEFAULT_VALUE = '0'


class MacDefaultsModuleTest(integration.ModuleCase):
    '''
    Integration tests for the mac_default module
    '''
    def setUp(self):
        '''
        Sets up the test requirements
        '''
        os_grain = self.run_function('grains.item', ['kernel'])
        # Must be running on a mac
        if os_grain['kernel'] not in 'Darwin':
            self.skipTest(
                'Test not applicable to \'{kernel}\' kernel'.format(
                    **os_grain
                )
            )

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'You must be logged in as root to run this test')
    @requires_system_grains
    def test_macdefaults_write_read(self, grains=None):
        '''
        Tests that writes and reads macdefaults
        '''
        write_domain = self.run_function('macdefaults.write',
                                         [DEFAULT_DOMAIN,
                                          DEFAULT_KEY,
                                          DEFAULT_VALUE])
        self.assertTrue(write_domain)

        read_domain = self.run_function('macdefaults.read',
                                        [DEFAULT_DOMAIN,
                                         DEFAULT_KEY])
        self.assertTrue(read_domain)
        self.assertEqual(read_domain, DEFAULT_VALUE)

if __name__ == '__main__':
    from integration import run_tests
    run_tests(MacDefaultsModuleTest)
