"""
Tests for the Openstack Cloud Provider
"""

import logging

import pytest
from tests.integration.cloud.helpers.cloud_test_base import TIMEOUT, CloudTest
from tests.support.case import ModuleCase
from tests.support.mixins import SaltReturnAssertsMixin
from tests.support.unit import skipIf

log = logging.getLogger(__name__)

try:
    import keystoneclient  # pylint: disable=import-error,unused-import
    from libcloud.common.openstack_identity import OpenStackIdentity_3_0_Connection
    from libcloud.common.openstack_identity import OpenStackIdentityTokenScope

    HAS_KEYSTONE = True
except ImportError:
    HAS_KEYSTONE = False

try:
    import shade  # pylint: disable=unused-import

    HAS_SHADE = True
except ImportError:
    HAS_SHADE = False


@skipIf(
    not HAS_KEYSTONE,
    "Please install keystoneclient and a keystone server before running"
    "openstack integration tests.",
)
class OpenstackTest(ModuleCase, SaltReturnAssertsMixin):
    """
    Validate the keystone state
    """

    endpoint = "http://localhost:35357/v2.0"
    token = "administrator"

    @pytest.mark.destructive_test
    def test_aaa_setup_keystone_endpoint(self):
        ret = self.run_state(
            "keystone.service_present",
            name="keystone",
            description="OpenStack Identity",
            service_type="identity",
            connection_endpoint=self.endpoint,
            connection_token=self.token,
        )
        self.assertTrue(
            ret["keystone_|-keystone_|-keystone_|-service_present"]["result"]
        )

        ret = self.run_state(
            "keystone.endpoint_present",
            name="keystone",
            region="RegionOne",
            publicurl="http://localhost:5000/v2.0",
            internalurl="http://localhost:5000/v2.0",
            adminurl="http://localhost:35357/v2.0",
            connection_endpoint=self.endpoint,
            connection_token=self.token,
        )
        self.assertTrue(
            ret["keystone_|-keystone_|-keystone_|-endpoint_present"]["result"]
        )

        ret = self.run_state(
            "keystone.tenant_present",
            name="admin",
            description="Admin Project",
            connection_endpoint=self.endpoint,
            connection_token=self.token,
        )
        self.assertTrue(ret["keystone_|-admin_|-admin_|-tenant_present"]["result"])

        ret = self.run_state(
            "keystone.tenant_present",
            name="demo",
            description="Demo Project",
            connection_endpoint=self.endpoint,
            connection_token=self.token,
        )
        self.assertTrue(ret["keystone_|-demo_|-demo_|-tenant_present"]["result"])

        ret = self.run_state(
            "keystone.role_present",
            name="admin",
            connection_endpoint=self.endpoint,
            connection_token=self.token,
        )
        self.assertTrue(ret["keystone_|-admin_|-admin_|-role_present"]["result"])

        ret = self.run_state(
            "keystone.role_present",
            name="user",
            connection_endpoint=self.endpoint,
            connection_token=self.token,
        )
        self.assertTrue(ret["keystone_|-user_|-user_|-role_present"]["result"])

        ret = self.run_state(
            "keystone.user_present",
            name="admin",
            email="admin@example.com",
            password="adminpass",
            tenant="admin",
            roles={"admin": ["admin"]},
            connection_endpoint=self.endpoint,
            connection_token=self.token,
        )
        self.assertTrue(ret["keystone_|-admin_|-admin_|-user_present"]["result"])

        ret = self.run_state(
            "keystone.user_present",
            name="demo",
            email="demo@example.com",
            password="demopass",
            tenant="demo",
            roles={"demo": ["user"]},
            connection_endpoint=self.endpoint,
            connection_token=self.token,
        )
        self.assertTrue(ret["keystone_|-demo_|-demo_|-user_present"]["result"])

    @pytest.mark.destructive_test
    def test_zzz_teardown_keystone_endpoint(self):
        ret = self.run_state(
            "keystone.user_absent",
            name="admin",
            connection_endpoint=self.endpoint,
            connection_token=self.token,
        )
        self.assertTrue(ret["keystone_|-admin_|-admin_|-user_absent"]["result"])

        ret = self.run_state(
            "keystone.user_absent",
            name="demo",
            connection_endpoint=self.endpoint,
            connection_token=self.token,
        )
        self.assertTrue(ret["keystone_|-demo_|-demo_|-user_absent"]["result"])

        ret = self.run_state(
            "keystone.role_absent",
            name="admin",
            connection_endpoint=self.endpoint,
            connection_token=self.token,
        )
        self.assertTrue(ret["keystone_|-admin_|-admin_|-role_absent"]["result"])

        ret = self.run_state(
            "keystone.role_absent",
            name="user",
            connection_endpoint=self.endpoint,
            connection_token=self.token,
        )
        self.assertTrue(ret["keystone_|-user_|-user_|-role_absent"]["result"])

        ret = self.run_state(
            "keystone.tenant_absent",
            name="admin",
            connection_endpoint=self.endpoint,
            connection_token=self.token,
        )
        self.assertTrue(ret["keystone_|-admin_|-admin_|-tenant_absent"]["result"])

        ret = self.run_state(
            "keystone.tenant_absent",
            name="demo",
            connection_endpoint=self.endpoint,
            connection_token=self.token,
        )
        self.assertTrue(ret["keystone_|-demo_|-demo_|-tenant_absent"]["result"])

        ret = self.run_state(
            "keystone.service_absent",
            name="keystone",
            connection_endpoint=self.endpoint,
            connection_token=self.token,
        )
        self.assertTrue(
            ret["keystone_|-keystone_|-keystone_|-service_absent"]["result"]
        )

    @pytest.mark.destructive_test
    def test_libcloud_auth_v3(self):
        driver = OpenStackIdentity_3_0_Connection(
            auth_url="http://localhost:5000",
            user_id="admin",
            key="adminpass",
            token_scope=OpenStackIdentityTokenScope.PROJECT,
            domain_name="Default",
            tenant_name="admin",
        )
        driver.authenticate()
        self.assertTrue(driver.auth_token)


@skipIf(not HAS_SHADE, "openstack driver requires `shade`")
class RackspaceTest(CloudTest):
    """
    Integration tests for the Rackspace cloud provider using the Openstack driver
    """

    PROVIDER = "openstack"
    REQUIRED_PROVIDER_CONFIG_ITEMS = ("auth", "cloud", "region_name")

    def test_instance(self):
        """
        Test creating an instance on rackspace with the openstack driver
        """
        # check if instance with salt installed returned
        ret_val = self.run_cloud(
            "-p rackspace-test {}".format(self.instance_name), timeout=TIMEOUT
        )
        self.assertInstanceExists(ret_val)

        self.assertDestroyInstance()
