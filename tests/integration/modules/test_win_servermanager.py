# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt libs
import salt.utils.platform

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.unit import skipIf


@skipIf(not salt.utils.platform.is_windows(), "windows test only")
class WinServermanagerTest(ModuleCase):
    """
    Test for salt.modules.win_servermanager
    """

    def test_list_available(self):
        """
        Test list available features to install
        """
        cmd = self.run_function("win_servermanager.list_available")
        self.assertIn("DNS", cmd)
        self.assertIn("NetworkController", cmd)
        self.assertIn("RemoteAccess", cmd)
