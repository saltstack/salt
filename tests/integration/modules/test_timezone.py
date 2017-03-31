# -*- coding: utf-8 -*-
'''
Integration tests for timezone module

Linux and Solaris are supported
'''

# Import python libs
from __future__ import absolute_import

# Import Salt Testing libs
import tests.integration as integration


class TimezoneLinuxModuleTest(integration.ModuleCase):
    def setUp(self):
        '''
        Set up Linux test environment
        '''
        ret_grain = self.run_function('grains.item', ['kernel'])
        if 'Linux' not in ret_grain['kernel']:
            self.skipTest('For Linux only')
        super(TimezoneLinuxModuleTest, self).setUp()

    def test_get_hwclock(self):
        timescale = ['UTC', 'localtime']
        ret = self.run_function('timezone.get_hwclock')
        self.assertIn(ret, timescale)


class TimezoneSolarisModuleTest(integration.ModuleCase):
    def setUp(self):
        '''
        Set up Solaris test environment
        '''
        ret_grain = self.run_function('grains.item', ['os_family'])
        if 'Solaris' not in ret_grain['os_family']:
            self.skipTest('For Solaris only')
        super(TimezoneSolarisModuleTest, self).setUp()

    def test_get_hwclock(self):
        timescale = ['UTC', 'localtime']
        ret = self.run_function('timezone.get_hwclock')
        self.assertIn(ret, timescale)
