# -*- coding: utf-8 -*-
'''
Integration tests for timezone module

Only Linux is supported for the mement
'''

# Import python libs
from __future__ import absolute_import

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration


class TimezoneModuleTest(integration.ModuleCase):
    def setUp(self):
        '''
        Set up Linux test environment
        '''
        ret_grain = self.run_function('grains.item', ['kernel'])
        if 'Linux' not in ret_grain['kernel']:
            self.skipTest('For Linux only')
        super(TimezoneModuleTest, self).setUp()

    def test_get_hwclock(self):
        timezone = ['UTC', 'localtime']
        ret = self.run_function('timezone.get_hwclock')
        self.assertIn(ret, timezone)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(TimezoneModuleTest)
