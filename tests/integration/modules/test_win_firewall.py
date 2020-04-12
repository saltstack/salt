# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Libs
import salt.utils.platform

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.helpers import destructiveTest
from tests.support.unit import skipIf


@skipIf(not salt.utils.platform.is_windows(), "Tests for only Windows")
class FirewallTest(ModuleCase):
    """
    Validate windows firewall module
    """

    def _pre_firewall_status(self, pre_run):
        post_run = self.run_function("firewall.get_config")
        network = ["Domain", "Public", "Private"]
        # compare the status of the firewall before and after test
        # and re-enable or disable depending on status before test run
        for net in network:
            if post_run[net] != pre_run[net]:
                if pre_run[net]:
                    self.assertTrue(self.run_function("firewall.enable", profile=net))
                else:
                    self.assertTrue(self.run_function("firewall.disable", profile=net))

    @destructiveTest
    def test_firewall_get_config(self):
        """
        test firewall.get_config
        """
        pre_run = self.run_function("firewall.get_config")
        # ensure all networks are enabled then test status
        self.assertTrue(self.run_function("firewall.enable", profile="allprofiles"))
        ret = self.run_function("firewall.get_config")
        network = ["Domain", "Public", "Private"]
        for net in network:
            self.assertTrue(ret[net])
        self._pre_firewall_status(pre_run)

    @destructiveTest
    def test_firewall_disable(self):
        """
        test firewall.disable
        """
        pre_run = self.run_function("firewall.get_config")
        network = "Private"

        ret = self.run_function("firewall.get_config")[network]
        if not ret:
            self.assertTrue(self.run_function("firewall.enable", profile=network))

        self.assertTrue(self.run_function("firewall.disable", profile=network))
        ret = self.run_function("firewall.get_config")[network]
        self.assertFalse(ret)
        self._pre_firewall_status(pre_run)

    @destructiveTest
    def test_firewall_enable(self):
        """
        test firewall.enable
        """
        pre_run = self.run_function("firewall.get_config")
        network = "Private"

        ret = self.run_function("firewall.get_config")[network]
        if ret:
            self.assertTrue(self.run_function("firewall.disable", profile=network))

        self.assertTrue(self.run_function("firewall.enable", profile=network))
        ret = self.run_function("firewall.get_config")[network]
        self.assertTrue(ret)
        self._pre_firewall_status(pre_run)

    def test_firewall_get_rule(self):
        """
        test firewall.get_rule
        """
        rule = "Remote Event Log Management (NP-In)"

        ret = self.run_function("firewall.get_rule", [rule])
        checks = ["Private", "LocalPort", "RemotePort"]
        for check in checks:
            self.assertIn(check, ret[rule])

    @destructiveTest
    def test_firewall_add_delete_rule(self):
        """
        test firewall.add_rule and delete_rule
        """
        rule = "test rule"
        port = "8080"

        # test adding firewall rule
        add_rule = self.run_function("firewall.add_rule", [rule, port])
        ret = self.run_function("firewall.get_rule", [rule])
        self.assertIn(rule, ret[rule])
        self.assertIn(port, ret[rule])

        # test deleting firewall rule
        self.assertTrue(self.run_function("firewall.delete_rule", [rule, port]))
        ret = self.run_function("firewall.get_rule", [rule])
        self.assertNotIn(rule, ret)
        self.assertNotIn(port, ret)
        self.assertIn("No rules match the specified criteria.", ret)
