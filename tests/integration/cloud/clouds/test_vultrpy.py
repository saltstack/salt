import time

import pytest

from tests.integration.cloud.helpers.cloud_test_base import TIMEOUT, CloudTest


class VultrTest(CloudTest):
    """
    Integration tests for the Vultr cloud provider in Salt-Cloud
    """

    PROVIDER = "vultr"
    REQUIRED_PROVIDER_CONFIG_ITEMS = ("api_key", "ssh_key_file", "ssh_key_name")

    def test_list_images(self):
        """
        Tests the return of running the --list-images command for Vultr
        """
        image_list = self.run_cloud(f"--list-images {self.PROVIDER}")

        self.assertIn("Debian 10 x64 (buster)", [i.strip() for i in image_list])

    def test_list_locations(self):
        """
        Tests the return of running the --list-locations command for Vultr
        """
        location_list = self.run_cloud(f"--list-locations {self.PROVIDER}")
        self.assertIn("New Jersey", [i.strip() for i in location_list])

    def test_list_sizes(self):
        """
        Tests the return of running the --list-sizes command for Vultr
        """
        size_list = self.run_cloud(f"--list-sizes {self.PROVIDER}")
        self.assertIn(
            "2048 MB RAM,55 GB SSD,2.00 TB BW", [i.strip() for i in size_list]
        )

    # Commented for now, Vultr driver does not yet support key management
    #    def test_key_management(self):
    #        '''
    #        Test key management
    #        '''
    #        pub = 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAAQQDDHr/jh2Jy4yALcK4JyWbVkPRaWmhck3IgCoeOO3z1e2dBowLh64QAM+Qb72pxekALga2oi4GvT+TlWNhzPH4V example'
    #        finger_print = '3b:16:bf:e4:8b:00:8b:b8:59:8c:a9:d3:f0:19:45:fa'
    #
    #        _key = self.run_cloud('-f create_key {0} name="MyPubKey" public_key="{1}"'.format(self.PROVIDER, pub))
    #
    #        # Upload public key
    #        self.assertIn(
    #            finger_print,
    #            [i.strip() for i in _key]
    #        )
    #
    #        try:
    #            # List all keys
    #            list_keypairs = self.run_cloud('-f list_keypairs {0}'.format(self.PROVIDER))
    #
    #            self.assertIn(
    #                finger_print,
    #                [i.strip() for i in list_keypairs]
    #            )
    #
    #            # List key
    #            show_keypair = self.run_cloud('-f show_keypair {0} keyname={1}'.format(self.PROVIDER, 'MyPubKey'))
    #
    #            self.assertIn(
    #                finger_print,
    #                [i.strip() for i in show_keypair]
    #            )
    #        except AssertionError:
    #            # Delete the public key if the above assertions fail
    #            self.run_cloud('-f remove_key {0} id={1}'.format(self.PROVIDER, finger_print))
    #            raise
    #
    #        # Delete public key
    #        self.assertTrue(self.run_cloud('-f remove_key {0} id={1}'.format(self.PROVIDER, finger_print)))

    @pytest.mark.skip(reason="Skipped temporarily")
    def test_instance(self):
        """
        Test creating an instance on Vultr
        """
        # check if instance with salt installed returned
        ret_val = self.run_cloud(
            f"-p vultr-test {self.instance_name}", timeout=TIMEOUT + 300
        )
        self.assertInstanceExists(ret_val)

        # Vultr won't let us delete an instance less than 5 minutes old.
        time.sleep(300)
        self.assertDestroyInstance()
