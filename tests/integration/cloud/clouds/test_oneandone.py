# -*- coding: utf-8 -*-
"""
    :codeauthor: :email:`Amel Ajdinovic <amel@stackpointcloud.com>`
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.integration.cloud.helpers.cloud_test_base import TIMEOUT, CloudTest
from tests.support.unit import skipIf

# Import Third-Party Libs
try:
    from oneandone.client import OneAndOneService  # pylint: disable=unused-import

    HAS_ONEANDONE = True
except ImportError:
    HAS_ONEANDONE = False


@skipIf(HAS_ONEANDONE is False, "salt-cloud requires >= 1and1 1.2.0")
class OneAndOneTest(CloudTest):
    """
    Integration tests for the 1and1 cloud provider
    """

    PROVIDER = "oneandone"
    REQUIRED_PROVIDER_CONFIG_ITEMS = ("api_token",)

    def test_list_images(self):
        """
        Tests the return of running the --list-images command for 1and1
        """
        image_list = self.run_cloud("--list-images {0}".format(self.PROVIDER_NAME))
        self.assertIn("coreOSimage", [i.strip() for i in image_list])

    def test_instance(self):
        """
        Test creating an instance on 1and1
        """
        # check if instance with salt installed returned
        ret_str = self.run_cloud(
            "-p oneandone-test {0}".format(self.instance_name), timeout=TIMEOUT
        )
        self.assertInstanceExists(ret_str)

        self.assertDestroyInstance()
