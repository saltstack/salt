# -*- coding: utf-8 -*-
'''
Integration tests for the mac_desktop execution module.
'''

# Import Python Libs
from __future__ import absolute_import
import os

# Import Salt Testing Libs
import tests.integration as integration
from tests.support.unit import skipIf
from tests.support.helpers import (
    destructiveTest,
    requires_system_grains
)


@skipIf(os.geteuid() != 0, 'You must be logged in as root to run this test')
class MacDesktopTestCase(integration.ModuleCase):
    '''
    Integration tests for the mac_desktop module.
    '''

    def setUp(self):
        '''
        Sets up test requirements.
        '''
        os_grain = self.run_function('grains.item', ['kernel'])
        if os_grain['kernel'] not in 'Darwin':
            self.skipTest(
                'Test not applicable to \'{kernel}\' kernel'.format(
                    **os_grain
                )
            )

    @requires_system_grains
    def test_get_output_volume(self, grains=None):
        '''
        Tests the return of get_output_volume.
        '''
        ret = self.run_function('desktop.get_output_volume')
        self.assertIsNotNone(ret)

    @destructiveTest
    @requires_system_grains
    def test_set_output_volume(self, grains=None):
        '''
        Tests the return of set_output_volume.
        '''
        current_vol = self.run_function('desktop.get_output_volume')
        to_set = 10
        if current_vol == str(to_set):
            to_set += 2
        new_vol = self.run_function('desktop.set_output_volume', [str(to_set)])
        check_vol = self.run_function('desktop.get_output_volume')
        self.assertEqual(new_vol, check_vol)

        # Set volume back to what it was before
        self.run_function('desktop.set_output_volume', [current_vol])

    @destructiveTest
    @requires_system_grains
    def test_screensaver(self, grains=None):
        '''
        Tests the return of the screensaver function.
        '''
        self.assertTrue(
            self.run_function('desktop.screensaver')
        )

    @destructiveTest
    @requires_system_grains
    def test_lock(self, grains=None):
        '''
        Tests the return of the lock function.
        '''
        self.assertTrue(
            self.run_function('desktop.lock')
        )

    @destructiveTest
    @requires_system_grains
    def test_say(self, grains=None):
        '''
        Tests the return of the say function.
        '''
        self.assertTrue(
            self.run_function('desktop.say', ['hello', 'world'])
        )
