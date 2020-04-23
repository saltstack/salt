# -*- coding: utf-8 -*-
"""
Tests for the Chocolatey State
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import Salt libs
import salt.utils.platform

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.helpers import destructiveTest
from tests.support.mixins import SaltReturnAssertsMixin
from tests.support.unit import skipIf

log = logging.getLogger(__name__)

__testcontext__ = {}


@destructiveTest
@skipIf(not salt.utils.platform.is_windows(), "Windows Specific Test")
class ChocolateyTest(ModuleCase, SaltReturnAssertsMixin):
    """
    Chocolatey State Tests
    These tests are destructive as the install and remove software
    """

    def setUp(self):
        """
        Ensure that Chocolatey is installed
        """
        super(ChocolateyTest, self).setUp()
        if "chocolatey" not in __testcontext__:
            self.run_function("chocolatey.bootstrap")
            __testcontext__["chocolatey"] = True

    def test_chocolatey(self):
        """
        Test the following:
        - `chocolatey.installed`
        - `chocolatey.upgraded`
        - `chocolatey.uninstalled`
        """
        # If this assert fails, we need to find new targets, this test needs to
        # be able to test successful installation of packages, so this package
        # needs to NOT be installed before we run the states below
        target = "firefox"
        pre_version = "52.0.2"
        upg_version = "57.0.2"
        log.debug("Making sure %s is not installed", target)
        self.assertFalse(self.run_function("chocolatey.version", [target]))

        try:
            ####################################################
            # Test `chocolatey.installed`
            ####################################################
            # Install the package
            log.debug("Testing chocolatey.installed")
            ret = self.run_state(
                "chocolatey.installed", name=target, version=pre_version
            )
            self.assertSaltTrueReturn(ret)

            # Verify the package is installed
            log.debug("Verifying install success")
            ret = self.run_function("chocolatey.version", [target])
            self.assertEqual(ret, {"Firefox": [pre_version]})

            ####################################################
            # Test `chocolatey.upgraded`
            ####################################################
            # Upgrade the package
            log.debug("Testing chocolatey.upgraded")
            ret = self.run_state(
                "chocolatey.upgraded", name=target, version=upg_version
            )
            self.assertSaltTrueReturn(ret)

            # Verify the package is upgraded
            log.debug("Verifying upgrade success")
            ret = self.run_function("chocolatey.version", [target])
            self.assertEqual(ret, {"Firefox": [upg_version]})

            ####################################################
            # Test `chocolatey.uninstalled`
            ####################################################
            # uninstall the package
            log.debug("Testing chocolatey.uninstalled")
            ret = self.run_state("chocolatey.uninstalled", name=target)
            self.assertSaltTrueReturn(ret)

            # Verify the package is uninstalled
            log.debug("Verifying uninstall success")
            ret = self.run_function("chocolatey.version", [target])
            self.assertEqual(ret, {})

        finally:
            # Always uninstall
            log.debug("Uninstalling %s", target)
            self.run_function("chocolatey.uninstall", [target])
