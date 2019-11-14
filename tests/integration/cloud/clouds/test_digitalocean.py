# -*- coding: utf-8 -*-
'''
Integration tests for DigitalOcean APIv2
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import base64
import hashlib
from Crypto.PublicKey import RSA

# Import Salt Testing Libs
from salt.config import cloud_config
from tests.integration.cloud.helpers.cloud_test_base import CloudTest, TIMEOUT
from tests.support.unit import skipIf

# Import Salt Libs
from salt.ext.six.moves import range
import salt.cloud
import salt.utils.stringutils


class DigitalOceanTest(CloudTest):
    '''
    Integration tests for the DigitalOcean cloud provider in Salt-Cloud
    '''
    PROVIDER = 'digitalocean'
    REQUIRED_PROVIDER_CONFIG_ITEMS = ('personal_access_token', 'ssh_key_file', 'ssh_key_name')

    def test_list_images(self):
        '''
        Tests the return of running the --list-images command for digitalocean
        '''
        image_list = self.run_cloud('--list-images {0}'.format(self.PROVIDER))
        self.assertIn(
            '14.04.5 x64',
            [i.strip() for i in image_list]
        )

    def test_list_locations(self):
        '''
        Tests the return of running the --list-locations command for digitalocean
        '''
        _list_locations = self.run_cloud('--list-locations {0}'.format(self.PROVIDER))
        self.assertIn(
            'San Francisco 2',
            [i.strip() for i in _list_locations]
        )

    def test_list_sizes(self):
        '''
        Tests the return of running the --list-sizes command for digitalocean
        '''
        _list_sizes = self.run_cloud('--list-sizes {0}'.format(self.PROVIDER))
        self.assertIn(
            '16gb',
            [i.strip() for i in _list_sizes]
        )

    def test_key_management(self):
        '''
        Test key management
        '''
        do_key_name = self.instance_name + '-key'

        # generate key and fingerprint
        ssh_key = RSA.generate(4096)
        pub = salt.utils.stringutils.to_str(ssh_key.publickey().exportKey("OpenSSH"))
        key_hex = hashlib.md5(base64.b64decode(pub.strip().split()[1].encode())).hexdigest()
        finger_print = ':'.join([key_hex[x:x+2] for x in range(0, len(key_hex), 2)])

        try:
            _key = self.run_cloud('-f create_key {0} name="{1}" public_key="{2}"'.format(self.PROVIDER,
                                                                                         do_key_name, pub))

            # Upload public key
            self.assertIn(
                finger_print,
                [i.strip() for i in _key]
            )

            # List all keys
            list_keypairs = self.run_cloud('-f list_keypairs {0}'.format(self.PROVIDER))

            self.assertIn(
                finger_print,
                [i.strip() for i in list_keypairs]
            )

            # List key
            show_keypair = self.run_cloud('-f show_keypair {0} keyname={1}'.format(self.PROVIDER, do_key_name))
            self.assertIn(
                finger_print,
                [i.strip() for i in show_keypair]
            )
        except AssertionError:
            # Delete the public key if the above assertions fail
            self.run_cloud('-f remove_key {0} id={1}'.format(self.PROVIDER, finger_print))
            raise
        finally:
            # Delete public key
            self.assertTrue(self.run_cloud('-f remove_key {0} id={1}'.format(self.PROVIDER, finger_print)))

    def test_instance(self):
        '''
        Test creating an instance on DigitalOcean
        '''
        self.assertCreateInstance(timeout=TIMEOUT)
        self.assertDestroyInstance()

    @skipIf(True, 'WAR ROOM TEMPORARY SKIP')            # needs to be rewritten to allow for dnf on Fedora 30 and RHEL 8
    def test_cloud_client_create_and_delete(self):
        '''
        Tests that a VM is created successfully when calling salt.cloud.CloudClient.create(),
        which does not require a profile configuration.

        Also checks that salt.cloud.CloudClient.destroy() works correctly since this test needs
        to remove the VM after creating it.

        This test was created as a regression check against Issue #41971.
        '''
        IMAGE_NAME = '18.04.3 (LTS) x64'
        LOCATION = 'sfo2'
        SIZE = '512mb'
        images = self.run_cloud('--list-images {0}'.format(self.profile_str))
        if not any(IMAGE_NAME == i.strip(': ') for i in images):
            self.skipTest('Image \'{1}\' was not found in image search.  Is the {0} provider '
                          'configured correctly for this test?'.format(self.PROVIDER, IMAGE_NAME))

        locations = self.run_cloud('--list-locations {0}'.format(self.profile_str))
        if not any(LOCATION == l.strip(': ') for l in locations):
            self.skipTest('Location \'{0}\' is not in the list of locations for \'{1}\'\n{2}'.format(LOCATION,
                                                                                                     self.PROVIDER,
                                                                                                     locations))

        # FIXME?  It works when passing a provider config to cloud_config instead of cloud_providers_config
        # FIXME?  Passing self.config to opts doesn't work, and neither does self.providers_config
        # FIXME?  CloudClient(opts=) wants the provider config created with cloud_config()
        opts = cloud_config(self.provider_config_path)

        # Create the VM using salt.cloud.CloudClient.create() instead of calling salt-cloud
        cloud_client = salt.cloud.CloudClient(opts=opts)
        ret_val = cloud_client.create(
            provider=self.profile_str,
            names=[self.instance_name],
            image=IMAGE_NAME,
            location=LOCATION,
            size=SIZE,
            vm_size=SIZE,
        )

        # Check that the VM was created correctly
        self.assertTrue(ret_val, 'Error in {} creation, no return value from create()'.format(self.instance_name))
        self.assertIn(self.instance_name, ret_val.keys())
        self.assertTrue(ret_val[self.instance_name].get('deployed'))
        self.assertEquals(ret_val[self.instance_name].get('name'), self.instance_name)
        self.assertEquals(ret_val[self.instance_name]['image']['name'], IMAGE_NAME)
        self.assertEquals(ret_val[self.instance_name]['size'].get('slug'), IMAGE_NAME)

        # Clean up after ourselves and delete the VM
        deletion_ret = cloud_client.destroy(names=[self.instance_name])

        # Check that the VM was deleted correctly
        self.assertDestroyInstance(deletion_ret=deletion_ret, timeout=TIMEOUT)
