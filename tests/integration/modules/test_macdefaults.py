# -*- coding: utf-8 -*-
'''
Validate the mac-defaults module
'''

# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function

import pytest

# Import Salt Testing Libs
from tests.support.case import ModuleCase

DEFAULT_DOMAIN = 'com.apple.AppleMultitouchMouse'
DEFAULT_KEY = 'MouseHorizontalScroll'
DEFAULT_VALUE = '0'


@pytest.mark.destructive_test
@pytest.mark.skip_if_not_root
class MacDefaultsModuleTest(ModuleCase):
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

    def test_macdefaults_write_read(self):
        '''
        Tests that writes and reads macdefaults
        '''
        write_domain = self.run_function('macdefaults.write',
                                         [DEFAULT_DOMAIN,
                                          DEFAULT_KEY,
                                          DEFAULT_VALUE])
        assert write_domain

        read_domain = self.run_function('macdefaults.read',
                                        [DEFAULT_DOMAIN,
                                         DEFAULT_KEY])
        assert read_domain
        assert read_domain == DEFAULT_VALUE
