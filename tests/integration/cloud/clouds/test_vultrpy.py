# -*- coding: utf-8 -*-
'''
Integration tests for Vultr
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import time

# Import Salt Testing Libs
from tests.support.case import ShellCase
from tests.support.runtests import RUNTIME_VARS
from tests.support.helpers import expensiveTest, generate_random_name
from tests.support.unit import skipIf

# Import Salt Libs
from salt.config import cloud_providers_config
from salt.ext import six


# Create the cloud instance name to be used throughout the tests
INSTANCE_NAME = generate_random_name('CLOUD-TEST-')
PROVIDER_NAME = 'vultr'
TIMEOUT = 500


@expensiveTest
class VultrTest(ShellCase):
    '''
    Integration tests for the Vultr cloud provider in Salt-Cloud
    '''
    PROVIDER = 'vultr'
    REQUIRED_PROVIDER_CONFIG_ITEMS = ('api_key', 'ssh_key_file', 'ssh_key_name')

    def test_list_images(self):
        '''
        Tests the return of running the --list-images command for Vultr
        '''
        image_list = self.run_cloud('--list-images {0}'.format(PROVIDER_NAME))

        self.assertIn(
            'Debian 8 x64 (jessie)',
            [i.strip() for i in image_list]
        )

    def test_list_locations(self):
        '''
        Tests the return of running the --list-locations command for Vultr
        '''
        location_list = self.run_cloud('--list-locations {0}'.format(PROVIDER_NAME))
        self.assertIn(
            'New Jersey',
            [i.strip() for i in location_list]
        )

    def test_list_sizes(self):
        '''
        Tests the return of running the --list-sizes command for Vultr
        '''
        size_list = self.run_cloud('--list-sizes {0}'.format(PROVIDER_NAME))
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
#        _key = self.run_cloud('-f create_key {0} name="MyPubKey" public_key="{1}"'.format(PROVIDER_NAME, pub))
#
#        # Upload public key
#        self.assertIn(
#            finger_print,
#            [i.strip() for i in _key]
#        )
#
#        try:
#            # List all keys
#            list_keypairs = self.run_cloud('-f list_keypairs {0}'.format(PROVIDER_NAME))
#
#            self.assertIn(
#                finger_print,
#                [i.strip() for i in list_keypairs]
#            )
#
#            # List key
#            show_keypair = self.run_cloud('-f show_keypair {0} keyname={1}'.format(PROVIDER_NAME, 'MyPubKey'))
#
#            self.assertIn(
#                finger_print,
#                [i.strip() for i in show_keypair]
#            )
#        except AssertionError:
#            # Delete the public key if the above assertions fail
#            self.run_cloud('-f remove_key {0} id={1}'.format(PROVIDER_NAME, finger_print))
#            raise
#
#        # Delete public key
#        self.assertTrue(self.run_cloud('-f remove_key {0} id={1}'.format(PROVIDER_NAME, finger_print)))

    @skipIf(True, 'Skipped temporarily')
    def test_instance(self):
        '''
        Test creating an instance on Vultr
        '''
        # check if instance with salt installed returned
        try:
            create_vm = self.run_cloud('-p vultr-test {0}'.format(INSTANCE_NAME), timeout=800)
            self.assertIn(
                INSTANCE_NAME,
                [i.strip() for i in create_vm]
            )
            self.assertNotIn('Failed to start', six.text_type(create_vm))
        except AssertionError:
            self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME), timeout=TIMEOUT)
            raise

        # Vultr won't let us delete an instance less than 5 minutes old.
        time.sleep(300)
        self.assertDestroyInstance()
