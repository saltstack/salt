"""
    :codeauthor: Li Kexian <doyenli@tencent.com>
"""

import os

import pytest
from saltfactories.utils import random_string

from salt.config import cloud_providers_config
from tests.support.case import ShellCase
from tests.support.runtests import RUNTIME_VARS

# Create the cloud instance name to be used throughout the tests
INSTANCE_NAME = random_string("CLOUD-TEST-", lowercase=False)
PROVIDER_NAME = "tencentcloud"


@pytest.mark.expensive_test
class TencentCloudTest(ShellCase):
    """
    Integration tests for the Tencent Cloud cloud provider in Salt-Cloud
    """

    def setUp(self):
        """
        Sets up the test requirements
        """
        super().setUp()

        # check if appropriate cloud provider and profile files are present
        profile_str = "tencentcloud-config"
        providers = self.run_cloud("--list-providers")

        if profile_str + ":" not in providers:
            self.skipTest(
                "Configuration file for {0} was not found. Check {0}.conf files "
                "in tests/integration/files/conf/cloud.*.d/ to run these tests.".format(
                    PROVIDER_NAME
                )
            )

        # check if personal access token, ssh_key_file, and ssh_key_names are present
        config = cloud_providers_config(
            os.path.join(
                RUNTIME_VARS.FILES, "conf", "cloud.providers.d", PROVIDER_NAME + ".conf"
            )
        )

        tid = config[profile_str][PROVIDER_NAME]["id"]
        key = config[profile_str][PROVIDER_NAME]["key"]
        if tid == "" or key == "":
            self.skipTest(
                "An api id and key must be provided to run these tests. Check "
                "tests/integration/files/conf/cloud.providers.d/{}.conf".format(
                    PROVIDER_NAME
                )
            )

    def test_instance(self):
        """
        Test creating an instance on Tencent Cloud
        """
        # check if instance with salt installed returned
        try:
            self.assertIn(
                INSTANCE_NAME,
                [
                    i.strip()
                    for i in self.run_cloud(
                        "-p tencentcloud-test {}".format(INSTANCE_NAME), timeout=500
                    )
                ],
            )
        except AssertionError:
            self.run_cloud("-d {} --assume-yes".format(INSTANCE_NAME), timeout=500)
            raise

        # delete the instance
        self.assertIn(
            INSTANCE_NAME + ":",
            [
                i.strip()
                for i in self.run_cloud(
                    "-d {} --assume-yes".format(INSTANCE_NAME), timeout=500
                )
            ],
        )

    def tearDown(self):
        """
        Clean up after tests
        """
        query = self.run_cloud("--query")
        ret_str = "        {}:".format(INSTANCE_NAME)

        # if test instance is still present, delete it
        if ret_str in query:
            self.run_cloud("-d {} --assume-yes".format(INSTANCE_NAME), timeout=500)
