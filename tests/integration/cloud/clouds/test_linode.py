"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""


# Create the cloud instance name to be used throughout the tests
from tests.integration.cloud.helpers.cloud_test_base import TIMEOUT, CloudTest


class LinodeTest(CloudTest):
    """
    Integration tests for the Linode cloud provider in Salt-Cloud
    """

    PROVIDER = "linode"
    REQUIRED_PROVIDER_CONFIG_ITEMS = ("apikey", "password")

    def setUp(self):
        """
        Sets up the test requirements
        """
        super().setUp()

        # check if the Linode APIv4 cloud provider
        if self.profile_str + "-v4:" not in self.providers:
            self.skipTest(
                "Configuration file for Linode using api_version ``v4`` was not found "
                "but is required to run all tests. Check linode.conf files in "
                "tests/integration/files/conf/cloud.*.d/ to run these tests."
            )

    def _test_instance(self, profile):
        """
        Test creating an instance on Linode for a given profile.
        """

        # create the instance
        args = ["-p", profile, self.instance_name]
        ret_str = self.run_cloud(" ".join(args), timeout=TIMEOUT)

        self.assertInstanceExists(ret_str)
        self.assertDestroyInstance()
        return ret_str

    def test_instance(self):
        return self._test_instance("linode-test")

    def test_instance_v4(self):
        return self._test_instance("linode-test-v4")
