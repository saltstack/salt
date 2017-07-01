# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
import os
import shutil

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.unit import skipIf
from tests.support.helpers import destructiveTest

# Import salt libs
import salt.utils

# Import 3rd-party libs
import salt.ext.six as six


@destructiveTest
@skipIf(salt.utils.is_windows(), 'No mtab on Windows')
@skipIf(salt.utils.is_darwin(), 'No mtab on Darwin')
class DiskModuleVirtualizationTest(ModuleCase):
    '''
    Test to make sure we return a clean result under Docker. Refs #8976

    This is factored into its own class so that we can have some certainty that setUp() and tearDown() are run.
    '''
    def setUp(self):
        # Make /etc/mtab unreadable
        if os.path.isfile('/etc/mtab'):
            shutil.move('/etc/mtab', '/tmp/mtab')

    def test_no_mtab(self):
        ret = self.run_function('disk.usage')
        self.assertDictEqual(ret, {})

    def tearDown(self):
        if os.path.isfile('/tmp/mtab'):
            shutil.move('/tmp/mtab', '/etc/mtab')


class DiskModuleTest(ModuleCase):
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
        if salt.utils.is_darwin():
            for key, val in six.iteritems(ret):
                self.assertTrue('filesystem' in val)
                self.assertTrue('512-blocks' in val)
                self.assertTrue('used' in val)
                self.assertTrue('available' in val)
                self.assertTrue('capacity' in val)
                self.assertTrue('iused' in val)
                self.assertTrue('ifree' in val)
                self.assertTrue('%iused' in val)
        else:
            for key, val in six.iteritems(ret):
                self.assertTrue('filesystem' in val)
                self.assertTrue('1K-blocks' in val)
                self.assertTrue('used' in val)
                self.assertTrue('available' in val)
                self.assertTrue('capacity' in val)

    @skipIf(salt.utils.is_windows(), 'inode info not available on Windows')
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
