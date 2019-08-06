# -*- coding: utf-8 -*-
'''
    :codeauthor: Ethan Devenport <ethand@stackpointcloud.com>
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import os

# Import Salt Testing Libs
from tests.support.paths import FILES
from tests.support.unit import skipIf
from tests.support.helpers import expensiveTest

# Import Salt Libs
from salt.config import cloud_providers_config

# Import Third-Party Libs
from tests.integration.cloud.helpers.cloud_test_base import TIMEOUT, CloudTest

try:
    # pylint: disable=unused-import
    from profitbricks.client import ProfitBricksService

    HAS_PROFITBRICKS = True
except ImportError:
    HAS_PROFITBRICKS = False

# Create the cloud instance name to be used throughout the tests
PROVIDER_NAME = 'profitbricks'
DRIVER_NAME = 'profitbricks'


@skipIf(HAS_PROFITBRICKS is False, 'salt-cloud requires >= profitbricks 4.1.0')
class ProfitBricksTest(CloudTest):
    '''
    Integration tests for the ProfitBricks cloud provider
    '''

    @expensiveTest
    def setUp(self):
        '''
        Sets up the test requirements
        '''
        super(ProfitBricksTest, self).setUp()

        # check if appropriate cloud provider and profile files are present
        profile_str = 'profitbricks-config'
        providers = self.run_cloud('--list-providers')
        if profile_str + ':' not in providers:
            self.skipTest(
                'Configuration file for {0} was not found. Check {0}.conf '
                'files in tests/integration/files/conf/cloud.*.d/ to run '
                'these tests.'.format(PROVIDER_NAME)
            )

        # check if credentials and datacenter_id present
        config = cloud_providers_config(
            os.path.join(
                FILES,
                'conf',
                'cloud.providers.d',
                PROVIDER_NAME + '.conf'
            )
        )

        username = config[profile_str][DRIVER_NAME]['username']
        password = config[profile_str][DRIVER_NAME]['password']
        datacenter_id = config[profile_str][DRIVER_NAME]['datacenter_id']
        self.datacenter_id = datacenter_id
        if username in ('' or 'foo') or password in ('' or 'bar') or datacenter_id == '':
            self.skipTest(
                'A username, password, and an datacenter must be provided to '
                'run these tests. Check '
                'tests/integration/files/conf/cloud.providers.d/{0}.conf'
                    .format(PROVIDER_NAME)
            )

        self.assertEqual(self._instance_exists(), False,
                         'The instance "{}" exists before it was created by the test'.format(self.INSTANCE_NAME))

    def test_list_images(self):
        '''
        Tests the return of running the --list-images command for ProfitBricks
        '''
        list_images = self.run_cloud('--list-images {0}'.format(PROVIDER_NAME))
        self.assertIn(
            'Ubuntu-16.04-LTS-server-2017-10-01',
            [i.strip() for i in list_images]
        )

    def test_list_image_alias(self):
        '''
        Tests the return of running the -f list_images
        command for ProfitBricks
        '''
        cmd = '-f list_images {0}'.format(PROVIDER_NAME)
        list_images = self.run_cloud(cmd)
        self.assertIn(
            '- ubuntu:latest',
            [i.strip() for i in list_images]
        )

    def test_list_sizes(self):
        '''
        Tests the return of running the --list_sizes command for ProfitBricks
        '''
        list_sizes = self.run_cloud('--list-sizes {0}'.format(PROVIDER_NAME))
        self.assertIn(
            'Micro Instance:',
            [i.strip() for i in list_sizes]
        )

    def test_list_datacenters(self):
        '''
        Tests the return of running the -f list_datacenters
        command for ProfitBricks
        '''
        cmd = '-f list_datacenters {0}'.format(PROVIDER_NAME)
        list_datacenters = self.run_cloud(cmd)
        self.assertIn(
            self.datacenter_id,
            [i.strip() for i in list_datacenters]
        )

    def test_list_nodes(self):
        '''
        Tests the return of running the -f list_nodes command for ProfitBricks
        '''
        list_nodes = self.run_cloud('-f list_nodes {0}'.format(PROVIDER_NAME))
        self.assertIn(
            'state:',
            [i.strip() for i in list_nodes]
        )

        self.assertIn(
            'name:',
            [i.strip() for i in list_nodes]
        )

    def test_list_nodes_full(self):
        '''
        Tests the return of running the -f list_nodes_full
        command for ProfitBricks
        '''
        cmd = '-f list_nodes_full {0}'.format(PROVIDER_NAME)
        list_nodes = self.run_cloud(cmd)
        self.assertIn(
            'state:',
            [i.strip() for i in list_nodes]
        )

        self.assertIn(
            'name:',
            [i.strip() for i in list_nodes]
        )

    def test_list_location(self):
        '''
        Tests the return of running the --list-locations
        command for ProfitBricks
        '''
        cmd = '--list-locations {0}'.format(PROVIDER_NAME)
        list_locations = self.run_cloud(cmd)

        self.assertIn(
            'de/fkb',
            [i.strip() for i in list_locations]
        )

        self.assertIn(
            'de/fra',
            [i.strip() for i in list_locations]
        )

        self.assertIn(
            'us/las',
            [i.strip() for i in list_locations]
        )

        self.assertIn(
            'us/ewr',
            [i.strip() for i in list_locations]
        )

    def test_instance(self):
        '''
        Test creating an instance on ProfitBricks
        '''
        # check if instance with salt installed returned
        self.assertIn(
            self.INSTANCE_NAME,
            [i.strip() for i in self.run_cloud(
                '-p profitbricks-test {0}'.format(self.INSTANCE_NAME),
                timeout=TIMEOUT
            )]
        )
        self.assertEqual(self._instance_exists(), True)

        self._destroy_instance()
