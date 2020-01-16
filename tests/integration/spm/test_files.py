# -*- coding: utf-8 -*-
'''
Tests for the spm files utility
'''
# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import shutil

import pytest

# Import Salt Testing libs
from tests.support.case import SPMCase


@pytest.mark.destructive_test
@pytest.mark.windows_whitelisted
class SPMFilesTest(SPMCase):
    '''
    Validate the spm files command
    '''
    def setUp(self):
        self.config = self._spm_config()
        self._spm_build_files(self.config)

    def test_spm_files(self):
        '''
        test spm files
        '''
        self._spm_create_update_repo(self.config)
        install = self.run_spm('install', self.config, 'apache')
        get_files = self.run_spm('files', self.config, 'apache')

        os.path.exists(os.path.join(self.config['formula_path'], 'apache',
                                    'apache.sls'))

    def tearDown(self):
        shutil.rmtree(self._tmp_spm)
