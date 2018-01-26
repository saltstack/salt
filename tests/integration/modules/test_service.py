# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.helpers import destructiveTest

# Import Salt libs
import salt.utils.path


@destructiveTest
class ServiceModuleTest(ModuleCase):
    '''
    Module testing the service module
    '''
    def setUp(self):
        self.service_name = 'cron'
        cmd_name = 'crontab'
        os_family = self.run_function('grains.get', ['os_family'])
        os_release = self.run_function('grains.get', ['osrelease'])
        if os_family == 'RedHat':
            self.service_name = 'crond'
        elif os_family == 'Arch':
            self.service_name = 'sshd'
            cmd_name = 'systemctl'
        elif os_family == 'MacOS':
            self.service_name = 'org.ntp.ntpd'
            if int(os_release.split('.')[1]) >= 13:
                self.service_name = 'com.apple.AirPlayXPCHelper'

        if salt.utils.path.which(cmd_name) is None:
            self.skipTest('{0} is not installed'.format(cmd_name))

    def test_service_status_running(self):
        '''
        test service.status execution module
        when service is running
        '''
        self.run_function('service.start', [self.service_name])
        check_service = self.run_function('service.status', [self.service_name])
        self.assertTrue(check_service)

    def test_service_status_dead(self):
        '''
        test service.status execution module
        when service is dead
        '''
        self.run_function('service.stop', [self.service_name])
        check_service = self.run_function('service.status', [self.service_name])
        self.assertFalse(check_service)
