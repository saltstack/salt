"""
    :codeauthor: :email:`David Murphy <damurphy@vmware.com>`
"""
import logging

import pytest

import salt.modules.napalm_mod as napalm_mod
import tests.support.napalm as napalm_test_support
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
