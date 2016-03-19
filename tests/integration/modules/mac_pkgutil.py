# -*- coding: utf-8 -*-
'''
integration tests for mac_pkgutil
'''

# Import python libs
from __future__ import absolute_import, print_function

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath, destructiveTest
ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils


def disabled(f):
    def _decorator(f):
        print('{0} has been disabled'.format(f.__name__))
    return _decorator(f)


class MacPkgutilModuleTest(integration.ModuleCase):
    '''
    Validate the mac_pkgutil module
    '''

    def setUp(self):
        '''
        Get current settings
        '''
        if not salt.utils.is_darwin():
            self.skipTest('Test only available on Mac OS X')

        if not salt.utils.which('pkgutil'):
            self.skipTest('Test requires pkgutil binary')

        if salt.utils.get_uid(salt.utils.get_user()) != 0:
            self.skipTest('Test requires root')

    def tearDown(self):
        '''
        Reset to original settings
        '''

    def test_list(self):
        '''
        Test darwin_pkgutil.list
        '''
        self.assertIsInstance(self.run_function('darwin_pkgutil.list'), list)

    def test_is_installed(self):
        '''
        Test darwin_pkgutil.is_installed
        '''
        # Test Package is installed
        self.assertTrue(
            self.run_function('darwin_pkgutil.is_installed',
                              ['com.apple.atrun']))

        # Test Package is not installed
        self.assertFalse(
            self.run_function('darwin_pkgutil.is_installed', ['spongebob']))

    @destructiveTest
    def test_install(self):
        '''
        Test darwin_pkgutil.install
        '''
        # Test if installed
        self.assertFalse(
            self.run_function('darwin_pkgutil.is_installed', ['????']))

        # Download the package from somewhere
        self.run_function('cp.get_url', ['????', '????'])

        # Test install
        self.assertTrue(self.run_function('darwin_pkgutil.install', ['?????']))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MacPkgutilModuleTest)
