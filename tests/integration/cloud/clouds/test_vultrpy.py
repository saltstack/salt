# -*- coding: utf-8 -*-
"""
Integration tests for Vultr
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

import time

# Import Salt Libs
import salt.cloud.clouds.vultrpy

# Import Salt Testing Libs
from tests.integration.cloud.helpers.cloud_test_base import (
    CloudTest,
    OverrideCloudConfig,
    requires_provider_config,
)
from tests.support.unit import skipIf


@requires_provider_config("api_key", "ssh_key_file", "ssh_key_name")
class VultrTest(CloudTest):
    """
    Integration tests for the Vultr cloud provider in Salt-Cloud
    """

    PROVIDER = "vultr"
    TEST_TIMEOUT = 1200

    PROVIDER = "vultr"
    REQUIRED_PROVIDER_CONFIG_ITEMS = ("api_key", "ssh_key_file", "ssh_key_name")

    def test_list_images(self):
        """
        Tests the return of running the --list-images command for Vultr
        """
        image_list = self.run_cloud(
            "--list-images {0}".format(self.PROVIDER), timeout=self.TEST_TIMEOUT
        )

        self.assertIn("Debian 10 x64 (buster)", [i.strip(": ") for i in image_list])

    def test_list_locations(self):
        """
        Tests the return of running the --list-locations command for Vultr
        """
        locations = {
            l.strip(":- ")
            for l in self.run_cloud(
                "--list-locations {0}".format(self.PROVIDER), timeout=self.TEST_TIMEOUT
            )
            if l.strip(":- ")
        }
        expected_locations = {
            "Amsterdam",
            "Atlanta",
            "Chicago",
            "Dallas",
            "Frankfurt",
            "London",
            "Los Angeles",
            "Miami",
            "New Jersey",
            "Paris",
            "Seattle",
            "Silicon Valley",
            "Singapore",
            "Sydney",
            "Tokyo",
            "Toronto",
        }
        self.assertTrue(
            locations.issuperset(expected_locations),
            "{} not in {}".format(locations, expected_locations),
        )

    def test_list_sizes(self):
        """
        Tests the return of running the --list-sizes command for Vultr
        """
        size_list = self.run_cloud(
            "--list-sizes {0}".format(self.PROVIDER), timeout=self.TEST_TIMEOUT
        )
        self.assertIn(
            "2048 MB RAM,64 GB SSD,2.00 TB BW", [i.strip() for i in size_list]
        )

    @skipIf(
        not hasattr(salt.cloud.clouds.vultrpy, "create_key"),
        'The vultr driver does not define the function "create_key"',
    )
    def test_key_management(self):
        """
        Test key management
        """
        pub = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAAQQDDHr/jh2Jy4yALcK4JyWbVkPRaWmhck3IgCoeOO3z1e2dBowLh64QAM+Qb72pxekALga2oi4GvT+TlWNhzPH4V example"
        finger_print = "3b:16:bf:e4:8b:00:8b:b8:59:8c:a9:d3:f0:19:45:fa"

        _key = self.run_cloud(
            '-f create_key {0} name="MyPubKey" public_key="{1}"'.format(
                self.PROVIDER, pub
            ),
            timeout=self.TEST_TIMEOUT,
        )

        # Upload public key
        self.assertIn(finger_print, [i.strip() for i in _key])

        try:
            # List all keys
            list_keypairs = self.run_cloud(
                "-f list_keypairs {0}".format(self.PROVIDER), timeout=self.TEST_TIMEOUT
            )

            self.assertIn(finger_print, [i.strip() for i in list_keypairs])

            # List key
            show_keypair = self.run_cloud(
                "-f show_keypair {0} keyname={1}".format(self.PROVIDER, "MyPubKey"),
                timeout=self.TEST_TIMEOUT,
            )

            self.assertIn(finger_print, [i.strip() for i in show_keypair])
        except AssertionError:
            # Delete the public key if the above assertions fail
            self.run_cloud(
                "-f remove_key {0} id={1}".format(self.PROVIDER, finger_print),
                timeout=self.TEST_TIMEOUT,
            )
            raise

        # Delete public key
        deletion_ret = self.run_cloud(
            "-f remove_key {0} id={1}".format(self.PROVIDER, finger_print),
            timeout=self.TEST_TIMEOUT,
        )
        self.assertTrue(deletion_ret)

    def test_instance(self):
        """
        Test creating an instance on Vultr
        """
        with OverrideCloudConfig(
            self.profile_config_path,
            self.profile_config_name,
            size="4096 MB RAM,80 GB SSD,3.00 TB BW",
        ):
            self.assertCreateInstance()
            # Vultr won't let us delete an instance less than 5 minutes old.
            time.sleep(300)
            self.assertDestroyInstance()
