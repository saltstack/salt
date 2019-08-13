# -*- coding: utf-8 -*-
'''
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import os

# Import Salt Testing Libs
from tests.support.case import ShellCase
from tests.support.runtests import RUNTIME_VARS
from tests.support.helpers import expensiveTest, generate_random_name
from tests.support.unit import skipIf, WAR_ROOM_SKIP

# Import Salt Libs
from salt.config import cloud_providers_config


# Create the cloud instance name to be used throughout the tests
INSTANCE_NAME = generate_random_name('CLOUD-TEST-')
PROVIDER_NAME = 'linode'


@skipIf(WAR_ROOM_SKIP, 'WAR ROOM TEMPORARY SKIP')
@expensiveTest
class LinodeTest(ShellCase):
    '''
    Integration tests for the Linode cloud provider in Salt-Cloud
    '''

    PROVIDER = 'linode'
    REQUIRED_PROVIDER_CONFIG_ITEMS = ('apikey', 'password')

    def test_instance(self):
        '''
        Test creating an instance on Linode
        '''
        # check if instance with salt installed returned
        try:
            self.assertIn(
                INSTANCE_NAME,
                [i.strip() for i in self.run_cloud('-p linode-test {0}'.format(INSTANCE_NAME), timeout=500)]
            )
        except AssertionError:
            self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME), timeout=500)
            raise

        # delete the instance
        try:
            self.assertIn(
                INSTANCE_NAME + ':',
                [i.strip() for i in self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME), timeout=500)]
            )
        except AssertionError:
            raise

    def tearDown(self):
        '''
        Clean up after tests
        '''
        query = self.run_cloud('--query')
        ret_str = '        {0}:'.format(INSTANCE_NAME)

        self.assertDestroyInstance()
