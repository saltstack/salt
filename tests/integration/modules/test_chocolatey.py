# -*- coding: utf-8 -*-

from __future__ import absolute_import

import pytest
import salt.modules.chocolatey as choco
import salt.utils.platform
from tests.support.case import ModuleCase
from tests.support.helpers import destructiveTest
from tests.support.unit import skipIf


@skipIf(not salt.utils.platform.is_windows(), "Tests for only Windows")
@pytest.mark.windows_whitelisted
class ChocolateyModuleTest(ModuleCase):
    """
    Validate Chocolatey module
    """

    @destructiveTest
    def setUp(self):
        """
        Ensure that Chocolatey is installed
        """
        self._chocolatey_bin = choco._find_chocolatey()
        if "ERROR" in self._chocolatey_bin:
            #    self.fail("Chocolatey is not installed")
            self.run_function("chocolatey.bootstrap")
        super(ChocolateyModuleTest, self).setUp()

    def test_list_(self):
        ret = self.run_function("chocolatey.list", narrow="adobereader", exact=True)
        self.assertTrue("adobereader" in ret)
