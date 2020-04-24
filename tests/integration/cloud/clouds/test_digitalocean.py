# -*- coding: utf-8 -*-
"""
Integration tests for DigitalOcean APIv2
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

import base64
import hashlib
import time

import salt.cloud
import salt.config
import salt.crypt
import salt.ext.six as six
import salt.utils.stringutils

# Import Salt Libs
from salt.ext.six.moves import range

# Import Salt Testing Libs
from tests.integration.cloud.helpers.cloud_test_base import (
    CloudTest,
    requires_provider_config,
)


@requires_provider_config("personal_access_token", "ssh_key_file", "ssh_key_name")
class DigitalOceanTest(CloudTest):
    """
    Integration tests for the DigitalOcean cloud provider in Salt-Cloud
    """

    PROVIDER = "digitalocean"

    PROVIDER = "digitalocean"
    REQUIRED_PROVIDER_CONFIG_ITEMS = (
        "personal_access_token",
        "ssh_key_file",
        "ssh_key_name",
    )

    def test_list_images(self):
        """
        Tests the return of running the --list-images command for digitalocean
        """
        image_list = self.run_cloud(
            "--list-images {0}".format(self.PROVIDER), timeout=self.TEST_TIMEOUT
        )
        self.assertIn("14.04.5 x64", [i.strip() for i in image_list])

    def test_list_locations(self):
        """
        Tests the return of running the --list-locations command for digitalocean
        """
        _list_locations = self.run_cloud(
            "--list-locations {0}".format(self.PROVIDER), timeout=self.TEST_TIMEOUT
        )
        self.assertIn("San Francisco 2", [i.strip() for i in _list_locations])

    def test_list_sizes(self):
        """
        Tests the return of running the --list-sizes command for digitalocean
        """
        _list_sizes = self.run_cloud(
            "--list-sizes {0}".format(self.PROVIDER), timeout=self.TEST_TIMEOUT
        )
        self.assertIn("16gb", [i.strip() for i in _list_sizes])

    def test_key_management(self):
        """
        Test key management
        """
        do_key_name = self.instance_name + "-key"

        # generate key and fingerprint
        if salt.crypt.HAS_M2:
            rsa_key = salt.crypt.RSA.gen_key(4096, 65537, lambda: None)
            pub = six.b(
                "ssh-rsa {}".format(
                    base64.b64encode(
                        six.b("\x00\x00\x00\x07ssh-rsa{}{}".format(*rsa_key.pub()))
                    )
                )
            )
        else:
            ssh_key = salt.crypt.RSA.generate(4096)
            pub = ssh_key.publickey().exportKey("OpenSSH")
        pub = salt.utils.stringutils.to_str(pub)
        key_hex = hashlib.md5(
            base64.b64decode(pub.strip().split()[1].encode())
        ).hexdigest()
        finger_print = ":".join([key_hex[x : x + 2] for x in range(0, len(key_hex), 2)])

        try:
            _key = self.run_cloud(
                '-f create_key {0} name="{1}" public_key="{2}"'.format(
                    self.PROVIDER, do_key_name, pub
                ),
                timeout=self.TEST_TIMEOUT,
            )

            # Upload public key
            self.assertIn(finger_print, [i.strip() for i in _key])

            # List all keys
            list_keypairs = self.run_cloud(
                "-f list_keypairs {0}".format(self.PROVIDER), timeout=self.TEST_TIMEOUT
            )

            self.assertIn(finger_print, [i.strip() for i in list_keypairs])

            # List key
            show_keypair = self.run_cloud(
                "-f show_keypair {0} keyname={1}".format(self.PROVIDER, do_key_name),
                timeout=self.TEST_TIMEOUT,
            )
            self.assertIn(finger_print, [i.strip() for i in show_keypair])
            self.assertIn(finger_print, [i.strip() for i in show_keypair])
        except AssertionError:
            # Delete the public key if the above assertions fail
            self.run_cloud(
                "-f remove_key {0} id={1}".format(self.PROVIDER, finger_print),
                timeout=self.TEST_TIMEOUT,
            )
            raise
        finally:
            # Delete public key
            deletion_ret = self.run_cloud(
                "-f remove_key {0} id={1}".format(self.PROVIDER, finger_print),
                timeout=self.TEST_TIMEOUT,
            )
            self.assertTrue(deletion_ret)

    def test_instance(self):
        """
        Test creating an instance on DigitalOcean
        """
        self.assertCreateInstance()
        self.assertDestroyInstance()

    def test_cloud_client_create_and_delete(self):
        """
        Tests that a VM is created successfully when calling salt.cloud.CloudClient.create(),
        which does not require a profile configuration.

        Also checks that salt.cloud.CloudClient.destroy() works correctly since this test needs
        to remove the VM after creating it.

        This test was created as a regression check against Issue #41971.
        """
        IMAGE_NAME = "18.04.3 (LTS) x64"
        LOCATION = "sfo2"
        SIZE = "512mb"

        opts = salt.config.cloud_config(
            self.profile_config_path,
            profiles_config_path=self.profile_config_path,
            providers_config_path=self.provider_config_path,
        )
        opts["timeout"] = self.TEST_TIMEOUT

        # Create the VM using salt.cloud.CloudClient.create() instead of calling salt-cloud
        cloud_client = salt.cloud.CloudClient(opts=opts)

        # Verify that the necessary options are available
        images = cloud_client.list_images(self.PROVIDER)[self.provider_config_name][
            self.PROVIDER
        ]
        self.assertIn(IMAGE_NAME, images)
        locations = cloud_client.list_locations(self.PROVIDER)[
            self.provider_config_name
        ][self.PROVIDER]
        self.assertIn(LOCATION, [loc["slug"] for loc in locations.values()])
        sizes = cloud_client.list_sizes(self.PROVIDER)[self.provider_config_name][
            self.PROVIDER
        ]
        self.assertIn(SIZE, sizes)

        ret_val = cloud_client.create(
            provider=self.provider_config_name,
            names=[self.instance_name],
            image=IMAGE_NAME,
            location=LOCATION,
            size=SIZE,
            vm_size=SIZE,
        )

        # Check that the return value is populated and contains all the correct values`
        self.assertTrue(
            ret_val,
            "Error in {} creation, no return value from create()".format(
                self.instance_name
            ),
        )
        self.assertIn(self.instance_name, ret_val.keys())
        self.assertTrue(ret_val[self.instance_name].get("deployed"))
        self.assertEqual(ret_val[self.instance_name].get("name"), self.instance_name)
        self.assertEqual(ret_val[self.instance_name]["image"]["name"], IMAGE_NAME)
        self.assertEqual(ret_val[self.instance_name]["size"].get("slug"), SIZE)

        # Do a thorough check for success
        self.assertInstanceExists()

        # Clean up after ourselves and delete the VM
        deletion_ret = cloud_client.destroy(names=[self.instance_name])

        # Give the cloud a minute to update the status of the VM
        time.sleep(60)

        # Check that the VM was deleted correctly
        self.assertEqual(
            deletion_ret,
            {self.provider_config_name: {self.PROVIDER: {self.instance_name: True}}},
        )
