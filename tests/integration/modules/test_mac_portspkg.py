"""
integration tests for mac_ports
"""

import pytest

from tests.support.case import ModuleCase


@pytest.mark.skip_if_not_root
@pytest.mark.skip_if_binaries_missing("port")
@pytest.mark.skip_unless_on_darwin
class MacPortsModuleTest(ModuleCase):
    """
    Validate the mac_ports module
    """

    AGREE_INSTALLED = False

    def setUp(self):
        """
        Get current settings
        """
        self.AGREE_INSTALLED = "agree" in self.run_function("pkg.list_pkgs")
        self.run_function("pkg.refresh_db")

    def tearDown(self):
        """
        Reset to original settings
        """
        if not self.AGREE_INSTALLED:
            self.run_function("pkg.remove", ["agree"])

    @pytest.mark.destructive_test
    def test_list_pkgs(self):
        """
        Test pkg.list_pkgs
        """
        self.run_function("pkg.install", ["agree"])
        self.assertIsInstance(self.run_function("pkg.list_pkgs"), dict)
        self.assertIn("agree", self.run_function("pkg.list_pkgs"))

    @pytest.mark.destructive_test
    def test_latest_version(self):
        """
        Test pkg.latest_version
        """
        self.run_function("pkg.install", ["agree"])
        result = self.run_function("pkg.latest_version", ["agree"], refresh=False)
        self.assertIsInstance(result, dict)
        self.assertIn("agree", result)

    @pytest.mark.destructive_test
    def test_remove(self):
        """
        Test pkg.remove
        """
        self.run_function("pkg.install", ["agree"])
        removed = self.run_function("pkg.remove", ["agree"])
        self.assertIsInstance(removed, dict)
        self.assertIn("agree", removed)

    @pytest.mark.destructive_test
    def test_install(self):
        """
        Test pkg.install
        """
        self.run_function("pkg.remove", ["agree"])
        installed = self.run_function("pkg.install", ["agree"])
        self.assertIsInstance(installed, dict)
        self.assertIn("agree", installed)

    def test_list_upgrades(self):
        """
        Test pkg.list_upgrades
        """
        self.assertIsInstance(
            self.run_function("pkg.list_upgrades", refresh=False), dict
        )

    @pytest.mark.destructive_test
    def test_upgrade_available(self):
        """
        Test pkg.upgrade_available
        """
        self.run_function("pkg.install", ["agree"])
        self.assertFalse(
            self.run_function("pkg.upgrade_available", ["agree"], refresh=False)
        )

    def test_refresh_db(self):
        """
        Test pkg.refresh_db
        """
        self.assertTrue(self.run_function("pkg.refresh_db"))

    @pytest.mark.destructive_test
    def test_upgrade(self):
        """
        Test pkg.upgrade
        """
        results = self.run_function("pkg.upgrade", refresh=False)
        self.assertIsInstance(results, dict)
        self.assertTrue(results["result"])
