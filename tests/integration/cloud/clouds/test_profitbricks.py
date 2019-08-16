# -*- coding: utf-8 -*-
'''
    :codeauthor: Ethan Devenport <ethand@stackpointcloud.com>
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
    # pylint: disable=unused-import
    from profitbricks.client import ProfitBricksService
    HAS_PROFITBRICKS = True
except ImportError:
    HAS_PROFITBRICKS = False

# Create the cloud instance name to be used throughout the tests
INSTANCE_NAME = generate_random_name('CLOUD-TEST-')
PROVIDER_NAME = 'profitbricks'
DRIVER_NAME = 'profitbricks'


@skipIf(HAS_PROFITBRICKS is False, 'salt-cloud requires >= profitbricks 4.1.0')
@expensiveTest
class ProfitBricksTest(ShellCase):
    '''
    Integration tests for the ProfitBricks cloud provider
    '''

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
                RUNTIME_VARS.FILES,
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

    def setUp(self):
        super(ProfitBricksTest, self).setUp()
        username = self.provider_config.get('username')
        password = self.provider_config.get('password')

        # A default username and password must be hard-coded as defaults as per issue #46265
        # If they are 'foo' and 'bar' it is the same as not being set

        self.skipTest('Conf items are missing that must be provided to run these tests:  username, password'
                      '\nCheck tests/integration/files/conf/cloud.providers.d/{0}.conf'.format(self.PROVIDER))

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
        try:
            self.assertIn(
                INSTANCE_NAME,
                [i.strip() for i in self.run_cloud(
                    '-p profitbricks-test {0}'.format(INSTANCE_NAME),
                    timeout=500
                )]
            )
        except AssertionError:
            self.run_cloud(
                '-d {0} --assume-yes'.format(INSTANCE_NAME),
                timeout=500
            )
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

        # if test instance is still present, delete it
        if ret in query:
            self.run_cloud(
                '-d {0} --assume-yes'.format(INSTANCE_NAME),
                timeout=500
            )
