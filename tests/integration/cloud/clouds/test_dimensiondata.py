# -*- coding: utf-8 -*-
"""
Integration tests for the Dimension Data cloud provider
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.case import ShellCase
from tests.support.helpers import expensiveTest
from tests.support.runtests import RUNTIME_VARS



def _random_name(size=6):
    '''
    Generates a random cloud instance name
    '''
    return 'cloud-test-' + ''.join(
        random.choice(string.ascii_lowercase + string.digits)
        for x in range(size)
    )


# Create the cloud instance name to be used throughout the tests
INSTANCE_NAME = _random_name()
PROVIDER_NAME = 'dimensiondata'


@expensiveTest
class DimensionDataTest(ShellCase):
    '''
    Integration tests for the Dimension Data cloud provider in Salt-Cloud
    '''

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
                RUNTIME_VARS.FILES,
                'conf',
                'cloud.providers.d',
                PROVIDER_NAME + '.conf'
            )
        )

        user_id = config[profile_str][PROVIDER_NAME]['user_id']
        key = config[profile_str][PROVIDER_NAME]['key']
        region = config[profile_str][PROVIDER_NAME]['region']

    PROVIDER = "dimensiondata"
    REQUIRED_PROVIDER_CONFIG_ITEMS = ("key", "region", "user_id")

    def test_list_images(self):
        """
        Tests the return of running the --list-images command for the dimensiondata cloud provider
        """
        image_list = self.run_cloud("--list-images {0}".format(self.PROVIDER))
        self.assertIn("Ubuntu 14.04 2 CPU", [i.strip() for i in image_list])

    def test_list_locations(self):
        """
        Tests the return of running the --list-locations command for the dimensiondata cloud provider
        """
        _list_locations = self.run_cloud("--list-locations {0}".format(self.PROVIDER))
        self.assertIn(
            "Australia - Melbourne MCP2", [i.strip() for i in _list_locations]
        )

    def test_list_sizes(self):
        """
        Tests the return of running the --list-sizes command for the dimensiondata cloud provider
        """
        _list_sizes = self.run_cloud("--list-sizes {0}".format(self.PROVIDER))
        self.assertIn("default", [i.strip() for i in _list_sizes])

    def test_instance(self):
        """
        Test creating an instance on Dimension Data's cloud
        """
        # check if instance with salt installed returned
        ret_val = self.run_cloud(
            "-p dimensiondata-test {0}".format(self.instance_name), timeout=TIMEOUT
        )
        self.assertInstanceExists(ret_val)

        self.assertDestroyInstance()
