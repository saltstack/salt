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

SERVICE_NAME = 'com.apple.apsd'
SERVICE_ENABLED = False


class MacServiceModuleTest(integration.ModuleCase):
    '''
    Validate the mac_service module
    '''

    def setUp(self):
        '''
        Get current settings
        '''
        global SERVICE_ENABLED

        if not salt.utils.is_darwin():
            self.skipTest('Test only available on Mac OS X')

        if not salt.utils.which('launchctl'):
            self.skipTest('Test requires launchctl binary')

        if not salt.utils.which('plutil'):
            self.skipTest('Test requires plutil binary')

        if salt.utils.get_uid(salt.utils.get_user()) != 0:
            self.skipTest('Test requires root')

        SERVICE_ENABLED = self.run_function('service.enabled', [SERVICE_NAME])

    def tearDown(self):
        '''
        Reset to original settings
        '''
        if SERVICE_ENABLED:
            self.run_function('service.start', [SERVICE_NAME])
        else:
            self.run_function('service.stop', [SERVICE_NAME])

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

    def test_list(self):
        '''
        Test service.list
        '''
        # Expected Functionality
        self.assertIn('PID', self.run_function('service.list'))
        self.assertIn(
            '{',
            self.run_function('service.list', ['com.apple.coreservicesd']))

        # Service not found
        self.assertIn(
            'Service not found',
            self.run_function('service.list', ['spongebob']))

    @destructiveTest
    def test_start(self):
        '''
        Test service.start
        Test service.stop
        Test service.status
        '''
        self.assertTrue(self.run_function('service.start', [SERVICE_NAME]))

        self.assertIn(
            'Service not found',
            self.run_function('service.start', ['spongebob']))

    @destructiveTest
    def test_stop(self):
        '''
        Test service.stop
        '''
        self.assertTrue(self.run_function('service.stop', [SERVICE_NAME]))

        self.assertIn(
            'Service not found',
            self.run_function('service.stop', ['spongebob']))

    @destructiveTest
    def test_status(self):
        '''
        Test service.status
        '''
        # A running service
        self.assertTrue(self.run_function('service.start', [SERVICE_NAME]))
        self.assertTrue(
            self.run_function('service.status', [SERVICE_NAME]).isdigit())

        # A stopped service
        self.assertTrue(self.run_function('service.stop', [SERVICE_NAME]))
        self.assertEqual(
            '',
            self.run_function('service.status', [SERVICE_NAME]))

        # Service not found
        self.assertEqual('', self.run_function('service.status', ['spongebob']))

    def test_available(self):
        '''
        Test service.available
        '''
        self.assertTrue(self.run_function('service.available', [SERVICE_NAME]))
        self.assertFalse(self.run_function('service.available', ['spongebob']))

    def test_missing(self):
        '''
        Test service.missing
        '''
        self.assertFalse(self.run_function('service.missing', [SERVICE_NAME]))
        self.assertTrue(self.run_function('service.missing', ['spongebob']))

    @destructiveTest
    def test_enabled(self):
        '''
        Test service.enabled
        '''
        self.assertTrue(self.run_function('service.start', [SERVICE_NAME]))
        self.assertTrue(self.run_function('service.enabled', [SERVICE_NAME]))

        self.assertTrue(self.run_function('service.stop', [SERVICE_NAME]))
        self.assertFalse(self.run_function('service.enabled', [SERVICE_NAME]))

        self.assertFalse(self.run_function('service.enabled', ['spongebob']))

    @destructiveTest
    def test_disabled(self):
        '''
        Test service.disabled
        '''
        self.assertTrue(self.run_function('service.start', [SERVICE_NAME]))
        self.assertFalse(self.run_function('service.disabled', [SERVICE_NAME]))

        self.assertTrue(self.run_function('service.stop', [SERVICE_NAME]))
        self.assertTrue(self.run_function('service.disabled', [SERVICE_NAME]))

        self.assertTrue(self.run_function('service.enabled', ['spongebob']))

    def test_get_all(self):
        '''
        Test service.get_all
        '''
        services = self.run_function('service.get_all')
        self.assertIsInstance(services, list)
        self.assertIn(SERVICE_NAME, services)

    def test_get_enabled(self):
        '''
        Test service.get_enabled
        '''
        services = self.run_function('service.get_enabled')
        self.assertIsInstance(services, list)
        self.assertIn('com.apple.coreservicesd', services)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MacServiceModuleTest)
