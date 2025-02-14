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

import pytest

import salt.proxy.nxos as nxos_proxy
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch
from tests.unit.modules.nxos.nxos_grains import n9k_grains
from tests.unit.modules.nxos.nxos_show_cmd_output import n9k_show_ver_list


@pytest.fixture
def configure_loader_modules():
    with patch("salt.proxy.nxos.CONNECTION", "ssh"):
        return {
            nxos_proxy: {
                "__opts__": {
                    "proxy": {
                        "host": "dt-n9k5-1.cisco.com",
                        "username": "admin",
                        "password": "password",
                    }
                },
            }
        }


def test_init():
    """UT: nxos module:init method - ssh proxy"""

    with patch("salt.proxy.nxos._init_ssh", autospec=True) as init_ssh:
        result = nxos_proxy.init()
        assert result == init_ssh.return_value


def test_init_opts_none():
    """UT: nxos module:init method - __opts__ connection is None"""

    with patch("salt.proxy.nxos.__opts__", {"proxy": {"connection": None}}):
        with patch("salt.proxy.nxos._init_ssh", autospec=True) as init_ssh:
            result = nxos_proxy.init()
            assert result == init_ssh.return_value


def test_initialized():
    """UT: nxos module:initialized method - ssh proxy"""

    with patch("salt.proxy.nxos._initialized_ssh", autospec=True) as initialized_ssh:
        result = nxos_proxy.initialized()
        assert result == initialized_ssh.return_value


def test_ping():
    """UT: nxos module:ping method - ssh proxy"""

    with patch("salt.proxy.nxos._ping_ssh", autospec=True) as ping_ssh:
        result = nxos_proxy.ping()
        assert result == ping_ssh.return_value


def test_grains():
    """UT: nxos module:grains method - ssh grains"""

    with patch(
        "salt.proxy.nxos.sendline", autospec=True, return_value=n9k_show_ver_list[0]
    ):
        result = nxos_proxy.grains()
        assert result == n9k_grains


def test_sendline():
    """UT: nxos module:sendline method - nxapi"""

    command = "show version"

    with patch("salt.proxy.nxos._sendline_ssh", autospec=True) as sendline_ssh:
        result = nxos_proxy.sendline(command)
        assert result == sendline_ssh.return_value


def test_proxy_config():
    """UT: nxos module:proxy_config method - ssh success path"""

    commands = ["feature bgp", "router bgp 65535"]

    with patch("salt.proxy.nxos.DEVICE_DETAILS", {"save_config": False}):
        with patch("salt.proxy.nxos._sendline_ssh", autospec=True) as sendline_ssh:
            result = nxos_proxy.proxy_config(commands)
            assert result == [commands, sendline_ssh.return_value]


def test_proxy_config_save_config():
    """UT: nxos module:proxy_config method - ssh success path"""

    commands = ["feature bgp", "router bgp 65535"]

    with patch("salt.proxy.nxos.DEVICE_DETAILS", {"save_config": None}):
        with patch("salt.proxy.nxos._sendline_ssh", autospec=True) as sendline_ssh:
            result = nxos_proxy.proxy_config(commands, save_config=True)
            assert result == [commands, sendline_ssh.return_value]


def test_proxy_config_error():
    """UT: nxos module:proxy_config method - CommandExecutionError"""

    with patch(
        "salt.proxy.nxos._sendline_ssh",
        autospec=True,
        side_effect=CommandExecutionError,
    ):
        with pytest.raises(CommandExecutionError):
            nxos_proxy.proxy_config("show version", save_config=True)


def test__init_ssh_device_details():
    with patch("salt.proxy.nxos.SSHConnection", autospec=True) as SSHConnection:
        SSHConnection().sendline.return_value = ["", ""]

        with patch("salt.proxy.nxos.DEVICE_DETAILS", {}) as device_details:
            nxos_proxy._init_ssh(None)
            assert nxos_proxy._worker_name() in device_details
            assert device_details["initialized"]
            assert device_details["save_config"]

        with patch.dict(nxos_proxy.__opts__["proxy"], {"save_config": False}):
            with patch("salt.proxy.nxos.DEVICE_DETAILS", {}) as device_details:
                nxos_proxy._init_ssh(None)
                assert nxos_proxy._worker_name() in device_details
                assert device_details["initialized"]
                assert not device_details["save_config"]


def test__init_ssh_opts():
    """UT: nxos module:_init_ssh method - successful connectinon"""

    with patch("salt.proxy.nxos.DEVICE_DETAILS", {}):
        with patch("salt.proxy.nxos.SSHConnection", autospec=True) as SSHConnection:
            SSHConnection().sendline.return_value = ["", ""]
            nxos_proxy._init_ssh(None)
            assert (
                nxos_proxy.__opts__["proxy"]["host"]
                == SSHConnection.call_args[1]["host"]
            )

            opts = MagicMock()
            nxos_proxy._init_ssh(opts)
            assert opts["proxy"]["host"] == SSHConnection.call_args[1]["host"]


def test__init_ssh_prompt():
    """UT: nxos module:_init_ssh method - prompt regex"""

    with patch("salt.proxy.nxos.DEVICE_DETAILS", {}):
        with patch("salt.proxy.nxos.SSHConnection", autospec=True) as SSHConnection:
            SSHConnection().sendline.return_value = ["", ""]

            with patch.dict(
                nxos_proxy.__opts__["proxy"], {"prompt_regex": "n9k.*device"}
            ):
                nxos_proxy._init_ssh(None)
                assert "n9k.*device" == SSHConnection.call_args[1]["prompt"]

            with patch.dict(
                nxos_proxy.__opts__["proxy"], {"prompt_name": "n9k-device"}
            ):
                nxos_proxy._init_ssh(None)
                assert "n9k-device.*#" == SSHConnection.call_args[1]["prompt"]

            nxos_proxy._init_ssh(None)
            assert ".+#$" == SSHConnection.call_args[1]["prompt"]


def test__initialized_ssh():
    """UT: nxos module:_initialized_ssh method"""

    with patch("salt.proxy.nxos.DEVICE_DETAILS", {"initialized": True}):
        result = nxos_proxy._initialized_ssh()
        assert result

    with patch("salt.proxy.nxos.DEVICE_DETAILS", {}):
        result = nxos_proxy._initialized_ssh()
        assert not result


def test__parse_output_for_errors():
    """UT: nxos module:_parse_output_for_errors method"""

    data = "% Incomplete command at '^' marker."
    command = "show"

    with pytest.raises(CommandExecutionError):
        nxos_proxy._parse_output_for_errors(data, command, error_pattern="Incomplete")

    data = "% Incomplete command at '^' marker."
    command = "show"

    with pytest.raises(CommandExecutionError):
        nxos_proxy._parse_output_for_errors(
            data, command, error_pattern=["Incomplete", "marker"]
        )

    data = "% Invalid command at '^' marker."
    command = "show bep"

    with pytest.raises(CommandExecutionError):
        nxos_proxy._parse_output_for_errors(data, command)

    data = "% Incomplete command at '^' marker."
    command = "show"

    nxos_proxy._parse_output_for_errors(data, command)

    data = "% Incomplete command at '^' marker."
    command = "show"

    nxos_proxy._parse_output_for_errors(data, command, error_pattern="foo")


def test__init_ssh_raise_exception():
    """UT: nxos module:_init_ssh method - raise exception"""

    class SSHException(Exception):
        pass

    with patch("salt.proxy.nxos.SSHConnection", autospec=True) as SSHConnection:
        with patch("salt.proxy.nxos.log", autospec=True) as log:
            with pytest.raises(SSHException):
                SSHConnection.side_effect = SSHException
                nxos_proxy._init_ssh(None)
            log.error.assert_called()
