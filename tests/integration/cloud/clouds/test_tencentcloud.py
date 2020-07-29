# -*- coding: utf-8 -*-
"""
    :codeauthor: Li Kexian <doyenli@tencent.com>
"""

from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.integration.cloud.helpers.cloud_test_base import (
    CloudTest,
    requires_provider_config,
)


@requires_provider_config("id", "key")
class TencentCloudTest(CloudTest):
    """
    Integration tests for the Tencent Cloud cloud provider in Salt-Cloud
    """

    PROVIDER = "tencentcloud"

    def test_instance(self):
        """
        Test creating and destroying an instance on Tencent Cloud
        """
        self.assertCreateInstance()
        self.assertDestroyInstance()
