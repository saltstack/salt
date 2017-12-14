# -*- coding: utf-8 -*-
'''
Tests for the service state
'''
# Import python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.helpers import destructiveTest
from tests.support.mixins import SaltReturnAssertsMixin

# Import salt libs
import salt.utils.path

INIT_DELAY = 5


@destructiveTest
class ServiceTest(ModuleCase, SaltReturnAssertsMixin):
    '''
    Validate the service state
    '''
    def setUp(self):
        self.service_name = 'cron'
        cmd_name = 'crontab'
        os_family = self.run_function('grains.get', ['os_family'])
        if os_family == 'RedHat':
            self.service_name = 'crond'
        elif os_family == 'Arch':
            self.service_name = 'systemd-journald'
            cmd_name = 'systemctl'

        if salt.utils.path.which(cmd_name) is None:
            self.skipTest('{0} is not installed'.format(cmd_name))

    def check_service_status(self, exp_return):
        '''
        helper method to check status of service
        '''
        check_status = self.run_function('service.status',
                                         name=self.service_name)
        if check_status is not exp_return:
            self.fail('status of service is not returning correctly')

    def test_service_running(self):
        '''
        test service.running state module
        '''
        stop_service = self.run_function('service.stop', self.service_name)
        self.assertTrue(stop_service)
        self.check_service_status(False)

        start_service = self.run_state('service.running',
                                       name=self.service_name)
        self.assertTrue(start_service)
        self.check_service_status(True)

    def test_service_dead(self):
        '''
        test service.dead state module
        '''
        start_service = self.run_state('service.running',
                                       name=self.service_name)
        self.assertSaltTrueReturn(start_service)
        self.check_service_status(True)

        ret = self.run_state('service.dead', name=self.service_name)
        self.assertSaltTrueReturn(ret)
        self.check_service_status(False)

    def test_service_dead_init_delay(self):
        '''
        test service.dead state module with init_delay arg
        '''
        start_service = self.run_state('service.running',
                                       name=self.service_name)
        self.assertSaltTrueReturn(start_service)
        self.check_service_status(True)

        ret = self.run_state('service.dead', name=self.service_name,
                             init_delay=INIT_DELAY)
        self.assertSaltTrueReturn(ret)
        self.check_service_status(False)
