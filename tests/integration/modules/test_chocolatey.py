# -*- coding: utf-8 -*-

from __future__ import absolute_import

import pytest
import salt.utils.path
import salt.utils.platform
from tests.support.case import ModuleCase
from tests.support.helpers import destructiveTest
from tests.support.sminion import create_sminion
from tests.support.unit import skipIf


@skipIf(not salt.utils.platform.is_windows(), "Tests for only Windows")
@destructiveTest
@pytest.mark.windows_whitelisted
class ChocolateyModuleTest(ModuleCase):
    """
    Validate Chocolatey module
    """

    @classmethod
    def setUpClass(cls):
        """
        Ensure that Chocolatey is installed
        """
        if salt.utils.path.which("chocolatey.exe") is None:
            sminion = create_sminion()
            sminion.functions.chocolatey.bootstrap()

    def test_list_(self):
        ret = self.run_function("chocolatey.list", narrow="adobereader", exact=True)
        self.assertTrue("adobereader" in ret)
