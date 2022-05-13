"""
    :codeauthor: :email:`Anthony Shaw <anthonyshaw@apache.org>`
"""


import salt.proxy.napalm as napalm_proxy
import tests.support.napalm as napalm_test_support
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class NapalmProxyTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        def mock_get_device(opts, *args, **kwargs):
            assert opts == self.test_opts
            return {"DRIVER": napalm_test_support.MockNapalmDevice(), "UP": True}

        patcher = patch("salt.utils.napalm.get_device", mock_get_device)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.test_opts = {
            "proxytype": "napalm",
            "driver": "junos",
            "host": "core05.nrt02",
            "id": "core05.nrt02",
        }
        module_globals = {
            "__salt__": {
                "config.option": MagicMock(
                    return_value={"test": {"driver": "test", "key": "2orgk34kgk34g"}}
                )
            }
        }
        module_globals["napalm_base"] = MagicMock()
        return {napalm_proxy: module_globals}

    def test_init(self):
        ret = napalm_proxy.init(self.test_opts)
        assert ret is True

    def test_alive(self):
        napalm_proxy.init(self.test_opts)
        ret = napalm_proxy.alive(self.test_opts)
        assert ret is True

    def test_ping(self):
        napalm_proxy.init(self.test_opts)
        ret = napalm_proxy.ping()
        assert ret is True

    def test_initialized(self):
        napalm_proxy.init(self.test_opts)
        ret = napalm_proxy.initialized()
        assert ret is True

    def test_get_device(self):
        napalm_proxy.init(self.test_opts)
        ret = napalm_proxy.get_device()
        assert ret["UP"] is True

    def test_get_grains(self):
        napalm_proxy.init(self.test_opts)
        ret = napalm_proxy.get_grains()
        assert ret["out"] == napalm_test_support.TEST_FACTS.copy()

    def test_grains_refresh(self):
        napalm_proxy.init(self.test_opts)
        ret = napalm_proxy.grains_refresh()
        assert ret["out"] == napalm_test_support.TEST_FACTS.copy()

    def test_fns(self):
        ret = napalm_proxy.fns()
        assert "details" in ret.keys()

    def test_shutdown(self):
        napalm_proxy.init(self.test_opts)
        ret = napalm_proxy.shutdown(self.test_opts)
        assert ret is True

    def test_call(self):
        napalm_proxy.init(self.test_opts)
        ret = napalm_proxy.call("get_arp_table")
        assert ret["out"] == napalm_test_support.TEST_ARP_TABLE.copy()
