"""
Tests for the spm remove utility
"""

import os
import shutil

import pytest

from tests.support.case import SPMCase


@pytest.mark.windows_whitelisted
@pytest.mark.destructive_test
class SPMRemoveTest(SPMCase):
    """
    Validate the spm remove command
    """

    def setUp(self):
        self.config = self._spm_config()
        self._spm_build_files(self.config)

    @pytest.mark.slow_test
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
