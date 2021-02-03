"""
Tests for the spm files utility
"""

import os
import shutil

import pytest
from tests.support.case import SPMCase


@pytest.mark.windows_whitelisted
@pytest.mark.destructive_test
class SPMFilesTest(SPMCase):
    """
    Validate the spm files command
    """

    def setUp(self):
        self.config = self._spm_config()
        self._spm_build_files(self.config)

    @pytest.mark.slow_test
    def test_spm_files(self):
        """
        test spm files
        """
        self._spm_create_update_repo(self.config)
        install = self.run_spm("install", self.config, "apache")
        get_files = self.run_spm("files", self.config, "apache")

        os.path.exists(
            os.path.join(self.config["formula_path"], "apache", "apache.sls")
        )

    def tearDown(self):
        shutil.rmtree(self._tmp_spm)
