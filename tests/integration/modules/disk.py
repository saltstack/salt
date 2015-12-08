# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
import os
import shutil

# Import Salt Testing libs
from salttesting import skipIf
from salttesting.helpers import (ensure_in_syspath, destructiveTest)
ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils

# Import 3rd-party libs
import salt.ext.six as six


class DiskModuleVirtualizationTest(integration.ModuleCase):
    '''
    Test to make sure we return a clean result under Docker. Refs #8976

    This is factored into its own class so that we can have some certainty that setUp() and tearDown() are run.
    '''
    @destructiveTest
    @skipIf(salt.utils.is_windows(), 'No mtab on Windows')
    def setUp(self):
        # Make /etc/mtab unreadable
        if os.path.isfile('/etc/mtab'):
            shutil.move('/etc/mtab', '/tmp/mtab')

    @destructiveTest
    @skipIf(salt.utils.is_windows(), 'No mtab on Windows')
    def test_no_mtab(self):
        ret = self.run_function('disk.usage')
        self.assertDictEqual(ret, {})

    @destructiveTest
    @skipIf(salt.utils.is_windows(), 'No mtab on Windows')
    def tearDown(self):
        if os.path.isfile('/tmp/mtab'):
            shutil.move('/tmp/mtab', '/etc/mtab')


class DiskModuleTest(integration.ModuleCase):
    '''
    Validate the disk module
    '''
    def test_usage(self):
        '''
        disk.usage
        '''
        ret = self.run_function('disk.usage')
        self.assertTrue(isinstance(ret, dict))
        if not isinstance(ret, dict):
            return
        for key, val in six.iteritems(ret):
            self.assertTrue('filesystem' in val)
            self.assertTrue('1K-blocks' in val)
            self.assertTrue('used' in val)
            self.assertTrue('available' in val)
            self.assertTrue('capacity' in val)

    def test_inodeusage(self):
        '''
        disk.inodeusage
        '''
        ret = self.run_function('disk.inodeusage')
        self.assertTrue(isinstance(ret, dict))
        if not isinstance(ret, dict):
            return
        for key, val in six.iteritems(ret):
            self.assertTrue('inodes' in val)
            self.assertTrue('used' in val)
            self.assertTrue('free' in val)
            self.assertTrue('use' in val)
            self.assertTrue('filesystem' in val)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(DiskModuleTest)
