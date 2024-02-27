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
import salt.utils.nxos as nxos_utils
from tests.support.mock import create_autospec, patch
from tests.unit.modules.nxos.nxos_grains import n9k_grains
from tests.unit.modules.nxos.nxos_show_cmd_output import n9k_show_ver_list


@pytest.fixture
def configure_loader_modules():
    with patch("salt.proxy.nxos.CONNECTION", "nxapi"):
        yield {nxos_proxy: {}}


def test_check_virtual():
    """UT: nxos module:check_virtual method - return value"""

    result = nxos_proxy.__virtual__()
    assert "nxos" in result


def test_init():
    """UT: nxos module:init method - nxapi proxy"""

    with patch.object(nxos_proxy, "__opts__", {"proxy": {"connection": "nxapi"}}):
        with patch("salt.proxy.nxos._init_nxapi", autospec=True) as init_nxapi:
            result = nxos_proxy.init()
            assert result == init_nxapi.return_value


def test_init_opts_none():
    """UT: nxos module:init method - __opts__ connection is None"""

    with patch.object(nxos_proxy, "__opts__", {"proxy": {"connection": None}}):
        with patch("salt.proxy.nxos._init_nxapi", autospec=True) as init_nxapi:
            result = nxos_proxy.init()
            assert result == init_nxapi.return_value


def test_init_bad_connection_type():
    """UT: nxos module:init method - bad CONNECTION type"""
    with patch.object(nxos_proxy, "__opts__", {"proxy": {"connection": "unknown"}}):
        assert not nxos_proxy.init()


def test_initialized():
    """UT: nxos module:initialized method - nxapi proxy"""

    with patch(
        "salt.proxy.nxos._initialized_nxapi", autospec=True
    ) as initialized_nxapi:
        result = nxos_proxy.initialized()
        assert result == initialized_nxapi.return_value


def test_ping():
    """UT: nxos module:ping method - nxapi proxy"""

    with patch("salt.proxy.nxos._ping_nxapi", autospec=True) as ping_nxapi:
        result = nxos_proxy.ping()
        assert result == ping_nxapi.return_value


def test_grains():
    """UT: nxos module:grains method - nxapi grains"""

    with patch(
        "salt.proxy.nxos.sendline", autospec=True, return_value=n9k_show_ver_list
    ):
        result = nxos_proxy.grains()
        assert result == n9k_grains


def test_grains_cache_set():
    """UT: nxos module:grains method - nxapi grains cache set"""

    with patch("salt.proxy.nxos.DEVICE_DETAILS", {"grains_cache": n9k_grains["nxos"]}):
        with patch(
            "salt.proxy.nxos.sendline",
            autospec=True,
            return_value=n9k_show_ver_list,
        ):
            result = nxos_proxy.grains()
            assert result == n9k_grains


def test_grains_refresh():
    """UT: nxos module:grains_refresh method - nxapi grains"""

    device_details = {"grains_cache": None}

    with patch("salt.proxy.nxos.DEVICE_DETAILS", device_details):
        with patch("salt.proxy.nxos.grains", autospec=True) as grains:
            result = nxos_proxy.grains_refresh()
            assert nxos_proxy.DEVICE_DETAILS["grains_cache"] == {}
            assert result == grains.return_value


def test_sendline():
    """UT: nxos module:sendline method - nxapi"""

    command = "show version"

    with patch("salt.proxy.nxos._nxapi_request", autospec=True) as nxapi_request:
        result = nxos_proxy.sendline(command)
        assert result == nxapi_request.return_value


def test_proxy_config():
    """UT: nxos module:proxy_config method - nxapi success path"""

    commands = ["feature bgp", "router bgp 65535"]

    with patch("salt.proxy.nxos.DEVICE_DETAILS", {"save_config": False}):
        with patch("salt.proxy.nxos._nxapi_request", autospec=True) as nxapi_request:
            result = nxos_proxy.proxy_config(commands)
            assert result == [commands, nxapi_request.return_value]


def test_proxy_config_save_config():
    """UT: nxos module:proxy_config method - nxapi success path"""

    commands = ["feature bgp", "router bgp 65535"]

    with patch("salt.proxy.nxos.DEVICE_DETAILS", {"save_config": None}):
        with patch("salt.proxy.nxos._nxapi_request", autospec=True) as nxapi_request:
            result = nxos_proxy.proxy_config(commands, save_config=True)
            assert result == [commands, nxapi_request.return_value]


def test__init_nxapi():
    """UT: nxos module:_init_nxapi method - successful connectinon"""

    opts = {"proxy": {"arg1": None}}
    nxapi_request = create_autospec(nxos_utils.nxapi_request, return_value="data")

    with patch("salt.proxy.nxos.DEVICE_DETAILS", {}) as device_details:
        with patch("salt.proxy.nxos.__utils__", {"nxos.nxapi_request": nxapi_request}):
            result = nxos_proxy._init_nxapi(opts)

            assert device_details["initialized"]
            assert device_details["up"]
            assert device_details["save_config"]
            assert result

            nxapi_request.assert_called_with("show clock", **opts["proxy"])


def test_bad__init_nxapi():
    class NXAPIException(Exception):
        pass

    nxapi_request = create_autospec(
        nxos_utils.nxapi_request, side_effect=NXAPIException
    )

    with patch("salt.proxy.nxos.__utils__", {"nxos.nxapi_request": nxapi_request}):
        with patch("salt.proxy.nxos.log", autospec=True) as log:
            with pytest.raises(NXAPIException):
                nxos_proxy._init_nxapi({"proxy": {"host": "HOST"}})
            log.error.assert_called()


def test__initialized_nxapi():
    """UT: nxos module:_initialized_nxapi method"""

    result = nxos_proxy._initialized_nxapi()
    assert not result

    with patch("salt.proxy.nxos.DEVICE_DETAILS", {"initialized": True}):
        result = nxos_proxy._initialized_nxapi()
        assert result


def test__ping_nxapi():
    """UT: nxos module:_ping_nxapi method"""

    result = nxos_proxy._ping_nxapi()
    assert not result

    with patch("salt.proxy.nxos.DEVICE_DETAILS", {"up": True}):
        result = nxos_proxy._ping_nxapi()
        assert result


def test__shutdown_nxapi():
    """UT: nxos module:_shutdown_nxapi method"""

    opts = {"id": "value"}

    with patch("salt.proxy.nxos.log", autospec=True):
        nxos_proxy._shutdown_nxapi()
        # nothing to test


def test__nxapi_request_ssh_return():
    """UT: nxos module:_nxapi_request method - CONNECTION == 'ssh'"""

    commands = "show version"

    with patch("salt.proxy.nxos.CONNECTION", "ssh"):
        result = nxos_proxy._nxapi_request(commands)
        assert "_nxapi_request is not available for ssh proxy" == result


def test__nxapi_request_connect():
    """UT: nxos module:_nxapi_request method"""

    commands = "show version"
    nxapi_request = create_autospec(nxos_utils.nxapi_request, return_value="data")

    with patch("salt.proxy.nxos.DEVICE_DETAILS", {"conn_args": {"arg1": None}}):
        with patch("salt.proxy.nxos.__utils__", {"nxos.nxapi_request": nxapi_request}):
            result = nxos_proxy._nxapi_request(commands)
            assert "data" == result
            nxapi_request.assert_called_with(commands, method="cli_conf", arg1=None)
