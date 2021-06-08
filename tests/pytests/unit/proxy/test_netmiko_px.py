"""
    :codeauthor: Gareth J. Greenaway <gareth@saltstack.com>
"""

import copy
import logging

import pytest
import salt.proxy.netmiko_px as netmiko_proxy
from saltfactories.utils import random_string
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def proxy_minion_config_module(salt_master_factory):
    factory = salt_master_factory.salt_proxy_minion_daemon(
        random_string("proxy-minion-"),
    )
    return factory.config


@pytest.fixture
def proxy_minion_config(proxy_minion_config_module):
    return copy.deepcopy(proxy_minion_config_module)


@pytest.fixture
def configure_loader_modules():
    return {netmiko_proxy: {}}


class MockNetmikoConnection:
    def is_alive(self):
        return False

    def send_config_set(self, *args, **kwargs):
        return args, kwargs


def test_check_virtual():
    """
    check netmiko_proxy virtual method - return value
    """

    with patch.object(netmiko_proxy, "HAS_NETMIKO", True):
        result = netmiko_proxy.__virtual__()
        assert "netmiko" in result

    expected = (
        False,
        "The netmiko proxy module requires netmiko library to be installed.",
    )
    with patch.object(netmiko_proxy, "HAS_NETMIKO", False):
        result = netmiko_proxy.__virtual__()
        assert expected == result


def test_init_skip_connect_on_init_true(proxy_minion_config):
    """
    check netmiko_proxy init method
    """

    proxy_minion_config["skip_connect_on_init"] = True

    result = netmiko_proxy.init(proxy_minion_config)
    assert "netmiko_device" in netmiko_proxy.__context__
    assert "args" in netmiko_proxy.__context__["netmiko_device"]

    assert "initialized" in netmiko_proxy.__context__["netmiko_device"]
    assert not netmiko_proxy.__context__["netmiko_device"]["initialized"]

    assert "up" in netmiko_proxy.__context__["netmiko_device"]
    assert netmiko_proxy.__context__["netmiko_device"]["up"]

    assert "always_alive" in netmiko_proxy.__context__["netmiko_device"]

    assert "conneciton" not in netmiko_proxy.__context__["netmiko_device"]


def test_init_skip_connect_on_init_false(proxy_minion_config):
    """
    check netmiko_proxy init method
    """

    proxy_minion_config["skip_connect_on_init"] = False

    mock_make_con = MagicMock()
    with patch.object(netmiko_proxy, "make_con", mock_make_con):
        result = netmiko_proxy.init(proxy_minion_config)

    assert "netmiko_device" in netmiko_proxy.__context__
    assert "args" in netmiko_proxy.__context__["netmiko_device"]

    assert "initialized" in netmiko_proxy.__context__["netmiko_device"]
    assert netmiko_proxy.__context__["netmiko_device"]["initialized"]

    assert "up" in netmiko_proxy.__context__["netmiko_device"]
    assert netmiko_proxy.__context__["netmiko_device"]["up"]

    assert "always_alive" in netmiko_proxy.__context__["netmiko_device"]

    assert "conneciton" not in netmiko_proxy.__context__["netmiko_device"]


def test_make_con(proxy_minion_config):
    """
    check netmiko_proxy make_con method
    """

    proxy_minion_config["skip_connect_on_init"] = True

    netmiko_proxy.init(proxy_minion_config)

    mock_connection = MockNetmikoConnection

    with patch.object(netmiko_proxy, "ConnectHandler", mock_connection, create=True):
        result = netmiko_proxy.make_con()
        assert result is not None


def test_make_con_raise_exception(proxy_minion_config):
    """
    check netmiko_proxy make_con method
    """

    def raise_exception(*arg, **kwarg):
        raise Exception("expected")

    proxy_minion_config["skip_connect_on_init"] = True

    netmiko_proxy.init(proxy_minion_config)

    mock_connection = MockNetmikoConnection

    with patch.object(netmiko_proxy, "DEFAULT_CONNECTION_TIMEOUT", 0), patch.object(
        netmiko_proxy, "ConnectHandler", raise_exception, create=True
    ):
        result = None
        try:
            result = netmiko_proxy.make_con(0)
        except Exception:  # pylint: disable=broad-except
            assert result is None


def test_ping(proxy_minion_config):
    """
    check netmiko_proxy ping method
    """

    proxy_minion_config["skip_connect_on_init"] = True

    netmiko_proxy.init(proxy_minion_config)

    result = netmiko_proxy.ping()
    assert result is True


def test_alive(proxy_minion_config, subtests):
    """
    check netmiko_proxy alive method
    """

    # Always alive False with skip_connect_on_init on True
    # should return alive as True
    with subtests.test("skip_connect_on_init=True, proxy_always_alive=False"):
        proxy_minion_config["skip_connect_on_init"] = True
        proxy_minion_config["proxy_always_alive"] = False

        netmiko_proxy.init(proxy_minion_config)

        result = netmiko_proxy.alive(proxy_minion_config)
        assert result

    # Always alive True with skip_connect_on_init on True
    # should return alive as False
    with subtests.test("skip_connect_on_init=True, proxy_always_alive=True"):
        proxy_minion_config["skip_connect_on_init"] = True
        proxy_minion_config["proxy_always_alive"] = True

        netmiko_proxy.init(proxy_minion_config)

        result = netmiko_proxy.alive(proxy_minion_config)
        assert not result

    # Always alive True with skip_connect_on_init on False
    # should return alive as True
    with subtests.test("skip_connect_on_init=False, proxy_always_alive=True"):
        proxy_minion_config["skip_connect_on_init"] = False
        proxy_minion_config["proxy_always_alive"] = True

        mock_make_con = MagicMock()
        with patch.object(netmiko_proxy, "make_con", mock_make_con):
            netmiko_proxy.init(proxy_minion_config)
            result = netmiko_proxy.alive(proxy_minion_config)
            assert result


def test_initialized(proxy_minion_config):
    """
    check netmiko_proxy alive method
    """

    proxy_minion_config["skip_connect_on_init"] = True

    netmiko_proxy.init(proxy_minion_config)

    result = netmiko_proxy.initialized()
    assert not result

    # Always alive True with skip_connect_on_init on False
    # should return alive as True
    proxy_minion_config["skip_connect_on_init"] = False

    mock_make_con = MagicMock()
    with patch.object(netmiko_proxy, "make_con", mock_make_con):
        netmiko_proxy.init(proxy_minion_config)
        result = netmiko_proxy.initialized()
        assert result
