# -*- coding: utf-8 -*-
"""
Integration tests for DigitalOcean APIv2
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

import base64
import hashlib

import salt.crypt

# Import Salt Libs
import salt.ext.six as six
import salt.utils.stringutils
from salt.ext.six.moves import range

# Import Salt Testing Libs
from tests.integration.cloud.helpers.cloud_test_base import TIMEOUT, CloudTest


class DigitalOceanTest(CloudTest):
    """
    Integration tests for the DigitalOcean cloud provider in Salt-Cloud
    """

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
        image_list = self.run_cloud("--list-images {0}".format(self.PROVIDER))
        self.assertIn("14.04.5 x64", [i.strip() for i in image_list])

    def test_list_locations(self):
        """
        Tests the return of running the --list-locations command for digitalocean
        """
        _list_locations = self.run_cloud("--list-locations {0}".format(self.PROVIDER))
        self.assertIn("San Francisco 2", [i.strip() for i in _list_locations])

    def test_list_sizes(self):
        """
        Tests the return of running the --list-sizes command for digitalocean
        """
        _list_sizes = self.run_cloud("--list-sizes {0}".format(self.PROVIDER))
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
                )
            )

            # Upload public key
            self.assertIn(finger_print, [i.strip() for i in _key])

            # List all keys
            list_keypairs = self.run_cloud("-f list_keypairs {0}".format(self.PROVIDER))

            self.assertIn(finger_print, [i.strip() for i in list_keypairs])

            # List key
            show_keypair = self.run_cloud(
                "-f show_keypair {0} keyname={1}".format(self.PROVIDER, do_key_name)
            )
            self.assertIn(finger_print, [i.strip() for i in show_keypair])
        except AssertionError:
            # Delete the public key if the above assertions fail
            self.run_cloud(
                "-f remove_key {0} id={1}".format(self.PROVIDER, finger_print)
            )
            raise
        finally:
            # Delete public key
            self.assertTrue(
                self.run_cloud(
                    "-f remove_key {0} id={1}".format(self.PROVIDER, finger_print)
                )
            )

    def test_instance(self):
        """
        Test creating an instance on DigitalOcean
        """
        # check if instance with salt installed returned
        ret_str = self.run_cloud(
            "-p digitalocean-test {0}".format(self.instance_name), timeout=TIMEOUT
        )
        self.assertInstanceExists(ret_str)

        self.assertDestroyInstance()
