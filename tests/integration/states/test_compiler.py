# -*- coding: utf-8 -*-
"""
tests for host state
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
import salt.utils.platform

# Import Salt Testing libs
from tests.support.case import ModuleCase

# Import 3rd-Party libs
HAS_LSB_RELEASE = True
try:
    import lsb_release
except ImportError:
    HAS_LSB_RELEASE = False


class CompileTest(ModuleCase):
    """
    Validate the state compiler
    """

    def test_multi_state(self):
        """
        Test the error with multiple states of the same type
        """
        ret = self.run_function("state.sls", mods="fuzz.multi_state")
        # Verify that the return is a list, aka, an error
        self.assertIsInstance(ret, list)

    def test_jinja_deep_error(self):
        """
        Test when we have an error in a execution module
        called by jinja
        """
        if salt.utils.platform.is_linux() and HAS_LSB_RELEASE:
            release = lsb_release.get_distro_information()
            if (
                release.get("ID") == "Debian"
                and int(release.get("RELEASE", "0")[0]) < 9
            ):
                self.skipTest("This test is flaky on Debian 8. Skipping.")

        ret = self.run_function("state.sls", ["issue-10010"])
        self.assertTrue(", in jinja_error" in ret[0].strip())
        self.assertTrue(ret[0].strip().endswith("Exception: hehehe"))
