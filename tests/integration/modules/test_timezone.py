# -*- coding: utf-8 -*-
'''
Integration tests for timezone module

Linux and Solaris are supported
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

try:
    import tzlocal  # pylint: disable=unused-import
    HAS_TZLOCAL = True
except ImportError:
    HAS_TZLOCAL = False

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.helpers import destructiveTest
from tests.support.unit import skipIf

# Import salt libs
import salt.utils.platform


class TimezoneLinuxModuleTest(ModuleCase):
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


class TimezoneSolarisModuleTest(ModuleCase):
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


@skipIf(not salt.utils.platform.is_windows(), 'windows test only')
class TimezoneWindowsModuleTest(ModuleCase):
    def setUp(self):
        self.pre = self.run_function('timezone.get_zone')

    def tearDown(self):
        post = self.run_function('timezone.get_zone')
        if self.pre != post:
            self.run_function('timezone.set_zone', [self.pre])

    def test_get_hwclock(self):
        timescale = ['UTC', 'localtime']
        ret = self.run_function('timezone.get_hwclock')
        self.assertIn(ret, timescale)

    @destructiveTest
    def test_get_zone(self):
        '''
        test timezone.set_zone, get_zone and zone_compare
        '''

        zone = 'America/Inuvik' if not HAS_TZLOCAL else 'America/Denver'

        # first set the zone
        assert self.run_function('timezone.set_zone', [zone])

        # check it set the correct zone
        ret = self.run_function('timezone.get_zone')
        assert zone in ret

        # compare zones
        assert self.run_function('timezone.zone_compare', [zone])

    def test_get_offset(self):
        '''
        test timezone.get_offset
        '''
        ret = self.run_function('timezone.get_offset')
        self.assertIn('-', ret)
