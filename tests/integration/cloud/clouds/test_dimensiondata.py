"""
Integration tests for the Dimension Data cloud provider
"""

from tests.integration.cloud.helpers.cloud_test_base import TIMEOUT, CloudTest


class DimensionDataTest(CloudTest):
    """
    Integration tests for the Dimension Data cloud provider in Salt-Cloud
    """

    PROVIDER = "dimensiondata"
    REQUIRED_PROVIDER_CONFIG_ITEMS = ("key", "region", "user_id")

    def test_list_images(self):
        """
        Tests the return of running the --list-images command for the dimensiondata cloud provider
        """
        image_list = self.run_cloud(f"--list-images {self.PROVIDER}")
        self.assertIn("Ubuntu 14.04 2 CPU", [i.strip() for i in image_list])

    def test_list_locations(self):
        """
        Tests the return of running the --list-locations command for the dimensiondata cloud provider
        """
        _list_locations = self.run_cloud(f"--list-locations {self.PROVIDER}")
        self.assertIn(
            "Australia - Melbourne MCP2", [i.strip() for i in _list_locations]
        )

    def test_list_sizes(self):
        """
        Tests the return of running the --list-sizes command for the dimensiondata cloud provider
        """
        _list_sizes = self.run_cloud(f"--list-sizes {self.PROVIDER}")
        self.assertIn("default", [i.strip() for i in _list_sizes])

    def test_instance(self):
        """
        Test creating an instance on Dimension Data's cloud
        """
        # check if instance with salt installed returned
        ret_val = self.run_cloud(
            f"-p dimensiondata-test {self.instance_name}", timeout=TIMEOUT
        )
        self.assertInstanceExists(ret_val)

        self.assertDestroyInstance()
