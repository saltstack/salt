# -*- coding: utf-8 -*-
"""
Tests for the spm remove utility
"""
from __future__ import absolute_import, print_function, unicode_literals

import os
import shutil

import pytest
from tests.support.case import SPMCase
from tests.support.helpers import destructiveTest, slowTest


@destructiveTest
@pytest.mark.windows_whitelisted
class SPMRemoveTest(SPMCase):
    """
    Validate the spm remove command
    """

    def setUp(self):
        self.config = self._spm_config()
        self._spm_build_files(self.config)

    @slowTest
    def test_spm_remove(self):
        """
        test spm remove from an inital repo install
        """
        # first install apache package
        self._spm_create_update_repo(self.config)
        install = self.run_spm("install", self.config, "apache")

        sls = os.path.join(self.config["formula_path"], "apache", "apache.sls")

        self.assertTrue(os.path.exists(sls))

        # now remove an make sure file is removed
        remove = self.run_spm("remove", self.config, "apache")
        sls = os.path.join(self.config["formula_path"], "apache", "apache.sls")

        self.assertFalse(os.path.exists(sls))

        self.assertIn("... removing apache", remove)

    def tearDown(self):
        shutil.rmtree(self._tmp_spm)
