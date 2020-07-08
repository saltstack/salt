# -*- coding: utf-8 -*-
"""
    :codeauthor: Megan Wilhite<mwilhite@saltstack.com>
"""

# Import Python libs
from __future__ import absolute_import

# Import Salt Libs
import salt.modules.mac_service as mac_service
from salt.exceptions import CommandExecutionError

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

    @patch.object(
        mac_service, "_get_domain_target", lambda name, service_target: ("", "")
    )
    def test_service_disabled_when_enabled(self):
        """
        test service.disabled when service is enabled
        """
        srv_name = "com.apple.atrun"
        cmd = 'disabled services = {\n\t"com.saltstack.salt.minion" => false\n\t"com.apple.atrun" => false\n{'

        with patch.object(mac_service, "launchctl", MagicMock(return_value=cmd)):
            self.assertFalse(mac_service.disabled(srv_name))

    @patch.object(
        mac_service, "_get_domain_target", lambda name, service_target: ("", "")
    )
    def test_service_disabled_when_disabled(self):
        """
        test service.disabled when service is disabled
        """
        srv_name = "com.apple.atrun"
        cmd = 'disabled services = {\n\t"com.saltstack.salt.minion" => false\n\t"com.apple.atrun" => true\n{'

        with patch.object(mac_service, "launchctl", MagicMock(return_value=cmd)):
            self.assertTrue(mac_service.disabled(srv_name))

    @patch.object(
        mac_service, "_get_domain_target", lambda name, service_target: ("", "")
    )
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
        with patch.object(
            mac_service, "_get_domain_target", MagicMock(return_value=("", ""))
        ):
            with patch.object(mac_service, "launchctl", MagicMock(return_value=cmd)):
                self.assertTrue(mac_service.disabled(srv_name))

    def test_service_enabled_when_enabled(self):
        """
        test service.enabled
        """
        mock_cmd = MagicMock(return_value=False)
        with patch("salt.modules.mac_service.__salt__", {"service.disabled": mock_cmd}):
            self.assertTrue(mac_service.enabled("com.apple.atrun"))

    def test_service_enabled_when_disabled(self):
        """
        test service.enabled
        """
        mock_cmd = MagicMock(return_value=True)
        with patch("salt.modules.mac_service.__salt__", {"service.disabled": mock_cmd}):
            self.assertFalse(mac_service.enabled("com.apple.atrun"))

    def test_service_loaded_when_true(self):
        """
        test service.enabled
        """
        mock_cmd = MagicMock(return_value="some_service_string")
        with patch("salt.modules.mac_service.__salt__", {"service.list": mock_cmd}):
            self.assertTrue(mac_service.loaded("com.piedpiper.daemon"))

    def test_service_loaded_when_false(self):
        """
        test service.enabled
        """
        mock_cmd = MagicMock(side_effect=CommandExecutionError)
        with patch("salt.modules.mac_service.__salt__", {"service.list": mock_cmd}):
            self.assertFalse(mac_service.loaded("com.apple.atrun"))

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

    def test_service_restart_already_loaded(self):
        mock_cmd = MagicMock(return_value=True)
        salt_dict = {
            "service.loaded": mock_cmd,
            "service.stop": mock_cmd,
            "service.start": mock_cmd,
        }
        with patch("salt.modules.mac_service.__salt__", salt_dict):
            self.assertTrue(mac_service.restart("com.hooli.daemon"))

    def test_service_restart_not_loaded(self):
        salt_dict = {
            "service.loaded": MagicMock(return_value=False),
            "service.start": MagicMock(return_value=True),
        }
        with patch("salt.modules.mac_service.__salt__", salt_dict):
            self.assertTrue(mac_service.restart("com.hooli.daemon"))

    def test_service_restart_failed_stop(self):
        salt_dict = {
            "service.loaded": MagicMock(return_value=True),
            "service.stop": MagicMock(side_effect=CommandExecutionError),
        }
        with patch("salt.modules.mac_service.__salt__", salt_dict):
            with self.assertRaises(CommandExecutionError):
                mac_service.restart("com.hooli.daemon")

    def test_service_restart_failed_start(self):
        salt_dict = {
            "service.loaded": MagicMock(return_value=False),
            "service.start": MagicMock(side_effect=CommandExecutionError),
        }
        with patch("salt.modules.mac_service.__salt__", salt_dict):
            with self.assertRaises(CommandExecutionError):
                mac_service.restart("com.hooli.daemon")

    def test_service_status_no_service(self):
        """
        Test service status with no service found
        """
        with patch.object(
            mac_service, "_get_service", MagicMock(side_effect=CommandExecutionError)
        ):
            self.assertEqual(mac_service.status("com.hooli.daemon"), "")

    @patch.object(mac_service, "_launch_agent", lambda name: False)
    @patch.object(mac_service, "_get_service", lambda name: {"": ""})
    @patch.object(mac_service, "_always_running_service", lambda name: True)
    def test_service_status_on_daemon_with_pid(self):
        """
        Test service status on dameon with PID.
        """
        mock_servie_list = "PID\tStatus\tLabel\n1061\t0\tcom.apple.storedownloadd.daemon\n524\t0\tcom.hooli.daemon\n243\t0\tcom.apple.coreservicesd\n451\t0\tcom.apple.touchbarserver\n815\t0\tcom.apple.deleted_helper"
        salt_dict = {
            "service.list": MagicMock(return_value=mock_servie_list),
            "service.loaded": MagicMock(return_value=True),
        }
        with patch("salt.modules.mac_service.__salt__", salt_dict):
            self.assertEqual(mac_service.status("com.hooli.daemon"), "524")

    @patch.object(mac_service, "_launch_agent", lambda name: True)
    @patch.object(mac_service, "_get_service", lambda name: {"": ""})
    @patch.object(mac_service, "_always_running_service", lambda name: True)
    def test_service_status_on_agent_with_pid(self):
        """
        Test service status on LaunchAgent with PID.
        """
        mock_servie_list = "PID\tStatus\tLabel\n1061\t0\tcom.apple.storedownloadd.daemon\n524\t0\tcom.hooli.agent\n243\t0\tcom.apple.coreservicesd"
        salt_dict = {
            "service.list": MagicMock(return_value=mock_servie_list),
            "service.loaded": MagicMock(return_value=True),
        }
        utils_dict = {
            "mac_utils.console_user": MagicMock(return_value="spongebob"),
        }
        with patch("salt.modules.mac_service.__salt__", salt_dict):
            with patch("salt.modules.mac_service.__utils__", utils_dict):
                self.assertEqual(mac_service.status("com.hooli.agent"), "524")

    @patch.object(mac_service, "_launch_agent", lambda name: True)
    @patch.object(mac_service, "_get_service", lambda name: {"": ""})
    @patch.object(mac_service, "_always_running_service", lambda name: True)
    def test_service_status_on_agent_with_no_pid_and_should_be_running(self):
        """
        Test service status on LaunchAgent with PID.
        """
        mock_servie_list = "PID\tStatus\tLabel\n1061\t0\tcom.apple.storedownloadd.daemon\n-\t0\tcom.hooli.agent\n243\t0\tcom.apple.coreservicesd"
        salt_dict = {
            "service.list": MagicMock(return_value=mock_servie_list),
            "service.loaded": MagicMock(return_value=True),
        }
        utils_dict = {
            "mac_utils.console_user": MagicMock(return_value="spongebob"),
        }
        with patch("salt.modules.mac_service.__salt__", salt_dict):
            with patch("salt.modules.mac_service.__utils__", utils_dict):
                self.assertEqual(mac_service.status("com.hooli.agent"), "")

    @patch.object(mac_service, "_launch_agent", lambda name: False)
    @patch.object(mac_service, "_get_service", lambda name: {"": ""})
    @patch.object(mac_service, "_always_running_service", lambda name: True)
    def test_service_status_on_daemon_with_no_pid_and_should_be_running(self):
        """
        Test service status on LaunchDaemon with no PID on an
        always running service that is loaded.
        """
        mock_servie_list = "PID\tStatus\tLabel\n1061\t0\tcom.apple.storedownloadd.daemon\n-\t0\tcom.hooli.daemon\n243\t0\tcom.apple.coreservicesd"
        salt_dict = {
            "service.list": MagicMock(return_value=mock_servie_list),
            "service.loaded": MagicMock(return_value=True),
        }
        with patch("salt.modules.mac_service.__salt__", salt_dict):
            self.assertEqual(mac_service.status("com.hooli.daemon"), "")

    @patch.object(mac_service, "_launch_agent", lambda name: False)
    @patch.object(mac_service, "_get_service", lambda name: {"": ""})
    @patch.object(mac_service, "_always_running_service", lambda name: False)
    def test_service_status_on_daemon_with_no_pid_and_not_always_running(self):
        """
        Test service status on LaunchDaemon with no PID on an
        always running service that is loaded.
        """
        mock_servie_list = "PID\tStatus\tLabel\n1061\t0\tcom.apple.storedownloadd.daemon\n-\t0\tcom.hooli.daemon\n243\t0\tcom.apple.coreservicesd"
        salt_dict = {
            "service.list": MagicMock(return_value=mock_servie_list),
            "service.loaded": MagicMock(return_value=True),
        }
        with patch("salt.modules.mac_service.__salt__", salt_dict):
            self.assertEqual(mac_service.status("com.hooli.daemon"), "loaded")
