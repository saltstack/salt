# -*- coding: utf-8 -*-
'''
Validate the mac-keychain module
'''

# Import Python Libs
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

CERT = 'salttest.p12'
CERT_ALIAS = 'Salt Test'
CERT_DEST= '/tmp/salttest.p12'
PASSWD = 'salttest'


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
        # Must copy the cert to the mac for all tests
        copy_cert = self.run_function('cp.get_file', ['salt://certs.{0}'.format(CERT), CERT_DEST])

#        self.assertTrue(copy_cert)
#        check_cert = self.run_function('file.find', ['/tmp'], name='{0}'.format(CERT))
#        if CERT not in str(check_cert):
#            self.skipTest(
#                'Can not copy the cert {0} to dir {1}'.format(CERT, CERT_DEST))


    @destructiveTest
    @skipIf(os.geteuid() != 0, 'You must be logged in as root to run this test')
    @requires_system_grains
    def test_mac_keychain_install(self, grains=None):
        '''
        Tests that attempts to install a certificate
        '''
        install_cert = self.run_function('keychain.install', [CERT_DEST, PASSWD])
        self.assertTrue(install_cert)

        #check to ensure the cert was installed
        certs_list = self.run_function('keychain.list_certs')
        self.assertIn(CERT_ALIAS, certs_list)

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'You must be logged in as root to run this test')
    @requires_system_grains
    def test_mac_keychain_uninstall(self, grains=None):
        '''
        Tests that attempts to uninstall a certificate
        '''
        self.run_function('keychain.install', [CERT_DEST, PASSWD])
        certs_list = self.run_function('keychain.list_certs')

        if CERT_ALIAS not in certs_list:
            self.run_function('keychain.uninstall', [CERT_ALIAS])
            self.skipTest('Failed to install keychain')

        uninstall_cert = self.run_function('keychain.uninstall', [CERT_ALIAS])
        certs_list = self.run_function('keychain.list_certs')

        #check to ensure the cert was uninstalled
        try:
            self.assertNotIn(CERT_ALIAS, str(certs_list))
        except CommandExecutionError:
            self.run_function('keychain.uninstall', [CERT_ALIAS])

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'You must be logged in as root to run this test')
    @requires_system_grains
    def test_mac_keychain_get_friendly_name(self, grains=None):
        '''
        Test that attempts to get friendly name of a cert
        '''

        self.run_function('keychain.install', [CERT_DEST, PASSWD])
        certs_list = self.run_function('keychain.list_certs')
        if CERT_ALIAS not in certs_list:
            self.run_function('keychain.uninstall', [CERT_ALIAS])
            self.skipTest('Failed to install keychain')

        get_name = self.run_function('keychain.get_friendly_name', [CERT_DEST, PASSWD])
        self.assertEqual(get_name, CERT_ALIAS)

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'You must be logged in as root to run this test')
    @requires_system_grains
    def test_mac_keychain_get_default_keychain(self, grains=None):
        '''
        Test that attempts to get the default keychain
        '''
        salt_get_keychain = self.run_function('keychain.get_default_keychain')
        sys_get_keychain = self.run_function('cmd.run', ['security default-keychain -d systemj'])
        self.assertEqual(salt_get_keychain, sys_get_keychain)

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'You must be logged in as root to run this test')
    @requires_system_grains
    def test_mac_keychain_set_default_keychain(self, grains=None):
        salt_get_keychain = self.run_function('keychain.get_default_keychain')
        set_keychain = self.run_function('keychain.set_default_keychain', ['/tmp/test'])

if __name__ == '__main__':
    from integration import run_tests
    run_tests(MacKeychainModuleTest)
