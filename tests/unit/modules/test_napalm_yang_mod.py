"""
    :codeauthor: :email:`Anthony Shaw <anthonyshaw@apache.org>`
"""


import salt.modules.napalm_network as napalm_network
import salt.modules.napalm_yang_mod as napalm_yang_mod
import tests.support.napalm as napalm_test_support
from salt.utils.immutabletypes import freeze
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class MockNapalmYangModel:
    def Root(self):
        return MagicMock()


class MockNapalmYangModels:
    openconfig_interfaces = MockNapalmYangModel()


class MockUtils:
    def __init__(self, test_diff):
        self.test_diff = test_diff

    def diff(self, *args):
        return self.test_diff


class MockNapalmYangModule:
    def __init__(self, test_diff):
        self.base = MockNapalmYangModel()
        self.models = MockNapalmYangModels()
        self.utils = MockUtils(test_diff)


class NapalmYangModModuleTestCase(TestCase, LoaderModuleMockMixin):
    @classmethod
    def setUpClass(cls):
        cls._test_config = freeze(
            {
                "comment": "Configuration discarded.",
                "already_configured": False,
                "result": True,
                "diff": (
                    '[edit interfaces xe-0/0/5]+   description "Adding a description";'
                ),
            }
        )
        cls._test_diff = freeze({"diff1": "value"})

    @classmethod
    def tearDownClass(cls):
        cls._test_config = cls._test_diff = None

    def setup_loader_modules(self):
        patcher = patch(
            "salt.utils.napalm.get_device",
            MagicMock(return_value=napalm_test_support.MockNapalmDevice()),
        )
        patcher.start()
        self.addCleanup(patcher.stop)

        def mock_net_load_config(**kwargs):
            return self._test_config.copy()

        module_globals = {
            "__salt__": {
                "config.get": MagicMock(
                    return_value={"test": {"driver": "test", "key": "2orgk34kgk34g"}}
                ),
                "file.file_exists": napalm_test_support.true,
                "file.join": napalm_test_support.join,
                "file.get_managed": napalm_test_support.get_managed_file,
                "random.hash": napalm_test_support.random_hash,
                "net.load_template": napalm_network.load_template,
                "net.load_config": mock_net_load_config,
            },
            "napalm_yang": MockNapalmYangModule(self._test_diff.copy()),
        }

        return {napalm_yang_mod: module_globals, napalm_network: module_globals}

    def test_diff(self):
        ret = napalm_yang_mod.diff({}, {"test": True}, "models.openconfig_interfaces")
        assert ret == self._test_diff.copy()

    def test_diff_list(self):
        """
        Test it with an actual list
        """
        ret = napalm_yang_mod.diff({}, {"test": True}, ["models.openconfig_interfaces"])
        assert ret == self._test_diff.copy()

    def test_parse(self):
        ret = napalm_yang_mod.parse("models.openconfig_interfaces")
        assert ret is not None

    def test_get_config(self):
        ret = napalm_yang_mod.get_config({}, "models.openconfig_interfaces")
        assert ret is not None

    def test_load_config(self):
        ret = napalm_yang_mod.load_config({}, "models.openconfig_interfaces")
        assert ret == self._test_config.copy()

    def test_compliance_report(self):
        ret = napalm_yang_mod.compliance_report({}, "models.openconfig_interfaces")
        assert ret is not None
