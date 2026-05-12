"""
Tests for the spm info utility
"""

import shutil

import pytest

from tests.support.case import SPMCase


@pytest.mark.windows_whitelisted
@pytest.mark.destructive_test
class SPMInfoTest(SPMCase):
    """
    Validate the spm info command
    """

    def setUp(self):
        self.config = self._spm_config()
        self._spm_build_files(self.config)

    @pytest.mark.slow_test
    def test_spm_info(self):
        """
        test spm build
        """
        self._spm_create_update_repo(self.config)
        install = self.run_spm("install", self.config, "apache")
        get_info = self.run_spm("info", self.config, "apache")

        check_info = ["Supported OSes", "Supported OS", "installing Apache"]
        for info in check_info:
            self.assertIn(info, "".join(get_info))

    def tearDown(self):
        shutil.rmtree(self._tmp_spm)
