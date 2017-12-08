# -*- coding: utf-8 -*-
'''
Tests for the Chocolatey State
'''
# Import Python libs
from __future__ import absolute_import
import logging

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.mixins import SaltReturnAssertsMixin
from tests.support.unit import skipIf
from tests.support.helpers import destructiveTest

# Import Salt libs
import salt.utils.platform

log = logging.getLogger(__name__)

__testcontext__ = {}


@destructiveTest
@skipIf(not salt.utils.platform.is_windows(), 'Windows Specific Test')
class ChocolateyTest(ModuleCase, SaltReturnAssertsMixin):
    '''
    Chocolatey State Tests
    These tests are destructive as the install and remove software
    '''

    def setUp(self):
        '''
        Ensure that Chocolatey is installed
        '''
        super(ChocolateyTest, self).setUp()
        if 'chocolatey' not in __testcontext__:
            self.run_function('chocolatey.bootstrap')
            __testcontext__['chocolatey'] = True

    def test_installed(self):
        '''
        Test `chocolatey.installed`
        '''

        # If this assert fails, we need to find new targets, this test needs to
        # be able to test successful installation of packages, so this package
        # needs to NOT be installed before we run the states below
        target = 'firefox'
        self.assertFalse(
            self.run_function('chocolatey.version', [target]))

        try:
            # Install the package
            ret = self.run_state('chocolatey.installed', name=target)
            self.assertSaltTrueReturn(ret)

            # Verify the package is installed
            self.assertTrue(
                self.run_function('chocolatey.version', [target]))

        finally:
            # Uninstall the package (cleanup)
            ret = self.run_state('chocolatey.uninstalled', name=target)
            self.assertSaltTrueReturn(ret)

    def test_uninstalled(self):
        '''
        Test `chocolatey.uninstalled`
        '''

        # Make sure firefox is installed by chocolatey
        target = 'firefox'
        if not self.run_function('chocolatey.version', [target]):
            self.assertTrue(
                self.run_function('chocolatey.install', [target]))

        # uninstall the package
        ret = self.run_state('chocolatey.uninstalled', name=target)
        self.assertSaltTrueReturn(ret)

        # Verify the package is uninstalled
        self.assertFalse(
            self.run_function('chocolatey.version', [target]))

    def test_upgraded(self):
        '''
        Test `chocolatey.upgraded`
        '''

        # If this assert fails, we need to find new targets, this test needs to
        # be able to test successful installation of packages, so this package
        # needs to NOT be installed before we run the states below
        target = 'firefox'
        self.assertFalse(
            self.run_function('chocolatey.version', [target]))

        # Make sure firefox is installed by chocolatey
        target = 'firefox'
        pre_version = '52.0.2'
        upg_version = '57.0.2'
        self.assertTrue(
            self.run_function('chocolatey.install', [target, pre_version]))

        ret = self.run_function('chocolatey.version', [target])
        self.assertEqual(ret, {'Firefox': pre_version})

        try:
            # upgrade the package
            ret = self.run_state(
                'chocolatey.upgraded',
                name=target,
                version=upg_version)
            self.assertSaltTrueReturn(ret)

            # Verify the package is upgraded
            ret = self.run_function('chocolatey.version', [target])
            self.assertEqual(ret, {'Firefox': upg_version})

        finally:
            # Uninstall the package (cleanup)
            ret = self.run_state('chocolatey.uninstalled', name=target)
            self.assertSaltTrueReturn(ret)
