# -*- coding: utf-8 -*-
"""
    :codeauthor: Tyler Johnson <tjohnson@saltstack.com>
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Create the cloud instance name to be used throughout the tests
from tests.integration.cloud.helpers.cloud_test_base import (
    CloudTest,
    OverrideCloudConfig,
    requires_provider_config,
)


@requires_provider_config("driver", "url")
class LibvirtTest(CloudTest):
    """
    Integration tests for the libvirt cloud provider in Salt-Cloud
    """

    PROVIDER = "libvirt"

    def test_instance(self):
        """
        Base case testing all the default values,
        Change one variable at a time for the other tests, no need to test every permutation of them
        """
        with OverrideCloudConfig(
            self.profile_config_path,
            self.profile_config_name,
            sudo=False,
            clone_strategy="full",
            ssh_agent=True,
            ssh_key="",
            ssh_password="",
            ip_source="ip-learning",
        ):
            self.assertCreateInstance()
            self.assertDestroyInstance()

    def test_sudo(self):
        with OverrideCloudConfig(
            self.profile_config_path, self.profile_config_name, sudo=True
        ):
            self.assertCreateInstance()
            self.assertDestroyInstance()

    def test_clone_strategy_quick(self):
        with OverrideCloudConfig(
            self.profile_config_path, self.profile_config_name, clone_strategy="quick"
        ):
            self.assertCreateInstance()
            self.assertDestroyInstance()

    def test_ssh_key(self):
        with OverrideCloudConfig(
            self.profile_config_path,
            self.profile_config_name,
            ssh_agent=False,
            ssh_key="TODO/path/to/ssh_key",
        ):
            self.assertCreateInstance()
            self.assertDestroyInstance()

    def test_ssh_password(self):
        with OverrideCloudConfig(
            self.profile_config_path,
            self.profile_config_name,
            ssh_agent=False,
            ssh_password="TODO the password",
        ):
            self.assertCreateInstance()
            self.assertDestroyInstance()

    def test_qemu_agent(self):
        with OverrideCloudConfig(
            self.profile_config_path, self.profile_config_name, ip_source="qemu_agent"
        ):
            self.assertCreateInstance()
            self.assertDestroyInstance()
