# -*- coding: utf-8 -*-
'''
Integration tests for the mac_desktop execution module.
'''

# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Testing Libs
from tests.support.case import ModuleCase

# Import 3rd-party libs
import pytest
from salt.ext import six


@pytest.mark.destructive_test
@pytest.mark.skip_if_not_root
class MacDesktopTestCase(ModuleCase):
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

    def test_get_output_volume(self):
        '''
        Tests the return of get_output_volume.
        '''
        ret = self.run_function('desktop.get_output_volume')
        assert ret is not None

    def test_set_output_volume(self):
        '''
        Tests the return of set_output_volume.
        '''
        current_vol = self.run_function('desktop.get_output_volume')
        to_set = 10
        if current_vol == six.text_type(to_set):
            to_set += 2
        new_vol = self.run_function('desktop.set_output_volume',
                                    [six.text_type(to_set)])
        check_vol = self.run_function('desktop.get_output_volume')
        assert new_vol == check_vol

        # Set volume back to what it was before
        self.run_function('desktop.set_output_volume', [current_vol])

    def test_screensaver(self):
        '''
        Tests the return of the screensaver function.
        '''
        assert self.run_function('desktop.screensaver')

    def test_lock(self):
        '''
        Tests the return of the lock function.
        '''
        assert self.run_function('desktop.lock')

    def test_say(self):
        '''
        Tests the return of the say function.
        '''
        assert self.run_function('desktop.say', ['hello', 'world'])
