# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Ethan Devenport <ethand@stackpointcloud.com>`
'''

# Import Python Libs
from __future__ import absolute_import
import os
import random
import string

# Import Salt Testing Libs
from salttesting import skipIf
from salttesting.helpers import ensure_in_syspath, expensiveTest

ensure_in_syspath('../../../')

# Import Salt Libs
import integration
from salt.config import cloud_providers_config
from salt.ext.six.moves import range

# Import Third-Party Libs
try:
    from profitbricks.client import ProfitBricksService  # pylint: disable=unused-import
    HAS_PROFITBRICKS = True
except ImportError:
    HAS_PROFITBRICKS = False


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
PROVIDER_NAME = 'profitbricks'
DRIVER_NAME = 'profitbricks'


@skipIf(HAS_PROFITBRICKS is False, 'salt-cloud requires >= profitbricks 2.3.0')
class ProfitBricksTest(integration.ShellCase):
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
                integration.FILES,
                'conf',
                'cloud.providers.d',
                PROVIDER_NAME + '.conf'
            )
        )

        username = config[profile_str][DRIVER_NAME]['username']
        password = config[profile_str][DRIVER_NAME]['password']
        datacenter_id = config[profile_str][DRIVER_NAME]['datacenter_id']
        if username == '' or password == '' or datacenter_id == '':
            self.skipTest(
                'A username, password, and an datacenter must be provided to '
                'run these tests. Check '
                'tests/integration/files/conf/cloud.providers.d/{0}.conf'
                .format(PROVIDER_NAME)
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
                    '-p profitbricks-test {0}'.format(INSTANCE_NAME)
                )]
            )
        except AssertionError:
            self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME))
            raise

        # delete the instance
        try:
            self.assertIn(
                INSTANCE_NAME + ':',
                [i.strip() for i in self.run_cloud(
                    '-d {0} --assume-yes'.format(INSTANCE_NAME)
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
            self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME))


if __name__ == '__main__':
    from integration import run_tests  # pylint: disable=import-error
    run_tests(ProfitBricksTest)
