# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt libs
import salt.utils.platform

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.unit import skipIf


@skipIf(not salt.utils.platform.is_windows(), "windows tests only")
class AutoRunsModuleTest(ModuleCase):
    """
    Test the autoruns module
    """

    def test_win_autoruns_list(self):
        """
        test win_autoruns.list module
        """
        ret = self.run_function("autoruns.list")
        self.assertIn("HKLM", str(ret))
        self.assertTrue(isinstance(ret, dict))
