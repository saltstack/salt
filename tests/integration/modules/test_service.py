# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.unit import skipIf
from tests.support.helpers import destructiveTest

# Import Salt libs
import salt.utils


@destructiveTest
@skipIf(salt.utils.which('docker') is None, 'docker is not installed')
class ServiceModuleTest(ModuleCase):
    '''
    Module testing the service module
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

        if salt.utils.which(cmd_name) is None:
            self.skipTest('{0} is not installed'.format(cmd_name))

    def test_service_status_running(self):
        '''
        test service.status execution module
        when service is running
        '''
        start_service = self.run_function('service.start', [self.service_name])

        check_service = self.run_function('service.status', [self.service_name])
        self.assertTrue(check_service)

    def test_service_status_dead(self):
        '''
        test service.status execution module
        when service is dead
        '''
        stop_service = self.run_function('service.stop', [self.service_name])

        check_service = self.run_function('service.status', [self.service_name])
        self.assertFalse(check_service)
