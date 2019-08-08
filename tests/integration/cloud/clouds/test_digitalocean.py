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
from tests.integration.cloud.helpers.cloud_test_base import CloudTest, TIMEOUT
from tests.support.paths import FILES
from tests.support.helpers import expensiveTest

# Import Salt Libs
from salt.ext.six.moves import range
import salt.utils.stringutils


# Create the cloud instance name to be used throughout the tests
PROVIDER_NAME = 'digitalocean'


class DigitalOceanTest(CloudTest):
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

        self.assertEqual(self._instance_exists(), False,
                         'The instance "{}" exists before it was created by the test'.format(self.instance_name))

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

        try:
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
        # check if instance with salt installed returned
        self.assertIn(
            self.instance_name,
            [i.strip() for i in self.run_cloud('-p digitalocean-test {0}'.format(self.instance_name), timeout=TIMEOUT)]
        )
        self.assertEqual(self._instance_exists(), True)
        self._destroy_instance()
