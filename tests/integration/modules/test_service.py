# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.unit import skipIf
from tests.support.helpers import destructiveTest

# Import Salt libs
import salt.utils

SERVICE_NAME = 'docker'


@destructiveTest
@skipIf(salt.utils.which('docker') is None, 'docker is not installed')
class ServiceModuleTest(ModuleCase):
    '''
    Module testing the service module
    '''
    def test_service_status_running(self):
        '''
        test service.status execution module
        when service is running
        '''
        start_service = self.run_function('service.start', [SERVICE_NAME])

        check_service = self.run_function('service.status', [SERVICE_NAME])
        self.assertTrue(check_service)

    def test_service_status_dead(self):
        '''
        test service.status execution module
        when service is dead
        '''
        stop_service = self.run_function('service.stop', [SERVICE_NAME])

        check_service = self.run_function('service.status', [SERVICE_NAME])
        self.assertFalse(check_service)
