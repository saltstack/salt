"""
Integration tests for Ruby Gem module
"""

import pytest
from tornado.httpclient import HTTPClient

import salt.utils.platform
from tests.support.case import ModuleCase


def check_status():
    """
    Check the status of the rubygems source
    """
    try:
        return HTTPClient().fetch("https://rubygems.org").code == 200
    except Exception:  # pylint: disable=broad-except
        return False


@pytest.mark.timeout_unless_on_windows(120)
@pytest.mark.skip_if_binaries_missing("gem")
@pytest.mark.windows_whitelisted
@pytest.mark.destructive_test
class GemModuleTest(ModuleCase):
    """
    Validate gem module
    """

    def setUp(self):
        if check_status() is False:
            self.skipTest("External resource 'https://rubygems.org' is not available")

        self.GEM_BIN = "gem.cmd" if salt.utils.platform.is_windows() else "gem"
        self.GEM = "tidy"
        self.GEM_VER = "1.1.2"
        self.OLD_GEM = "brass"
        self.OLD_VERSION = "1.0.0"
        self.NEW_VERSION = "1.3.0"
        self.GEM_LIST = [self.GEM, self.OLD_GEM]
        for name in (
            "GEM",
            "GEM_VER",
            "OLD_GEM",
            "OLD_VERSION",
            "NEW_VERSION",
            "GEM_LIST",
        ):
            self.addCleanup(delattr, self, name)

        def uninstall_gem():
            # Remove gem if it is already installed
            if self.run_function("gem.list", [self.GEM]):
                self.run_function("gem.uninstall", [self.GEM])

        self.addCleanup(uninstall_gem)

        def uninstall_old_gem():
            if self.run_function("gem.list", [self.OLD_GEM]):
                self.run_function("gem.uninstall", [self.OLD_GEM])

        # Ensure OLD_GEM is not installed before the test (handles leftover state
        # from a previously failed run that skipped its own cleanup).
        uninstall_old_gem()
        self.addCleanup(uninstall_old_gem)

    def run_function(self, function, *args, **kwargs):
        """Override run_function to use the gem binary"""
        kwargs["gem_bin"] = self.GEM_BIN
        return super().run_function(function, *args, **kwargs)

    @pytest.mark.slow_test
    def test_install_uninstall(self):
        """
        gem.install
        gem.uninstall
        """
        self.run_function("gem.install", [self.GEM])
        gem_list = self.run_function("gem.list", [self.GEM])
        self.assertIn(self.GEM, gem_list)

        self.run_function("gem.uninstall", [self.GEM])
        self.assertFalse(self.run_function("gem.list", [self.GEM]))

    @pytest.mark.slow_test
    def test_install_version(self):
        """
        gem.install rake version=11.1.2
        """
        self.run_function("gem.install", [self.GEM], version=self.GEM_VER)
        gem_list = self.run_function("gem.list", [self.GEM])
        self.assertIn(self.GEM, gem_list)
        self.assertIn(self.GEM_VER, gem_list[self.GEM])

        self.run_function("gem.uninstall", [self.GEM])
        self.assertFalse(self.run_function("gem.list", [self.GEM]))

    @pytest.mark.slow_test
    def test_list(self):
        """
        gem.list
        """
        self.run_function("gem.install", [" ".join(self.GEM_LIST)])

        all_ret = self.run_function("gem.list")
        for gem in self.GEM_LIST:
            self.assertIn(gem, all_ret)

        single_ret = self.run_function("gem.list", [self.GEM])
        self.assertIn(self.GEM, single_ret)

        self.run_function("gem.uninstall", [" ".join(self.GEM_LIST)])

    @pytest.mark.slow_test
    def test_list_upgrades(self):
        """
        gem.list_upgrades
        """
        # install outdated gem
        self.run_function("gem.install", [self.OLD_GEM], version=self.OLD_VERSION)

        ret = self.run_function("gem.list_upgrades")
        self.assertIn(self.OLD_GEM, ret)

        self.run_function("gem.uninstall", [self.OLD_GEM])

    @pytest.mark.slow_test
    def test_sources_add_remove(self):
        """
        gem.sources_add
        gem.sources_remove
        """
        source = "http://production.cf.rubygems.org"

        self.run_function("gem.sources_add", [source])
        sources_list = self.run_function("gem.sources_list")
        self.assertIn(source, sources_list)

        self.run_function("gem.sources_remove", [source])
        sources_list = self.run_function("gem.sources_list")
        self.assertNotIn(source, sources_list)

    @pytest.mark.slow_test
    def test_update(self):
        """
        gem.update
        """
        self.run_function("gem.install", [self.OLD_GEM], version=self.OLD_VERSION)
        gem_list = self.run_function("gem.list", [self.OLD_GEM])
        self.assertEqual({self.OLD_GEM: [self.OLD_VERSION]}, gem_list)

        self.run_function("gem.update", [self.OLD_GEM])
        gem_list = self.run_function("gem.list", [self.OLD_GEM])
        installed_versions = gem_list.get(self.OLD_GEM, [])

        if installed_versions == [self.OLD_VERSION]:
            # gem update may be unable to install a newer version when the
            # only available release requires a Ruby version not present on
            # this system (e.g. brass >= 1.3.0 requires Ruby >= 3.1).
            self.skipTest(
                "gem update did not install a newer version of {}; the "
                "latest release may require a newer Ruby version".format(self.OLD_GEM)
            )

        self.assertEqual(
            {self.OLD_GEM: [self.NEW_VERSION, self.OLD_VERSION]},
            gem_list,
        )

        self.run_function("gem.uninstall", [self.OLD_GEM])
        self.assertFalse(self.run_function("gem.list", [self.OLD_GEM]))

    @pytest.mark.slow_test
    def test_update_system(self):
        """
        gem.update_system
        """
        ret = self.run_function("gem.update_system")
        self.assertTrue(ret)
