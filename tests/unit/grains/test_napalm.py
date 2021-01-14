"""
    :codeauthor: :email:`Anthony Shaw <anthonyshaw@apache.org>`
"""


import salt.grains.napalm as napalm_grains
import salt.proxy.napalm as napalm_proxy
import tests.support.napalm as napalm_test_support
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class NapalmGrainsTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        patcher = patch.object(
            napalm_grains.salt.utils.napalm, "is_proxy", MagicMock(return_value=True)
        )
        patcher.start()
        test_device_cache = {
            "DRIVER": napalm_test_support.MockNapalmDevice(),
            "DRIVER_NAME": "cisco",
            "OS_VERSION": "1.2.3",
            "HOSTNAME": "test-device.com",
            "USERNAME": "admin",
        }

        test_cache = {"result": True, "out": napalm_test_support.TEST_FACTS}
        patcher = patch("salt.grains.napalm.DEVICE_CACHE", test_device_cache)
        patcher.start()
        patcher = patch("salt.grains.napalm.GRAINS_CACHE", test_cache)
        patcher.start()
        self.addCleanup(patch.stopall)
        module_globals = {
            "__salt__": {
                "config.option": MagicMock(
                    return_value={"test": {"driver": "test", "key": "2orgk34kgk34g"}}
                ),
                "file.file_exists": napalm_test_support.true,
                "file.join": napalm_test_support.join,
                "file.get_managed": napalm_test_support.get_managed_file,
                "random.hash": napalm_test_support.random_hash,
            }
        }

        return {napalm_grains: module_globals}

    def test_os(self):
        ret = napalm_grains.getos(proxy=napalm_proxy)
        assert ret["os"] == "cisco"

    def test_os_version(self):
        ret = napalm_grains.version(proxy=napalm_proxy)
        assert ret["version"] == "1.2.3"

    def test_model(self):
        ret = napalm_grains.model(proxy=napalm_proxy)
        assert ret["model"] == "test_model"

    def test_serial(self):
        ret = napalm_grains.serial(proxy=napalm_proxy)
        assert ret["serial"] == "123456"

    def test_vendor(self):
        ret = napalm_grains.vendor(proxy=napalm_proxy)
        assert ret["vendor"] == "cisco"

    def test_uptime(self):
        ret = napalm_grains.uptime(proxy=napalm_proxy)
        assert ret["uptime"] == "Forever"

    def test_interfaces(self):
        ret = napalm_grains.interfaces(proxy=napalm_proxy)
        assert ret["interfaces"] == napalm_test_support.TEST_INTERFACES

    def test_username(self):
        ret = napalm_grains.username(proxy=napalm_proxy)
        assert ret["username"] == "admin"

    def test_hostname(self):
        ret = napalm_grains.hostname(proxy=napalm_proxy)
        assert ret["hostname"] == "test-device.com"

    def test_host(self):
        ret = napalm_grains.host(proxy=napalm_proxy)
        assert ret["host"] == "test-device.com"
