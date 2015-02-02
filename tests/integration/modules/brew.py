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
        super(BrewModuleTest, self).setUp()
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
