# -*- coding: utf-8 -*-
'''
integration tests for mac_ports
'''

# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.helpers import destructiveTest, skip_if_not_root

# Import Salt libs
import salt.utils.path
import salt.utils.platform


@skip_if_not_root
class MacPortsModuleTest(ModuleCase):
    '''
    Validate the mac_ports module
    '''
    AGREE_INSTALLED = False

    def setUp(self):
        '''
        Get current settings
        '''
        if not salt.utils.platform.is_darwin():
            self.skipTest('Test only available on macOS')

        if not salt.utils.path.which('port'):
            self.skipTest('Test requires port binary')

        self.AGREE_INSTALLED = 'agree' in self.run_function('pkg.list_pkgs')
        self.run_function('pkg.refresh_db')

    def tearDown(self):
        '''
        Reset to original settings
        '''
        if not self.AGREE_INSTALLED:
            self.run_function('pkg.remove', ['agree'])

    @destructiveTest
    def test_list_pkgs(self):
        '''
        Test pkg.list_pkgs
        '''
        self.run_function('pkg.install', ['agree'])
        self.assertIsInstance(self.run_function('pkg.list_pkgs'), dict)
        self.assertIn('agree', self.run_function('pkg.list_pkgs'))

    @destructiveTest
    def test_latest_version(self):
        '''
        Test pkg.latest_version
        '''
        self.run_function('pkg.install', ['agree'])
        result = self.run_function('pkg.latest_version',
                                   ['agree'],
                                   refresh=False)
        self.assertIsInstance(result, dict)
        self.assertIn('agree', result)

    @destructiveTest
    def test_remove(self):
        '''
        Test pkg.remove
        '''
        self.run_function('pkg.install', ['agree'])
        removed = self.run_function('pkg.remove', ['agree'])
        self.assertIsInstance(removed, dict)
        self.assertIn('agree', removed)

    @destructiveTest
    def test_install(self):
        '''
        Test pkg.install
        '''
        self.run_function('pkg.remove', ['agree'])
        installed = self.run_function('pkg.install', ['agree'])
        self.assertIsInstance(installed, dict)
        self.assertIn('agree', installed)

    def test_list_upgrades(self):
        '''
        Test pkg.list_upgrades
        '''
        self.assertIsInstance(
            self.run_function('pkg.list_upgrades', refresh=False), dict)

    @destructiveTest
    def test_upgrade_available(self):
        '''
        Test pkg.upgrade_available
        '''
        self.run_function('pkg.install', ['agree'])
        self.assertFalse(self.run_function('pkg.upgrade_available',
                                           ['agree'],
                                           refresh=False))

    def test_refresh_db(self):
        '''
        Test pkg.refresh_db
        '''
        self.assertTrue(self.run_function('pkg.refresh_db'))

    @destructiveTest
    def test_upgrade(self):
        '''
        Test pkg.upgrade
        '''
        results = self.run_function('pkg.upgrade', refresh=False)
        self.assertIsInstance(results, dict)
        self.assertTrue(results['result'])
