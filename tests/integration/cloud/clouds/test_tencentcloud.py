# -*- coding: utf-8 -*-
"""
    :codeauthor: Li Kexian <doyenli@tencent.com>
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

import os

# Import Salt Libs
from salt.config import cloud_providers_config

# Import Salt Testing Libs
from tests.support.case import ShellCase
from tests.support.helpers import expensiveTest, generate_random_name
from tests.support.runtests import RUNTIME_VARS

# Create the cloud instance name to be used throughout the tests
INSTANCE_NAME = generate_random_name("CLOUD-TEST-")
PROVIDER_NAME = "tencentcloud"


@expensiveTest
class TencentCloudTest(ShellCase):
    """
    Integration tests for the Tencent Cloud cloud provider in Salt-Cloud
    """

    def setUp(self):
        """
        Sets up the test requirements
        """
        super(TencentCloudTest, self).setUp()

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
                "tests/integration/files/conf/cloud.providers.d/{0}.conf".format(
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
                        "-p tencentcloud-test {0}".format(INSTANCE_NAME), timeout=500
                    )
                ],
            )
        except AssertionError:
            self.run_cloud("-d {0} --assume-yes".format(INSTANCE_NAME), timeout=500)
            raise

        # delete the instance
        self.assertIn(
            INSTANCE_NAME + ":",
            [
                i.strip()
                for i in self.run_cloud(
                    "-d {0} --assume-yes".format(INSTANCE_NAME), timeout=500
                )
            ],
        )

    def tearDown(self):
        """
        Clean up after tests
        """
        query = self.run_cloud("--query")
        ret_str = "        {0}:".format(INSTANCE_NAME)

        # if test instance is still present, delete it
        if ret_str in query:
            self.run_cloud("-d {0} --assume-yes".format(INSTANCE_NAME), timeout=500)
