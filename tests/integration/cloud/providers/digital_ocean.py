# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''

# Import Python Libs
import os
import random
import string

# Import Salt Testing Libs
from salttesting.helpers import ensure_in_syspath, expensiveTest

ensure_in_syspath('../../../')

# Import Salt Libs
import integration
from salt.config import cloud_providers_config


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
PROVIDER_NAME = 'digital_ocean'


class DigitalOceanTest(integration.ShellCase):
    '''
    Integration tests for the DigitalOcean cloud provider in Salt-Cloud
    '''

    @expensiveTest
    def setUp(self):
        '''
        Sets up the test requirements
        '''
        super(DigitalOceanTest, self).setUp()

        # check if appropriate cloud provider and profile files are present
        profile_str = 'digitalocean-config'
        providers = self.run_cloud('--list-providers')
        if profile_str + ':' not in providers:
            self.skipTest(
                'Configuration file for {0} was not found. Check {0}.conf files '
                'in tests/integration/files/conf/cloud.*.d/ to run these tests.'
                .format(PROVIDER_NAME)
            )

        # check if client_key and api_key are present
        path = os.path.join(integration.FILES,
                            'conf',
                            'cloud.providers.d',
                            PROVIDER_NAME + '.conf')
        config = cloud_providers_config(path)

        api = config[profile_str][PROVIDER_NAME]['api_key']
        client = config[profile_str][PROVIDER_NAME]['client_key']
        ssh_file = config[profile_str][PROVIDER_NAME]['ssh_key_file']
        ssh_name = config[profile_str][PROVIDER_NAME]['ssh_key_name']

        if api == '' or client == '' or ssh_file == '' or ssh_name == '':
            self.skipTest(
                'A client key, an api key, an ssh key file, and an ssh key name '
                'must be provided to run these tests. Check '
                'tests/integration/files/conf/cloud.providers.d/{0}.conf'
                .format(PROVIDER_NAME)
            )

    def test_list_images(self):
        '''
        Tests the return of running the --list-images command for digital ocean
        '''
        image_name = '14.10 x64'
        ret_str = '                {0}'.format(image_name)
        list_images = self.run_cloud('--list-images {0}'.format(PROVIDER_NAME))
        self.assertIn(ret_str, list_images)

    def test_list_locations(self):
        '''
        Tests the return of running the --list-locations command for digital ocean
        '''
        location_name = 'San Francisco 1'
        ret_str = '                {0}'.format(location_name)
        list_locations = self.run_cloud('--list-locations {0}'.format(PROVIDER_NAME))
        self.assertIn(ret_str, list_locations)

    def test_list_sizes(self):
        '''
        Tests the return of running the --list-sizes command for digital ocean
        '''
        size_name = '16GB'
        ret_str = '                {0}'.format(size_name)
        list_sizes = self.run_cloud('--list-sizes {0}'.format(PROVIDER_NAME))
        self.assertIn(ret_str, list_sizes)

    def test_instance(self):
        '''
        Test creating an instance on DigitalOcean
        '''

        # create the instance
        instance = self.run_cloud('-p digitalocean-test {0}'.format(INSTANCE_NAME))
        ret_str = '        {0}'.format(INSTANCE_NAME)

        # check if instance with salt installed returned
        try:
            self.assertIn(ret_str, instance)
        except AssertionError:
            self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME))
            raise

        # delete the instance
        delete = self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME))
        ret_str = '                OK'
        try:
            self.assertIn(ret_str, delete)
        except AssertionError:
            raise

        # Final clean-up of created instance, in case something went wrong.
        # This was originally in a tearDown function, but that didn't make sense
        # To run this for each test when not all tests create instances.
        query = self.run_cloud('--query')
        ret_str = '        {0}:'.format(INSTANCE_NAME)

        # if test instance is still present, delete it
        if ret_str in query:
            self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(DigitalOceanTest)
