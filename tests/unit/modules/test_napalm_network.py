"""
    :codeauthor: Anthony Shaw <anthonyshaw@apache.org>
"""


import salt.modules.napalm_network as napalm_network
import tests.support.napalm as napalm_test_support
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class NapalmNetworkModuleTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        patcher = patch(
            "salt.utils.napalm.get_device",
            MagicMock(return_value=napalm_test_support.MockNapalmDevice()),
        )
        patcher.start()
        self.addCleanup(patcher.stop)
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

        return {napalm_network: module_globals}

    def test_connected_pass(self):
        ret = napalm_network.connected()
        assert ret["out"] is True

    def test_facts(self):
        ret = napalm_network.facts()
        assert ret["out"] == napalm_test_support.TEST_FACTS.copy()

    def test_environment(self):
        ret = napalm_network.environment()
        assert ret["out"] == napalm_test_support.TEST_ENVIRONMENT.copy()

    def test_cli_single_command(self):
        """
        Test that CLI works with 1 arg
        """
        ret = napalm_network.cli("show run")
        assert ret["out"] == napalm_test_support.TEST_COMMAND_RESPONSE.copy()

    def test_cli_multi_command(self):
        """
        Test that CLI works with 2 arg
        """
        ret = napalm_network.cli("show run", "show run")
        assert ret["out"] == napalm_test_support.TEST_COMMAND_RESPONSE.copy()

    def test_traceroute(self):
        ret = napalm_network.traceroute("destination.com")
        assert list(ret["out"].keys())[0] == "success"

    def test_ping(self):
        ret = napalm_network.ping("destination.com")
        assert list(ret["out"].keys())[0] == "success"

    def test_arp(self):
        ret = napalm_network.arp()
        assert ret["out"] == napalm_test_support.TEST_ARP_TABLE.copy()

    def test_ipaddrs(self):
        ret = napalm_network.ipaddrs()
        assert ret["out"] == napalm_test_support.TEST_IPADDRS.copy()

    def test_interfaces(self):
        ret = napalm_network.interfaces()
        assert ret["out"] == napalm_test_support.TEST_INTERFACES.copy()

    def test_lldp(self):
        ret = napalm_network.lldp()
        assert ret["out"] == napalm_test_support.TEST_LLDP_NEIGHBORS.copy()

    def test_mac(self):
        ret = napalm_network.mac()
        assert ret["out"] == napalm_test_support.TEST_MAC_TABLE.copy()

    def test_config(self):
        ret = napalm_network.config("running")
        assert ret["out"] == napalm_test_support.TEST_RUNNING_CONFIG.copy()

    def test_optics(self):
        ret = napalm_network.optics()
        assert ret["out"] == napalm_test_support.TEST_OPTICS.copy()

    def test_load_config(self):
        ret = napalm_network.load_config(text="new config")
        assert ret["result"]

    def test_load_config_replace(self):
        ret = napalm_network.load_config(text="new config", replace=True)
        assert ret["result"]

    def test_load_template(self):
        ret = napalm_network.load_template("set_ntp_peers", peers=["192.168.0.1"])
        assert ret["out"] is None

    def test_commit(self):
        ret = napalm_network.commit()
        assert ret["out"] == napalm_test_support.TEST_RUNNING_CONFIG.copy()

    def test_discard_config(self):
        ret = napalm_network.discard_config()
        assert ret["out"] == napalm_test_support.TEST_RUNNING_CONFIG.copy()

    def test_compare_config(self):
        ret = napalm_network.compare_config()
        assert ret["out"] == napalm_test_support.TEST_RUNNING_CONFIG.copy()

    def test_rollback(self):
        ret = napalm_network.rollback()
        assert ret["out"] == napalm_test_support.TEST_RUNNING_CONFIG.copy()

    def test_config_changed(self):
        ret = napalm_network.config_changed()
        assert ret == (True, "")

    def test_config_control(self):
        ret = napalm_network.config_control()
        assert ret == (True, "")
