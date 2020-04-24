# -*- coding: utf-8 -*-
"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.integration.cloud.helpers.cloud_test_base import (
    CloudTest,
    requires_provider_config,
)


@requires_provider_config("apikey", "password")
class LinodeTest(CloudTest):
    """
    Integration tests for the Linode cloud provider in Salt-Cloud
    """

    PROVIDER = "linode"

    def test_instance(self):
        """
        Test creating an instance on Linode
        """
        self.assertCreateInstance()
        self.assertDestroyInstance()
