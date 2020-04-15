# -*- coding: utf-8 -*-
"""
    :codeauthor: Megan Wilhite <mwilhite@saltstack.com>
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
from salt.ext import six

# Create the cloud instance name to be used throughout the tests
from tests.integration.cloud.helpers.cloud_test_base import TIMEOUT, CloudTest


class VMWareTest(CloudTest):
    """
    Integration tests for the vmware cloud provider in Salt-Cloud
    """

    PROVIDER = "vmware"
    REQUIRED_PROVIDER_CONFIG_ITEMS = ("password", "user", "url")

    def test_instance(self):
        """
        Tests creating and deleting an instance on vmware and installing salt
        """
        # create the instance
        disk_datastore = self.config["vmware-test"]["devices"]["disk"]["Hard disk 2"][
            "datastore"
        ]

        ret_val = self.run_cloud(
            "-p vmware-test {0}".format(self.instance_name), timeout=TIMEOUT
        )
        disk_datastore_str = "                [{0}] {1}/Hard disk 2-flat.vmdk".format(
            disk_datastore, self.instance_name
        )

        # check if instance returned with salt installed
        self.assertInstanceExists(ret_val)
        self.assertIn(
            disk_datastore_str,
            ret_val,
            msg="Hard Disk 2 did not use the Datastore {0} ".format(disk_datastore),
        )

        self.assertDestroyInstance()

    def test_snapshot(self):
        """
        Tests creating snapshot and creating vm with --no-deploy
        """
        # create the instance
        ret_val = self.run_cloud(
            "-p vmware-test {0} --no-deploy".format(self.instance_name), timeout=TIMEOUT
        )

        # check if instance returned with salt installed
        self.assertInstanceExists(ret_val)

        create_snapshot = self.run_cloud(
            "-a create_snapshot {0} \
                                         snapshot_name='Test Cloud' \
                                         memdump=True -y".format(
                self.instance_name
            ),
            timeout=TIMEOUT,
        )
        s_ret_str = "Snapshot created successfully"

        self.assertIn(s_ret_str, six.text_type(create_snapshot))

        self.assertDestroyInstance()
