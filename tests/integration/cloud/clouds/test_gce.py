"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
    :codeauthor: Tomas Sirny <tsirny@gmail.com>
"""


from tests.integration.cloud.helpers.cloud_test_base import TIMEOUT, CloudTest


class GCETest(CloudTest):
    """
    Integration tests for the GCE cloud provider in Salt-Cloud
    """

    PROVIDER = "gce"
    REQUIRED_PROVIDER_CONFIG_ITEMS = (
        "project",
        "service_account_email_address",
        "service_account_private_key",
    )

    def test_instance(self):
        """
        Tests creating and deleting an instance on GCE
        """

        # create the instance
        ret_str = self.run_cloud(
            "-p gce-test {}".format(self.instance_name), timeout=TIMEOUT
        )

        # check if instance returned with salt installed
        self.assertInstanceExists(ret_str)
        self.assertDestroyInstance()

    def test_instance_extra(self):
        """
        Tests creating and deleting an instance on GCE
        """

        # create the instance
        ret_str = self.run_cloud(
            "-p gce-test-extra {}".format(self.instance_name), timeout=TIMEOUT
        )

        # check if instance returned with salt installed
        self.assertInstanceExists(ret_str)
        self.assertDestroyInstance()
