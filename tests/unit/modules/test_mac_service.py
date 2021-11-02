"""
    :codeauthor: Megan Wilhite<mwilhite@saltstack.com>
"""


import pytest
import salt.modules.mac_service as mac_service
from salt.exceptions import CommandExecutionError
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class MacServiceTestCase(TestCase, LoaderModuleMockMixin):
    """
    TestCase for salt.modules.mac_service module
    """

    def setup_loader_modules(self):
        return {mac_service: {"__context__": {}}}

    def test_service_disabled_when_enabled(self):
        """
        test service.disabled when service is enabled
        """
        srv_name = "com.apple.atrun"
        cmd = (
            'disabled services = {\n\t"com.saltstack.salt.minion" =>'
            ' false\n\t"com.apple.atrun" => false\n{'
        )
        domain_ret = MagicMock(return_value=("", ""))
        with patch.object(mac_service, "_get_domain_target", domain_ret):
            with patch.object(mac_service, "launchctl", MagicMock(return_value=cmd)):
                assert mac_service.disabled(srv_name) is False

    def test_service_disabled_when_disabled(self):
        """
        test service.disabled when service is disabled
        """
        srv_name = "com.apple.atrun"
        cmd = (
            'disabled services = {\n\t"com.saltstack.salt.minion" =>'
            ' false\n\t"com.apple.atrun" => true\n{'
        )
        domain_ret = MagicMock(return_value=("", ""))
        with patch.object(mac_service, "_get_domain_target", domain_ret):
            with patch.object(mac_service, "launchctl", MagicMock(return_value=cmd)):
                assert mac_service.disabled(srv_name) is True

    def test_service_disabled_srvname_wrong(self):
        """
        test service.disabled when service is just slightly wrong
        """
        srv_names = ["com.apple.atru", "com", "apple"]
        cmd = (
            'disabled services = {\n\t"com.saltstack.salt.minion" =>'
            ' false\n\t"com.apple.atrun" => true\n}'
        )
        domain_ret = MagicMock(return_value=("", ""))
        with patch.object(mac_service, "_get_domain_target", domain_ret):
            for name in srv_names:
                with patch.object(
                    mac_service, "launchctl", MagicMock(return_value=cmd)
                ):
                    assert mac_service.disabled(name) is False

    def test_service_disabled_status_upper_case(self):
        """
        test service.disabled when disabled status is uppercase
        """
        srv_name = "com.apple.atrun"
        cmd = (
            'disabled services = {\n\t"com.saltstack.salt.minion" =>'
            ' false\n\t"com.apple.atrun" => True\n{'
        )
        domain_ret = MagicMock(return_value=("", ""))
        with patch.object(mac_service, "_get_domain_target", domain_ret):
            with patch.object(mac_service, "launchctl", MagicMock(return_value=cmd)):
                assert mac_service.disabled(srv_name) is True

    def test_service_enabled_when_enabled(self):
        """
        test service.enabled when not disabled
        """
        mock_cmd = MagicMock(return_value=False)
        with patch.dict(mac_service.__salt__, {"service.disabled": mock_cmd}):
            assert mac_service.enabled("com.apple.atrun") is True

    def test_service_enabled_when_disabled(self):
        """
        test service.enabled if service is disabled
        """
        mock_cmd = MagicMock(return_value=True)
        with patch.dict(mac_service.__salt__, {"service.disabled": mock_cmd}):
            assert mac_service.enabled("com.apple.atrun") is False

    def test_service_loaded_when_true(self):
        """
        test service.loaded with a loaded service.
        """
        mock_cmd = MagicMock(return_value="some_service_string")
        with patch.dict(mac_service.__salt__, {"service.list": mock_cmd}):
            assert mac_service.loaded("com.apple.atrun") is True

    def test_service_loaded_when_false(self):
        """
        test service.loaded with an unloaded service.
        """
        mock_cmd = MagicMock(side_effect=CommandExecutionError)
        with patch.dict(mac_service.__salt__, {"service.list": mock_cmd}):
            assert mac_service.loaded("com.apple.atrun") is False

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

    def test_service_name_change_salt_minion(self):
        srv_name = "salt-minion"
        info = {
            "com.saltstack.salt.minion": {
                "file_name": "com.saltstack.salt.minion.plist",
                "file_path": "/Library/LaunchDaemons/com.saltstack.salt.minion.plist",
                "plist": {
                    "HardResourceLimits": {"NumberOfFiles": 100000},
                    "KeepAlive": True,
                    "Label": "com.saltstack.salt.minion",
                    "ProgramArguments": ["/opt/salt/bin/start-salt-minion.sh"],
                    "RunAtLoad": True,
                    "SoftResourceLimits": {"NumberOfFiles": 100000},
                },
            }
        }
        with patch.dict(
            mac_service.__utils__,
            {"mac_utils.available_services": MagicMock(return_value=info)},
        ):
            assert (
                mac_service._get_service(srv_name) == info["com.saltstack.salt.minion"]
            )

    def test_service_name_change_salt_master(self):
        srv_name = "salt-master"
        info = {
            "com.saltstack.salt.master": {
                "file_name": "com.saltstack.salt.master.plist",
                "file_path": "/Library/LaunchDaemons/com.saltstack.salt.master.plist",
                "plist": {
                    "HardResourceLimits": {"NumberOfFiles": 100000},
                    "KeepAlive": True,
                    "Label": "com.saltstack.salt.master",
                    "ProgramArguments": ["/opt/salt/bin/start-salt-master.sh"],
                    "RunAtLoad": True,
                    "SoftResourceLimits": {"NumberOfFiles": 100000},
                },
            }
        }
        with patch.dict(
            mac_service.__utils__,
            {"mac_utils.available_services": MagicMock(return_value=info)},
        ):
            assert (
                mac_service._get_service(srv_name) == info["com.saltstack.salt.master"]
            )

    def test_service_name_change_salt_api(self):
        srv_name = "salt-api"
        info = {
            "com.saltstack.salt.api": {
                "file_name": "com.saltstack.salt.api.plist",
                "file_path": "/Library/LaunchDaemons/com.saltstack.salt.api.plist",
                "plist": {
                    "HardResourceLimits": {"NumberOfFiles": 100000},
                    "KeepAlive": True,
                    "Label": "com.saltstack.salt.api",
                    "ProgramArguments": ["/opt/salt/bin/start-salt-api.sh"],
                    "RunAtLoad": True,
                    "SoftResourceLimits": {"NumberOfFiles": 100000},
                },
            }
        }
        with patch.dict(
            mac_service.__utils__,
            {"mac_utils.available_services": MagicMock(return_value=info)},
        ):
            assert mac_service._get_service(srv_name) == info["com.saltstack.salt.api"]

    def test_service_name_change_salt_syndic(self):
        srv_name = "salt-syndic"
        info = {
            "com.saltstack.salt.syndic": {
                "file_name": "com.saltstack.salt.syndic.plist",
                "file_path": "/Library/LaunchDaemons/com.saltstack.salt.syndic.plist",
                "plist": {
                    "HardResourceLimits": {"NumberOfFiles": 100000},
                    "KeepAlive": True,
                    "Label": "com.saltstack.salt.syndic",
                    "ProgramArguments": ["/opt/salt/bin/start-salt-syndic.sh"],
                    "RunAtLoad": True,
                    "SoftResourceLimits": {"NumberOfFiles": 100000},
                },
            }
        }
        with patch.dict(
            mac_service.__utils__,
            {"mac_utils.available_services": MagicMock(return_value=info)},
        ):
            assert (
                mac_service._get_service(srv_name) == info["com.saltstack.salt.syndic"]
            )

    def test_service_restart_already_loaded(self):
        mock_cmd = MagicMock(return_value=True)
        salt_dict = {
            "service.loaded": mock_cmd,
            "service.stop": mock_cmd,
            "service.start": mock_cmd,
        }
        with patch.dict(mac_service.__salt__, salt_dict):
            assert mac_service.restart("com.salt") is True

    def test_service_restart_not_loaded(self):
        salt_dict = {
            "service.loaded": MagicMock(return_value=False),
            "service.start": MagicMock(return_value=True),
        }
        with patch.dict(mac_service.__salt__, salt_dict):
            assert mac_service.restart("com.salt") is True

    def test_service_restart_failed_stop(self):
        salt_dict = {
            "service.loaded": MagicMock(return_value=True),
            "service.stop": MagicMock(side_effect=CommandExecutionError),
        }
        with patch.dict(mac_service.__salt__, salt_dict):
            with pytest.raises(CommandExecutionError):
                assert mac_service.restart("com.salt")

    def test_service_restart_failed_start(self):
        salt_dict = {
            "service.loaded": MagicMock(return_value=False),
            "service.start": MagicMock(side_effect=CommandExecutionError),
        }
        with patch.dict(mac_service.__salt__, salt_dict):
            with pytest.raises(CommandExecutionError):
                assert mac_service.restart("com.salt")

    def test_service_status_no_service(self):
        """
        Test service status with no service found
        """
        with patch.object(
            mac_service, "_get_service", MagicMock(side_effect=CommandExecutionError)
        ):
            assert mac_service.status("com.salt") is False

    @patch.object(mac_service, "_launch_agent", lambda _: False)
    @patch.object(mac_service, "_get_service", lambda _: {"": ""})
    @patch.object(mac_service, "_always_running_service", lambda _: True)
    def test_service_status_on_daemon_with_pid(self):
        """
        Test service status on dameon with PID.
        """
        mock_service_list = (
            '{\n\t"LimitLoadToSessionType" = "System";\n\t"Label" ='
            ' "com.salt";\n\t"OnDemand" = false;\n\t"LastExitStatus" = 0;\n\t"PID" ='
            ' 218;\n\t"Program" = "/opt/salt";\n\t\t"--disable-keepalive";\n\t);\n};'
        )
        salt_dict = {
            "service.list": MagicMock(return_value=mock_service_list),
        }
        with patch.dict(mac_service.__salt__, salt_dict):
            assert mac_service.status("com.salt") is True

    @patch.object(mac_service, "_launch_agent", lambda _: True)
    @patch.object(mac_service, "_get_service", lambda _: {"": ""})
    @patch.object(mac_service, "_always_running_service", lambda _: True)
    def test_service_status_on_agent_with_pid(self):
        """
        Test service status on LaunchAgent with PID.
        """
        mock_service_list = (
            '{\n\t"LimitLoadToSessionType" = "Aqua";\n\t"Label" ='
            ' "com.salt";\n\t"OnDemand" = false;\n\t"LastExitStatus" = 19968;\n\t"PID"'
            ' = 218;\n\t"Program" = "/opt/salt";\n\t"ProgramArguments" ='
            ' (\n\t\t"/opt/salt";\n\t\t"--syslog";\n\t);\n};'
        )
        salt_dict = {
            "service.list": MagicMock(return_value=mock_service_list),
        }
        utils_dict = {
            "mac_utils.console_user": MagicMock(return_value="spongebob"),
        }
        with patch.dict(mac_service.__salt__, salt_dict):
            with patch.dict(mac_service.__utils__, utils_dict):
                assert mac_service.status("com.salt") is True

    @patch.object(mac_service, "_launch_agent", lambda _: True)
    @patch.object(mac_service, "_get_service", lambda _: {"": ""})
    @patch.object(mac_service, "_always_running_service", lambda _: True)
    def test_service_status_on_agent_with_no_pid_and_should_be_running(self):
        """
        Test service status on LaunchAgent with No PID and should be running.
        """
        mock_service_list = (
            '{\n\t"LimitLoadToSessionType" = "Aqua";\n\t"Label" ='
            ' "com.salt";\n\t"OnDemand" = false;\n\t"LastExitStatus" ='
            ' 19968;\n\t"Program" = "/opt/salt";\n\t"ProgramArguments" ='
            ' (\n\t\t"/opt/salt";\n\t\t"--syslog";\n\t);\n};'
        )
        salt_dict = {
            "service.list": MagicMock(return_value=mock_service_list),
        }
        utils_dict = {
            "mac_utils.console_user": MagicMock(return_value="spongebob"),
        }
        with patch.dict(mac_service.__salt__, salt_dict):
            with patch.dict(mac_service.__utils__, utils_dict):
                assert mac_service.status("com.salt") is False

    @patch.object(mac_service, "_launch_agent", lambda _: False)
    @patch.object(mac_service, "_get_service", lambda _: {"": ""})
    @patch.object(mac_service, "_always_running_service", lambda _: True)
    def test_service_status_on_daemon_with_no_pid_and_should_be_running(self):
        """
        Test service status on LaunchDaemon with no PID and an
        always running service that is loaded.
        """
        mock_service_list = (
            '{\n\t"LimitLoadToSessionType" = "System";\n\t"Label" ='
            ' "com.salt";\n\t"OnDemand" = false;\n\t"LastExitStatus" ='
            ' 19968;\n\t"Program" = "/opt/salt.sh";\n\t"ProgramArguments" ='
            ' (\n\t\t"/opt/salt.sh";\n\t\t"--disable-keepalive";\n\t);\n};'
        )
        salt_dict = {
            "service.list": MagicMock(return_value=mock_service_list),
        }
        with patch.dict(mac_service.__salt__, salt_dict):
            assert mac_service.status("com.salt") is False

    @patch.object(mac_service, "_launch_agent", lambda _: False)
    @patch.object(mac_service, "_get_service", lambda _: {"": ""})
    @patch.object(mac_service, "_always_running_service", lambda _: False)
    def test_service_status_on_daemon_with_no_pid_and_not_always_running(self):
        """
        Test service status on LaunchDaemon with no PID and not an always
        running service.
        """
        mock_service_list = (
            '{\n\t"LimitLoadToSessionType" = "System";\n\t"Label" ='
            ' "com.salt";\n\t"OnDemand" = false;\n\t"LastExitStatus" ='
            ' 19968;\n\t"Program" = "/opt/salt.sh";\n\t"ProgramArguments" ='
            ' (\n\t\t"/opt/salt.sh";\n\t\t"--disable-keepalive";\n\t);\n};'
        )
        salt_dict = {
            "service.list": MagicMock(return_value=mock_service_list),
        }
        with patch.dict(mac_service.__salt__, salt_dict):
            assert mac_service.status("com.salt") is True

    @patch.object(mac_service, "_launch_agent", lambda _: False)
    @patch.object(mac_service, "_get_service", lambda _: {"": ""})
    @patch.object(mac_service, "_always_running_service", lambda _: False)
    def test_service_status_on_daemon_with_failing_list_check(self):
        """
        Test service status on LaunchDaemon with no PID on an
        always running service that is loaded.
        """
        mock_service_list = (
            '{\n\t"LimitLoadToSessionType" = "System";\n\t"Label" ='
            ' "com.salt";\n\t"OnDemand" = false;\n\t"LastExitStatus" ='
            ' 19968;\n\t"Program" = "/opt/salt.sh";\n\t"ProgramArguments" ='
            ' (\n\t\t"/opt/salt.sh";\n\t\t"--disable-keepalive";\n\t);\n};'
        )
        salt_dict = {
            "service.list": MagicMock(side_effect=CommandExecutionError),
        }
        with patch.dict(mac_service.__salt__, salt_dict):
            assert mac_service.status("com.salt") is False

    def test_get_service_on_service_dead(self):
        """
        Test service.dead changes.
        https://github.com/saltstack/salt/issues/57907
        """
        utils_dict = {
            "mac_utils.available_services": MagicMock(return_value={}),
        }
        context_dict = {
            "using_cached_services": True,
            "service.state": "dead",
        }
        name_in_service = MagicMock(side_effect=[{}, {"com.salt": True}])
        with patch.dict(mac_service.__utils__, utils_dict):
            with patch.object(mac_service, "_name_in_services", name_in_service):
                with patch.dict(mac_service.__context__, context_dict):
                    with pytest.raises(CommandExecutionError):
                        assert mac_service._get_service("com.salt")
                # find the service on a second go with no service.dead
                with patch.dict(mac_service.__context__, {}):
                    assert mac_service._get_service("com.salt") == {"com.salt": True}
