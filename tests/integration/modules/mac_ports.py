# -*- coding: utf-8 -*-
'''
integration tests for mac_ports
'''

# Import python libs
from __future__ import absolute_import, print_function

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath, destructiveTest
ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils


class MacPortsModuleTest(integration.ModuleCase):
    '''
    Validate the mac_ports module
    '''

    def setUp(self):
        '''
        Get current settings
        '''
        if not salt.utils.is_darwin():
            self.skipTest('Test only available on Mac OS X')

        if not salt.utils.which('port'):
            self.skipTest('Test requires port binary')

        if salt.utils.get_uid(salt.utils.get_user()) != 0:
            self.skipTest('Test requires root')

    def tearDown(self):
        '''
        Reset to original settings
        '''
        self.run_function('pkg.remove', [''], pkgs='["agree","cowsay","chef"]')

    def test_list_pkgs(self):
        '''
        Test pkg.list_pkgs
        '''
        self.run_function('pkg.install', [''], pkgs='["agree","cowsay","chef"]')
        self.assertIsInstance(self.run_function('pkg.list_pkgs'), dict)
        self.assertIn('agree', self.run_function('pkg.list_pkgs'))

    def test_latest_version(self):
        '''
        Test pkg.latest_version
        '''
        self.run_function('pkg.install', [''], pkgs='["agree","cowsay","chef"]')
        self.assertIsInstance(
            self.run_function('pkg.latest_version', ['agree']), dict)
        self.assertIn(
            'agree',
            self.run_function('pkg.latest_version', ['agree']))

    def test_remove(self):
        '''
        Test pkg.remove
        '''
        self.run_function('pkg.install', [''], pkgs='["agree","cowsay","chef"]')
        removed = self.run_function('pkg.remove', ['agree'])
        self.assertIsInstance(removed, dict)
        self.assertIn('agree', removed)

    def test_install(self):
        '''
        Test pkg.install
        '''
        self.run_function('pkg.remove', [''], pkgs='["agree","cowsay","chef"]')
        installed = self.run_function('pkg.install', ['agree'])
        self.assertIsInstance(installed, dict)
        self.assertIn('agree', installed)

    def test_list_upgrades(self):
        '''
        Test pkg.list_upgrades
        '''
        self.assertIsInstance(self.run_function('pkg.list_upgrades'), dict)

    def test_upgrade_available(self):
        '''
        Test pkg.upgrade_available
        '''
        self.run_function('pkg.install', ['agree'])
        self.assertFalse(self.run_function('pkg.upgrade_available', ['agree']))

    def test_refresh_db(self):
        '''
        Test pkg.refresh_db
        '''
        self.assertTrue(self.run_function('pkg.refresh_db'))

    def test_upgrade(self):
        '''
        Test pkg.upgrade
        '''
        results = self.run_function('pkg.upgrade')
        self.assertIsInstance(results, dict)
        self.assertTrue(results['result'])


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MacPortsModuleTest)
