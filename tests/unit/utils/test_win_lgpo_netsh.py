# -*- coding: utf-8 -*-

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.utils.platform
import salt.utils.win_lgpo_netsh as win_lgpo_netsh
from salt.exceptions import CommandExecutionError

# Import Salt Testing Libs
from tests.support.helpers import destructiveTest
from tests.support.unit import TestCase, skipIf


@skipIf(not salt.utils.platform.is_windows(), "System is not Windows")
class WinLgpoNetshTestCase(TestCase):
    def test_get_settings_firewallpolicy_local(self):
        ret = win_lgpo_netsh.get_settings(
            profile="domain", section="firewallpolicy", store="local"
        )
        self.assertIn("Inbound", ret)
        self.assertIn("Outbound", ret)

    def test_get_settings_firewallpolicy_lgpo(self):
        ret = win_lgpo_netsh.get_settings(
            profile="domain", section="firewallpolicy", store="lgpo"
        )
        self.assertIn("Inbound", ret)
        self.assertIn("Outbound", ret)

    def test_get_settings_logging_local(self):
        ret = win_lgpo_netsh.get_settings(
            profile="domain", section="logging", store="local"
        )
        self.assertIn("FileName", ret)
        self.assertIn("LogAllowedConnections", ret)
        self.assertIn("LogDroppedConnections", ret)
        self.assertIn("MaxFileSize", ret)

    def test_get_settings_logging_lgpo(self):
        ret = win_lgpo_netsh.get_settings(
            profile="domain", section="logging", store="lgpo"
        )
        self.assertIn("FileName", ret)
        self.assertIn("LogAllowedConnections", ret)
        self.assertIn("LogDroppedConnections", ret)
        self.assertIn("MaxFileSize", ret)

    def test_get_settings_settings_local(self):
        ret = win_lgpo_netsh.get_settings(
            profile="domain", section="settings", store="local"
        )
        self.assertIn("InboundUserNotification", ret)
        self.assertIn("LocalConSecRules", ret)
        self.assertIn("LocalFirewallRules", ret)
        self.assertIn("RemoteManagement", ret)
        self.assertIn("UnicastResponseToMulticast", ret)

    def test_get_settings_settings_lgpo(self):
        ret = win_lgpo_netsh.get_settings(
            profile="domain", section="settings", store="lgpo"
        )
        self.assertIn("InboundUserNotification", ret)
        self.assertIn("LocalConSecRules", ret)
        self.assertIn("LocalFirewallRules", ret)
        self.assertIn("RemoteManagement", ret)
        self.assertIn("UnicastResponseToMulticast", ret)

    def test_get_settings_state_local(self):
        ret = win_lgpo_netsh.get_settings(
            profile="domain", section="state", store="local"
        )
        self.assertIn("State", ret)

    def test_get_settings_state_lgpo(self):
        ret = win_lgpo_netsh.get_settings(
            profile="domain", section="state", store="lgpo"
        )
        self.assertIn("State", ret)

    def test_get_all_settings_local(self):
        ret = win_lgpo_netsh.get_all_settings(profile="domain", store="local")

        self.assertIn("Inbound", ret)
        self.assertIn("Outbound", ret)
        self.assertIn("FileName", ret)
        self.assertIn("LogAllowedConnections", ret)
        self.assertIn("LogDroppedConnections", ret)
        self.assertIn("MaxFileSize", ret)
        self.assertIn("InboundUserNotification", ret)
        self.assertIn("LocalConSecRules", ret)
        self.assertIn("LocalFirewallRules", ret)
        self.assertIn("RemoteManagement", ret)
        self.assertIn("UnicastResponseToMulticast", ret)
        self.assertIn("State", ret)

    def test_get_all_settings_lgpo(self):
        ret = win_lgpo_netsh.get_all_settings(profile="domain", store="local")

        self.assertIn("Inbound", ret)
        self.assertIn("Outbound", ret)
        self.assertIn("FileName", ret)
        self.assertIn("LogAllowedConnections", ret)
        self.assertIn("LogDroppedConnections", ret)
        self.assertIn("MaxFileSize", ret)
        self.assertIn("InboundUserNotification", ret)
        self.assertIn("LocalConSecRules", ret)
        self.assertIn("LocalFirewallRules", ret)
        self.assertIn("RemoteManagement", ret)
        self.assertIn("UnicastResponseToMulticast", ret)
        self.assertIn("State", ret)

    def test_get_all_profiles_local(self):
        ret = win_lgpo_netsh.get_all_profiles(store="local")
        self.assertIn("Domain Profile", ret)
        self.assertIn("Private Profile", ret)
        self.assertIn("Public Profile", ret)

    def test_get_all_profiles_lgpo(self):
        ret = win_lgpo_netsh.get_all_profiles(store="lgpo")
        self.assertIn("Domain Profile", ret)
        self.assertIn("Private Profile", ret)
        self.assertIn("Public Profile", ret)

    @destructiveTest
    def test_set_firewall_settings_inbound_local(self):
        current = win_lgpo_netsh.get_settings(
            profile="domain", section="firewallpolicy", store="local"
        )["Inbound"]
        try:
            ret = win_lgpo_netsh.set_firewall_settings(
                profile="domain", inbound="allowinbound", store="local"
            )
            self.assertTrue(ret)
            new = win_lgpo_netsh.get_settings(
                profile="domain", section="firewallpolicy", store="local"
            )["Inbound"]
            self.assertEqual("AllowInbound", new)
        finally:
            ret = win_lgpo_netsh.set_firewall_settings(
                profile="domain", inbound=current, store="local"
            )
            self.assertTrue(ret)

    @destructiveTest
    def test_set_firewall_settings_inbound_local_notconfigured(self):
        current = win_lgpo_netsh.get_settings(
            profile="domain", section="firewallpolicy", store="local"
        )["Inbound"]
        try:
            self.assertRaises(
                CommandExecutionError,
                win_lgpo_netsh.set_firewall_settings,
                profile="domain",
                inbound="notconfigured",
                store="local",
            )
        finally:
            ret = win_lgpo_netsh.set_firewall_settings(
                profile="domain", inbound=current, store="local"
            )
            self.assertTrue(ret)

    @destructiveTest
    def test_set_firewall_settings_inbound_lgpo_notconfigured(self):
        current = win_lgpo_netsh.get_settings(
            profile="domain", section="firewallpolicy", store="lgpo"
        )["Inbound"]
        try:
            ret = win_lgpo_netsh.set_firewall_settings(
                profile="domain", inbound="notconfigured", store="lgpo"
            )
            self.assertTrue(ret)
            new = win_lgpo_netsh.get_settings(
                profile="domain", section="firewallpolicy", store="lgpo"
            )["Inbound"]
            self.assertEqual("NotConfigured", new)
        finally:
            ret = win_lgpo_netsh.set_firewall_settings(
                profile="domain", inbound=current, store="lgpo"
            )
            self.assertTrue(ret)

    @destructiveTest
    def test_set_firewall_settings_outbound_local(self):
        current = win_lgpo_netsh.get_settings(
            profile="domain", section="firewallpolicy", store="local"
        )["Outbound"]
        try:
            ret = win_lgpo_netsh.set_firewall_settings(
                profile="domain", outbound="allowoutbound", store="local"
            )
            self.assertTrue(ret)
            new = win_lgpo_netsh.get_settings(
                profile="domain", section="firewallpolicy", store="local"
            )["Outbound"]
            self.assertEqual("AllowOutbound", new)
        finally:
            ret = win_lgpo_netsh.set_firewall_settings(
                profile="domain", outbound=current, store="local"
            )
            self.assertTrue(ret)

    @destructiveTest
    def test_set_firewall_logging_allowed_local_enable(self):
        current = win_lgpo_netsh.get_settings(
            profile="domain", section="logging", store="local"
        )["LogAllowedConnections"]
        try:
            ret = win_lgpo_netsh.set_logging_settings(
                profile="domain",
                setting="allowedconnections",
                value="enable",
                store="local",
            )
            self.assertTrue(ret)
            new = win_lgpo_netsh.get_settings(
                profile="domain", section="logging", store="local"
            )["LogAllowedConnections"]
            self.assertEqual("Enable", new)
        finally:
            ret = win_lgpo_netsh.set_logging_settings(
                profile="domain",
                setting="allowedconnections",
                value=current,
                store="local",
            )
            self.assertTrue(ret)

    @destructiveTest
    def test_set_firewall_logging_allowed_local_notconfigured(self):
        current = win_lgpo_netsh.get_settings(
            profile="domain", section="logging", store="local"
        )["LogAllowedConnections"]
        try:
            self.assertRaises(
                CommandExecutionError,
                win_lgpo_netsh.set_logging_settings,
                profile="domain",
                setting="allowedconnections",
                value="notconfigured",
                store="local",
            )
        finally:
            ret = win_lgpo_netsh.set_logging_settings(
                profile="domain",
                setting="allowedconnections",
                value=current,
                store="local",
            )
            self.assertTrue(ret)

    @destructiveTest
    def test_set_firewall_logging_allowed_lgpo_notconfigured(self):
        current = win_lgpo_netsh.get_settings(
            profile="domain", section="logging", store="lgpo"
        )["LogAllowedConnections"]
        try:
            ret = win_lgpo_netsh.set_logging_settings(
                profile="domain",
                setting="allowedconnections",
                value="notconfigured",
                store="lgpo",
            )
            self.assertTrue(ret)
            new = win_lgpo_netsh.get_settings(
                profile="domain", section="logging", store="lgpo"
            )["LogAllowedConnections"]
            self.assertEqual("NotConfigured", new)
        finally:
            ret = win_lgpo_netsh.set_logging_settings(
                profile="domain",
                setting="allowedconnections",
                value=current,
                store="lgpo",
            )
            self.assertTrue(ret)

    def test_set_firewall_logging_dropped_local_enable(self):
        current = win_lgpo_netsh.get_settings(
            profile="domain", section="logging", store="local"
        )["LogDroppedConnections"]
        try:
            ret = win_lgpo_netsh.set_logging_settings(
                profile="domain",
                setting="droppedconnections",
                value="enable",
                store="local",
            )
            self.assertTrue(ret)
            new = win_lgpo_netsh.get_settings(
                profile="domain", section="logging", store="local"
            )["LogDroppedConnections"]
            self.assertEqual("Enable", new)
        finally:
            ret = win_lgpo_netsh.set_logging_settings(
                profile="domain",
                setting="droppedconnections",
                value=current,
                store="local",
            )
            self.assertTrue(ret)

    def test_set_firewall_logging_filename_local(self):
        current = win_lgpo_netsh.get_settings(
            profile="domain", section="logging", store="local"
        )["FileName"]
        try:
            ret = win_lgpo_netsh.set_logging_settings(
                profile="domain",
                setting="filename",
                value="C:\\Temp\\test.log",
                store="local",
            )
            self.assertTrue(ret)
            new = win_lgpo_netsh.get_settings(
                profile="domain", section="logging", store="local"
            )["FileName"]
            self.assertEqual("C:\\Temp\\test.log", new)
        finally:
            ret = win_lgpo_netsh.set_logging_settings(
                profile="domain", setting="filename", value=current, store="local"
            )
            self.assertTrue(ret)

    def test_set_firewall_logging_maxfilesize_local(self):
        current = win_lgpo_netsh.get_settings(
            profile="domain", section="logging", store="local"
        )["MaxFileSize"]
        try:
            ret = win_lgpo_netsh.set_logging_settings(
                profile="domain", setting="maxfilesize", value="16384", store="local"
            )
            self.assertTrue(ret)
            new = win_lgpo_netsh.get_settings(
                profile="domain", section="logging", store="local"
            )["MaxFileSize"]
            self.assertEqual("16384", new)
        finally:
            ret = win_lgpo_netsh.set_logging_settings(
                profile="domain", setting="maxfilesize", value=current, store="local"
            )
            self.assertTrue(ret)

    @destructiveTest
    def test_set_firewall_settings_fwrules_local_enable(self):
        self.assertRaises(
            CommandExecutionError,
            win_lgpo_netsh.set_settings,
            profile="domain",
            setting="localfirewallrules",
            value="enable",
            store="local",
        )

    @destructiveTest
    def test_set_firewall_settings_fwrules_lgpo_notconfigured(self):
        current = win_lgpo_netsh.get_settings(
            profile="domain", section="settings", store="lgpo"
        )["LocalFirewallRules"]
        try:
            ret = win_lgpo_netsh.set_settings(
                profile="domain",
                setting="localfirewallrules",
                value="notconfigured",
                store="lgpo",
            )
            self.assertTrue(ret)
            new = win_lgpo_netsh.get_settings(
                profile="domain", section="settings", store="lgpo"
            )["LocalFirewallRules"]
            self.assertEqual("NotConfigured", new)
        finally:
            ret = win_lgpo_netsh.set_settings(
                profile="domain",
                setting="localfirewallrules",
                value=current,
                store="lgpo",
            )
            self.assertTrue(ret)

    @destructiveTest
    def test_set_firewall_settings_consecrules_local_enable(self):
        self.assertRaises(
            CommandExecutionError,
            win_lgpo_netsh.set_settings,
            profile="domain",
            setting="localconsecrules",
            value="enable",
            store="local",
        )

    def test_set_firewall_settings_notification_local_enable(self):
        current = win_lgpo_netsh.get_settings(
            profile="domain", section="settings", store="local"
        )["InboundUserNotification"]
        try:
            ret = win_lgpo_netsh.set_settings(
                profile="domain",
                setting="inboundusernotification",
                value="enable",
                store="local",
            )
            self.assertTrue(ret)
            new = win_lgpo_netsh.get_settings(
                profile="domain", section="settings", store="local"
            )["InboundUserNotification"]
            self.assertEqual("Enable", new)
        finally:
            ret = win_lgpo_netsh.set_settings(
                profile="domain",
                setting="inboundusernotification",
                value=current,
                store="local",
            )
            self.assertTrue(ret)

    @destructiveTest
    def test_set_firewall_settings_notification_local_notconfigured(self):
        current = win_lgpo_netsh.get_settings(
            profile="domain", section="settings", store="local"
        )["InboundUserNotification"]
        try:
            self.assertRaises(
                CommandExecutionError,
                win_lgpo_netsh.set_settings,
                profile="domain",
                setting="inboundusernotification",
                value="notconfigured",
                store="local",
            )
        finally:
            ret = win_lgpo_netsh.set_settings(
                profile="domain",
                setting="inboundusernotification",
                value=current,
                store="local",
            )
            self.assertTrue(ret)

    def test_set_firewall_settings_notification_lgpo_notconfigured(self):
        current = win_lgpo_netsh.get_settings(
            profile="domain", section="settings", store="lgpo"
        )["InboundUserNotification"]
        try:
            ret = win_lgpo_netsh.set_settings(
                profile="domain",
                setting="inboundusernotification",
                value="notconfigured",
                store="lgpo",
            )
            self.assertTrue(ret)
            new = win_lgpo_netsh.get_settings(
                profile="domain", section="settings", store="lgpo"
            )["InboundUserNotification"]
            self.assertEqual("NotConfigured", new)
        finally:
            ret = win_lgpo_netsh.set_settings(
                profile="domain",
                setting="inboundusernotification",
                value=current,
                store="lgpo",
            )
            self.assertTrue(ret)

    def test_set_firewall_settings_remotemgmt_local_enable(self):
        current = win_lgpo_netsh.get_settings(
            profile="domain", section="settings", store="local"
        )["RemoteManagement"]
        try:
            ret = win_lgpo_netsh.set_settings(
                profile="domain",
                setting="remotemanagement",
                value="enable",
                store="local",
            )
            self.assertTrue(ret)
            new = win_lgpo_netsh.get_settings(
                profile="domain", section="settings", store="local"
            )["RemoteManagement"]
            self.assertEqual("Enable", new)
        finally:
            ret = win_lgpo_netsh.set_settings(
                profile="domain",
                setting="remotemanagement",
                value=current,
                store="local",
            )
            self.assertTrue(ret)

    def test_set_firewall_settings_unicast_local_disable(self):
        current = win_lgpo_netsh.get_settings(
            profile="domain", section="settings", store="local"
        )["UnicastResponseToMulticast"]
        try:
            ret = win_lgpo_netsh.set_settings(
                profile="domain",
                setting="unicastresponsetomulticast",
                value="disable",
                store="local",
            )
            self.assertTrue(ret)
            new = win_lgpo_netsh.get_settings(
                profile="domain", section="settings", store="local"
            )["UnicastResponseToMulticast"]
            self.assertEqual("Disable", new)
        finally:
            ret = win_lgpo_netsh.set_settings(
                profile="domain",
                setting="unicastresponsetomulticast",
                value=current,
                store="local",
            )
            self.assertTrue(ret)

    @destructiveTest
    def test_set_firewall_state_local_on(self):
        current = win_lgpo_netsh.get_settings(
            profile="domain", section="state", store="local"
        )["State"]
        try:
            ret = win_lgpo_netsh.set_state(profile="domain", state="off", store="local")
            self.assertTrue(ret)
            new = win_lgpo_netsh.get_settings(
                profile="domain", section="state", store="local"
            )["State"]
            self.assertEqual("OFF", new)
        finally:
            ret = win_lgpo_netsh.set_state(
                profile="domain", state=current, store="local"
            )
            self.assertTrue(ret)

    @destructiveTest
    def test_set_firewall_state_local_notconfigured(self):
        current = win_lgpo_netsh.get_settings(
            profile="domain", section="state", store="local"
        )["State"]
        try:
            self.assertRaises(
                CommandExecutionError,
                win_lgpo_netsh.set_state,
                profile="domain",
                state="notconfigured",
                store="local",
            )
        finally:
            ret = win_lgpo_netsh.set_state(
                profile="domain", state=current, store="local"
            )
            self.assertTrue(ret)

    @destructiveTest
    def test_set_firewall_state_lgpo_notconfigured(self):
        current = win_lgpo_netsh.get_settings(
            profile="domain", section="state", store="local"
        )["State"]
        try:
            ret = win_lgpo_netsh.set_state(
                profile="domain", state="notconfigured", store="lgpo"
            )
            self.assertTrue(ret)
            new = win_lgpo_netsh.get_settings(
                profile="domain", section="state", store="lgpo"
            )["State"]
            self.assertEqual("NotConfigured", new)
        finally:
            ret = win_lgpo_netsh.set_state(
                profile="domain", state=current, store="lgpo"
            )
            self.assertTrue(ret)
