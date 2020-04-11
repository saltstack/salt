# -*- coding: utf-8 -*-
"""
Simple Smoke Tests for Connected SSH minions
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.case import SSHCase
from tests.support.helpers import requires_system_grains, skip_if_not_root


class SSHMasterTestCase(SSHCase):
    """
    Test ssh master functionality
    """

    def test_can_it_ping(self):
        """
        Ensure the proxy can ping
        """
        ret = self.run_function("test.ping")
        self.assertEqual(ret, True)

    @requires_system_grains
    @skip_if_not_root
    def test_service(self, grains):
        service = "cron"
        os_family = grains["os_family"]
        os_release = grains["osrelease"]
        if os_family == "RedHat":
            service = "crond"
        elif os_family == "Arch":
            service = "sshd"
        elif os_family == "MacOS":
            service = "org.ntp.ntpd"
            if int(os_release.split(".")[1]) >= 13:
                service = "com.apple.AirPlayXPCHelper"
        ret = self.run_function("service.get_all")
        self.assertIn(service, ret)
        self.run_function("service.stop", [service])
        ret = self.run_function("service.status", [service])
        self.assertFalse(ret)
        self.run_function("service.start", [service])
        ret = self.run_function("service.status", [service])
        self.assertTrue(ret)

    @requires_system_grains
    def test_grains_items(self, grains):
        os_family = grains["os_family"]
        ret = self.run_function("grains.items")
        if os_family == "MacOS":
            self.assertEqual(ret["kernel"], "Darwin")
        else:
            self.assertEqual(ret["kernel"], "Linux")

    def test_state_apply(self):
        ret = self.run_function("state.apply", ["core"])
        for key, value in ret.items():
            self.assertTrue(value["result"])

    def test_state_highstate(self):
        ret = self.run_function("state.highstate")
        for key, value in ret.items():
            self.assertTrue(value["result"])
