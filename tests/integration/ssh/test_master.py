"""
Simple Smoke Tests for Connected SSH minions
"""

import pytest
from saltfactories.utils.tempfiles import temp_file
from tests.support.case import SSHCase
from tests.support.helpers import requires_system_grains
from tests.support.runtests import RUNTIME_VARS


class SSHMasterTestCase(SSHCase):
    """
    Test ssh master functionality
    """

    @pytest.mark.slow_test
    def test_can_it_ping(self):
        """
        Ensure the proxy can ping
        """
        ret = self.run_function("test.ping")
        self.assertEqual(ret, True)

    @requires_system_grains
    @pytest.mark.slow_test
    @pytest.mark.skip_if_not_root
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

    @pytest.mark.slow_test
    def test_state_apply(self):
        core_state = """
        {}/testfile:
          file:
            - managed
            - source: salt://testfile
            - makedirs: true
            """.format(
            RUNTIME_VARS.TMP
        )

        with temp_file("core.sls", core_state, RUNTIME_VARS.TMP_BASEENV_STATE_TREE):
            ret = self.run_function("state.apply", ["core"])
            for key, value in ret.items():
                self.assertTrue(value["result"])

    @pytest.mark.slow_test
    def test_state_highstate(self):
        top_sls = """
        base:
          '*':
            - core
            """

        core_state = """
        {}/testfile:
          file:
            - managed
            - source: salt://testfile
            - makedirs: true
            """.format(
            RUNTIME_VARS.TMP
        )

        with temp_file(
            "top.sls", top_sls, RUNTIME_VARS.TMP_BASEENV_STATE_TREE
        ), temp_file("core.sls", core_state, RUNTIME_VARS.TMP_BASEENV_STATE_TREE):
            ret = self.run_function("state.highstate")
            for key, value in ret.items():
                self.assertTrue(value["result"])
