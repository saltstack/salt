# -*- coding: utf-8 -*-
'''
Tests for the service state
'''
# Import python libs
from __future__ import absolute_import

# Import Salt Testing libs
import tests.integration as integration
from tests.support.unit import skipIf
from tests.support.helpers import destructiveTest

# Import salt libs
import salt.utils

INIT_DELAY = 5
SERVICE_NAME = 'crond'


@destructiveTest
@skipIf(salt.utils.which('crond') is None, 'crond not installed')
class ServiceTest(integration.ModuleCase,
                  integration.SaltReturnAssertsMixin):
    '''
    Validate the service state
    '''
    def check_service_status(self, exp_return):
        '''
        helper method to check status of service
        '''
        check_status = self.run_function('service.status', name=SERVICE_NAME)
        if check_status is not exp_return:
            self.fail('status of service is not returning correctly')

    def test_service_dead(self):
        '''
        test service.dead state module
        '''
        start_service = self.run_state('service.running', name=SERVICE_NAME)
        self.assertSaltTrueReturn(start_service)
        self.check_service_status(True)

        ret = self.run_state('service.dead', name=SERVICE_NAME)
        self.assertSaltTrueReturn(ret)
        self.check_service_status(False)

    def test_service_dead_init_delay(self):
        '''
        test service.dead state module with init_delay arg
        '''
        start_service = self.run_state('service.running', name=SERVICE_NAME)
        self.assertSaltTrueReturn(start_service)
        self.check_service_status(True)

        ret = self.run_state('service.dead', name=SERVICE_NAME,
                             init_delay=INIT_DELAY)
        self.assertSaltTrueReturn(ret)
        self.check_service_status(False)
