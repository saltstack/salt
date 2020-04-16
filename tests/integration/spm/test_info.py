# -*- coding: utf-8 -*-
"""
Tests for the spm info utility
"""
# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import shutil

# Import Salt Testing libs
from tests.support.case import SPMCase
from tests.support.helpers import destructiveTest


@destructiveTest
class SPMInfoTest(SPMCase):
    """
    Validate the spm info command
    """

    def setUp(self):
        self.config = self._spm_config()
        self._spm_build_files(self.config)

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
