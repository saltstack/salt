# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

import os

# Import Salt Libs
import salt.utils.files
import salt.utils.platform
from tests.support.case import ModuleCase
from tests.support.helpers import destructiveTest

# Import Salt Testing libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import skipIf


@skipIf(not salt.utils.platform.is_windows(), "Tests for only Windows")
class DscModuleTest(ModuleCase):
    """
    Validate PowerShell DSC module
    """

    def setUp(self):
        self.ps1file = os.path.join(RUNTIME_VARS.TMP, "HelloWorld.ps1")
        with salt.utils.files.fopen(
            os.path.join(RUNTIME_VARS.FILES, "file", "base", "HelloWorld.ps1"), "rb"
        ) as sfp:
            with salt.utils.files.fopen(self.ps1file, "wb") as dfp:
                dfp.write(sfp.read())
        self.psd1file = os.path.join(RUNTIME_VARS.TMP, "HelloWorld.psd1")
        with salt.utils.files.fopen(
            os.path.join(RUNTIME_VARS.FILES, "file", "base", "HelloWorld.psd1"), "rb"
        ) as sfp:
            with salt.utils.files.fopen(self.psd1file, "wb") as dfp:
                dfp.write(sfp.read())
        super(DscModuleTest, self).setUp()

    def tearDown(self):
        if os.path.isfile(self.ps1file):
            os.remove(self.ps1file)
        if os.path.isfile(self.psd1file):
            os.remove(self.psd1file)
        super(DscModuleTest, self).tearDown()

    @destructiveTest
    def test_compile_config(self):
        ret = self.run_function(
            "dsc.compile_config",
            self.ps1file,
            config_name="HelloWorld",
            config_data=self.psd1file,
        )
        self.assertTrue(ret["Exists"])
