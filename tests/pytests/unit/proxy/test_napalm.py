"""
    :codeauthor: :email:`Anthony Shaw <anthonyshaw@apache.org>`
"""
import pytest

import salt.proxy.napalm as napalm_proxy
import tests.support.napalm as napalm_test_support
from tests.support.mock import MagicMock, patch


@pytest.fixture
def test_opts():
    return {
        "proxytype": "napalm",
        "driver": "junos",
        "host": "core05.nrt02",
        "id": "core05.nrt02",
    }


@pytest.fixture
def configure_loader_modules(test_opts):
    def mock_get_device(opts, *args, **kwargs):
        assert opts == test_opts
        return {"DRIVER": napalm_test_support.MockNapalmDevice(), "UP": True}

    module_globals = {
        "__salt__": {
            "config.option": MagicMock(
                return_value={"test": {"driver": "test", "key": "2orgk34kgk34g"}}
            )
        }
    }
    module_globals["napalm_base"] = MagicMock()
    with patch("salt.utils.napalm.get_device", mock_get_device):
        yield {napalm_proxy: module_globals}


def test_init(test_opts):
    ret = napalm_proxy.init(test_opts)
    assert ret is True


def test_alive(test_opts):
    napalm_proxy.init(test_opts)
    ret = napalm_proxy.alive(test_opts)
    assert ret is True


def test_ping(test_opts):
    napalm_proxy.init(test_opts)
    ret = napalm_proxy.ping()
    assert ret is True


def test_initialized(test_opts):
    napalm_proxy.init(test_opts)
    ret = napalm_proxy.initialized()
    assert ret is True


def test_get_device(test_opts):
    napalm_proxy.init(test_opts)
    ret = napalm_proxy.get_device()
    assert ret["UP"] is True


def test_get_grains(test_opts):
    napalm_proxy.init(test_opts)
    ret = napalm_proxy.get_grains()
    assert ret["out"] == napalm_test_support.TEST_FACTS.copy()


def test_grains_refresh(test_opts):
    napalm_proxy.init(test_opts)
    ret = napalm_proxy.grains_refresh()
    assert ret["out"] == napalm_test_support.TEST_FACTS.copy()


def test_fns():
    ret = napalm_proxy.fns()
    assert "details" in ret.keys()


def test_shutdown(test_opts):
    napalm_proxy.init(test_opts)
    ret = napalm_proxy.shutdown(test_opts)
    assert ret is True


def test_call(test_opts):
    napalm_proxy.init(test_opts)
    ret = napalm_proxy.call("get_arp_table")
    assert ret["out"] == napalm_test_support.TEST_ARP_TABLE.copy()
