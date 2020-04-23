# -*- coding: utf-8 -*-
"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Create the cloud instance name to be used throughout the tests
from tests.integration.cloud.helpers.cloud_test_base import TIMEOUT, CloudTest

# Import Salt Testing Libs
from tests.support.unit import skipIf


@skipIf(True, "waiting on bug report fixes from #13365")
class GoGridTest(CloudTest):
    """
    Integration tests for the GoGrid cloud provider in Salt-Cloud
    """

    PROVIDER = "gogrid"
    REQUIRED_PROVIDER_CONFIG_ITEMS = ("apikey", "sharedsecret")

    def test_instance(self):
        """
        Test creating an instance on GoGrid
        """
        # check if instance with salt installed returned
        ret_str = self.run_cloud(
            "-p gogrid-test {0}".format(self.instance_name), timeout=TIMEOUT
        )
        self.assertInstanceExists(ret_str)

        self.assertDestroyInstance()
