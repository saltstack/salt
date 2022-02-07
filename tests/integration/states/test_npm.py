"""
    :codeauthor: Erik Johnson (erik@saltstack.com)
    tests.integration.states.npm
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

import os

import pytest
import salt.utils.path
import salt.utils.platform
from salt.utils.versions import LooseVersion
from tests.support.case import ModuleCase
from tests.support.mixins import SaltReturnAssertsMixin
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import skipIf

MAX_NPM_VERSION = "5.0.0"


@skipIf(salt.utils.path.which("npm") is None, "npm not installed")
class NpmStateTest(ModuleCase, SaltReturnAssertsMixin):
    @skipIf(salt.utils.path.which("git") is None, "git is not installed")
    @skipIf(salt.utils.platform.is_darwin(), "TODO this test hangs on mac.")
    @pytest.mark.requires_network
    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_npm_install_url_referenced_package(self):
        """
        Determine if URL-referenced NPM module can be successfully installed.
        """
        npm_version = self.run_function("cmd.run", ["npm -v"])
        if LooseVersion(npm_version) >= LooseVersion(MAX_NPM_VERSION):
            user = os.environ.get("SUDO_USER", "root")
            npm_dir = os.path.join(RUNTIME_VARS.TMP, "git-install-npm")
            self.run_state("file.directory", name=npm_dir, user=user, dir_mode="755")
        else:
            user = None
            npm_dir = None
        ret = self.run_state(
            "npm.installed",
            name="request/request#v2.81.1",
            runas=user,
            dir=npm_dir,
            registry="http://registry.npmjs.org/",
        )
        self.assertSaltTrueReturn(ret)
        ret = self.run_state(
            "npm.removed",
            name="git://github.com/request/request",
            runas=user,
            dir=npm_dir,
        )
        self.assertSaltTrueReturn(ret)
        if npm_dir is not None:
            self.run_state("file.absent", name=npm_dir)

    @pytest.mark.requires_network
    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_npm_installed_pkgs(self):
        """
        Basic test to determine if NPM module successfully installs multiple
        packages.
        """
        ret = self.run_state(
            "npm.installed",
            name="unused",
            pkgs=["pm2@2.10.4", "grunt@1.0.2"],
            registry="http://registry.npmjs.org/",
        )
        self.assertSaltTrueReturn(ret)

    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_npm_cache_clean(self):
        """
        Basic test to determine if NPM successfully cleans its cached packages.
        """
        npm_version = self.run_function("cmd.run", ["npm -v"])
        if LooseVersion(npm_version) >= LooseVersion(MAX_NPM_VERSION):
            self.skipTest("Skip with npm >= 5.0.0 until #41770 is fixed")
        ret = self.run_state("npm.cache_cleaned", name="unused", force=True)
        self.assertSaltTrueReturn(ret)
