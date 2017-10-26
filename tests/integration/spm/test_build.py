# -*- coding: utf-8 -*-
'''
Tests for the spm build utility
'''
# Import python libs
from __future__ import absolute_import
import os
import shutil
import textwrap

# Import Salt Testing libs
from tests.support.case import SPMCase, ModuleCase
from tests.support.helpers import destructiveTest
from tests.support.unit import skipIf

# Import Salt Libraries
import salt.utils


@destructiveTest
class SPMBuildTest(SPMCase, ModuleCase):
    '''
    Validate the spm build command
    '''
    def setUp(self):
        self.config = self._spm_config()
        self.formula_dir = os.path.join(' '.join(self.config['file_roots']['base']), 'formulas')
        self.formula_sls_dir = os.path.join(self.formula_dir, 'apache')
        self.formula_sls = os.path.join(self.formula_sls_dir, 'apache.sls')
        self.formula_file = os.path.join(self.formula_dir, 'FORMULA')

        dirs = [self.formula_dir, self.formula_sls_dir]
        for formula_dir in dirs:
            os.makedirs(formula_dir)

        with salt.utils.fopen(self.formula_sls, 'w') as fp:
            fp.write(textwrap.dedent('''\
                     install-apache:
                       pkg.installed:
                         - name: apache2
                     '''))

        with salt.utils.fopen(self.formula_file, 'w') as fp:
            fp.write(textwrap.dedent('''\
                     name: apache
                     os: RedHat, Debian, Ubuntu, Suse, FreeBSD
                     os_family: RedHat, Debian, Suse, FreeBSD
                     version: 201506
                     release: 2
                     summary: Formula for installing Apache
                     description: Formula for installing Apache
                     '''))

    def test_spm_build(self):
        '''
        test spm build
        '''
        build_spm = self.run_spm('build', self.config, self.formula_dir)
        spm_file = os.path.join(self.config['spm_build_dir'], 'apache-201506-2.spm')
        # Make sure .spm file gets created
        self.assertTrue(os.path.exists(spm_file))
        # Make sure formula path dir is created
        self.assertTrue(os.path.isdir(self.config['formula_path']))

    @skipIf(salt.utils.which('fallocate') is None, 'fallocate not installed')
    def test_spm_build_big_file(self):
        '''
        test spm build
        '''
        big_file = self.run_function('cmd.run',
                                     ['fallocate -l 1G {0}'.format(os.path.join(self.formula_sls_dir,
                                                                              'bigfile.txt'))])
        build_spm = self.run_spm('build', self.config, self.formula_dir)
        spm_file = os.path.join(self.config['spm_build_dir'], 'apache-201506-2.spm')
        install = self.run_spm('install', self.config, spm_file)

        get_files = self.run_spm('files', self.config, 'apache')

        files = ['apache.sls', 'bigfile.txt']
        for sls in files:
            self.assertIn(sls, ' '.join(get_files))

    def test_spm_build_exclude(self):
        '''
        test spm build
        '''
        git_dir = os.path.join(self.formula_sls_dir, '.git')
        os.makedirs(git_dir)
        files = ['donotbuild1', 'donotbuild2', 'donotbuild3']

        for git_file in files:
            with salt.utils.fopen(os.path.join(git_dir, git_file), 'w') as fp:
                fp.write('Please do not include me in build')

        build_spm = self.run_spm('build', self.config, self.formula_dir)
        spm_file = os.path.join(self.config['spm_build_dir'], 'apache-201506-2.spm')
        install = self.run_spm('install', self.config, spm_file)

        get_files = self.run_spm('files', self.config, 'apache')

        for git_file in files:
            self.assertNotIn(git_file, ' '.join(get_files))

    def tearDown(self):
        shutil.rmtree(self._tmp_spm)
