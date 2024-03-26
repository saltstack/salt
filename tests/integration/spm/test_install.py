"""
Tests for the spm install utility
"""

import os

import pytest

import salt.utils.files
import salt.utils.path
import salt.utils.yaml
from tests.support.case import SPMCase
from tests.support.helpers import Webserver


@pytest.mark.destructive_test
@pytest.mark.windows_whitelisted
class SPMInstallTest(SPMCase):
    """
    Validate the spm install command
    """

    def setUp(self):
        self.config = self._spm_config()
        self._spm_build_files(self.config)
        self.spm_build_dir = self.config["spm_build_dir"]
        if "http" in self.id():
            # only start the webserver when testing http
            self.webserver = Webserver()
            self.webserver.root = self.spm_build_dir
            self.webserver.start()
            self.addCleanup(self.webserver.stop)
            self.repo_dir = self.config["spm_repos_config"] + ".d"
            self.repo = os.path.join(self.repo_dir, "spm.repo")
            url = {"my_repo": {"url": self.webserver.url("")[:-1]}}

            if not os.path.exists(self.repo_dir):
                os.makedirs(self.repo_dir)

            with salt.utils.files.fopen(self.repo, "w") as fp:
                salt.utils.yaml.safe_dump(url, fp)

    def test_spm_install_http(self):
        """
        test spm install using http repo
        """
        build_spm = self.run_spm("build", self.config, self.formula_dir)
        spm_file = os.path.join(self.spm_build_dir, "apache-201506-2.spm")

        create_repo = self.run_spm("create_repo", self.config, self.spm_build_dir)

        for root, dirs, files in salt.utils.path.os_walk(self.spm_build_dir):
            for fp in files:
                self.webserver.url(fp)

        install = self.run_spm("install", self.config, "apache")

        sls = os.path.join(self.config["formula_path"], "apache", "apache.sls")

        self.assertTrue(os.path.exists(sls))

    @pytest.mark.slow_test
    def test_spm_install_local_dir(self):
        """
        test spm install from local directory
        """
        build_spm = self.run_spm("build", self.config, self.formula_dir)
        spm_file = os.path.join(self.config["spm_build_dir"], "apache-201506-2.spm")

        install = self.run_spm("install", self.config, spm_file)

        sls = os.path.join(self.config["formula_path"], "apache", "apache.sls")

        self.assertTrue(os.path.exists(sls))

    @pytest.mark.slow_test
    def test_spm_install_from_repo(self):
        """
        test spm install from repo
        """
        self._spm_create_update_repo(self.config)
        install = self.run_spm("install", self.config, "apache")

        sls = os.path.join(self.config["formula_path"], "apache", "apache.sls")

        self.assertTrue(os.path.exists(sls))
