# -*- coding: utf-8 -*-
'''
Tests for the spm build utility
'''
# Import python libs
from __future__ import absolute_import
import os
import shutil

# Import Salt Testing libs
from tests.support.case import SPMCase
from tests.support.helpers import destructiveTest


@destructiveTest
class SPMBuildTest(SPMCase):
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
        build_spm = self.run_spm('build', self.config, self.formula_dir)
        spm_file = os.path.join(self.config['spm_build_dir'], 'apache-201506-2.spm')
        # Make sure .spm file gets created
        self.assertTrue(os.path.exists(spm_file))
        # Make sure formula path dir is created
        self.assertTrue(os.path.isdir(self.config['formula_path']))

    def tearDown(self):
        shutil.rmtree(self._tmp_spm)
