# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Amel Ajdinovic <amel@stackpointcloud.com>`
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import os

# Import Salt Testing Libs
from tests.support.case import ShellCase
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import skipIf
from tests.support.helpers import expensiveTest, generate_random_name

# Import Salt Libs
from salt.config import cloud_providers_config

# Import Third-Party Libs
try:
    from oneandone.client import OneAndOneService  # pylint: disable=unused-import
    HAS_ONEANDONE = True
except ImportError:
    HAS_ONEANDONE = False


# Create the cloud instance name to be used throughout the tests
INSTANCE_NAME = generate_random_name('CLOUD-TEST-')
PROVIDER_NAME = 'oneandone'
DRIVER_NAME = 'oneandone'


@skipIf(HAS_ONEANDONE is False, 'salt-cloud requires >= 1and1 1.2.0')
@expensiveTest
class OneAndOneTest(ShellCase):
    '''
    Integration tests for the 1and1 cloud provider
    '''
    PROVIDER = 'oneandone'
    REQUIRED_PROVIDER_CONFIG_ITEMS = ('api_token',)

    def test_list_images(self):
        '''
        Tests the return of running the --list-images command for 1and1
        '''
        image_list = self.run_cloud('--list-images {0}'.format(PROVIDER_NAME))
        self.assertIn(
            'coreOSimage',
            [i.strip() for i in image_list]
        )

    def test_instance(self):
        '''
        Test creating an instance on 1and1
        '''
        # check if instance with salt installed returned
        try:
            self.assertIn(
                INSTANCE_NAME,
                [i.strip() for i in self.run_cloud(
                    '-p oneandone-test {0}'.format(INSTANCE_NAME), timeout=500
                )]
            )
        except AssertionError:
            self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME), timeout=500)
            raise

        # delete the instance
        try:
            self.assertIn(
                INSTANCE_NAME + ':',
                [i.strip() for i in self.run_cloud(
                    '-d {0} --assume-yes'.format(INSTANCE_NAME), timeout=500
                )]
            )
        except AssertionError:
            raise

    def tearDown(self):
        '''
        Clean up after tests
        '''
        query = self.run_cloud('--query')
        ret = '        {0}:'.format(INSTANCE_NAME)

        self.assertDestroyInstance()
