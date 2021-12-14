"""
integration tests for mac_pkgutil
"""

import os

import pytest
from tests.support.case import ModuleCase
from tests.support.helpers import requires_system_grains, runs_on
from tests.support.runtests import RUNTIME_VARS

TEST_PKG_URL = (
    "https://distfiles.macports.org/MacPorts/MacPorts-2.3.4-10.11-ElCapitan.pkg"
)
TEST_PKG_NAME = "org.macports.MacPorts"


@runs_on(kernel="Darwin")
@pytest.mark.skip_if_not_root
@pytest.mark.skip_if_binaries_missing("pkgutil")
class MacPkgutilModuleTest(ModuleCase):
    """
    Validate the mac_pkgutil module
    """

    @classmethod
    def setUpClass(cls):
        cls.test_pkg = os.path.join(
            RUNTIME_VARS.TMP, "MacPorts-2.3.4-10.11-ElCapitan.pkg"
        )

    @requires_system_grains
    def setUp(self, grains):  # pylint: disable=arguments-differ
        """
        Get current settings
        """
        os_release = grains["osrelease"]
        self.pkg_name = "com.apple.pkg.BaseSystemResources"
        if int(os_release.split(".")[1]) >= 13:
            self.pkg_name = "com.apple.pkg.iTunesX"

    def tearDown(self):
        """
        Reset to original settings
        """
        self.run_function("pkgutil.forget", [TEST_PKG_NAME])
        self.run_function("file.remove", ["/opt/local"])

    @pytest.mark.slow_test
    def test_list(self):
        """
        Test pkgutil.list
        """
        self.assertIsInstance(self.run_function("pkgutil.list"), list)
        self.assertIn(self.pkg_name, self.run_function("pkgutil.list"))

    @pytest.mark.slow_test
    def test_is_installed(self):
        """
        Test pkgutil.is_installed
        """
        # Test Package is installed
        self.assertTrue(self.run_function("pkgutil.is_installed", [self.pkg_name]))

        # Test Package is not installed
        self.assertFalse(self.run_function("pkgutil.is_installed", ["spongebob"]))

    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_install_forget(self):
        """
        Test pkgutil.install
        Test pkgutil.forget
        """
        # Test if installed
        self.assertFalse(self.run_function("pkgutil.is_installed", [TEST_PKG_NAME]))

        # Download the package
        self.run_function("cp.get_url", [TEST_PKG_URL, self.test_pkg])

        # Test install
        self.assertTrue(
            self.run_function("pkgutil.install", [self.test_pkg, TEST_PKG_NAME])
        )
        self.assertIn(
            "Unsupported scheme",
            self.run_function("pkgutil.install", ["ftp://test", "spongebob"]),
        )

        # Test forget
        self.assertTrue(self.run_function("pkgutil.forget", [TEST_PKG_NAME]))
