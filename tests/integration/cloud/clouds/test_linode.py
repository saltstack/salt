# -*- coding: utf-8 -*-
"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Create the cloud instance name to be used throughout the tests
from tests.integration.cloud.helpers.cloud_test_base import TIMEOUT, CloudTest


class LinodeTest(CloudTest):
    """
    Integration tests for the Linode cloud provider in Salt-Cloud
    """

    PROVIDER = "linode"
    REQUIRED_PROVIDER_CONFIG_ITEMS = ("apikey", "password")

    def test_instance(self):
        """
        Test creating an instance on Linode
        """
        # check if instance with salt installed returned
        ret_str = self.run_cloud(
            "-p linode-test {0}".format(self.instance_name), timeout=TIMEOUT
        )
        self.assertInstanceExists(ret_str)

        self.assertDestroyInstance()
