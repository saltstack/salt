# -*- coding: utf-8 -*-
'''
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
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
INSTANCE_NAME = generate_random_name('cloud-test-').lower()
PROVIDER_NAME = 'joyent'
TIMEOUT = 500


class JoyentTest(ShellCase):
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
                FILES,
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

        self.assertEqual(self._instance_exists(), False,
                         'The instance "{}" exists before it was created by the test'.format(INSTANCE_NAME))

    def _instance_exists(self):
        return '        {0}:'.format(INSTANCE_NAME) in self.run_cloud('--query')

    def test_instance(self):
        '''
        Test creating and deleting instance on Joyent
        '''
        self.assertIn(
            INSTANCE_NAME,
            [i.strip() for i in self.run_cloud('-p joyent-test {0}'.format(INSTANCE_NAME), timeout=500)]
        )
        self.assertEqual(self._instance_exists(), True)

    def tearDown(self):
        '''
        Clean up after tests
        '''
        delete = self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME), timeout=TIMEOUT)
        # example response: ['gce-config:', '----------', '    gce:', '----------', 'cloud-test-dq4e6c:', 'True', '']
        delete_str = ''.join(delete)

        # check if deletion was performed appropriately
        self.assertIn(INSTANCE_NAME, delete_str)
        self.assertIn('True', delete_str)
