# -*- coding: utf-8 -*-
'''
Integration tests for the Dimension Data cloud provider
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import os

# Import Salt Testing Libs
from tests.integration.cloud.helpers.cloud_test_base import CloudTest, TIMEOUT
from tests.support.paths import FILES
from tests.support.helpers import expensiveTest

# Import Salt Libs
from salt.config import cloud_providers_config


# Create the cloud instance name to be used throughout the tests
PROVIDER_NAME = 'dimensiondata'


class DimensionDataTest(CloudTest):
    '''
    Integration tests for the Dimension Data cloud provider in Salt-Cloud
    '''

    @expensiveTest
    def setUp(self):
        '''
        Sets up the test requirements
        '''
        super(DimensionDataTest, self).setUp()

        # check if appropriate cloud provider and profile files are present
        profile_str = 'dimensiondata-config'
        providers = self.run_cloud('--list-providers')
        if profile_str + ':' not in providers:
            self.skipTest(
                'Configuration file for {0} was not found. Check {0}.conf files '
                'in tests/integration/files/conf/cloud.*.d/ to run these tests.'
                .format(PROVIDER_NAME)
            )

        # check if user_id, key, and region are present
        config = cloud_providers_config(
            os.path.join(
                FILES,
                'conf',
                'cloud.providers.d',
                PROVIDER_NAME + '.conf'
            )
        )

        user_id = config[profile_str][PROVIDER_NAME]['user_id']
        key = config[profile_str][PROVIDER_NAME]['key']
        region = config[profile_str][PROVIDER_NAME]['region']

        if user_id == '' or key == '' or region == '':
            self.skipTest(
                'A user Id, password, and a region '
                'must be provided to run these tests. Check '
                'tests/integration/files/conf/cloud.providers.d/{0}.conf'
                .format(PROVIDER_NAME)
            )

        self.assertFalse(self._instance_exists(),
                         'The instance "{}" exists before it was created by the test'.format(self.instance_name))

    def test_list_images(self):
        '''
        Tests the return of running the --list-images command for the dimensiondata cloud provider
        '''
        image_list = self.run_cloud('--list-images {0}'.format(PROVIDER_NAME))
        self.assertIn(
            'Ubuntu 14.04 2 CPU',
            [i.strip() for i in image_list]
        )

    def test_list_locations(self):
        '''
        Tests the return of running the --list-locations command for the dimensiondata cloud provider
        '''
        _list_locations = self.run_cloud('--list-locations {0}'.format(PROVIDER_NAME))
        self.assertIn(
            'Australia - Melbourne MCP2',
            [i.strip() for i in _list_locations]
        )

    def test_list_sizes(self):
        '''
        Tests the return of running the --list-sizes command for the dimensiondata cloud provider
        '''
        _list_sizes = self.run_cloud('--list-sizes {0}'.format(PROVIDER_NAME))
        self.assertIn(
            'default',
            [i.strip() for i in _list_sizes]
        )

    def test_instance(self):
        '''
        Test creating an instance on Dimension Data's cloud
        '''
        # check if instance with salt installed returned
        ret_val = self.run_cloud('-p dimensiondata-test {0}'.format(self.instance_name), timeout=TIMEOUT)
        self.assertInstanceExists(ret_val)

        self._destroy_instance()
