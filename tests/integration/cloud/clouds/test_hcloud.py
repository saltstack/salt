# -*- coding: utf-8 -*-
"""
    Tests for the Hetzner-Public-Cloud driver

    You will need to set a master with ip/hostname in the cloud.profiled.d/hcloud.conf as well as a valid api_key in the
    cloud.providers.d/hcloud.conf. A api_key can be found in a specific project in the hetzner public cloud.

    hcloud-test:
        ...
        ...
        ...
        minion:
            master: ip_or_hostname_of_testing_machine
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Create the cloud instance name to be used throughout the tests
from tests.integration.cloud.helpers.cloud_test_base import TIMEOUT, CloudTest


class HCloudTest(CloudTest):
    """
    Integration tests for the Hetzner-Public-Cloud provider in Salt-Cloud
    """

    PROVIDER = "hcloud"
    REQUIRED_PROVIDER_CONFIG_ITEMS = ("api_key", "ssh_keyfile", "ssh_keyfile_public")

    def test_instance(self):
        """
        Test creating an instance on Hetzner-Public-Cloud
        """
        # check if instance with salt installed returned
        ret_str = self.run_cloud(
            "-p hcloud-test {0}".format(self.instance_name), timeout=TIMEOUT
        )
        self.assertInstanceExists(ret_str)

        self.assertDestroyInstance()
