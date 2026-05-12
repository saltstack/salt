"""
Integration tests for functions located in the salt.cloud.__init__.py file.
"""

import pytest

import salt.cloud
from tests.integration.cloud.helpers.cloud_test_base import CloudTest
from tests.support.helpers import PRE_PYTEST_SKIP


@PRE_PYTEST_SKIP
class CloudClientTestCase(CloudTest):
    """
    Integration tests for the CloudClient class. Uses DigitalOcean as a salt-cloud provider.
    """

    PROVIDER = "digitalocean"
    REQUIRED_PROVIDER_CONFIG_ITEMS = tuple()
    IMAGE_NAME = "14.04.5 x64"

    @pytest.mark.expensive_test
    def setUp(self):

        # Use a --list-images salt-cloud call to see if the DigitalOcean provider is
        # configured correctly before running any tests.
        images = self.run_cloud(f"--list-images {self.PROVIDER}")

        if self.image_name not in [i.strip() for i in images]:
            self.skipTest(
                "Image '{}' was not found in image search. Is the {} provider "
                "configured correctly for this test?".format(
                    self.PROVIDER, self.image_name
                )
            )

    def test_cloud_client_create_and_delete(self):
        """
        Tests that a VM is created successfully when calling salt.cloud.CloudClient.create(),
        which does not require a profile configuration.

        Also checks that salt.cloud.CloudClient.destroy() works correctly since this test needs
        to remove the VM after creating it.

        This test was created as a regression check against Issue #41971.
        """
        cloud_client = salt.cloud.CloudClient(self.config_file)

        # Create the VM using salt.cloud.CloudClient.create() instead of calling salt-cloud
        ret_val = cloud_client.create(
            provider=self.PROVIDER,
            names=[self.instance_name],
            image=self.IMAGE_NAME,
            location="sfo1",
            size="512mb",
            vm_size="512mb",
        )

        # Check that the VM was created correctly
        self.assertInstanceExists(ret_val)

        # Clean up after ourselves and delete the VM
        deleted = cloud_client.destroy(names=[self.instance_name])

        # Check that the VM was deleted correctly
        self.assertIn(self.instance_name, deleted)
