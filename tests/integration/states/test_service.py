# -*- coding: utf-8 -*-
"""
Tests for the service state
"""
# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import re

# Import salt libs
import salt.utils.path
import salt.utils.platform

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.helpers import destructiveTest
from tests.support.mixins import SaltReturnAssertsMixin

INIT_DELAY = 5


@destructiveTest
class ServiceTest(ModuleCase, SaltReturnAssertsMixin):
    """
    Validate the service state
    """

    def setUp(self):
        self.service_name = "cron"
        cmd_name = "crontab"
        os_family = self.run_function("grains.get", ["os_family"])
        os_release = self.run_function("grains.get", ["osrelease"])
        self.stopped = False
        self.running = True
        if os_family == "RedHat":
            self.service_name = "crond"
        elif os_family == "Arch":
            self.service_name = "sshd"
            cmd_name = "systemctl"
        elif os_family == "MacOS":
            self.service_name = "org.ntp.ntpd"
            if int(os_release.split(".")[1]) >= 13:
                self.service_name = "com.apple.AirPlayXPCHelper"
            self.stopped = ""
            self.running = "[0-9]"
        elif os_family == "Windows":
            self.service_name = "Spooler"

        self.pre_srv_enabled = (
            True
            if self.service_name in self.run_function("service.get_enabled")
            else False
        )
        self.post_srv_disable = False
        if not self.pre_srv_enabled:
            self.run_function("service.enable", name=self.service_name)
            self.post_srv_disable = True

        if os_family != "Windows" and salt.utils.path.which(cmd_name) is None:
            self.skipTest("{0} is not installed".format(cmd_name))

    def tearDown(self):
        if self.post_srv_disable:
            self.run_function("service.disable", name=self.service_name)

    def check_service_status(self, exp_return):
        """
        helper method to check status of service
        """
        check_status = self.run_function("service.status", name=self.service_name)

        try:
            if not re.match(exp_return, check_status):
                self.fail("status of service is not returning correctly")
        except TypeError:
            if check_status is not exp_return:
                self.fail("status of service is not returning correctly")

    def test_service_running(self):
        """
        test service.running state module
        """
        if self.run_function("service.status", name=self.service_name):
            stop_service = self.run_function("service.stop", name=self.service_name)
            self.assertTrue(stop_service)
        self.check_service_status(self.stopped)

        if salt.utils.platform.is_darwin():
            # make sure the service is enabled on macosx
            enable = self.run_function("service.enable", name=self.service_name)

        start_service = self.run_state("service.running", name=self.service_name)
        self.assertTrue(start_service)
        self.check_service_status(self.running)

    def test_service_dead(self):
        """
        test service.dead state module
        """
        start_service = self.run_state("service.running", name=self.service_name)
        self.assertSaltTrueReturn(start_service)
        self.check_service_status(self.running)

        ret = self.run_state("service.dead", name=self.service_name)
        self.assertSaltTrueReturn(ret)
        self.check_service_status(self.stopped)

    def test_service_dead_init_delay(self):
        """
        test service.dead state module with init_delay arg
        """
        start_service = self.run_state("service.running", name=self.service_name)
        self.assertSaltTrueReturn(start_service)
        self.check_service_status(self.running)

        ret = self.run_state(
            "service.dead", name=self.service_name, init_delay=INIT_DELAY
        )
        self.assertSaltTrueReturn(ret)
        self.check_service_status(self.stopped)
