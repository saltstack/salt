# -*- coding: utf-8 -*-
'''
Integration tests for Vultr
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import time

# Import Salt Testing Libs
from tests.integration.cloud.helpers.cloud_test_base import CloudTest, TIMEOUT
from tests.support.paths import FILES
from tests.support.helpers import expensiveTest
from tests.support.unit import skipIf

# Import Salt Libs
from salt.config import cloud_providers_config
from salt.ext import six


# Create the cloud instance name to be used throughout the tests
PROVIDER_NAME = 'vultr'


class VultrTest(CloudTest):
    '''
    Integration tests for the Vultr cloud provider in Salt-Cloud
    '''

    @expensiveTest
    def setUp(self):
        '''
        Sets up the test requirements
        '''
        super(VultrTest, self).setUp()

        # check if appropriate cloud provider and profile files are present
        profile_str = 'vultr-config'
        providers = self.run_cloud('--list-providers')
        if profile_str + ':' not in providers:
            self.skipTest(
                'Configuration file for {0} was not found. Check {0}.conf files '
                'in tests/integration/files/conf/cloud.*.d/ to run these tests.'
                .format(PROVIDER_NAME)
            )

        # check if api_key, ssh_key_file, and ssh_key_names are present
        config = cloud_providers_config(
            os.path.join(
                FILES,
                'conf',
                'cloud.providers.d',
                PROVIDER_NAME + '.conf'
            )
        )

        api_key = config[profile_str][PROVIDER_NAME]['api_key']
        ssh_file = config[profile_str][PROVIDER_NAME]['ssh_key_file']
        ssh_name = config[profile_str][PROVIDER_NAME]['ssh_key_name']

        if api_key == '' or ssh_file == '' or ssh_name == '':
            self.skipTest(
                'An API key, an ssh key file, and an ssh key name '
                'must be provided to run these tests. Check '
                'tests/integration/files/conf/cloud.providers.d/{0}.conf'
                .format(PROVIDER_NAME)
            )

        self.assertEqual(self._instance_exists(), False,
                         'The instance "{}" exists before it was created by the test'.format(self.instance_name))

    def test_list_images(self):
        '''
        Tests the return of running the --list-images command for Vultr
        '''
        image_list = self.run_cloud('--list-images {0}'.format(self.PROVIDER_NAME))

        self.assertIn(
            'Debian 8 x64 (jessie)',
            [i.strip() for i in image_list]
        )

    def test_list_locations(self):
        '''
        Tests the return of running the --list-locations command for Vultr
        '''
        location_list = self.run_cloud('--list-locations {0}'.format(self.PROVIDER_NAME))
        self.assertIn(
            'New Jersey',
            [i.strip() for i in location_list]
        )

    def test_list_sizes(self):
        '''
        Tests the return of running the --list-sizes command for Vultr
        '''
        size_list = self.run_cloud('--list-sizes {0}'.format(self.PROVIDER_NAME))
        self.assertIn(
            '32768 MB RAM,4x110 GB SSD,40.00 TB BW',
            [i.strip() for i in size_list]
        )

    # Commented for now, Vultr driver does not yet support key management
    #    def test_key_management(self):
    #        '''
    #        Test key management
    #        '''
    #        pub = 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAAQQDDHr/jh2Jy4yALcK4JyWbVkPRaWmhck3IgCoeOO3z1e2dBowLh64QAM+Qb72pxekALga2oi4GvT+TlWNhzPH4V example'
    #        finger_print = '3b:16:bf:e4:8b:00:8b:b8:59:8c:a9:d3:f0:19:45:fa'
    #
    #        _key = self.run_cloud('-f create_key {0} name="MyPubKey" public_key="{1}"'.format(self.PROVIDER, pub))
    #
    #        # Upload public key
    #        self.assertIn(
    #            finger_print,
    #            [i.strip() for i in _key]
    #        )
    #
    #        try:
    #            # List all keys
    #            list_keypairs = self.run_cloud('-f list_keypairs {0}'.format(self.PROVIDER))
    #
    #            self.assertIn(
    #                finger_print,
    #                [i.strip() for i in list_keypairs]
    #            )
    #
    #            # List key
    #            show_keypair = self.run_cloud('-f show_keypair {0} keyname={1}'.format(self.PROVIDER, 'MyPubKey'))
    #
    #            self.assertIn(
    #                finger_print,
    #                [i.strip() for i in show_keypair]
    #            )
    #        except AssertionError:
    #            # Delete the public key if the above assertions fail
    #            self.run_cloud('-f remove_key {0} id={1}'.format(self.PROVIDER, finger_print))
    #            raise
    #
    #        # Delete public key
    #        self.assertTrue(self.run_cloud('-f remove_key {0} id={1}'.format(self.PROVIDER, finger_print)))

    @skipIf(True, 'Skipped temporarily')
    def test_instance(self):
        '''
        Test creating an instance on Vultr
        '''
        # check if instance with salt installed returned
        create_vm = self.run_cloud('-p vultr-test {0}'.format(self.instance_name), timeout=TIMEOUT + 300)
        self.assertIn(
            self.instance_name,
            [i.strip() for i in create_vm]
        )
        self.assertNotIn('Failed to start', six.text_type(create_vm))
        self.assertEqual(self._instance_exists(), True)

        # Vultr won't let us delete an instance less than 5 minutes old.
        time.sleep(300)
        self._destroy_instance()
