# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.case import ShellCase


class SPMTest(ShellCase):
    '''
    Test spm script
    '''

    def test_spm_help(self):
        '''
        test --help argument for spm
        '''
        expected_args = ['--version', '--assume-yes', '--help']
        output = self.run_spm('--help')
        for arg in expected_args:
            self.assertIn(arg, ''.join(output))

    def test_spm_bad_arg(self):
        '''
        test correct output when bad argument passed
        '''
        expected_args = ['--version', '--assume-yes', '--help']
        output = self.run_spm('doesnotexist')
        for arg in expected_args:
            self.assertIn(arg, ''.join(output))
