# -*- coding: utf-8 -*-
'''
integration tests for mac_pkgutil
'''

# Import python libs
from __future__ import absolute_import
import os

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath, destructiveTest
ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils

TEST_PKG_URL = 'https://distfiles.macports.org/MacPorts/MacPorts-2.3.4-10.11-ElCapitan.pkg'
TEST_PKG_NAME = 'org.macports.MacPorts'
TEST_PKG = os.path.join(integration.TMP, 'MacPorts-2.3.4-10.11-ElCapitan.pkg')


class MacPkgutilModuleTest(integration.ModuleCase):
    '''
    Validate the mac_pkgutil module
    '''

    def setUp(self):
        '''
        Get current settings
        '''
        if not salt.utils.is_darwin():
            self.skipTest('Test only available on macOS')

        if not salt.utils.which('pkgutil'):
            self.skipTest('Test requires pkgutil binary')

        if salt.utils.get_uid(salt.utils.get_user()) != 0:
            self.skipTest('Test requires root')

    def tearDown(self):
        '''
        Reset to original settings
        '''
        self.run_function('pkgutil.forget', ['org.macports.MacPorts'])
        self.run_function('file.remove', ['/opt/local'])

    def test_list(self):
        '''
        Test pkgutil.list
        '''
        self.assertIsInstance(self.run_function('pkgutil.list'), list)
        self.assertIn('com.apple.pkg.BaseSystemResources',
                      self.run_function('pkgutil.list'))

    def test_is_installed(self):
        '''
        Test pkgutil.is_installed
        '''
        # Test Package is installed
        self.assertTrue(
            self.run_function('pkgutil.is_installed',
                              ['com.apple.pkg.BaseSystemResources']))

        # Test Package is not installed
        self.assertFalse(
            self.run_function('pkgutil.is_installed', ['spongebob']))

    @destructiveTest
    def test_install_forget(self):
        '''
        Test pkgutil.install
        Test pkgutil.forget
        '''
        # Test if installed
        self.assertFalse(
            self.run_function('pkgutil.is_installed', [TEST_PKG_NAME]))

        # Download the package
        self.run_function('cp.get_url', [TEST_PKG_URL, TEST_PKG])

        # Test install
        self.assertTrue(
            self.run_function('pkgutil.install', [TEST_PKG, TEST_PKG_NAME]))
        self.assertIn(
            'Unsupported scheme',
            self.run_function('pkgutil.install', ['ftp://test', 'spongebob']))

        # Test forget
        self.assertTrue(self.run_function('pkgutil.forget', [TEST_PKG_NAME]))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MacPkgutilModuleTest)
