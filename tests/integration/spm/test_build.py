# -*- coding: utf-8 -*-
'''
Tests for the spm build utility
'''
# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import shutil

# Import Salt libs
import salt.utils.files
import salt.utils.path

# Import Salt Testing libs
from tests.support.case import SPMCase, ModuleCase
from tests.support.helpers import destructiveTest
from tests.support.unit import skipIf


@destructiveTest
class SPMBuildTest(SPMCase, ModuleCase):
    '''
    Validate the spm build command
    '''
    def setUp(self):
        self.config = self._spm_config()
        self._spm_build_files(self.config)

    def test_spm_build(self):
        '''
        test spm build
        '''
        self.run_spm('build', self.config, self.formula_dir)
        spm_file = os.path.join(self.config['spm_build_dir'], 'apache-201506-2.spm')
        # Make sure .spm file gets created
        self.assertTrue(os.path.exists(spm_file))
        # Make sure formula path dir is created
        self.assertTrue(os.path.isdir(self.config['formula_path']))

    @skipIf(salt.utils.path.which('fallocate') is None, 'fallocate not installed')
    def test_spm_build_big_file(self):
        '''
        test spm build with a big file
        '''
        # check to make sure there is enough space to run this test
        check_space = self.run_function('status.diskusage', ['/tmp'])
        space = check_space['/tmp']['available']
        if space < 3000000000:
            self.skipTest('Not enough space on host to run this test')

        self.run_function('cmd.run',
                          ['fallocate -l 1G {0}'.format(os.path.join(self.formula_sls_dir,
                                                                     'bigfile.txt'))])
        self.run_spm('build', self.config, self.formula_dir)
        spm_file = os.path.join(self.config['spm_build_dir'], 'apache-201506-2.spm')
        self.run_spm('install', self.config, spm_file)

        get_files = self.run_spm('files', self.config, 'apache')

        files = ['apache.sls', 'bigfile.txt']
        for sls in files:
            self.assertIn(sls, ' '.join(get_files))

    def test_spm_build_exclude(self):
        '''
        test spm build while excluding directory
        '''
        git_dir = os.path.join(self.formula_sls_dir, '.git')
        os.makedirs(git_dir)
        files = ['donotbuild1', 'donotbuild2', 'donotbuild3']

        for git_file in files:
            with salt.utils.files.fopen(os.path.join(git_dir, git_file), 'w') as fp:
                fp.write('Please do not include me in build')

        self.run_spm('build', self.config, self.formula_dir)
        spm_file = os.path.join(self.config['spm_build_dir'], 'apache-201506-2.spm')
        self.run_spm('install', self.config, spm_file)

        get_files = self.run_spm('files', self.config, 'apache')

        for git_file in files:
            self.assertNotIn(git_file, ' '.join(get_files))

    def tearDown(self):
        shutil.rmtree(self._tmp_spm)
