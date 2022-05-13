"""
    :codeauthor: Anthony Shaw <anthonyshaw@apache.org>
"""


import salt.modules.libcloud_dns as libcloud_dns
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock
from tests.support.unit import TestCase, skipIf


class MockDNSDriver:
    def __init__(self):
        pass


def get_mock_driver():
    return MockDNSDriver()


@skipIf(not libcloud_dns.HAS_LIBCLOUD, "No libcloud installed")
class LibcloudDnsModuleTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        module_globals = {
            "_get_driver": MagicMock(return_value=MockDNSDriver()),
            "__salt__": {
                "config.option": MagicMock(
                    return_value={"test": {"driver": "test", "key": "2orgk34kgk34g"}}
                )
            },
        }
        if libcloud_dns.HAS_LIBCLOUD is False:
            module_globals["sys.modules"] = {"libcloud": MagicMock()}

        return {libcloud_dns: module_globals}

    def test_module_creation(self):
        client = libcloud_dns._get_driver("test")
        self.assertFalse(client is None)
