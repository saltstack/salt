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
