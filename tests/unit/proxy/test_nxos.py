"""
    :codeauthor: Mike Wiebe <@mikewiebe>
"""

# Copyright (c) 2019 Cisco and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import salt.proxy.nxos as nxos_proxy
import salt.utils.nxos as nxos_utils
from salt.exceptions import CommandExecutionError
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, create_autospec, patch
from tests.support.unit import TestCase
from tests.unit.modules.nxos.nxos_grains import n9k_grains
from tests.unit.modules.nxos.nxos_show_cmd_output import n9k_show_ver_list


class NxosNxapiProxyTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {nxos_proxy: {"CONNECTION": "nxapi"}}

    def test_check_virtual(self):

        """UT: nxos module:check_virtual method - return value"""

        result = nxos_proxy.__virtual__()
        self.assertIn("nxos", result)

    def test_init(self):

        """UT: nxos module:init method - nxapi proxy"""

        with patch.object(nxos_proxy, "__opts__", {"proxy": {"connection": "nxapi"}}):
            with patch("salt.proxy.nxos._init_nxapi", autospec=True) as init_nxapi:
                result = nxos_proxy.init()
                self.assertEqual(result, init_nxapi.return_value)

    def test_init_opts_none(self):

        """UT: nxos module:init method - __opts__ connection is None"""

        with patch.object(nxos_proxy, "__opts__", {"proxy": {"connection": None}}):
            with patch("salt.proxy.nxos._init_nxapi", autospec=True) as init_nxapi:
                result = nxos_proxy.init()
                self.assertEqual(result, init_nxapi.return_value)

    def test_init_bad_connection_type(self):

        """UT: nxos module:init method - bad CONNECTION type"""
        with patch.object(nxos_proxy, "__opts__", {"proxy": {"connection": "unknown"}}):
            self.assertFalse(nxos_proxy.init())

    def test_initialized(self):

        """UT: nxos module:initialized method - nxapi proxy"""

        with patch(
            "salt.proxy.nxos._initialized_nxapi", autospec=True
        ) as initialized_nxapi:
            result = nxos_proxy.initialized()
            self.assertEqual(result, initialized_nxapi.return_value)

    def test_ping(self):

        """UT: nxos module:ping method - nxapi proxy"""

        with patch("salt.proxy.nxos._ping_nxapi", autospec=True) as ping_nxapi:
            result = nxos_proxy.ping()
            self.assertEqual(result, ping_nxapi.return_value)

    def test_grains(self):

        """UT: nxos module:grains method - nxapi grains"""

        with patch(
            "salt.proxy.nxos.sendline", autospec=True, return_value=n9k_show_ver_list
        ):
            result = nxos_proxy.grains()
            self.assertEqual(result, n9k_grains)

    def test_grains_cache_set(self):

        """UT: nxos module:grains method - nxapi grains cache set"""

        with patch(
            "salt.proxy.nxos.DEVICE_DETAILS", {"grains_cache": n9k_grains["nxos"]}
        ):
            with patch(
                "salt.proxy.nxos.sendline",
                autospec=True,
                return_value=n9k_show_ver_list,
            ):
                result = nxos_proxy.grains()
                self.assertEqual(result, n9k_grains)

    def test_grains_refresh(self):

        """UT: nxos module:grains_refresh method - nxapi grains"""

        device_details = {"grains_cache": None}

        with patch("salt.proxy.nxos.DEVICE_DETAILS", device_details):
            with patch("salt.proxy.nxos.grains", autospec=True) as grains:
                result = nxos_proxy.grains_refresh()
                self.assertEqual(nxos_proxy.DEVICE_DETAILS["grains_cache"], {})
                self.assertEqual(result, grains.return_value)

    def test_sendline(self):

        """UT: nxos module:sendline method - nxapi"""

        command = "show version"

        with patch("salt.proxy.nxos._nxapi_request", autospec=True) as nxapi_request:
            result = nxos_proxy.sendline(command)
            self.assertEqual(result, nxapi_request.return_value)

    def test_proxy_config(self):

        """UT: nxos module:proxy_config method - nxapi success path"""

        commands = ["feature bgp", "router bgp 65535"]

        with patch("salt.proxy.nxos.DEVICE_DETAILS", {"save_config": False}):
            with patch(
                "salt.proxy.nxos._nxapi_request", autospec=True
            ) as nxapi_request:
                result = nxos_proxy.proxy_config(commands)
                self.assertEqual(result, [commands, nxapi_request.return_value])

    def test_proxy_config_save_config(self):

        """UT: nxos module:proxy_config method - nxapi success path"""

        commands = ["feature bgp", "router bgp 65535"]

        with patch("salt.proxy.nxos.DEVICE_DETAILS", {"save_config": None}):
            with patch(
                "salt.proxy.nxos._nxapi_request", autospec=True
            ) as nxapi_request:
                result = nxos_proxy.proxy_config(commands, save_config=True)
                self.assertEqual(result, [commands, nxapi_request.return_value])

    def test__init_nxapi(self):

        """UT: nxos module:_init_nxapi method - successful connectinon"""

        opts = {"proxy": {"arg1": None}}
        nxapi_request = create_autospec(nxos_utils.nxapi_request, return_value="data")

        with patch("salt.proxy.nxos.DEVICE_DETAILS", {}) as device_details:
            with patch(
                "salt.proxy.nxos.__utils__", {"nxos.nxapi_request": nxapi_request}
            ):
                result = nxos_proxy._init_nxapi(opts)

                self.assertTrue(device_details["initialized"])
                self.assertTrue(device_details["up"])
                self.assertTrue(device_details["save_config"])
                self.assertTrue(result)

                nxapi_request.assert_called_with("show clock", **opts["proxy"])

    def test_bad__init_nxapi(self):
        class NXAPIException(Exception):
            pass

        nxapi_request = create_autospec(
            nxos_utils.nxapi_request, side_effect=NXAPIException
        )

        with patch("salt.proxy.nxos.__utils__", {"nxos.nxapi_request": nxapi_request}):
            with patch("salt.proxy.nxos.log", autospec=True) as log:
                with self.assertRaises(NXAPIException):
                    nxos_proxy._init_nxapi({"proxy": {"host": "HOST"}})
                log.error.assert_called()

    def test__initialized_nxapi(self):

        """UT: nxos module:_initialized_nxapi method"""

        result = nxos_proxy._initialized_nxapi()
        self.assertFalse(result)

        with patch("salt.proxy.nxos.DEVICE_DETAILS", {"initialized": True}):
            result = nxos_proxy._initialized_nxapi()
            self.assertTrue(result)

    def test__ping_nxapi(self):

        """UT: nxos module:_ping_nxapi method"""

        result = nxos_proxy._ping_nxapi()
        self.assertFalse(result)

        with patch("salt.proxy.nxos.DEVICE_DETAILS", {"up": True}):
            result = nxos_proxy._ping_nxapi()
            self.assertTrue(result)

    def test__shutdown_nxapi(self):

        """UT: nxos module:_shutdown_nxapi method"""

        opts = {"id": "value"}

        with patch("salt.proxy.nxos.log", autospec=True):
            nxos_proxy._shutdown_nxapi()
            # nothing to test

    def test__nxapi_request_ssh_return(self):

        """UT: nxos module:_nxapi_request method - CONNECTION == 'ssh'"""

        commands = "show version"

        with patch("salt.proxy.nxos.CONNECTION", "ssh"):
            result = nxos_proxy._nxapi_request(commands)
            self.assertEqual("_nxapi_request is not available for ssh proxy", result)

    def test__nxapi_request_connect(self):

        """UT: nxos module:_nxapi_request method"""

        commands = "show version"
        nxapi_request = create_autospec(nxos_utils.nxapi_request, return_value="data")

        with patch("salt.proxy.nxos.DEVICE_DETAILS", {"conn_args": {"arg1": None}}):
            with patch(
                "salt.proxy.nxos.__utils__", {"nxos.nxapi_request": nxapi_request}
            ):
                result = nxos_proxy._nxapi_request(commands)
                self.assertEqual("data", result)
                nxapi_request.assert_called_with(commands, method="cli_conf", arg1=None)


class NxosSSHProxyTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {
            nxos_proxy: {
                "__opts__": {
                    "proxy": {
                        "host": "dt-n9k5-1.cisco.com",
                        "username": "admin",
                        "password": "password",
                    }
                },
                "CONNECTION": "ssh",
            }
        }

    def test_init(self):

        """UT: nxos module:init method - ssh proxy"""

        with patch("salt.proxy.nxos._init_ssh", autospec=True) as init_ssh:
            result = nxos_proxy.init()
            self.assertEqual(result, init_ssh.return_value)

    def test_init_opts_none(self):

        """UT: nxos module:init method - __opts__ connection is None"""

        with patch("salt.proxy.nxos.__opts__", {"proxy": {"connection": None}}):
            with patch("salt.proxy.nxos._init_ssh", autospec=True) as init_ssh:
                result = nxos_proxy.init()
                self.assertEqual(result, init_ssh.return_value)

    def test_initialized(self):

        """UT: nxos module:initialized method - ssh proxy"""

        with patch(
            "salt.proxy.nxos._initialized_ssh", autospec=True
        ) as initialized_ssh:
            result = nxos_proxy.initialized()
            self.assertEqual(result, initialized_ssh.return_value)

    def test_ping(self):

        """UT: nxos module:ping method - ssh proxy"""

        with patch("salt.proxy.nxos._ping_ssh", autospec=True) as ping_ssh:
            result = nxos_proxy.ping()
            self.assertEqual(result, ping_ssh.return_value)

    def test_grains(self):

        """UT: nxos module:grains method - ssh grains"""

        with patch(
            "salt.proxy.nxos.sendline", autospec=True, return_value=n9k_show_ver_list[0]
        ):
            result = nxos_proxy.grains()
            self.assertEqual(result, n9k_grains)

    def test_sendline(self):

        """UT: nxos module:sendline method - nxapi"""

        command = "show version"

        with patch("salt.proxy.nxos._sendline_ssh", autospec=True) as sendline_ssh:
            result = nxos_proxy.sendline(command)
            self.assertEqual(result, sendline_ssh.return_value)

    def test_proxy_config(self):

        """UT: nxos module:proxy_config method - ssh success path"""

        commands = ["feature bgp", "router bgp 65535"]

        with patch("salt.proxy.nxos.DEVICE_DETAILS", {"save_config": False}):
            with patch("salt.proxy.nxos._sendline_ssh", autospec=True) as sendline_ssh:
                result = nxos_proxy.proxy_config(commands)
                self.assertEqual(result, [commands, sendline_ssh.return_value])

    def test_proxy_config_save_config(self):

        """UT: nxos module:proxy_config method - ssh success path"""

        commands = ["feature bgp", "router bgp 65535"]

        with patch("salt.proxy.nxos.DEVICE_DETAILS", {"save_config": None}):
            with patch("salt.proxy.nxos._sendline_ssh", autospec=True) as sendline_ssh:
                result = nxos_proxy.proxy_config(commands, save_config=True)
                self.assertEqual(result, [commands, sendline_ssh.return_value])

    def test_proxy_config_error(self):

        """UT: nxos module:proxy_config method - CommandExecutionError"""

        with patch(
            "salt.proxy.nxos._sendline_ssh",
            autospec=True,
            side_effect=CommandExecutionError,
        ):
            with self.assertRaises(CommandExecutionError):
                nxos_proxy.proxy_config("show version", save_config=True)

    def test__init_ssh_device_details(self):
        with patch("salt.proxy.nxos.SSHConnection", autospec=True) as SSHConnection:
            SSHConnection().sendline.return_value = ["", ""]

            with patch("salt.proxy.nxos.DEVICE_DETAILS", {}) as device_details:
                nxos_proxy._init_ssh(None)
                self.assertIn(nxos_proxy._worker_name(), device_details)
                self.assertTrue(device_details["initialized"])
                self.assertTrue(device_details["save_config"])

            with patch.dict(nxos_proxy.__opts__["proxy"], {"save_config": False}):
                with patch("salt.proxy.nxos.DEVICE_DETAILS", {}) as device_details:
                    nxos_proxy._init_ssh(None)
                    self.assertIn(nxos_proxy._worker_name(), device_details)
                    self.assertTrue(device_details["initialized"])
                    self.assertFalse(device_details["save_config"])

    def test__init_ssh_opts(self):

        """UT: nxos module:_init_ssh method - successful connectinon"""

        with patch("salt.proxy.nxos.DEVICE_DETAILS", {}):
            with patch("salt.proxy.nxos.SSHConnection", autospec=True) as SSHConnection:
                SSHConnection().sendline.return_value = ["", ""]
                nxos_proxy._init_ssh(None)
                self.assertEqual(
                    nxos_proxy.__opts__["proxy"]["host"],
                    SSHConnection.call_args[1]["host"],
                )

                opts = MagicMock()
                nxos_proxy._init_ssh(opts)
                self.assertEqual(
                    opts["proxy"]["host"], SSHConnection.call_args[1]["host"]
                )

    def test__init_ssh_prompt(self):

        """UT: nxos module:_init_ssh method - prompt regex"""

        with patch("salt.proxy.nxos.DEVICE_DETAILS", {}):
            with patch("salt.proxy.nxos.SSHConnection", autospec=True) as SSHConnection:
                SSHConnection().sendline.return_value = ["", ""]

                with patch.dict(
                    nxos_proxy.__opts__["proxy"], {"prompt_regex": "n9k.*device"}
                ):
                    nxos_proxy._init_ssh(None)
                    self.assertEqual(
                        "n9k.*device", SSHConnection.call_args[1]["prompt"]
                    )

                with patch.dict(
                    nxos_proxy.__opts__["proxy"], {"prompt_name": "n9k-device"}
                ):
                    nxos_proxy._init_ssh(None)
                    self.assertEqual(
                        "n9k-device.*#", SSHConnection.call_args[1]["prompt"]
                    )

                nxos_proxy._init_ssh(None)
                self.assertEqual(".+#$", SSHConnection.call_args[1]["prompt"])

    def test__initialized_ssh(self):

        """UT: nxos module:_initialized_ssh method"""

        with patch("salt.proxy.nxos.DEVICE_DETAILS", {"initialized": True}):
            result = nxos_proxy._initialized_ssh()
            self.assertTrue(result)

        with patch("salt.proxy.nxos.DEVICE_DETAILS", {}):
            result = nxos_proxy._initialized_ssh()
            self.assertFalse(result)

    def test__parse_output_for_errors(self):

        """UT: nxos module:_parse_output_for_errors method"""

        data = "% Incomplete command at '^' marker."
        command = "show"

        with self.assertRaises(CommandExecutionError):
            nxos_proxy._parse_output_for_errors(
                data, command, error_pattern="Incomplete"
            )

        data = "% Incomplete command at '^' marker."
        command = "show"

        with self.assertRaises(CommandExecutionError):
            nxos_proxy._parse_output_for_errors(
                data, command, error_pattern=["Incomplete", "marker"]
            )

        data = "% Invalid command at '^' marker."
        command = "show bep"

        with self.assertRaises(CommandExecutionError):
            nxos_proxy._parse_output_for_errors(data, command)

        data = "% Incomplete command at '^' marker."
        command = "show"

        nxos_proxy._parse_output_for_errors(data, command)

        data = "% Incomplete command at '^' marker."
        command = "show"

        nxos_proxy._parse_output_for_errors(data, command, error_pattern="foo")

    def test__init_ssh_raise_exception(self):

        """UT: nxos module:_init_ssh method - raise exception"""

        class SSHException(Exception):
            pass

        with patch("salt.proxy.nxos.SSHConnection", autospec=True) as SSHConnection:
            with patch("salt.proxy.nxos.log", autospec=True) as log:
                with self.assertRaises(SSHException):
                    SSHConnection.side_effect = SSHException
                    nxos_proxy._init_ssh(None)
                log.error.assert_called()
