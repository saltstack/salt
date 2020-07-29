# -*- coding: utf-8 -*-
"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
    :codeauthor: Tomas Sirny <tsirny@gmail.com>
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.integration.cloud.helpers.cloud_test_base import (
    CloudTest,
    requires_profile_config,
    requires_provider_config,
)


@requires_provider_config(
    "project", "service_account_email_address", "service_account_private_key"
)
class GCETest(CloudTest):
    """
    Integration tests for the GCE cloud provider in Salt-Cloud
    """

    PROVIDER = "gce"
    EXTRA_PROVIDER_CONFIG = "gce-test-extra"
    TEST_TIMEOUT = 800

    PROVIDER = "gce"
    REQUIRED_PROVIDER_CONFIG_ITEMS = (
        "project",
        "service_account_email_address",
        "service_account_private_key",
    )

    def test_instance(self):
        """
        Tests creating and deleting an instance on GCE
        """
        self.assertCreateInstance()
        self.assertDestroyInstance()

    @requires_profile_config(profile_config_name=EXTRA_PROVIDER_CONFIG)
    def test_instance_extra(self):
        """
        Tests creating and deleting an instance on GCE
        """
        self.assertCreateInstance(profile_config_name=self.EXTRA_PROVIDER_CONFIG)
        self.assertDestroyInstance()
