# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.helpers import destructiveTest
from tests.support.unit import skipIf

# Import Salt libs
import salt.utils.path
import salt.utils.platform


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
        elif salt.utils.platform.is_windows():
            self.service_name = 'Spooler'

        self.pre_srv_status = self.run_function('service.status', [self.service_name])
        self.pre_srv_enabled = True if self.service_name in self.run_function('service.get_enabled') else False

        if salt.utils.path.which(cmd_name) is None and not salt.utils.platform.is_windows():
            self.skipTest('{0} is not installed'.format(cmd_name))

    def tearDown(self):
        post_srv_status = self.run_function('service.status', [self.service_name])
        post_srv_enabled = True if self.service_name in self.run_function('service.get_enabled') else False

        if post_srv_status != self.pre_srv_status:
            if self.pre_srv_status:
                self.run_function('service.enable', [self.service_name])
            else:
                self.run_function('service.disable', [self.service_name])

        if post_srv_enabled != self.pre_srv_enabled:
            if self.pre_srv_enabled:
                self.run_function('service.enable', [self.service_name])
            else:
                self.run_function('service.disable', [self.service_name])
        del self.service_name

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

    def test_service_restart(self):
        '''
        test service.restart
        '''
        self.assertTrue(self.run_function('service.restart', [self.service_name]))

    def test_service_enable(self):
        '''
        test service.get_enabled and service.enable module
        '''
        # disable service before test
        self.assertTrue(self.run_function('service.disable', [self.service_name]))

        self.assertTrue(self.run_function('service.enable', [self.service_name]))
        self.assertIn(self.service_name, self.run_function('service.get_enabled'))

    def test_service_disable(self):
        '''
        test service.get_disabled and service.disable module
        '''
        # enable service before test
        self.assertTrue(self.run_function('service.enable', [self.service_name]))

        self.assertTrue(self.run_function('service.disable', [self.service_name]))
        self.assertIn(self.service_name, self.run_function('service.get_disabled'))

    @skipIf(not salt.utils.platform.is_windows(), 'Windows Only Test')
    def test_service_get_service_name(self):
        '''
        test service.get_service_name
        '''
        ret = self.run_function('service.get_service_name')
        self.assertIn(self.service_name, ret.values())
