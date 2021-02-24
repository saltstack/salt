"""
    :codeauthor: Megan Wilhite <mwilhite@saltstack.com>
"""

import socket

from tests.integration.cloud.helpers.cloud_test_base import TIMEOUT, CloudTest


class VMWareTest(CloudTest):
    """
    Integration tests for the vmware cloud provider in Salt-Cloud
    """

    PROVIDER = "vmware"
    REQUIRED_PROVIDER_CONFIG_ITEMS = ("password", "user", "url")

    def setUp(self):
        super().setUp()
        test_host = self.provider_config["url"]
        try:
            socket.gethostbyname_ex(test_host)
        except OSError as exc:
            self.skipTest(
                "The required vmware host at {} is not available: {}".format(
                    test_host, exc
                )
            )

    def test_instance(self):
        """
        Tests creating and deleting an instance on vmware and installing salt
        """
        # create the instance
        disk_datastore = self.config["vmware-test"]["devices"]["disk"]["Hard disk 2"][
            "datastore"
        ]

        ret_val = self.run_cloud(
            "-p vmware-test {}".format(self.instance_name), timeout=TIMEOUT
        )
        disk_datastore_str = "                [{}] {}/Hard disk 2-flat.vmdk".format(
            disk_datastore, self.instance_name
        )

        # check if instance returned with salt installed
        self.assertInstanceExists(ret_val)
        self.assertIn(
            disk_datastore_str,
            ret_val,
            msg="Hard Disk 2 did not use the Datastore {} ".format(disk_datastore),
        )

        self.assertDestroyInstance()

    def test_snapshot(self):
        """
        Tests creating snapshot and creating vm with --no-deploy
        """
        # create the instance
        ret_val = self.run_cloud(
            "-p vmware-test {} --no-deploy".format(self.instance_name), timeout=TIMEOUT
        )

        # check if instance returned with salt installed
        self.assertInstanceExists(ret_val)

        create_snapshot = self.run_cloud(
            "-a create_snapshot {} snapshot_name='Test Cloud' memdump=True -y".format(
                self.instance_name
            ),
            timeout=TIMEOUT,
        )
        s_ret_str = "Snapshot created successfully"

        self.assertIn(s_ret_str, str(create_snapshot))

        self.assertDestroyInstance()
