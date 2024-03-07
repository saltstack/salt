"""
    :codeauthor: :email:`Anthony Shaw <anthonyshaw@apache.org>`
"""

import salt.modules.napalm_probes as napalm_probes
import tests.support.napalm as napalm_test_support
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class NapalmProbesModuleTestCase(TestCase, LoaderModuleMockMixin):
    @classmethod
    def setUpClass(cls):
        cls._test_probes = {
            "new_probe": {
                "new_test1": {
                    "probe_type": "icmp-ping",
                    "target": "192.168.0.1",
                    "source": "192.168.0.2",
                    "probe_count": 13,
                    "test_interval": 3,
                }
            }
        }
        cls._test_delete_probes = {
            "existing_probe": {"existing_test1": {}, "existing_test2": {}}
        }
        cls._test_schedule_probes = {
            "test_probe": {"existing_test1": {}, "existing_test2": {}}
        }

    @classmethod
    def tearDownClass(cls):
        cls._test_probes = cls._test_delete_probes = cls._test_schedule_probes = None

    def setup_loader_modules(self):
        patcher = patch(
            "salt.utils.napalm.get_device",
            MagicMock(return_value=napalm_test_support.MockNapalmDevice()),
        )
        patcher.start()
        self.addCleanup(patcher.stop)

        def mock_net_load(template, *args, **kwargs):
            if template == "set_probes":
                assert kwargs["probes"] == self._test_probes.copy()
                return napalm_test_support.TEST_TERM_CONFIG.copy()
            if template == "delete_probes":
                assert kwargs["probes"] == self._test_delete_probes.copy()
                return napalm_test_support.TEST_TERM_CONFIG.copy()
            if template == "schedule_probes":
                assert kwargs["probes"] == self._test_schedule_probes.copy()
                return napalm_test_support.TEST_TERM_CONFIG.copy()
            raise ValueError(f"incorrect template {template}")

        module_globals = {
            "__salt__": {
                "config.get": MagicMock(
                    return_value={"test": {"driver": "test", "key": "2orgk34kgk34g"}}
                ),
                "file.file_exists": napalm_test_support.true,
                "file.join": napalm_test_support.join,
                "file.get_managed": napalm_test_support.get_managed_file,
                "random.hash": napalm_test_support.random_hash,
                "net.load_template": mock_net_load,
            }
        }

        return {napalm_probes: module_globals}

    def test_probes_config(self):
        ret = napalm_probes.config()
        assert ret["out"] == napalm_test_support.TEST_PROBES_CONFIG.copy()

    def test_probes_results(self):
        ret = napalm_probes.results()
        assert ret["out"] == napalm_test_support.TEST_PROBES_RESULTS.copy()

    def test_set_probes(self):
        ret = napalm_probes.set_probes(self._test_probes.copy())
        assert ret["result"] is True

    def test_delete_probes(self):
        ret = napalm_probes.delete_probes(self._test_delete_probes.copy())
        assert ret["result"] is True

    def test_schedule_probes(self):
        ret = napalm_probes.schedule_probes(self._test_schedule_probes.copy())
        assert ret["result"] is True
