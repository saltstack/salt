"""
Tests for the spm repo
"""

import os
import shutil

import pytest

from tests.support.case import SPMCase


@pytest.mark.windows_whitelisted
@pytest.mark.destructive_test
class SPMRepoTest(SPMCase):
    """
    Validate commands related to spm repo
    """

    def setUp(self):
        self.config = self._spm_config()
        self._spm_build_files(self.config)

    def test_spm_create_update_repo(self):
        """
        test spm create_repo
        """
        self._spm_create_update_repo(self.config)

        self.assertTrue(os.path.exists(self.config["spm_db"]))

        l_repo_file = os.path.join(self.config["spm_cache_dir"], "local_repo.p")
        self.assertTrue(os.path.exists(l_repo_file))

    def tearDown(self):
        shutil.rmtree(self._tmp_spm)
