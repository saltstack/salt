# -*- coding: utf-8 -*-
'''
Integration tests for DigitalOcean APIv2
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import os

# Import Salt Testing Libs
from tests.support.case import ShellCase
from tests.support.paths import FILES
from tests.support.helpers import expensiveTest, generate_random_name

# Import Salt Libs
from salt.config import cloud_providers_config

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
            'San Francisco 1',
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
        pub = 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAAQQDDHr/jh2Jy4yALcK4JyWbVkPRaWmhck3IgCoeOO3z1e2dBowLh64QAM+Qb72pxekALga2oi4GvT+TlWNhzPH4V example'
        finger_print = '3b:16:bf:e4:8b:00:8b:b8:59:8c:a9:d3:f0:19:45:fa'

        _key = self.run_cloud('-f create_key {0} name="MyPubKey" public_key="{1}"'.format(PROVIDER_NAME, pub))

        # Upload public key
        self.assertIn(
            finger_print,
            [i.strip() for i in _key]
        )

        try:
            # List all keys
            list_keypairs = self.run_cloud('-f list_keypairs {0}'.format(PROVIDER_NAME))

            self.assertIn(
                finger_print,
                [i.strip() for i in list_keypairs]
            )

            # List key
            show_keypair = self.run_cloud('-f show_keypair {0} keyname={1}'.format(PROVIDER_NAME, 'MyPubKey'))

            self.assertIn(
                finger_print,
                [i.strip() for i in show_keypair]
            )
        except AssertionError:
            # Delete the public key if the above assertions fail
            self.run_cloud('-f remove_key {0} id={1}'.format(PROVIDER_NAME, finger_print))
            raise

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

        # delete the instance
        try:
            self.assertIn(
                'True',
                [i.strip() for i in self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME), timeout=500)]
            )
        except AssertionError:
            raise

        # Final clean-up of created instance, in case something went wrong.
        # This was originally in a tearDown function, but that didn't make sense
        # To run this for each test when not all tests create instances.
        if INSTANCE_NAME in [i.strip() for i in self.run_cloud('--query')]:
            self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME), timeout=500)
