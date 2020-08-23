"""
    :codeauthor: :email:`Anthony Shaw <anthonyshaw@apache.org>`
"""


import salt.modules.napalm_network as napalm_network
import salt.modules.napalm_users as napalm_users
import tests.support.napalm as napalm_test_support
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class NapalmUsersModuleTestCase(TestCase, LoaderModuleMockMixin):
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
                "net.load_template": napalm_network.load_template,
            }
        }

        return {napalm_users: module_globals, napalm_network: module_globals}

    def test_config(self):
        ret = napalm_users.config()
        assert ret["out"] == napalm_test_support.TEST_USERS.copy()

    def test_set_users(self):
        ret = napalm_users.set_users({"mircea": {}})
        assert ret["result"] is False

    def test_delete_users(self):
        ret = napalm_users.delete_users({"mircea": {}})
        assert ret["result"] is False
