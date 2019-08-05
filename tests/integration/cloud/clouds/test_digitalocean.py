# -*- coding: utf-8 -*-
'''
Integration tests for DigitalOcean APIv2
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import base64
import hashlib
import os
from Crypto.PublicKey import RSA

# Import Salt Testing Libs
from tests.support.case import ShellCase
from tests.support.paths import FILES
from tests.support.helpers import expensiveTest, generate_random_name

# Import Salt Libs
from salt.config import cloud_providers_config
from salt.ext.six.moves import range
import salt.utils.stringutils


# Create the cloud instance name to be used throughout the tests
INSTANCE_NAME = generate_random_name('CLOUD-TEST-')
PROVIDER_NAME = 'digitalocean'


class DigitalOceanTest(ShellCase):
    '''
    Integration tests for the DigitalOcean cloud provider in Salt-Cloud
    '''

    @expensiveTest
    def setUp(self):
        '''
        Sets up the test requirements
        '''
        super(DigitalOceanTest, self).setUp()

        # check if appropriate cloud provider and profile files are present
        profile_str = 'digitalocean-config'
        providers = self.run_cloud('--list-providers')
        if profile_str + ':' not in providers:
            self.skipTest(
                'Configuration file for {0} was not found. Check {0}.conf files '
                'in tests/integration/files/conf/cloud.*.d/ to run these tests.'
                .format(PROVIDER_NAME)
            )

        # check if personal access token, ssh_key_file, and ssh_key_names are present
        config = cloud_providers_config(
            os.path.join(
                FILES,
                'conf',
                'cloud.providers.d',
                PROVIDER_NAME + '.conf'
            )
        )

        personal_token = config[profile_str][PROVIDER_NAME]['personal_access_token']
        ssh_file = config[profile_str][PROVIDER_NAME]['ssh_key_file']
        ssh_name = config[profile_str][PROVIDER_NAME]['ssh_key_name']

        if personal_token == '' or ssh_file == '' or ssh_name == '':
            self.skipTest(
                'A personal access token, an ssh key file, and an ssh key name '
                'must be provided to run these tests. Check '
                'tests/integration/files/conf/cloud.providers.d/{0}.conf'
                .format(PROVIDER_NAME)
            )

    def test_list_images(self):
        '''
        Tests the return of running the --list-images command for digitalocean
        '''
        image_list = self.run_cloud('--list-images {0}'.format(PROVIDER_NAME))
        self.assertIn(
            '14.04.5 x64',
            [i.strip() for i in image_list]
        )

    def test_list_locations(self):
        '''
        Tests the return of running the --list-locations command for digitalocean
        '''
        _list_locations = self.run_cloud('--list-locations {0}'.format(PROVIDER_NAME))
        self.assertIn(
            'San Francisco 2',
            [i.strip() for i in _list_locations]
        )

    def test_list_sizes(self):
        '''
        Tests the return of running the --list-sizes command for digitalocean
        '''
        _list_sizes = self.run_cloud('--list-sizes {0}'.format(PROVIDER_NAME))
        self.assertIn(
            '16gb',
            [i.strip() for i in _list_sizes]
        )

    def test_key_management(self):
        '''
        Test key management
        '''
        do_key_name = INSTANCE_NAME + '-key'

        # generate key and fingerprint
        ssh_key = RSA.generate(4096)
        pub = salt.utils.stringutils.to_str(ssh_key.publickey().exportKey("OpenSSH"))
        key_hex = hashlib.md5(base64.b64decode(pub.strip().split()[1].encode())).hexdigest()
        finger_print = ':'.join([key_hex[x:x+2] for x in range(0, len(key_hex), 2)])

        try:
            _key = self.run_cloud('-f create_key {0} name="{1}" public_key="{2}"'.format(PROVIDER_NAME, do_key_name, pub))

            # Upload public key
            self.assertIn(
                finger_print,
                [i.strip() for i in _key]
            )

            # List all keys
            list_keypairs = self.run_cloud('-f list_keypairs {0}'.format(PROVIDER_NAME))

            self.assertIn(
                finger_print,
                [i.strip() for i in list_keypairs]
            )

            # List key
            show_keypair = self.run_cloud('-f show_keypair {0} keyname={1}'.format(PROVIDER_NAME,
                                                                                   do_key_name))
            self.assertIn(
                finger_print,
                [i.strip() for i in show_keypair]
            )
        except AssertionError:
            # Delete the public key if the above assertions fail
            self.run_cloud('-f remove_key {0} id={1}'.format(PROVIDER_NAME, finger_print))
            raise
        finally:
            # Delete public key
            self.assertTrue(self.run_cloud('-f remove_key {0} id={1}'.format(PROVIDER_NAME, finger_print)))

    def test_instance(self):
        '''
        Test creating an instance on DigitalOcean
        '''
        # check if instance with salt installed returned
        try:
            self.assertIn(
                INSTANCE_NAME,
                [i.strip() for i in self.run_cloud('-p digitalocean-test {0}'.format(INSTANCE_NAME), timeout=500)]
            )
        except AssertionError:
            self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME), timeout=500)
            raise

        # Try up to 10 times to delete the instance since it might not be
        # available for deletion right away.
        for num_try in range(10):
            # delete the instance
            try:
                self.assertIn(
                    'True',
                    [i.strip() for i in self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME), timeout=500)]
                )
            except AssertionError:
                # The deletion did not succeed, wait 10s and try again
                if num_try < 9:
                    log.warning('Unable to delete azure instance on try %d', num_try)
                    time.sleep(10)
                else:
                    raise
            else:
                # The deletion succeeded
                break

        # Final clean-up of created instance, in case something went wrong.
        # This was originally in a tearDown function, but that didn't make sense
        # To run this for each test when not all tests create instances.
        if INSTANCE_NAME in [i.strip() for i in self.run_cloud('--query')]:
            self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME), timeout=500)
