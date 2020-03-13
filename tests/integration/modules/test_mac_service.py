# -*- coding: utf-8 -*-
'''
integration tests for mac_service
'''

# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function

import pytest

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.unit import skipIf

# Import Salt libs
import salt.utils.path
import salt.utils.platform


@skipIf(not salt.utils.platform.is_darwin(), 'Test only available on macOS')
@skipIf(not salt.utils.path.which('launchctl'), 'Test requires launchctl binary')
@skipIf(not salt.utils.path.which('plutil'), 'Test requires plutil binary')
@pytest.mark.skip_if_not_root
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
        assert isinstance(service_info, dict)
        assert service_info['plist']['Label'] == self.SERVICE_NAME

        # Missing Service
        assert 'Service not found' in \
            self.run_function('service.show', ['spongebob'])

    def test_launchctl(self):
        '''
        Test service.launchctl
        '''
        # Expected Functionality
        assert self.run_function('service.launchctl',
                              ['error', 'bootstrap', 64])
        assert self.run_function('service.launchctl',
                              ['error', 'bootstrap', 64],
                              return_stdout=True) == \
            '64: unknown error code'

        # Raise an error
        assert 'Failed to error service' in \
            self.run_function('service.launchctl', ['error', 'bootstrap'])

    def test_list(self):
        '''
        Test service.list
        '''
        # Expected Functionality
        assert 'PID' in self.run_function('service.list')
        assert '{' in \
            self.run_function('service.list', ['com.apple.coreservicesd'])

        # Service not found
        assert 'Service not found' in \
            self.run_function('service.list', ['spongebob'])

    @pytest.mark.destructive_test
    def test_enable(self):
        '''
        Test service.enable
        '''
        assert self.run_function('service.enable', [self.SERVICE_NAME])

        assert 'Service not found' in \
            self.run_function('service.enable', ['spongebob'])

    @pytest.mark.destructive_test
    def test_disable(self):
        '''
        Test service.disable
        '''
        assert self.run_function('service.disable', [self.SERVICE_NAME])

        assert 'Service not found' in \
            self.run_function('service.disable', ['spongebob'])

    @pytest.mark.destructive_test
    def test_start(self):
        '''
        Test service.start
        Test service.stop
        Test service.status
        '''
        assert self.run_function('service.start', [self.SERVICE_NAME])

        assert 'Service not found' in \
            self.run_function('service.start', ['spongebob'])

    @pytest.mark.destructive_test
    def test_stop(self):
        '''
        Test service.stop
        '''
        assert self.run_function('service.stop', [self.SERVICE_NAME])

        assert 'Service not found' in \
            self.run_function('service.stop', ['spongebob'])

    @pytest.mark.destructive_test
    def test_status(self):
        '''
        Test service.status
        '''
        # A running service
        assert self.run_function('service.start', [self.SERVICE_NAME])
        assert self.run_function('service.status', [self.SERVICE_NAME]).isdigit()

        # A stopped service
        assert self.run_function('service.stop', [self.SERVICE_NAME])
        assert '' == \
            self.run_function('service.status', [self.SERVICE_NAME])

        # Service not found
        assert '' == self.run_function('service.status', ['spongebob'])

    def test_available(self):
        '''
        Test service.available
        '''
        assert self.run_function('service.available', [self.SERVICE_NAME])
        assert not self.run_function('service.available', ['spongebob'])

    def test_missing(self):
        '''
        Test service.missing
        '''
        assert not self.run_function('service.missing', [self.SERVICE_NAME])
        assert self.run_function('service.missing', ['spongebob'])

    @pytest.mark.destructive_test
    def test_enabled(self):
        '''
        Test service.enabled
        '''
        assert self.run_function('service.start', [self.SERVICE_NAME])
        assert self.run_function('service.enabled', [self.SERVICE_NAME])

        assert self.run_function('service.stop', [self.SERVICE_NAME])
        assert not self.run_function('service.enabled', [self.SERVICE_NAME])

        assert not self.run_function('service.enabled', ['spongebob'])

    @pytest.mark.destructive_test
    def test_disabled(self):
        '''
        Test service.disabled
        '''
        SERVICE_NAME = 'com.apple.nfsd'
        assert self.run_function('service.start', [SERVICE_NAME])
        assert not self.run_function('service.disabled', [SERVICE_NAME])

        assert self.run_function('service.disable', [SERVICE_NAME])
        assert self.run_function('service.disabled', [SERVICE_NAME])
        assert self.run_function('service.enable', [SERVICE_NAME])

        assert not self.run_function('service.disabled', ['spongebob'])

    def test_get_all(self):
        '''
        Test service.get_all
        '''
        services = self.run_function('service.get_all')
        assert isinstance(services, list)
        assert self.SERVICE_NAME in services

    def test_get_enabled(self):
        '''
        Test service.get_enabled
        '''
        services = self.run_function('service.get_enabled')
        assert isinstance(services, list)
        assert 'com.apple.coreservicesd' in services
