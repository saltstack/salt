# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import
import os
import random
import string

# Import Salt Testing Libs
import tests.integration as integration
from tests.support.helpers import expensiveTest

# Import Salt Libs
from salt.config import cloud_providers_config
from salt.ext.six.moves import range  # pylint: disable=redefined-builtin


def __random_name(size=6):
    '''
    Generates a random cloud instance name
    '''
    return 'CLOUD-TEST-' + ''.join(
        random.choice(string.ascii_uppercase + string.digits)
        for x in range(size)
    )

# Create the cloud instance name to be used throughout the tests
INSTANCE_NAME = __random_name()
PROVIDER_NAME = 'joyent'


class JoyentTest(integration.ShellCase):
    '''
    Integration tests for the Joyent cloud provider in Salt-Cloud
    '''

    @expensiveTest
    def setUp(self):
        '''
        Sets up the test requirements
        '''
        super(JoyentTest, self).setUp()

        # check if appropriate cloud provider and profile files are present
        profile_str = 'joyent-config'
        providers = self.run_cloud('--list-providers')
        if profile_str + ':' not in providers:
            self.skipTest(
                'Configuration file for {0} was not found. Check {0}.conf files '
                'in tests/integration/files/conf/cloud.*.d/ to run these tests.'
                .format(PROVIDER_NAME)
            )

        # check if user, password, private_key, and keyname are present
        config = cloud_providers_config(
            os.path.join(
                integration.FILES,
                'conf',
                'cloud.providers.d',
                PROVIDER_NAME + '.conf'
            )
        )

        user = config[profile_str][PROVIDER_NAME]['user']
        password = config[profile_str][PROVIDER_NAME]['password']
        private_key = config[profile_str][PROVIDER_NAME]['private_key']
        keyname = config[profile_str][PROVIDER_NAME]['keyname']

        if user == '' or password == '' or private_key == '' or keyname == '':
            self.skipTest(
                'A user name, password, private_key file path, and a key name '
                'must be provided to run these tests. Check '
                'tests/integration/files/conf/cloud.providers.d/{0}.conf'
                .format(PROVIDER_NAME)
            )

    def test_instance(self):
        '''
        Test creating and deleting instance on Joyent
        '''
        try:
            self.assertIn(
                INSTANCE_NAME,
                [i.strip() for i in self.run_cloud('-p joyent-test {0}'.format(INSTANCE_NAME), timeout=500)]
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

        # if test instance is still present, delete it
        if ret_str in query:
            self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME), timeout=500)
