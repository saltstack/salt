# -*- coding: utf-8 -*-
"""
    :codeauthor: Megan Wilhite<mwilhite@saltstack.com>
"""

# Import Python libs
from __future__ import absolute_import

# Import Salt Libs
import salt.modules.mac_service as mac_service

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class MacServiceTestCase(TestCase, LoaderModuleMockMixin):
    """
    TestCase for salt.modules.mac_service module
    """

    def setup_loader_modules(self):
        return {mac_service: {}}

    def test_service_disabled_when_enabled(self):
        """
        test service.disabled when service is enabled
        """
        srv_name = "com.apple.atrun"
        cmd = 'disabled services = {\n\t"com.saltstack.salt.minion" => false\n\t"com.apple.atrun" => false\n{'

        with patch.object(mac_service, "launchctl", MagicMock(return_value=cmd)):
            self.assertFalse(mac_service.disabled(srv_name))

    def test_service_disabled_when_disabled(self):
        """
        test service.disabled when service is disabled
        """
        srv_name = "com.apple.atrun"
        cmd = 'disabled services = {\n\t"com.saltstack.salt.minion" => false\n\t"com.apple.atrun" => true\n{'

        with patch.object(mac_service, "launchctl", MagicMock(return_value=cmd)):
            self.assertTrue(mac_service.disabled(srv_name))

    def test_service_disabled_srvname_wrong(self):
        """
        test service.disabled when service is just slightly wrong
        """
        srv_names = ["com.apple.atru", "com", "apple"]
        cmd = 'disabled services = {\n\t"com.saltstack.salt.minion" => false\n\t"com.apple.atrun" => true\n}'
        for name in srv_names:
            with patch.object(mac_service, "launchctl", MagicMock(return_value=cmd)):
                self.assertFalse(mac_service.disabled(name))

    def test_service_disabled_status_upper_case(self):
        """
        test service.disabled when disabled status is uppercase
        """
        srv_name = "com.apple.atrun"
        cmd = 'disabled services = {\n\t"com.saltstack.salt.minion" => false\n\t"com.apple.atrun" => True\n{'

        with patch.object(mac_service, "launchctl", MagicMock(return_value=cmd)):
            self.assertTrue(mac_service.disabled(srv_name))

    def test_service_keep_alive_pathstate_file_rm(self):
        """
        test _always_running_service when keep_alive
        has pathstate set in plist file and file doesn't exist
        """
        srv_name = "com.apple.atrun"
        info = {
            "plist": {
                "EnableTransactions": True,
                "ProgramArguments": ["/usr/libexec/ntpd-wrapper"],
                "Label": "org.ntp.ntpd",
                "KeepAlive": {"PathState": {"/private/etc/ntp.conf": True}},
            }
        }

        with patch.object(mac_service, "show", MagicMock(return_value=info)):
            with patch("os.path.exists", MagicMock(return_value=False)):
                assert mac_service._always_running_service(srv_name) is False

    def test_service_keep_alive_empty(self):
        """
        test _always_running_service when keep_alive
        is empty
        """
        srv_name = "com.apple.atrun"
        info = {
            "plist": {
                "EnableTransactions": True,
                "ProgramArguments": ["/usr/libexec/ntpd-wrapper"],
                "Label": "org.ntp.ntpd",
                "KeepAlive": {},
            }
        }

        with patch.object(mac_service, "show", MagicMock(return_value=info)):
            with patch("os.path.exists", MagicMock(return_value=False)):
                assert mac_service._always_running_service(srv_name) is False

    def test_service_keep_alive_pathstate_false(self):
        """
        test _always_running_service when keep_alive
        has pathstate set in plist file and file is false
        """
        srv_name = "com.apple.atrun"
        info = {
            "plist": {
                "EnableTransactions": True,
                "ProgramArguments": ["/usr/libexec/ntpd-wrapper"],
                "Label": "org.ntp.ntpd",
                "KeepAlive": {"PathState": {"/private/etc/ntp.conf": False}},
            }
        }

        with patch.object(mac_service, "show", MagicMock(return_value=info)):
            with patch("os.path.exists", MagicMock(return_value=False)):
                assert mac_service._always_running_service(srv_name) is True

    def test_service_keep_alive_pathstate(self):
        """
        test _always_running_service when keep_alive
        has pathstate set in plist file
        """
        srv_name = "com.apple.atrun"
        info = {
            "plist": {
                "EnableTransactions": True,
                "ProgramArguments": ["/usr/libexec/ntpd-wrapper"],
                "Label": "org.ntp.ntpd",
                "KeepAlive": {"PathState": {"/private/etc/ntp.conf": True}},
            }
        }

        with patch.object(mac_service, "show", MagicMock(return_value=info)):
            with patch("os.path.exists", MagicMock(return_value=True)):
                assert mac_service._always_running_service(srv_name) is True

    def test_service_keep_alive(self):
        """
        test _always_running_service when keep_alive set
        """
        srv_name = "com.apple.atrun"
        info = {
            "plist": {
                "EnableTransactions": True,
                "ProgramArguments": ["/usr/libexec/ntpd-wrapper"],
                "Label": "org.ntp.ntpd",
                "KeepAlive": True,
            }
        }

        with patch.object(mac_service, "show", MagicMock(return_value=info)):
            assert mac_service._always_running_service(srv_name) is True

    def test_service_keep_alive_false(self):
        """
        test _always_running_service when keep_alive False
        """
        srv_name = "com.apple.atrun"
        info = {
            "plist": {
                "EnableTransactions": True,
                "ProgramArguments": ["/usr/libexec/ntpd-wrapper"],
                "Label": "org.ntp.ntpd",
                "KeepAlive": False,
            }
        }

        with patch.object(mac_service, "show", MagicMock(return_value=info)):
            assert mac_service._always_running_service(srv_name) is False

    def test_service_keep_alive_missing(self):
        """
        test _always_running_service when keep_alive not in dict
        """
        srv_name = "com.apple.atrun"
        info = {
            "plist": {
                "EnableTransactions": True,
                "ProgramArguments": ["/usr/libexec/ntpd-wrapper"],
                "Label": "org.ntp.ntpd",
            }
        }

        with patch.object(mac_service, "show", MagicMock(return_value=info)):
            assert mac_service._always_running_service(srv_name) is False

    def test_service_keep_alive_wrong_setting(self):
        """
        test _always_running_service when keep_alive
        has pathstate set in plist file
        """
        srv_name = "com.apple.atrun"
        info = {
            "plist": {
                "EnableTransactions": True,
                "ProgramArguments": ["/usr/libexec/ntpd-wrapper"],
                "Label": "org.ntp.ntpd",
                "KeepAlive": {"Doesnotexist": {"doesnt_exist": True}},
            }
        }

        with patch.object(mac_service, "show", MagicMock(return_value=info)):
            assert mac_service._always_running_service(srv_name) is False
