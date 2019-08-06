# -*- coding: utf-8 -*-
'''
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.paths import FILES
from tests.support.helpers import expensiveTest, generate_random_name

# Import Salt Libs
from salt.config import cloud_providers_config

# Create the cloud instance name to be used throughout the tests
INSTANCE_NAME = generate_random_name('cloud-test-').lower()
PROVIDER_NAME = 'linode'
TIMEOUT = 500


class LinodeTest(CloudTest):
    '''
    Integration tests for the Linode cloud provider in Salt-Cloud
    '''

    @expensiveTest
    def setUp(self):
        '''
        Sets up the test requirements
        '''
        super(LinodeTest, self).setUp()

        # check if appropriate cloud provider and profile files are present
        profile_str = 'linode-config'
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

        api = config[profile_str][PROVIDER_NAME]['apikey']
        password = config[profile_str][PROVIDER_NAME]['password']
        if api == '' or password == '':
            self.skipTest(
                'An api key and password must be provided to run these tests. Check '
                'tests/integration/files/conf/cloud.providers.d/{0}.conf'.format(
                    PROVIDER_NAME
                )
            )

        self.assertEqual(self._instance_exists(), False,
                         'The instance "{}" exists before it was created by the test'.format(INSTANCE_NAME))

    def _instance_exists(self):
        return '        {0}:'.format(INSTANCE_NAME) in self.run_cloud('--query')

    def test_instance(self):
        '''
        Test creating an instance on Linode
        '''
        # check if instance with salt installed returned
        self.assertIn(
            INSTANCE_NAME,
            [i.strip() for i in self.run_cloud('-p linode-test {0}'.format(INSTANCE_NAME), timeout=500)]
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
