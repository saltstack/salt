# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
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
import salt.utils
from salt.exceptions import CommandExecutionError

# Brew doesn't support local package installation - So, let's
# Grab some small packages available online for brew
ADD_PKG = 'algol68g'
DEL_PKG = 'acme'


class BrewModuleTest(integration.ModuleCase):
    '''
    Integration tests for the brew module
    '''

    def setUp(self):
        '''
        Sets up the test requirements
        '''
        os_grain = self.run_function('grains.item', ['kernel'])
        brew = salt.utils.which('brew')
        # Must be running on a mac
        if os_grain['kernel'] not in 'Darwin':
            self.skipTest(
                'Test not applicable to \'{kernel}\' kernel'.format(
                    **os_grain
                )
            )
        # Must have brew installed
        if not brew:
            self.skipTest(
                'You must have brew installed to run these tests'
            )

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'You must be logged in as root to run this test')
    @requires_system_grains
    def test_brew_install(self, grains=None):
        '''
        Tests the installation of packages
        '''
        try:
            self.run_function('pkg.install', [ADD_PKG])
            pkg_list = self.run_function('pkg.list_pkgs')
            try:
                self.assertIn(ADD_PKG, pkg_list)
            except AssertionError:
                self.run_function('pkg.remove', [ADD_PKG])
                raise
        except CommandExecutionError:
            self.run_function('pkg.remove', [ADD_PKG])
            raise

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'You must be logged in as root to run this test')
    @requires_system_grains
    def test_remove(self, grains=None):
        '''
        Tests the removal of packages
        '''
        try:
            # Install a package to delete - If unsuccessful, skip the test
            self.run_function('pkg.install', [DEL_PKG])
            pkg_list = self.run_function('pkg.list_pkgs')
            if DEL_PKG not in pkg_list:
                self.run_function('pkg.install', [DEL_PKG])
                self.skipTest('Failed to install a package to delete')

            # Now remove the installed package
            self.run_function('pkg.remove', [DEL_PKG])
            del_list = self.run_function('pkg.list_pkgs')
            try:
                self.assertNotIn(DEL_PKG, del_list)
            except AssertionError:
                raise
        except CommandExecutionError:
            self.run_function('pkg.remove', [DEL_PKG])
            raise

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'You must be logged in as root to run this test')
    @requires_system_grains
    def test_mac_brew_pkg_version(self, grains=None):
        '''
        Test pkg.version for mac. Installs
        a package and then checks we can get
        a version for the installed package.
        '''
        try:
            self.run_function('pkg.install', [ADD_PKG])
            pkg_list = self.run_function('pkg.list_pkgs')
            version = self.run_function('pkg.version', [ADD_PKG])
            try:
                self.assertTrue(version,
                                msg=('version: {0} is empty,\
                                or other issue is present'.format(version)))
                self.assertIn(ADD_PKG, pkg_list,
                              msg=('package: {0} is not in\
                              the list of installed packages: {1}'
                              .format(ADD_PKG, pkg_list)))
                #make sure the version is accurate and is listed in the pkg_list
                self.assertIn(version, str(pkg_list[ADD_PKG]),
                              msg=('The {0} version: {1} is \
                              not listed in the pkg_list: {2}'
                              .format(ADD_PKG, version, pkg_list[ADD_PKG])))
            except AssertionError:
                self.run_function('pkg.remove', [ADD_PKG])
                raise
        except CommandExecutionError:
            self.run_function('pkg.remove', [ADD_PKG])
            raise

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'You must be logged in as root to run this test')
    @requires_system_grains
    def test_mac_brew_refresh_db(self, grains=None):
        '''
        Integration test to ensure pkg.refresh_db works with brew
        '''
        refresh_brew = self.run_function('pkg.refresh_db')
        self.assertTrue(refresh_brew)

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'You must be logged in as root to run this test')
    @requires_system_grains
    def tearDown(self, grains=None):
        '''
        Clean up after tests
        '''
        pkg_list = self.run_function('pkg.list_pkgs')

        # Remove any installed packages
        if ADD_PKG in pkg_list:
            self.run_function('pkg.remove', [ADD_PKG])
        if DEL_PKG in pkg_list:
            self.run_function('pkg.remove', [DEL_PKG])


if __name__ == '__main__':
    from integration import run_tests
    run_tests(BrewModuleTest)
