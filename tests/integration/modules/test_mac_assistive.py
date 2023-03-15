"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""

import pytest

from tests.support.case import ModuleCase

OSA_SCRIPT = "/usr/bin/osascript"


@pytest.mark.destructive_test
@pytest.mark.skip_if_not_root
@pytest.mark.skip_initial_gh_actions_failure
@pytest.mark.skip_unless_on_darwin
class MacAssistiveTest(ModuleCase):
    """
    Integration tests for the mac_assistive module.
    """

    def setUp(self):
        """
        Sets up test requirements
        """
        # Let's install a bundle to use in tests
        self.run_function("assistive.install", [OSA_SCRIPT, True])

    def tearDown(self):
        """
        Clean up after tests
        """
        # Delete any bundles that were installed
        osa_script = self.run_function("assistive.installed", [OSA_SCRIPT])
        if osa_script:
            self.run_function("assistive.remove", [OSA_SCRIPT])

        smile_bundle = "com.smileonmymac.textexpander"
        smile_bundle_present = self.run_function("assistive.installed", [smile_bundle])
        if smile_bundle_present:
            self.run_function("assistive.remove", [smile_bundle])

    @pytest.mark.slow_test
    def test_install_and_remove(self):
        """
        Tests installing and removing a bundled ID or command to use assistive access.
        """
        new_bundle = "com.smileonmymac.textexpander"
        self.assertTrue(self.run_function("assistive.install", [new_bundle]))
        self.assertTrue(self.run_function("assistive.remove", [new_bundle]))

    @pytest.mark.slow_test
    def test_installed(self):
        """
        Tests the True and False return of assistive.installed.
        """
        # OSA script should have been installed in setUp function
        self.assertTrue(self.run_function("assistive.installed", [OSA_SCRIPT]))
        # Clean up install
        self.run_function("assistive.remove", [OSA_SCRIPT])
        # Installed should now return False
        self.assertFalse(self.run_function("assistive.installed", [OSA_SCRIPT]))

    @pytest.mark.slow_test
    def test_enable(self):
        """
        Tests setting the enabled status of a bundled ID or command.
        """
        # OSA script should have been installed and enabled in setUp function
        # Now let's disable it, which should return True.
        self.assertTrue(self.run_function("assistive.enable", [OSA_SCRIPT, False]))
        # Double check the script was disabled, as intended.
        self.assertFalse(self.run_function("assistive.enabled", [OSA_SCRIPT]))
        # Now re-enable
        self.assertTrue(self.run_function("assistive.enable", [OSA_SCRIPT]))
        # Double check the script was enabled, as intended.
        self.assertTrue(self.run_function("assistive.enabled", [OSA_SCRIPT]))

    @pytest.mark.slow_test
    def test_enabled(self):
        """
        Tests if a bundled ID or command is listed in assistive access returns True.
        """
        # OSA script should have been installed in setUp function, which sets
        # enabled to True by default.
        self.assertTrue(self.run_function("assistive.enabled", [OSA_SCRIPT]))
        # Disable OSA Script
        self.run_function("assistive.enable", [OSA_SCRIPT, False])
        # Assert against new disabled status
        self.assertFalse(self.run_function("assistive.enabled", [OSA_SCRIPT]))
