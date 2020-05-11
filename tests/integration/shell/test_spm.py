# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import os

# Import Salt Testing libs
from tests.support.case import ShellCase, SPMCase


class SPMTest(ShellCase, SPMCase):
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

    def test_spm_assume_yes(self):
        '''
        test spm install with -y arg
        '''
        config = self._spm_config(assume_yes=False)
        self._spm_build_files(config)

        spm_file = os.path.join(config['spm_build_dir'],
                                'apache-201506-2.spm')

        build = self.run_spm('build {0} -c {1}'.format(self.formula_dir,
                                                       self._tmp_spm))

        install = self.run_spm('install {0} -c {1} -y'.format(spm_file,
                                                           self._tmp_spm))

        self.assertTrue(os.path.exists(os.path.join(config['formula_path'],
                                                    'apache', 'apache.sls')))

    def test_spm_force(self):
        '''
        test spm install with -f arg
        '''
        config = self._spm_config(assume_yes=False)
        self._spm_build_files(config)

        spm_file = os.path.join(config['spm_build_dir'],
                                'apache-201506-2.spm')

        build = self.run_spm('build {0} -c {1}'.format(self.formula_dir,
                                                       self._tmp_spm))

        install = self.run_spm('install {0} -c {1} -y'.format(spm_file,
                                                           self._tmp_spm))

        self.assertTrue(os.path.exists(os.path.join(config['formula_path'],
                                                    'apache', 'apache.sls')))

        # check if it forces the install after its already been installed it
        install = self.run_spm('install {0} -c {1} -y -f'.format(spm_file,
                                                           self._tmp_spm))

        self.assertEqual(['... installing apache'], install)
