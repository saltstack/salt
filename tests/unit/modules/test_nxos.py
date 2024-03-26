"""
    :codeauthor: Mike Wiebe <@mikewiebe>
"""

import pytest

import salt.modules.cp as cp_module
import salt.modules.file as file_module
import salt.modules.nxos as nxos_module
import salt.utils.nxos as nxos_utils
import salt.utils.pycrypto
from salt.exceptions import CommandExecutionError, SaltInvocationError
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, create_autospec, patch
from tests.support.unit import TestCase
from tests.unit.modules.nxos.nxos_config import (
    config_input_file,
    config_result,
    config_result_file,
    initial_config,
    initial_config_file,
    modified_config,
    modified_config_file,
    save_running_config,
    set_role,
    template_engine_file_str,
    template_engine_file_str_file,
    unset_role,
)
from tests.unit.modules.nxos.nxos_grains import n9k_grains
from tests.unit.modules.nxos.nxos_show_cmd_output import (
    n9k_get_user_output,
    n9k_show_user_account,
    n9k_show_user_account_list,
    n9k_show_ver,
    n9k_show_ver_int_list,
    n9k_show_ver_int_list_structured,
    n9k_show_ver_list,
)
from tests.unit.modules.nxos.nxos_show_run import (
    n9k_running_config,
    n9k_show_running_config_list,
    n9k_show_running_inc_username_list,
)


class NxosTestCase(TestCase, LoaderModuleMockMixin):
    """Test cases for salt.modules.nxos"""

    COPY_RS = "copy running-config startup-config"

    def setup_loader_modules(self):
        sendline = create_autospec(
            nxos_module.sendline, autospec=True, return_value={"command": "fake_output"}
        )
        return {nxos_module: {"__proxy__": {"nxos.sendline": sendline}}}

    @staticmethod
    def test_check_virtual():
        """UT: nxos module:check_virtual method - return value"""

        result = nxos_module.__virtual__()
        assert "nxos" in result

    def test_ping_proxy(self):
        """UT: nxos module:ping method - proxy"""
        with patch("salt.utils.platform.is_proxy", return_value=True, autospec=True):
            with patch.dict(
                nxos_module.__proxy__, {"nxos.ping": MagicMock(return_value=True)}
            ):
                result = nxos_module.ping()
                self.assertTrue(result)

    def test_ping_native_minion(self):
        """UT: nxos module:ping method - proxy"""

        with patch("salt.utils.platform.is_proxy", return_value=False, autospec=True):
            with patch.dict(
                nxos_module.__utils__, {"nxos.ping": MagicMock(return_value=True)}
            ):
                result = nxos_module.ping()
                self.assertTrue(result)

    def test_check_password_return_none(self):
        """UT: nxos module:check_password method - return None"""

        username = "admin"
        password = "foo"

        with patch("salt.modules.nxos.get_user", return_value=None, autospec=True):
            result = nxos_module.check_password(username, password, encrypted=False)
            self.assertIsNone(result)

    def test_check_password_password_nxos_comment(self):
        """UT: nxos module:check_password method - password_line has '!'"""

        username = "admin"
        password = "foo"

        with patch("salt.modules.nxos.get_user", return_value="!", autospec=True):
            result = nxos_module.check_password(username, password, encrypted=False)
            self.assertFalse(result)

    @pytest.mark.skipif(
        "sha256" not in salt.utils.pycrypto.methods,
        reason="compatible crypt method for fake data not available",
    )
    def test_check_password_password_encrypted_false(self):
        """UT: nxos module:check_password method - password is not encrypted"""

        username = "salt_test"
        password = "foobar123&"

        with patch(
            "salt.modules.nxos.get_user",
            return_value=n9k_get_user_output,
            autospec=True,
        ):
            result = nxos_module.check_password(username, password, encrypted=False)
            self.assertTrue(result)

    def test_check_password_password_encrypted_true(self):
        """UT: nxos module:check_password method - password is encrypted"""

        username = "salt_test"
        password = "$5$mkXh6O4T$YUVtA89HbXCnue63kgghPlaqPHyaXhdtxPBbPEHhbRC"

        with patch(
            "salt.modules.nxos.get_user",
            return_value=n9k_get_user_output,
            autospec=True,
        ):
            result = nxos_module.check_password(username, password, encrypted=True)
            self.assertTrue(result)

    def test_check_password_password_encrypted_true_negative(self):
        """UT: nxos module:check_password method - password is not encrypted"""

        username = "salt_test"
        password = "foobar123&"

        with patch(
            "salt.modules.nxos.get_user", return_value=n9k_running_config, autospec=True
        ):
            result = nxos_module.check_password(username, password, encrypted=True)
            self.assertFalse(result)

    def test_check_role_true(self):
        """UT: nxos module:check_role method - Role configured"""

        username = "salt_test"
        roles = ["network-admin", "dev-ops"]

        with patch("salt.modules.nxos.get_roles", return_value=roles, autospec=True):
            result = nxos_module.check_role(username, "dev-ops")
            self.assertTrue(result)

    def test_check_role_false(self):
        """UT: nxos module:check_role method - Role not configured"""

        username = "salt_test"
        roles = ["network-admin", "dev-ops"]

        with patch("salt.modules.nxos.get_roles", return_value=roles, autospec=True):
            result = nxos_module.check_role(username, "network-operator")
            self.assertFalse(result)

    def test_cmd_any_function(self):
        """UT: nxos module:cmd method - check_role function"""

        with patch.dict(
            nxos_module.__salt__,
            {
                "nxos.check_role": create_autospec(
                    nxos_module.check_role, return_value=True
                )
            },
        ):
            result = nxos_module.cmd(
                "check_role",
                "salt_test",
                "network-admin",
                encrypted=True,
                __pub_fun="nxos.cmd",
            )
            self.assertTrue(result)

    def test_cmd_function_absent(self):
        """UT: nxos module:cmd method - non existent function"""

        result = nxos_module.cmd(
            "cool_new_function", "salt_test", "network-admin", encrypted=True
        )
        self.assertFalse(result)

    def test_find_single_match(self):
        """UT: nxos module:test_find method - Find single match in running config"""

        find_pattern = "^vrf context testing$"
        find_string = "vrf context testing"

        with patch(
            "salt.modules.nxos.show_run", return_value=n9k_running_config, autospec=True
        ):
            result = nxos_module.find(find_pattern)
            self.assertIn(find_string, result)

    def test_find_multiple_matches(self):
        """UT: nxos module:test_find method - Find multiple matches in running config"""

        find_pattern = "^no logging.*$"
        find_string = "no logging event link-status enable"

        with patch(
            "salt.modules.nxos.show_run", return_value=n9k_running_config, autospec=True
        ):
            result = nxos_module.find(find_pattern)
            self.assertIn(find_string, result)
            self.assertEqual(len(result), 7)

    def test_get_roles_user_not_configured(self):
        """UT: nxos module:get_roles method - User not configured"""

        username = "salt_does_not_exist"
        user_info = ""

        with patch("salt.modules.nxos.get_user", return_value=user_info, autospec=True):
            result = nxos_module.get_roles(username)
            self.assertEqual(result, [])

    def test_get_roles_user_configured(self):
        """UT: nxos module:get_roles method - User configured"""

        username = "salt_test"
        expected_result = ["network-operator", "network-admin", "dev-ops"]

        with patch("salt.modules.nxos.get_user", return_value=username, autospec=True):
            for rv in [n9k_show_user_account, n9k_show_user_account_list]:
                with patch(
                    "salt.modules.nxos.sendline", return_value=rv, autospec=True
                ):
                    result = nxos_module.get_roles(username)
                    self.assertEqual(result.sort(), expected_result.sort())

    def test_get_roles_user_configured_no_role(self):
        """UT: nxos module:get_roles method - User configured no roles"""

        username = "salt_test"

        with patch("salt.modules.nxos.get_user", return_value=username, autospec=True):
            with patch("salt.modules.nxos.sendline", return_value="", autospec=True):
                result = nxos_module.get_roles(username)
                self.assertEqual(result, [])

    def test_get_user_configured(self):
        """UT: nxos module:get_user method - User configured"""

        username = "salt_test"
        expected_output = n9k_show_running_inc_username_list[0]

        for rv in [
            n9k_show_running_inc_username_list[0],
            n9k_show_running_inc_username_list,
        ]:
            with patch("salt.modules.nxos.sendline", return_value=rv, autospec=True):
                result = nxos_module.get_user(username)
                self.assertEqual(result, expected_output)

    def test_grains(self):
        """UT: nxos module:grains method"""

        nxos_module.DEVICE_DETAILS["grains_cache"] = {}
        expected_grains = {
            "software": {
                "BIOS": "version 08.36",
                "NXOS": "version 9.2(1)",
                "BIOS compile time": "06/07/2019",
                "NXOS image file is": "bootflash:///nxos.9.2.1.bin",
                "NXOS compile time": "7/17/2018 16:00:00 [07/18/2018 00:21:19]",
            },
            "hardware": {"Device name": "n9k-device", "bootflash": "53298520 kB"},
            "plugins": ["Core Plugin", "Ethernet Plugin"],
        }
        with patch.dict(
            nxos_module.__salt__,
            {
                "utils.nxos.system_info": create_autospec(
                    nxos_utils.system_info, return_value=n9k_grains
                )
            },
        ):
            with patch(
                "salt.modules.nxos.show_ver", return_value=n9k_show_ver, autospec=True
            ):
                result = nxos_module.grains()
                self.assertEqual(result, expected_grains)

    def test_grains_get_cache(self):
        """UT: nxos module:grains method"""

        expected_grains = {
            "software": {
                "BIOS": "version 08.36",
                "NXOS": "version 9.2(1)",
                "BIOS compile time": "06/07/2019",
                "NXOS image file is": "bootflash:///nxos.9.2.1.bin",
                "NXOS compile time": "7/17/2018 16:00:00 [07/18/2018 00:21:19]",
            },
            "hardware": {"Device name": "n9k-device", "bootflash": "53298520 kB"},
            "plugins": ["Core Plugin", "Ethernet Plugin"],
        }
        nxos_module.DEVICE_DETAILS["grains_cache"] = expected_grains
        with patch.dict(
            nxos_module.__salt__,
            {
                "utils.nxos.system_info": create_autospec(
                    nxos_utils.system_info, return_value=n9k_grains
                )
            },
        ):
            with patch(
                "salt.modules.nxos.show_ver", return_value=n9k_show_ver, autospec=True
            ):
                result = nxos_module.grains()
                self.assertEqual(result, expected_grains)

    def test_grains_refresh(self):
        """UT: nxos module:grains_refresh method"""

        expected_grains = {
            "software": {
                "BIOS": "version 08.36",
                "NXOS": "version 9.2(1)",
                "BIOS compile time": "06/07/2019",
                "NXOS image file is": "bootflash:///nxos.9.2.1.bin",
                "NXOS compile time": "7/17/2018 16:00:00 [07/18/2018 00:21:19]",
            },
            "hardware": {"Device name": "n9k-device", "bootflash": "53298520 kB"},
            "plugins": ["Core Plugin", "Ethernet Plugin"],
        }

        with patch(
            "salt.modules.nxos.grains", return_value=expected_grains, autospec=True
        ):
            result = nxos_module.grains_refresh()
            self.assertEqual(result, expected_grains)

    def test_system_info(self):
        """UT: nxos module:system_info method"""

        expected_grains = {
            "software": {
                "BIOS": "version 08.36",
                "NXOS": "version 9.2(1)",
                "BIOS compile time": "06/07/2019",
                "NXOS image file is": "bootflash:///nxos.9.2.1.bin",
                "NXOS compile time": "7/17/2018 16:00:00 [07/18/2018 00:21:19]",
            },
            "hardware": {"Device name": "n9k-device", "bootflash": "53298520 kB"},
            "plugins": ["Core Plugin", "Ethernet Plugin"],
        }
        with patch.dict(
            nxos_module.__salt__,
            {
                "utils.nxos.system_info": create_autospec(
                    nxos_utils.system_info, return_value=n9k_grains
                )
            },
        ):
            with patch(
                "salt.modules.nxos.show_ver", return_value=n9k_show_ver, autospec=True
            ):
                result = nxos_module.system_info()
                self.assertEqual(result, expected_grains)

    def test_sendline_invalid_method(self):
        """UT: nxos module:sendline method - invalid method"""

        command = "show version"
        method = "invalid"

        # Execute the function under test
        result = nxos_module.sendline(command, method)

        self.assertIn("INPUT ERROR", result)

    def test_sendline_valid_method_proxy(self):
        """UT: nxos module:sendline method - valid method over proxy"""

        command = "show version"
        method = "cli_show_ascii"

        with patch("salt.utils.platform.is_proxy", return_value=True, autospec=True):
            with patch.dict(
                nxos_module.__proxy__,
                {"nxos.sendline": MagicMock(return_value=n9k_show_ver)},
            ):
                result = nxos_module.sendline(command, method)
                self.assertIn(n9k_show_ver, result)

    def test_sendline_valid_method_nxapi_uds(self):
        """UT: nxos module:sendline method - valid method over nxapi uds"""

        command = "show version"
        method = "cli_show_ascii"

        with patch("salt.utils.platform.is_proxy", MagicMock(return_value=False)):
            with patch(
                "salt.modules.nxos._nxapi_request",
                return_value=n9k_show_ver,
                autospec=True,
            ):
                result = nxos_module.sendline(command, method)
                self.assertIn(n9k_show_ver, result)

    def test_show_raw_text_invalid(self):
        """UT: nxos module:show method - invalid argument"""

        command = "show version"
        raw_text = "invalid"

        result = nxos_module.show(command, raw_text)
        self.assertIn("INPUT ERROR", result)

    def test_show_raw_text_true(self):
        """UT: nxos module:show method - raw_test true"""

        command = "show version"
        raw_text = True

        with patch(
            "salt.modules.nxos.sendline", autospec=True, return_value=n9k_show_ver
        ):
            result = nxos_module.show(command, raw_text)
            self.assertEqual(result, n9k_show_ver)

    def test_show_raw_text_true_multiple_commands(self):
        """UT: nxos module:show method - raw_test true multiple commands"""

        command = "show bgp sessions ; show processes"
        raw_text = True
        data = ["bgp_session_data", "process_data"]

        with patch("salt.modules.nxos.sendline", autospec=True, return_value=data):
            result = nxos_module.show(command, raw_text)
            self.assertEqual(result, data)

    def test_show_nxapi(self):
        """UT: nxos module:show method - nxapi returns info as list"""

        command = "show version; show interface eth1/1"
        raw_text = True

        with patch(
            "salt.modules.nxos.sendline",
            autospec=True,
            return_value=n9k_show_ver_int_list,
        ):
            result = nxos_module.show(command, raw_text)
            self.assertEqual(result[0], n9k_show_ver_int_list[0])
            self.assertEqual(result[1], n9k_show_ver_int_list[1])

    def test_show_nxapi_structured(self):
        """UT: nxos module:show method - nxapi returns info as list"""

        command = "show version; show interface eth1/1"
        raw_text = False

        with patch(
            "salt.modules.nxos.sendline",
            autospec=True,
            return_value=n9k_show_ver_int_list_structured,
        ):
            result = nxos_module.show(command, raw_text)
            self.assertEqual(result[0], n9k_show_ver_int_list_structured[0])
            self.assertEqual(result[1], n9k_show_ver_int_list_structured[1])

    def test_show_run(self):
        """UT: nxos module:show_run method"""

        expected_output = n9k_show_running_config_list[0]

        for rv in [n9k_show_running_config_list[0], n9k_show_running_config_list]:
            with patch("salt.modules.nxos.sendline", autospec=True, return_value=rv):
                result = nxos_module.show_run()
                self.assertEqual(result, expected_output)

    def test_show_ver(self):
        """UT: nxos module:show_ver method"""

        expected_output = n9k_show_ver_list[0]

        for rv in [n9k_show_ver_list[0], n9k_show_ver_list]:
            with patch("salt.modules.nxos.sendline", autospec=True, return_value=rv):
                result = nxos_module.show_ver()
                self.assertEqual(result, expected_output)

    def test_add_config(self):
        """UT: nxos module:add_config method"""

        expected_output = "COMMAND_LIST: feature bgp"

        with patch(
            "salt.modules.nxos.config", autospec=True, return_value=expected_output
        ):
            result = nxos_module.add_config("feature bgp")
            self.assertEqual(result, expected_output)

    def test_config_commands(self):
        """UT: nxos module:config method - Using commands arg"""

        commands = ["no feature ospf", ["no feature ospf"]]
        expected_output = (
            "COMMAND_LIST: no feature ospf\n\n--- \n+++ \n@@ -19,7 +19,6 @@\n feature"
            " bash-shell\n cfs eth distribute\n feature ngmvpn\n-feature ospf\n feature"
            " pim\n feature lldp\n \n"
        )

        for cmd_set in commands:
            with patch(
                "salt.modules.nxos.sendline",
                autospec=True,
                side_effect=[initial_config, modified_config],
            ):
                mock_cmd = create_autospec(
                    file_module.apply_template_on_contents,
                    return_value=template_engine_file_str,
                )
                with patch.dict(
                    nxos_module.__salt__, {"file.apply_template_on_contents": mock_cmd}
                ):
                    with patch(
                        "salt.modules.nxos._configure_device",
                        autospec=True,
                        return_value=config_result,
                    ):
                        result = nxos_module.config(cmd_set, save_config=False)
                        self.assertEqual(result, expected_output)

    def test_config_commands_template_none(self):
        """UT: nxos module:config method - Template engine is None"""

        commands = ["no feature ospf", ["no feature ospf"]]
        expected_output = (
            "COMMAND_LIST: no feature ospf\n\n--- \n+++ \n@@ -19,7 +19,6 @@\n feature"
            " bash-shell\n cfs eth distribute\n feature ngmvpn\n-feature ospf\n feature"
            " pim\n feature lldp\n \n"
        )

        for cmd_set in commands:
            with patch(
                "salt.modules.nxos.sendline",
                autospec=True,
                side_effect=[initial_config, modified_config],
            ):
                mock_cmd = create_autospec(
                    file_module.apply_template_on_contents,
                    return_value=template_engine_file_str,
                )
                with patch.dict(
                    nxos_module.__salt__, {"file.apply_template_on_contents": mock_cmd}
                ):
                    with patch(
                        "salt.modules.nxos._configure_device",
                        autospec=True,
                        return_value=config_result,
                    ):
                        result = nxos_module.config(cmd_set, template_engine=None)
                        self.assertEqual(result, expected_output)

    def test_config_commands_string(self):
        """UT: nxos module:config method - Using commands arg and output is string"""

        commands = "no feature ospf"
        expected_output = (
            "COMMAND_LIST: no feature ospf\n\n--- \n+++ \n@@ -19,7 +19,6 @@\n feature"
            " bash-shell\n cfs eth distribute\n feature ngmvpn\n-feature ospf\n feature"
            " pim\n feature lldp\n \n"
        )

        with patch(
            "salt.modules.nxos.sendline",
            autospec=True,
            side_effect=[initial_config[0], modified_config[0]],
        ):
            mock_cmd = create_autospec(
                file_module.apply_template_on_contents,
                return_value=template_engine_file_str,
            )
            with patch.dict(
                nxos_module.__salt__, {"file.apply_template_on_contents": mock_cmd}
            ):
                with patch(
                    "salt.modules.nxos._configure_device",
                    autospec=True,
                    return_value=config_result,
                ):
                    result = nxos_module.config(commands)
                    self.assertEqual(result, expected_output)

    def test_config_file(self):
        """UT: nxos module:config method - Using config_file arg"""

        config_file = "salt://bgp_config.txt"
        expected_output = (
            "COMMAND_LIST: feature bgp ; ! ; router bgp 55 ; address-family ipv4"
            " unicast ; no client-to-client reflection ; additional-paths send\n\n---"
            " \n+++ \n@@ -19,6 +19,7 @@\n feature bash-shell\n cfs eth distribute\n"
            " feature ngmvpn\n+feature bgp\n feature pim\n feature lldp\n \n@@ -233,6"
            " +234,10 @@\n line console\n line vty\n boot nxos"
            " bootflash:/nxos.9.2.4.bin \n+router bgp 55\n+  address-family ipv4"
            " unicast\n+    no client-to-client reflection\n+    additional-paths"
            " send\n \n no logging logfile\n no logging monitor\n"
        )

        with patch(
            "salt.modules.nxos.sendline",
            autospec=True,
            side_effect=[initial_config_file, modified_config_file],
        ):
            mock_cmd = create_autospec(
                cp_module.get_file_str, return_value=config_input_file
            )
            with patch.dict(nxos_module.__salt__, {"cp.get_file_str": mock_cmd}):
                mock_cmd = create_autospec(
                    file_module.apply_template_on_contents,
                    return_value=template_engine_file_str_file,
                )
                with patch.dict(
                    nxos_module.__salt__, {"file.apply_template_on_contents": mock_cmd}
                ):
                    with patch(
                        "salt.modules.nxos._configure_device",
                        autospec=True,
                        return_value=config_result_file,
                    ):
                        result = nxos_module.config(config_file=config_file)
                        self.assertEqual(result, expected_output)

    def test_config_file_error1(self):
        """UT: nxos module:config method - Error file not found"""

        config_file = "salt://bgp_config.txt"

        with patch(
            "salt.modules.nxos.sendline",
            autospec=True,
            side_effect=[initial_config_file, modified_config_file],
        ):
            mock_cmd = create_autospec(cp_module.get_file_str, return_value=False)
            with patch.dict(nxos_module.__salt__, {"cp.get_file_str": mock_cmd}):
                mock_cmd = create_autospec(
                    file_module.apply_template_on_contents,
                    return_value=template_engine_file_str_file,
                )
                with patch.dict(
                    nxos_module.__salt__, {"file.apply_template_on_contents": mock_cmd}
                ):
                    with patch(
                        "salt.modules.nxos._configure_device",
                        autospec=True,
                        return_value=config_result_file,
                    ):
                        with self.assertRaises(CommandExecutionError):
                            nxos_module.config(config_file=config_file)

    def test_config_nxos_error_ssh(self):
        """UT: nxos module:config method - nxos device error over ssh transport"""

        commands = ["feature bgp", "router bgp 57"]
        config_result = [
            ["feature bgp", "router bgp 57"],
            "bgp instance is already running; Tag is 55",
        ]
        expected_output = (
            "COMMAND_LIST: feature bgp ; router bgp 57\nbgp instance is already"
            " running; Tag is 55\n--- \n+++ \n@@ -19,7 +19,6 @@\n feature bash-shell\n"
            " cfs eth distribute\n feature ngmvpn\n-feature ospf\n feature pim\n"
            " feature lldp\n \n"
        )

        with patch(
            "salt.modules.nxos.sendline",
            autospec=True,
            side_effect=[initial_config[0], modified_config[0]],
        ):
            mock_cmd = create_autospec(
                file_module.apply_template_on_contents,
                return_value=template_engine_file_str,
            )
            with patch.dict(
                nxos_module.__salt__, {"file.apply_template_on_contents": mock_cmd}
            ):
                with patch(
                    "salt.modules.nxos._configure_device",
                    autospec=True,
                    return_value=config_result,
                ):
                    result = nxos_module.config(commands)
                    self.assertEqual(result, expected_output)

    def test_commands_error(self):
        """UT: nxos module:config method - Mandatory arg commands not specified"""

        commands = None

        with patch(
            "salt.modules.nxos.sendline",
            autospec=True,
            side_effect=[initial_config_file, modified_config_file],
        ):
            mock_cmd = create_autospec(cp_module.get_file_str, return_value=False)
            with patch.dict(nxos_module.__salt__, {"cp.get_file_str": mock_cmd}):
                mock_cmd = create_autospec(
                    file_module.apply_template_on_contents,
                    return_value=template_engine_file_str_file,
                )
                with patch.dict(
                    nxos_module.__salt__, {"file.apply_template_on_contents": mock_cmd}
                ):
                    with patch(
                        "salt.modules.nxos._configure_device",
                        autospec=True,
                        return_value=config_result_file,
                    ):
                        with self.assertRaises(CommandExecutionError):
                            nxos_module.config(commands=commands)

    def test_config_file_error2(self):
        """UT: nxos module:config method - Mandatory arg config_file not specified"""

        config_file = None

        with patch(
            "salt.modules.nxos.sendline",
            autospec=True,
            side_effect=[initial_config_file, modified_config_file],
        ):
            mock_cmd = create_autospec(cp_module.get_file_str, return_value=False)
            with patch.dict(nxos_module.__salt__, {"cp.get_file_str": mock_cmd}):
                mock_cmd = create_autospec(
                    file_module.apply_template_on_contents,
                    return_value=template_engine_file_str_file,
                )
                with patch.dict(
                    nxos_module.__salt__, {"file.apply_template_on_contents": mock_cmd}
                ):
                    with patch(
                        "salt.modules.nxos._configure_device",
                        autospec=True,
                        return_value=config_result_file,
                    ):
                        with self.assertRaises(CommandExecutionError):
                            nxos_module.config(config_file=config_file)

    def test_delete_config(self):
        """UT: nxos module:delete_config method"""

        for lines in ["feature bgp", ["feature bgp"]]:
            with patch("salt.modules.nxos.config", autospec=True):
                result = nxos_module.delete_config(lines)
                nxos_module.config.assert_called_with(["no feature bgp"])
                self.assertEqual(result, nxos_module.config.return_value)

    def test_remove_user(self):
        """UT: nxos module:remove_user method"""

        with patch("salt.modules.nxos.config", autospec=True):
            result = nxos_module.remove_user("salt_test")
            nxos_module.config.assert_called_with("no username salt_test")
            self.assertEqual(result, nxos_module.config.return_value)

    def test_replace(self):
        """UT: nxos module:replace method"""

        old_value = "feature bgp"
        new_value = "feature ospf"

        with patch(
            "salt.modules.nxos.show_run",
            autospec=True,
            return_value=n9k_show_running_config_list[0],
        ):
            with patch(
                "salt.modules.nxos.delete_config", autospec=True, return_value=None
            ):
                with patch(
                    "salt.modules.nxos.config", autospec=True, return_value=None
                ):
                    result = nxos_module.replace(old_value, new_value)
                    self.assertEqual(result["old"], ["feature bgp"])
                    self.assertEqual(result["new"], ["feature ospf"])

    def test_replace_full_match_true(self):
        """UT: nxos module:replace method - full match true"""

        old_value = "feature bgp"
        new_value = "feature ospf"

        with patch(
            "salt.modules.nxos.show_run",
            autospec=True,
            return_value=n9k_show_running_config_list[0],
        ):
            with patch(
                "salt.modules.nxos.delete_config", autospec=True, return_value=None
            ):
                with patch(
                    "salt.modules.nxos.config", autospec=True, return_value=None
                ):
                    result = nxos_module.replace(old_value, new_value, full_match=True)
                    self.assertEqual(result["old"], ["feature bgp"])
                    self.assertEqual(result["new"], ["feature ospf"])

    def test_replace_no_match(self):
        """UT: nxos module:replace method - no match"""

        old_value = "feature does_not_exist"
        new_value = "feature ospf"

        with patch(
            "salt.modules.nxos.show_run",
            autospec=True,
            return_value=n9k_show_running_config_list[0],
        ):
            with patch(
                "salt.modules.nxos.delete_config", autospec=True, return_value=None
            ):
                with patch(
                    "salt.modules.nxos.config", autospec=True, return_value=None
                ):
                    result = nxos_module.replace(old_value, new_value)
                    self.assertEqual(result["old"], [])
                    self.assertEqual(result["new"], [])

    def test_save_running_config(self):
        """UT: nxos module:save_running_config method"""

        with patch(
            "salt.modules.nxos.config", autospec=True, return_value=save_running_config
        ):
            result = nxos_module.save_running_config()
            self.assertEqual(result, save_running_config)

    def test_set_password_enc_false_cs_none(self):
        """UT: nxos module:set_password method - encrypted False, crypt_salt None"""

        username = "devops"
        password = "test123TMM^&"
        hashed_pass = "$5$ZcZqm15X$exHN2m6yrPKpYhGArK3Vml3ZjNbJaJYdzWyf0fp1Up2"
        config_line = (
            "username devops password 5"
            " $5$ZcZqm15X$exHN2m6yrPKpYhGArK3Vml3ZjNbJaJYdzWyf0fp1Up2"
        )

        with patch("salt.modules.nxos.get_user", autospec=True):
            with patch(
                "salt.modules.nxos.gen_hash", autospec=True, return_value=hashed_pass
            ):
                with patch(
                    "salt.modules.nxos.config",
                    autospec=True,
                    return_value="password_set",
                ) as config:
                    result = nxos_module.set_password(username, password)
                    config.assert_called_with(config_line)
                    self.assertEqual("password_set", result)

    def test_set_password_enc_false_cs_set(self):
        """UT: nxos module:set_password method - encrypted False, crypt_salt set"""

        username = "devops"
        password = "test123TMM^&"
        crypt_salt = "ZcZqm15X"
        hashed_pass = "$5$ZcZqm15X$exHN2m6yrPKpYhGArK3Vml3ZjNbJaJYdzWyf0fp1Up2"
        config_line = (
            "username devops password 5"
            " $5$ZcZqm15X$exHN2m6yrPKpYhGArK3Vml3ZjNbJaJYdzWyf0fp1Up2"
        )

        with patch("salt.modules.nxos.get_user", autospec=True):
            with patch(
                "salt.modules.nxos.gen_hash", autospec=True, return_value=hashed_pass
            ):
                with patch(
                    "salt.modules.nxos.config",
                    autospec=True,
                    return_value="password_set",
                ) as config:
                    result = nxos_module.set_password(
                        username, password, crypt_salt=crypt_salt
                    )
                    config.assert_called_with(config_line)
                    self.assertEqual("password_set", result)

    def test_set_password_enc_true(self):
        """UT: nxos module:set_password method - encrypted True"""

        username = "devops"
        password = "test123TMM^&"
        hashed_pass = "$5$ZcZqm15X$exHN2m6yrPKpYhGArK3Vml3ZjNbJaJYdzWyf0fp1Up2"
        config_line = "username devops password 5 test123TMM^&"

        with patch("salt.modules.nxos.get_user", autospec=True):
            with patch(
                "salt.modules.nxos.gen_hash", autospec=True, return_value=hashed_pass
            ):
                with patch(
                    "salt.modules.nxos.config",
                    autospec=True,
                    return_value="password_set",
                ) as config:
                    result = nxos_module.set_password(
                        username, password, encrypted=True
                    )
                    config.assert_called_with(config_line)
                    self.assertEqual("password_set", result)

    def test_set_password_role_none(self):
        """UT: nxos module:set_password method - role none"""

        username = "devops"
        password = "test123TMM^&"
        hashed_pass = "$5$ZcZqm15X$exHN2m6yrPKpYhGArK3Vml3ZjNbJaJYdzWyf0fp1Up2"
        config_line = "username devops password 5 test123TMM^& role devops"

        with patch("salt.modules.nxos.get_user", autospec=True):
            with patch(
                "salt.modules.nxos.gen_hash", autospec=True, return_value=hashed_pass
            ):
                with patch(
                    "salt.modules.nxos.config",
                    autospec=True,
                    return_value="password_set",
                ) as config:
                    # Execute the function under test
                    result = nxos_module.set_password(
                        username, password, encrypted=True, role="devops"
                    )
                    config.assert_called_with(config_line)
                    self.assertEqual("password_set", result)

    def test_set_password_blowfish_crypt(self):
        """UT: nxos module:set_password method - role none"""

        with self.assertRaises(SaltInvocationError):
            nxos_module.set_password(
                "username", "password", encrypted=True, algorithm="blowfish"
            )

    def test_set_role(self):
        """UT: nxos module:save_running_config method"""

        username = "salt_test"
        role = "vdc-admin"

        with patch("salt.modules.nxos.config", autospec=True, return_value=set_role):
            result = nxos_module.set_role(username, role)
            self.assertEqual(result, set_role)

    def test_unset_role(self):
        """UT: nxos module:save_running_config method"""

        username = "salt_test"
        role = "vdc-admin"

        with patch("salt.modules.nxos.config", autospec=True, return_value=unset_role):
            result = nxos_module.unset_role(username, role)
            self.assertEqual(result, unset_role)

    def test_configure_device(self):
        """UT: nxos module:_configure_device method"""

        with patch("salt.utils.platform.is_proxy", autospec=True, return_value=True):
            with patch.dict(
                nxos_module.__proxy__,
                {"nxos.proxy_config": MagicMock(return_value="configured")},
            ):
                result = nxos_module._configure_device("feature bgp")
                self.assertEqual(result, "configured")

        with patch("salt.utils.platform.is_proxy", autospec=True, return_value=False):
            with patch.object(
                nxos_module, "_nxapi_config", MagicMock(return_value="configured")
            ):
                nxos_module._configure_device("feature bgp")
                self.assertEqual(result, "configured")

    def test_nxapi_config(self):
        """UT: nxos module:_nxapi_config method"""

        mock_cmd = MagicMock(return_value={"nxos": {"save_config": False}})
        with patch.dict(nxos_module.__salt__, {"config.get": mock_cmd}):
            with patch(
                "salt.modules.nxos._nxapi_request",
                return_value="router_data",
                autospec=True,
            ):
                result = nxos_module._nxapi_config("show version")
                self.assertEqual(result, [["show version"], "router_data"])

    def test_nxapi_config_failure(self):
        """UT: nxos module:_nxapi_config method"""

        side_effect = ["Failure", "saved_data"]

        mock_cmd = MagicMock(return_value={"nxos": {"save_config": True}})
        with patch.dict(nxos_module.__salt__, {"config.get": mock_cmd}):
            with patch(
                "salt.modules.nxos._nxapi_request",
                side_effect=side_effect,
                autospec=True,
            ):
                result = nxos_module._nxapi_config("show bad_command")
                self.assertEqual(result, [["show bad_command"], "Failure"])

    def test_nxapi_request_proxy(self):
        """UT: nxos module:_nxapi_request method - proxy"""

        with patch("salt.utils.platform.is_proxy", autospec=True, return_value=True):
            mock_request = create_autospec(
                nxos_utils.nxapi_request, return_value="router_data"
            )
            with patch.dict(
                nxos_module.__proxy__, {"nxos._nxapi_request": mock_request}
            ):
                result = nxos_module._nxapi_request("show version")
                self.assertEqual(result, "router_data")

    def test_nxapi_request_no_proxy(self):
        """UT: nxos module:_nxapi_request method - no proxy"""

        with patch("salt.utils.platform.is_proxy", autospec=True, return_value=False):
            mock_cmd = MagicMock(return_value={"nxos": {"save_config": False}})
            with patch.dict(nxos_module.__salt__, {"config.get": mock_cmd}):
                mock_request = create_autospec(nxos_utils.nxapi_request)
                with patch.dict(
                    nxos_module.__utils__, {"nxos.nxapi_request": mock_request}
                ):
                    result = nxos_module._nxapi_request("show version")
                    self.assertEqual(result, mock_request.return_value)
                    mock_request.assert_called_with(
                        "show version", "cli_conf", **mock_cmd.return_value
                    )
