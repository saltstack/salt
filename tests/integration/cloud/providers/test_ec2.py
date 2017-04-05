# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import
import os
import random
import string

# Import Salt Libs
from salt.config import cloud_providers_config

# Import Salt Testing Libs
from tests.support.case import ShellCase
from tests.support.paths import FILES
from tests.support.helpers import expensiveTest

# Import Third-Party Libs
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin


def __random_name(size=6):
    '''
    Generates a radom cloud instance name
    '''
    return 'CLOUD-TEST-' + ''.join(
        random.choice(string.ascii_uppercase + string.digits)
        for x in range(size)
    )

# Create the cloud instance name to be used throughout the tests
INSTANCE_NAME = __random_name()
PROVIDER_NAME = 'ec2'


class EC2Test(ShellCase):
    '''
    Integration tests for the EC2 cloud provider in Salt-Cloud
    '''

    @expensiveTest
    def setUp(self):
        '''
        Sets up the test requirements
        '''
        super(EC2Test, self).setUp()

        # check if appropriate cloud provider and profile files are present
        profile_str = 'ec2-config'
        providers = self.run_cloud('--list-providers')

        if profile_str + ':' not in providers:
            self.skipTest(
                'Configuration file for {0} was not found. Check {0}.conf files '
                'in tests/integration/files/conf/cloud.*.d/ to run these tests.'
                .format(PROVIDER_NAME)
            )

        # check if id, key, keyname, securitygroup, private_key, location,
        # and provider are present
        config = cloud_providers_config(
            os.path.join(
                FILES,
                'conf',
                'cloud.providers.d',
                PROVIDER_NAME + '.conf'
            )
        )

        id_ = config[profile_str][PROVIDER_NAME]['id']
        key = config[profile_str][PROVIDER_NAME]['key']
        key_name = config[profile_str][PROVIDER_NAME]['keyname']
        sec_group = config[profile_str][PROVIDER_NAME]['securitygroup']
        private_key = config[profile_str][PROVIDER_NAME]['private_key']
        location = config[profile_str][PROVIDER_NAME]['location']

        conf_items = [id_, key, key_name, sec_group, private_key, location]
        missing_conf_item = []

        for item in conf_items:
            if item == '':
                missing_conf_item.append(item)

        if missing_conf_item:
            self.skipTest(
                'An id, key, keyname, security group, private key, and location must '
                'be provided to run these tests. One or more of these elements is '
                'missing. Check tests/integration/files/conf/cloud.providers.d/{0}.conf'
                .format(PROVIDER_NAME)
            )

    def test_instance(self):
        '''
        Tests creating and deleting an instance on EC2 (classic)
        '''
        # create the instance
        instance = self.run_cloud('-p ec2-test {0}'.format(INSTANCE_NAME), timeout=500)
        ret_str = '{0}:'.format(INSTANCE_NAME)

        # check if instance returned with salt installed
        try:
            self.assertIn(ret_str, instance)
        except AssertionError:
            self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME), timeout=500)
            raise

        # delete the instance
        delete = self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME), timeout=500)
        ret_str = '                    shutting-down'

        # check if deletion was performed appropriately
        try:
            self.assertIn(ret_str, delete)
        except AssertionError:
            raise

    def tearDown(self):
        '''
        Clean up after tests
        '''
        query = self.run_cloud('--query')
        ret_str = '        {0}:'.format(INSTANCE_NAME)

        # if test instance is still present, delete it
        if ret_str in query:
            self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME), timeout=500)
