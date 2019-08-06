# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Amel Ajdinovic <amel@stackpointcloud.com>`
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.integration.cloud.helpers.cloud_test_base import CloudTest, TIMEOUT
from tests.support.paths import FILES
from tests.support.unit import skipIf

# Import Third-Party Libs
try:
    from oneandone.client import OneAndOneService  # pylint: disable=unused-import

    HAS_ONEANDONE = True
except ImportError:
    HAS_ONEANDONE = False

# Create the cloud instance name to be used throughout the tests
INSTANCE_NAME = generate_random_name('CLOUD-TEST-')
PROVIDER_NAME = 'oneandone'
DRIVER_NAME = 'oneandone'


@skipIf(HAS_ONEANDONE is False, 'salt-cloud requires >= 1and1 1.2.0')
class OneAndOneTest(CloudTest):
    '''
    Integration tests for the 1and1 cloud provider
    '''

    @expensiveTest
    def setUp(self):
        '''
        Sets up the test requirements
        '''
        super(OneAndOneTest, self).setUp()

        # check if appropriate cloud provider and profile files are present
        profile_str = 'oneandone-config'
        providers = self.run_cloud('--list-providers')
        if profile_str + ':' not in providers:
            self.skipTest(
                'Configuration file for {0} was not found. Check {0}.conf '
                'files in tests/integration/files/conf/cloud.*.d/ to run '
                'these tests.'.format(PROVIDER_NAME)
            )

        # check if api_token present
        config = cloud_providers_config(
            os.path.join(
                FILES,
                'conf',
                'cloud.providers.d',
                PROVIDER_NAME + '.conf'
            )
        )

        api_token = config[profile_str][DRIVER_NAME]['api_token']
        if api_token == '':
            self.skipTest(
                'api_token must be provided to '
                'run these tests. Check '
                'tests/integration/files/conf/cloud.providers.d/{0}.conf'
                    .format(PROVIDER_NAME)
            )

        self.assertEqual(self._instance_exists(), False,
                         'The instance "{}" exists before it was created by the test'.format(INSTANCE_NAME))

    def test_list_images(self):
        '''
        Tests the return of running the --list-images command for 1and1
        '''
        image_list = self.run_cloud('--list-images {0}'.format(self.PROVIDER_NAME))
        self.assertIn(
            'coreOSimage',
            [i.strip() for i in image_list]
        )

    def test_instance(self):
        '''
        Test creating an instance on 1and1
        '''
        # check if instance with salt installed returned
        self.assertIn(
            INSTANCE_NAME,
            [i.strip() for i in self.run_cloud(
                '-p oneandone-test {0}'.format(INSTANCE_NAME), timeout=TIMEOUT
            )]
        )
        self.assertEqual(self._instance_exists(), True)

        self._destroy_instance()
