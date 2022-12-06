"""
    :codeauthor: :email:`Anthony Shaw <anthonyshaw@apache.org>`
"""
import pytest

import salt.modules.libcloud_loadbalancer as libcloud_loadbalancer
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase

try:
    from libcloud.loadbalancer.base import Algorithm, BaseDriver, LoadBalancer, Member

    HAS_LIBCLOUD = True
except ImportError:
    HAS_LIBCLOUD = False

if HAS_LIBCLOUD:

    class MockLBDriver(BaseDriver):
        def __init__(self):  # pylint: disable=W0231
            self._TEST_BALANCER = LoadBalancer(
                id="test_id",
                name="test_balancer",
                state=0,  # RUNNING
                ip="1.2.3.4",
                port=80,
                driver=self,
                extra={},
            )
            self._TEST_MEMBER = Member(
                id="member_id",
                ip="12.3.4.5",
                port=443,
                balancer=self._TEST_BALANCER,
                extra=None,
            )

        def get_balancer(self, balancer_id):
            assert balancer_id == "test_id"
            return self._TEST_BALANCER

        def list_balancers(self):
            return [self._TEST_BALANCER]

        def list_protocols(self):
            return ["http", "https"]

        def create_balancer(self, name, port, protocol, algorithm, members):
            assert name == "new_test_balancer"
            assert port == 80
            assert protocol == "http"
            assert isinstance(algorithm, (Algorithm, int))
            assert isinstance(members, list)
            return self._TEST_BALANCER

        def destroy_balancer(self, balancer):
            assert balancer == self._TEST_BALANCER
            return True

        def balancer_attach_member(self, balancer, member):
            assert isinstance(balancer, LoadBalancer)
            assert isinstance(member, Member)
            assert member.id is None
            assert balancer.id == "test_id"
            return self._TEST_MEMBER

        def balancer_detach_member(self, balancer, member):
            assert isinstance(balancer, LoadBalancer)
            assert isinstance(member, Member)
            assert member.id == "member_id"
            assert balancer.id == "test_id"
            return True

        def balancer_list_members(self, balancer):
            assert isinstance(balancer, LoadBalancer)
            assert balancer.id == "test_id"
            return [self._TEST_MEMBER]

else:
    MockLBDriver = object


def get_mock_driver():
    return MockLBDriver()


@pytest.mark.skipif(not HAS_LIBCLOUD, reason="No libcloud package")
@patch(
    "salt.modules.libcloud_loadbalancer._get_driver",
    MagicMock(return_value=MockLBDriver()),
)
class LibcloudLoadBalancerModuleTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        module_globals = {
            "__salt__": {
                "config.option": MagicMock(
                    return_value={"test": {"driver": "test", "key": "2orgk34kgk34g"}}
                )
            }
        }
        if libcloud_loadbalancer.HAS_LIBCLOUD is False:
            module_globals["sys.modules"] = {"libcloud": MagicMock()}

        return {libcloud_loadbalancer: module_globals}

    def test_module_creation(self):
        client = libcloud_loadbalancer._get_driver("test")
        self.assertFalse(client is None)

    def _validate_balancer(self, balancer):
        self.assertEqual(balancer["name"], "test_balancer")

    def _validate_member(self, member):
        self.assertEqual(member["id"], "member_id")
        self.assertEqual(member["ip"], "12.3.4.5")

    def test_list_balancers(self):
        balancers = libcloud_loadbalancer.list_balancers("test")
        self.assertEqual(len(balancers), 1)
        self._validate_balancer(balancers[0])

    def test_list_protocols(self):
        protocols = libcloud_loadbalancer.list_protocols("test")
        self.assertEqual(len(protocols), 2)
        self.assertTrue("http" in protocols)

    def test_create_balancer(self):
        balancer = libcloud_loadbalancer.create_balancer(
            "new_test_balancer", 80, "http", "test"
        )
        self._validate_balancer(balancer)

    def test_create_balancer_custom_algorithm(self):
        balancer = libcloud_loadbalancer.create_balancer(
            "new_test_balancer", 80, "http", "test", algorithm="LEAST_CONNECTIONS"
        )
        self._validate_balancer(balancer)

    def test_destroy_balancer(self):
        result = libcloud_loadbalancer.destroy_balancer("test_id", "test")
        self.assertTrue(result)

    def test_get_balancer_by_name(self):
        balancer = libcloud_loadbalancer.get_balancer_by_name("test_balancer", "test")
        self._validate_balancer(balancer)

    def test_get_balancer(self):
        balancer = libcloud_loadbalancer.get_balancer("test_id", "test")
        self._validate_balancer(balancer)

    def test_balancer_attach_member(self):
        member = libcloud_loadbalancer.balancer_attach_member(
            "test_id", "12.3.4.5", 443, "test"
        )
        self._validate_member(member)

    def test_balancer_detach_member(self):
        result = libcloud_loadbalancer.balancer_detach_member(
            "test_id", "member_id", "test"
        )
        self.assertTrue(result)

    def test_list_balancer_members(self):
        members = libcloud_loadbalancer.list_balancer_members("test_id", "test")
        self._validate_member(members[0])
