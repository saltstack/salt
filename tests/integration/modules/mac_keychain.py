# -*- coding: utf-8 -*-
'''
Validate the mac-keychain module
'''

# Import Python Libs
from __future__ import absolute_import
import os

# Import Salt Testing Libs
from salttesting import skipIf
from salttesting.helpers import (
    destructiveTest,
    ensure_in_syspath,
    requires_system_grains
)
ensure_in_syspath('../../')

# Import Salt Libs
import integration
from salt.exceptions import CommandExecutionError

CERT = os.path.join(
    integration.FILES,
    'file',
    'base',
    'certs',
    'salttest.p12'
)
CERT_ALIAS = 'Salt Test'
PASSWD = 'salttest'


@destructiveTest
@skipIf(os.geteuid() != 0, 'You must be logged in as root to run this test')
class MacKeychainModuleTest(integration.ModuleCase):
    '''
    Integration tests for the mac_keychain module
    '''
    def setUp(self):
        '''
        Sets up the test requirements
        '''
        os_grain = self.run_function('grains.item', ['kernel'])
        # Must be running on a mac
        if os_grain['kernel'] not in 'Darwin':
            self.skipTest(
                'Test not applicable to \'{kernel}\' kernel'.format(
                    **os_grain
                )
            )

    def tearDown(self):
        '''
        Clean up after tests
        '''
        # Remove the salttest cert, if left over.
        certs_list = self.run_function('keychain.list_certs')
        if CERT_ALIAS in certs_list:
            self.run_function('keychain.uninstall', [CERT_ALIAS])

    @requires_system_grains
    def test_mac_keychain_install(self, grains=None):
        '''
        Tests that attempts to install a certificate
        '''
        install_cert = self.run_function('keychain.install', [CERT, PASSWD])
        self.assertTrue(install_cert)

        # check to ensure the cert was installed
        certs_list = self.run_function('keychain.list_certs')
        self.assertIn(CERT_ALIAS, certs_list)

    @requires_system_grains
    def test_mac_keychain_uninstall(self, grains=None):
        '''
        Tests that attempts to uninstall a certificate
        '''
        self.run_function('keychain.install', [CERT, PASSWD])
        certs_list = self.run_function('keychain.list_certs')

        if CERT_ALIAS not in certs_list:
            self.run_function('keychain.uninstall', [CERT_ALIAS])
            self.skipTest('Failed to install keychain')

        # uninstall cert
        self.run_function('keychain.uninstall', [CERT_ALIAS])
        certs_list = self.run_function('keychain.list_certs')

        # check to ensure the cert was uninstalled
        try:
            self.assertNotIn(CERT_ALIAS, str(certs_list))
        except CommandExecutionError:
            self.run_function('keychain.uninstall', [CERT_ALIAS])

    @requires_system_grains
    def test_mac_keychain_get_friendly_name(self, grains=None):
        '''
        Test that attempts to get friendly name of a cert
        '''
        self.run_function('keychain.install', [CERT, PASSWD])
        certs_list = self.run_function('keychain.list_certs')
        if CERT_ALIAS not in certs_list:
            self.run_function('keychain.uninstall', [CERT_ALIAS])
            self.skipTest('Failed to install keychain')

        get_name = self.run_function('keychain.get_friendly_name', [CERT, PASSWD])
        self.assertEqual(get_name, CERT_ALIAS)

    @requires_system_grains
    def test_mac_keychain_get_default_keychain(self, grains=None):
        '''
        Test that attempts to get the default keychain
        '''
        salt_get_keychain = self.run_function('keychain.get_default_keychain')
        sys_get_keychain = self.run_function('cmd.run',
                                             ['security default-keychain -d user'])
        self.assertEqual(salt_get_keychain, sys_get_keychain)

    @requires_system_grains
    def test_mac_keychain_list_certs(self, grains=None):
        '''
        Test that attempts to list certs
        '''
        cert_default = 'com.apple.systemdefault'
        certs = self.run_function('keychain.list_certs')
        self.assertIn(cert_default, certs)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MacKeychainModuleTest)
