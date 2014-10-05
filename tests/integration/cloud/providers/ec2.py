# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''

# Import Python Libs
import os
import random
import string

# Import Salt Libs
import integration
from salt.config import cloud_providers_config

# Import Salt Testing Libs
from salttesting.helpers import ensure_in_syspath, expensiveTest

ensure_in_syspath('../../../')


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


class EC2Test(integration.ShellCase):
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
        profile_str = 'ec2-config:'
        provider = 'ec2'
        providers = self.run_cloud('--list-providers')

        if profile_str not in providers:
            self.skipTest(
                'Configuration file for {0} was not found. Check {0}.conf files '
                'in tests/integration/files/conf/cloud.*.d/ to run these tests.'
                .format(provider)
            )

        # check if id, key, keyname, securitygroup, private_key, location,
        # and provider are present
        path = os.path.join(integration.FILES,
                            'conf',
                            'cloud.providers.d',
                            provider + '.conf')
        config = cloud_providers_config(path)

        id = config['ec2-config']['ec2']['id']
        key = config['ec2-config']['ec2']['key']
        keyname = config['ec2-config']['ec2']['keyname']
        sec_group = config['ec2-config']['ec2']['securitygroup']
        private_key = config['ec2-config']['ec2']['private_key']
        location = config['ec2-config']['ec2']['location']

        conf_items = [id, key, keyname, sec_group, private_key, location]
        missing_conf_item = []

        for item in conf_items:
            if item == '':
                missing_conf_item.append(item)

        if missing_conf_item:
            self.skipTest(
                'An id, key, keyname, security group, private key, and location must '
                'be provided to run these tests. One or more of these elements is '
                'missing. Check tests/integration/files/conf/cloud.providers.d/{0}.conf'
                .format(provider)
            )

    def test_instance(self):
        '''
        Tests creating and deleting an instance on EC2 (classic)
        '''

        # create the instance
        instance = self.run_cloud('-p ec2-test {0}'.format(INSTANCE_NAME))
        ret_str = '{0}:'.format(INSTANCE_NAME)

        # check if instance returned with salt installed
        try:
            self.assertIn(ret_str, instance)
        except AssertionError:
            self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME))
            raise

        # delete the instance
        delete = self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME))
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
            self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(EC2Test)
