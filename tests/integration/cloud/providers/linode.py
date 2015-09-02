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
from salttesting.helpers import ensure_in_syspath, expensiveTest

ensure_in_syspath('../../../')

# Import Salt Libs
import integration
from salt.config import cloud_providers_config
from salt.ext.six.moves import range


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
PROVIDER_NAME = 'linode'


class LinodeTest(integration.ShellCase):
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
                integration.FILES,
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

    def test_instance(self):
        '''
        Test creating an instance on Linode
        '''
        # check if instance with salt installed returned
        try:
            self.assertIn(
                INSTANCE_NAME,
                [i.strip() for i in self.run_cloud('-p linode-test {0}'.format(INSTANCE_NAME))]
            )
        except AssertionError:
            self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME))
            raise

        # delete the instance
        try:
            self.assertIn(
                INSTANCE_NAME + ':',
                [i.strip() for i in self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME))]
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
            self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME))


if __name__ == '__main__':
    from integration import run_tests  # pylint: disable=import-error
    run_tests(LinodeTest)
