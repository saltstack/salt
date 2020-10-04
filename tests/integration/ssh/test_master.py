"""
Simple Smoke Tests for Connected SSH minions
"""

from tests.support.case import SSHCase
from tests.support.helpers import requires_system_grains, skip_if_not_root, slowTest


class SSHMasterTestCase(SSHCase):
    """
    Test ssh master functionality
    """

    @slowTest
    def test_can_it_ping(self):
        """
        Ensure the proxy can ping
        """
        ret = self.run_function("test.ping")
        self.assertEqual(ret, True)

    @requires_system_grains
    @skip_if_not_root
    @slowTest
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
        self.run_function("service.enable", [service])
        ret = self.run_function("service.get_all")
        self.assertIn(service, ret)
        self.run_function("service.stop", [service])
        ret = self.run_function("service.status", [service])
        self.assertFalse(ret)
        self.run_function("service.start", [service])
        ret = self.run_function("service.status", [service])
        self.assertTrue(ret)

    @slowTest
    def test_state_apply(self):
        ret = self.run_function("state.apply", ["core"])
        for key, value in ret.items():
            self.assertTrue(value["result"])

    @slowTest
    def test_state_highstate(self):
        ret = self.run_function("state.highstate")
        for key, value in ret.items():
            self.assertTrue(value["result"])
