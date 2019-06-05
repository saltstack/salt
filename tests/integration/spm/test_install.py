# -*- coding: utf-8 -*-
'''
Tests for the spm install utility
'''
# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import shutil

# Import Salt Testing libs
from tests.support.case import SPMCase
from tests.support.helpers import destructiveTest


@destructiveTest
class SPMInstallTest(SPMCase):
    '''
    Validate the spm install command
    '''
    def setUp(self):
        self.config = self._spm_config()
        self._spm_build_files(self.config)

    def test_spm_install_local_dir(self):
        '''
        test spm install from local directory
        '''
        build_spm = self.run_spm('build', self.config, self.formula_dir)
        spm_file = os.path.join(self.config['spm_build_dir'],
                                'apache-201506-2.spm')

        install = self.run_spm('install', self.config, spm_file)

        sls = os.path.join(self.config['formula_path'], 'apache', 'apache.sls')

        self.assertTrue(os.path.exists(sls))

    def test_spm_install_from_repo(self):
        '''
        test spm install from repo
        '''
        self._spm_create_update_repo(self.config)
        install = self.run_spm('install', self.config, 'apache')

        sls = os.path.join(self.config['formula_path'], 'apache', 'apache.sls')

        self.assertTrue(os.path.exists(sls))

    def tearDown(self):
        shutil.rmtree(self._tmp_spm)
