# -*- coding: utf-8 -*-
'''
integration tests for mac_service
'''

# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.unit import skipIf
from tests.support.helpers import destructiveTest, skip_if_not_root

# Import Salt libs
import salt.utils.path
import salt.utils.platform


@skipIf(not salt.utils.platform.is_darwin(), 'Test only available on macOS')
@skipIf(not salt.utils.path.which('launchctl'), 'Test requires launchctl binary')
@skipIf(not salt.utils.path.which('plutil'), 'Test requires plutil binary')
@skip_if_not_root
class MacServiceModuleTest(ModuleCase):
    '''
    Validate the mac_service module
    '''
    SERVICE_NAME = 'com.apple.apsd'
    SERVICE_ENABLED = False

    def setUp(self):
        '''
        Get current state of the test service
        '''
        self.SERVICE_ENABLED = self.run_function('service.enabled',
                                                 [self.SERVICE_NAME])

    def tearDown(self):
        '''
        Reset the test service to the original state
        '''
        if self.SERVICE_ENABLED:
            self.run_function('service.start', [self.SERVICE_NAME])
            self.run_function('service.enable', [self.SERVICE_NAME])
        else:
            self.run_function('service.stop', [self.SERVICE_NAME])
            self.run_function('service.disable', [self.SERVICE_NAME])

    def test_show(self):
        '''
        Test service.show
        '''
        # Existing Service
        service_info = self.run_function('service.show', [self.SERVICE_NAME])
        self.assertIsInstance(service_info, dict)
        self.assertEqual(service_info['plist']['Label'], self.SERVICE_NAME)

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
            self.run_function('service.launchctl',
                              ['error', 'bootstrap', 64]))
        self.assertEqual(
            self.run_function('service.launchctl',
                              ['error', 'bootstrap', 64],
                              return_stdout=True),
            '64: unknown error code')

        # Raise an error
        self.assertIn(
            'Failed to error service',
            self.run_function('service.launchctl', ['error', 'bootstrap']))

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
    def test_enable(self):
        '''
        Test service.enable
        '''
        self.assertTrue(
            self.run_function('service.enable', [self.SERVICE_NAME]))

        self.assertIn(
            'Service not found',
            self.run_function('service.enable', ['spongebob']))

    @destructiveTest
    def test_disable(self):
        '''
        Test service.disable
        '''
        self.assertTrue(
            self.run_function('service.disable', [self.SERVICE_NAME]))

        self.assertIn(
            'Service not found',
            self.run_function('service.disable', ['spongebob']))

    @destructiveTest
    def test_start(self):
        '''
        Test service.start
        Test service.stop
        Test service.status
        '''
        self.assertTrue(self.run_function('service.start', [self.SERVICE_NAME]))

        self.assertIn(
            'Service not found',
            self.run_function('service.start', ['spongebob']))

    @destructiveTest
    def test_stop(self):
        '''
        Test service.stop
        '''
        self.assertTrue(self.run_function('service.stop', [self.SERVICE_NAME]))

        self.assertIn(
            'Service not found',
            self.run_function('service.stop', ['spongebob']))

    @destructiveTest
    def test_status(self):
        '''
        Test service.status
        '''
        # A running service
        self.assertTrue(self.run_function('service.start', [self.SERVICE_NAME]))
        self.assertTrue(
            self.run_function('service.status', [self.SERVICE_NAME]).isdigit())

        # A stopped service
        self.assertTrue(self.run_function('service.stop', [self.SERVICE_NAME]))
        self.assertEqual(
            '',
            self.run_function('service.status', [self.SERVICE_NAME]))

        # Service not found
        self.assertEqual('', self.run_function('service.status', ['spongebob']))

    def test_available(self):
        '''
        Test service.available
        '''
        self.assertTrue(
            self.run_function('service.available', [self.SERVICE_NAME]))
        self.assertFalse(self.run_function('service.available', ['spongebob']))

    def test_missing(self):
        '''
        Test service.missing
        '''
        self.assertFalse(self.run_function('service.missing', [self.SERVICE_NAME]))
        self.assertTrue(self.run_function('service.missing', ['spongebob']))

    @destructiveTest
    def test_enabled(self):
        '''
        Test service.enabled
        '''
        self.assertTrue(self.run_function('service.start', [self.SERVICE_NAME]))
        self.assertTrue(
            self.run_function('service.enabled', [self.SERVICE_NAME]))

        self.assertTrue(self.run_function('service.stop', [self.SERVICE_NAME]))
        self.assertFalse(
            self.run_function('service.enabled', [self.SERVICE_NAME]))

        self.assertFalse(self.run_function('service.enabled', ['spongebob']))

    @destructiveTest
    def test_disabled(self):
        '''
        Test service.disabled
        '''
        SERVICE_NAME = 'com.apple.nfsd'
        self.assertTrue(self.run_function('service.start', [SERVICE_NAME]))
        self.assertFalse(
            self.run_function('service.disabled', [SERVICE_NAME]))

        self.assertTrue(self.run_function('service.disable', [SERVICE_NAME]))
        self.assertTrue(
            self.run_function('service.disabled', [SERVICE_NAME]))
        self.assertTrue(self.run_function('service.enable', [SERVICE_NAME]))

        self.assertFalse(self.run_function('service.disabled', ['spongebob']))

    def test_get_all(self):
        '''
        Test service.get_all
        '''
        services = self.run_function('service.get_all')
        self.assertIsInstance(services, list)
        self.assertIn(self.SERVICE_NAME, services)

    def test_get_enabled(self):
        '''
        Test service.get_enabled
        '''
        services = self.run_function('service.get_enabled')
        self.assertIsInstance(services, list)
        self.assertIn('com.apple.coreservicesd', services)
