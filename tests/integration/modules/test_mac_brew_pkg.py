"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""

import pytest
from salt.exceptions import CommandExecutionError
from tests.support.case import ModuleCase
from tests.support.helpers import runs_on

# Brew doesn't support local package installation - So, let's
# Grab some small packages available online for brew
ADD_PKG = "algol68g"
DEL_PKG = "acme"


@pytest.mark.skip_if_not_root
@runs_on(kernel="Darwin")
@pytest.mark.destructive_test
@pytest.mark.skip_if_binaries_missing("brew")
class BrewModuleTest(ModuleCase):
    """
    Integration tests for the brew module
    """

    @pytest.mark.slow_test
    def test_brew_install(self):
        """
        Tests the installation of packages
        """
        try:
            self.run_function("pkg.install", [ADD_PKG])
            pkg_list = self.run_function("pkg.list_pkgs")
            try:
                self.assertIn(ADD_PKG, pkg_list)
            except AssertionError:
                self.run_function("pkg.remove", [ADD_PKG])
                raise
        except CommandExecutionError:
            self.run_function("pkg.remove", [ADD_PKG])
            raise

    @pytest.mark.slow_test
    def test_remove(self):
        """
        Tests the removal of packages
        """
        try:
            # Install a package to delete - If unsuccessful, skip the test
            self.run_function("pkg.install", [DEL_PKG])
            pkg_list = self.run_function("pkg.list_pkgs")
            if DEL_PKG not in pkg_list:
                self.run_function("pkg.install", [DEL_PKG])
                self.skipTest("Failed to install a package to delete")

            # Now remove the installed package
            self.run_function("pkg.remove", [DEL_PKG])
            del_list = self.run_function("pkg.list_pkgs")
            self.assertNotIn(DEL_PKG, del_list)
        except CommandExecutionError:
            self.run_function("pkg.remove", [DEL_PKG])
            raise

    @pytest.mark.slow_test
    def test_version(self):
        """
        Test pkg.version for mac. Installs a package and then checks we can get
        a version for the installed package.
        """
        try:
            self.run_function("pkg.install", [ADD_PKG])
            pkg_list = self.run_function("pkg.list_pkgs")
            version = self.run_function("pkg.version", [ADD_PKG])
            try:
                self.assertTrue(
                    version,
                    msg="version: {} is empty, or other issue is present".format(
                        version
                    ),
                )
                self.assertIn(
                    ADD_PKG,
                    pkg_list,
                    msg="package: {} is not in the list of installed packages: {}".format(
                        ADD_PKG, pkg_list
                    ),
                )
                # make sure the version is accurate and is listed in the pkg_list
                self.assertIn(
                    version,
                    str(pkg_list[ADD_PKG]),
                    msg="The {} version: {} is not listed in the pkg_list: {}".format(
                        ADD_PKG, version, pkg_list[ADD_PKG]
                    ),
                )
            except AssertionError:
                self.run_function("pkg.remove", [ADD_PKG])
                raise
        except CommandExecutionError:
            self.run_function("pkg.remove", [ADD_PKG])
            raise

    @pytest.mark.slow_test
    def test_latest_version(self):
        """
        Test pkg.latest_version:
          - get the latest version available
          - install the package
          - get the latest version available
          - check that the latest version is empty after installing it
        """
        try:
            self.run_function("pkg.remove", [ADD_PKG])
            uninstalled_latest = self.run_function("pkg.latest_version", [ADD_PKG])

            self.run_function("pkg.install", [ADD_PKG])
            installed_latest = self.run_function("pkg.latest_version", [ADD_PKG])
            version = self.run_function("pkg.version", [ADD_PKG])
            try:
                self.assertTrue(isinstance(uninstalled_latest, str))
                self.assertEqual(installed_latest, version)
            except AssertionError:
                self.run_function("pkg.remove", [ADD_PKG])
                raise
        except CommandExecutionError:
            self.run_function("pkg.remove", [ADD_PKG])
            raise

    @pytest.mark.slow_test
    def test_refresh_db(self):
        """
        Integration test to ensure pkg.refresh_db works with brew
        """
        refresh_brew = self.run_function("pkg.refresh_db")
        self.assertTrue(refresh_brew)

    @pytest.mark.slow_test
    def test_list_upgrades(self):
        """
        Test pkg.list_upgrades: data is in the form {'name1': 'version1',
        'name2': 'version2', ... }
        """
        try:
            upgrades = self.run_function("pkg.list_upgrades")
            try:
                self.assertTrue(isinstance(upgrades, dict))
                if upgrades:
                    for name in upgrades:
                        self.assertTrue(isinstance(name, str))
                        self.assertTrue(isinstance(upgrades[name], str))
            except AssertionError:
                self.run_function("pkg.remove", [ADD_PKG])
                raise
        except CommandExecutionError:
            self.run_function("pkg.remove", [ADD_PKG])
            raise

    @pytest.mark.slow_test
    def test_info_installed(self):
        """
        Test pkg.info_installed: info returned has certain fields used by
        mac_brew.latest_version
        """
        try:
            self.run_function("pkg.install", [ADD_PKG])
            info = self.run_function("pkg.info_installed", [ADD_PKG])
            try:
                self.assertTrue(ADD_PKG in info)
                self.assertTrue("versions" in info[ADD_PKG])
                self.assertTrue("revision" in info[ADD_PKG])
                self.assertTrue("stable" in info[ADD_PKG]["versions"])
            except AssertionError:
                self.run_function("pkg.remove", [ADD_PKG])
                raise
        except CommandExecutionError:
            self.run_function("pkg.remove", [ADD_PKG])
            raise

    def tearDown(self):
        """
        Clean up after tests
        """
        pkg_list = self.run_function("pkg.list_pkgs")

        # Remove any installed packages
        if ADD_PKG in pkg_list:
            self.run_function("pkg.remove", [ADD_PKG])
        if DEL_PKG in pkg_list:
            self.run_function("pkg.remove", [DEL_PKG])
