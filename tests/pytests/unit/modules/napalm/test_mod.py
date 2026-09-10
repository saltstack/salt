"""
    :codeauthor: :email:`David Murphy <damurphy@vmware.com>`
"""

import logging

import pytest

import salt.modules.napalm_mod as napalm_mod
import tests.support.napalm as napalm_test_support
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__file__)


@pytest.fixture
def configure_loader_modules():
    module_globals = {
        "__salt__": {
            "config.get": MagicMock(
                return_value={"test": {"driver": "test", "key": "2orgk34kgk34g"}}
            ),
            "file.file_exists": napalm_test_support.true,
            "file.join": napalm_test_support.join,
            "file.get_managed": napalm_test_support.get_managed_file,
            "random.hash": napalm_test_support.random_hash,
        }
    }

    return {napalm_mod: module_globals}


def test_config_kwargs_empty():
    test_napalm_opts = {
        "HOSTNAME": None,
        "USERNAME": None,
        "DRIVER_NAME": None,
        "PASSWORD": "",
        "TIMEOUT": 60,
        "OPTIONAL_ARGS": {
            "config_lock": False,
            "keepalive": 5,
        },
        "ALWAYS_ALIVE": True,
        "PROVIDER": None,
        "UP": False,
    }
    with patch(
        "salt.utils.napalm.get_device_opts", MagicMock(return_value=test_napalm_opts)
    ):
        test_kwargs = {}
        ret = napalm_mod.pyeapi_nxos_api_args(kwargs=test_kwargs)
        assert ret["transport"] == "https"
        assert ret["port"] == 443


def test_config_kwargs_none():
    test_napalm_opts = {
        "HOSTNAME": None,
        "USERNAME": None,
        "DRIVER_NAME": None,
        "PASSWORD": "",
        "TIMEOUT": 60,
        "OPTIONAL_ARGS": {
            "config_lock": False,
            "keepalive": 5,
            "transport": None,
            "port": None,
        },
        "ALWAYS_ALIVE": True,
        "PROVIDER": None,
        "UP": False,
    }
    with patch(
        "salt.utils.napalm.get_device_opts", MagicMock(return_value=test_napalm_opts)
    ):
        test_kwargs = {}
        ret = napalm_mod.pyeapi_nxos_api_args(kwargs=test_kwargs)
        assert ret["transport"] == "https"
        assert ret["port"] == 443


def test_config_kwargs_http_no_port():
    test_napalm_opts = {
        "HOSTNAME": None,
        "USERNAME": None,
        "DRIVER_NAME": None,
        "PASSWORD": "",
        "TIMEOUT": 60,
        "OPTIONAL_ARGS": {
            "config_lock": False,
            "keepalive": 5,
            "transport": "http",
        },
        "ALWAYS_ALIVE": True,
        "PROVIDER": None,
        "UP": False,
    }
    with patch(
        "salt.utils.napalm.get_device_opts", MagicMock(return_value=test_napalm_opts)
    ):
        test_kwargs = {}
        ret = napalm_mod.pyeapi_nxos_api_args(kwargs=test_kwargs)
        assert ret["transport"] == "http"
        assert ret["port"] == 80


def test_config_kwargs_http_and_port():
    test_napalm_opts = {
        "HOSTNAME": None,
        "USERNAME": None,
        "DRIVER_NAME": None,
        "PASSWORD": "",
        "TIMEOUT": 60,
        "OPTIONAL_ARGS": {
            "config_lock": False,
            "keepalive": 5,
            "transport": "http",
            "port": 8080,
        },
        "ALWAYS_ALIVE": True,
        "PROVIDER": None,
        "UP": False,
    }
    with patch(
        "salt.utils.napalm.get_device_opts", MagicMock(return_value=test_napalm_opts)
    ):
        test_kwargs = {}
        ret = napalm_mod.pyeapi_nxos_api_args(kwargs=test_kwargs)
        assert ret["transport"] == "http"
        assert ret["port"] == 8080


def test_config_kwargs_https_no_port():
    test_napalm_opts = {
        "HOSTNAME": None,
        "USERNAME": None,
        "DRIVER_NAME": None,
        "PASSWORD": "",
        "TIMEOUT": 60,
        "OPTIONAL_ARGS": {
            "config_lock": False,
            "keepalive": 5,
            "transport": "https",
        },
        "ALWAYS_ALIVE": True,
        "PROVIDER": None,
        "UP": False,
    }
    with patch(
        "salt.utils.napalm.get_device_opts", MagicMock(return_value=test_napalm_opts)
    ):
        test_kwargs = {}
        ret = napalm_mod.pyeapi_nxos_api_args(kwargs=test_kwargs)
        assert ret["transport"] == "https"
        assert ret["port"] == 443


def test_config_kwargs_https_and_port():
    test_napalm_opts = {
        "HOSTNAME": None,
        "USERNAME": None,
        "DRIVER_NAME": None,
        "PASSWORD": "",
        "TIMEOUT": 60,
        "OPTIONAL_ARGS": {
            "config_lock": False,
            "keepalive": 5,
            "transport": "https",
            "port": 5432,
        },
        "ALWAYS_ALIVE": True,
        "PROVIDER": None,
        "UP": False,
    }
    with patch(
        "salt.utils.napalm.get_device_opts", MagicMock(return_value=test_napalm_opts)
    ):
        test_kwargs = {}
        ret = napalm_mod.pyeapi_nxos_api_args(kwargs=test_kwargs)
        assert ret["transport"] == "https"
        assert ret["port"] == 5432


def test_config_kwargs_werid_transport_port():
    test_napalm_opts = {
        "HOSTNAME": None,
        "USERNAME": None,
        "DRIVER_NAME": None,
        "PASSWORD": "",
        "TIMEOUT": 60,
        "OPTIONAL_ARGS": {
            "config_lock": False,
            "keepalive": 5,
            "transport": "nxos_protocol",
            "port": 2080,
        },
        "ALWAYS_ALIVE": True,
        "PROVIDER": None,
        "UP": False,
    }
    with patch(
        "salt.utils.napalm.get_device_opts", MagicMock(return_value=test_napalm_opts)
    ):
        test_kwargs = {}
        ret = napalm_mod.pyeapi_nxos_api_args(kwargs=test_kwargs)
        assert ret["transport"] == "nxos_protocol"
        assert ret["port"] == 2080


def test_rpc_user_map_overrides_default():
    # A user-supplied napalm_rpc_map entry must win over the built-in default
    # (the old order let default_map clobber it), without mutating the config.
    user_map = {"junos": "napalm.custom_rpc"}
    custom = MagicMock(return_value="custom-result")
    with patch.dict(
        napalm_mod.__salt__,
        {
            "config.get": MagicMock(return_value=user_map),
            "napalm.custom_rpc": custom,
        },
    ), patch.dict(napalm_mod.__grains__, {"os": "junos"}):
        # Call the undecorated body; the proxy_napalm_wrap decorator would try to
        # open a real device (this fix is in the function body, not the wrapper).
        ret = napalm_mod.rpc.__wrapped__("show version")
    custom.assert_called_once_with("show version")
    assert ret == "custom-result"
    # the config object returned by config.get must not be mutated with defaults
    assert user_map == {"junos": "napalm.custom_rpc"}


def test_netmiko_args_unknown_os_raises_clean_error():
    # An os grain not in the map (custom/community driver, no user override)
    # must raise a clear CommandExecutionError, not a raw KeyError.
    napalm_opts = {
        "HOSTNAME": "device",
        "USERNAME": "user",
        "PASSWORD": "pass",
        "TIMEOUT": 60,
        "OPTIONAL_ARGS": {},
    }
    with patch(
        "salt.utils.napalm.get_device_opts", MagicMock(return_value=napalm_opts)
    ), patch.object(napalm_mod, "HAS_NETMIKO", True), patch.object(
        napalm_mod, "_get_netmiko_args", MagicMock(return_value={})
    ), patch.dict(
        napalm_mod.__salt__, {"config.get": MagicMock(return_value={})}
    ), patch.dict(
        napalm_mod.__grains__, {"os": "customdriver"}
    ):
        with pytest.raises(CommandExecutionError) as exc:
            napalm_mod.netmiko_args.__wrapped__()
    # Specifically the "no device type for this driver" error (naming the os),
    # not the earlier "netmiko is not installed" gate.
    assert "customdriver" in str(exc.value)
