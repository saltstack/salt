# -*- coding: utf-8 -*-
'''
integration tests for mac_service
'''

# Import python libs
from __future__ import absolute_import, print_function

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath, destructiveTest
ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils

SERVICE_NAME = 'org.cups.cupsd'


class MacServiceModuleTest(integration.ModuleCase):
    '''
    Validate the mac_service module
    '''

    def setUp(self):
        '''
        Get current settings
        '''
        if not salt.utils.is_darwin():
            self.skipTest('Test only available on Mac OS X')

        if not salt.utils.which('launchctl'):
            self.skipTest('Test requires launchctl binary')

        if not salt.utils.which('plutil'):
            self.skipTest('Test requires plutil binary')

        if salt.utils.get_uid(salt.utils.get_user()) != 0:
            self.skipTest('Test requires root')

    def tearDown(self):
        '''
        Reset to original settings
        '''
        pass

    def test_show(self):
        '''
        Test service.show
        '''
        # Existing Service
        service_info = self.run_function('service.show', [SERVICE_NAME])
        self.assertIsInstance(service_info, dict)
        self.assertEqual(service_info['plist']['Label'], SERVICE_NAME)

        # Missing Service
        self.assertIn(
            'Service not found',
            self.run_function('service.show', ['spongebob']))

    def test_launchctl(self):
        '''
        Test service.launchctl
        '''
        # Expected Functionality
        self.assertTrue(
            self.run_function('service.launchctl', ['error', 'bootstrap', 64]))
        self.assertEqual(
            self.run_function('service.launchctl', ['error',
                                                    'bootstrap',
                                                    64,
                                                    'return_stdout=True']),
            '64: unknown error code')

        # Raise an error
        self.assertIn(
            ' Failed to error service',
            self.run_function('service.launchctl', ['error']))

    def


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MacServiceModuleTest)
