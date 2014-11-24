# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''

# Import Python Libs
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

# Import Third-Party Libs
try:
    import azure  # pylint: disable=W0611
    HAS_AZURE = True
except ImportError:
    HAS_AZURE = False


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


@skipIf(HAS_AZURE is False, 'These tests require azure to be installed.')
class AzureTest(integration.ShellCase):
    '''
    Integration tests for the Azure cloud provider in Salt-Cloud
    '''

    @expensiveTest
    def setUp(self):
        '''
        Sets up the test requirements
        '''
        super(AzureTest, self).setUp()

        # check if appropriate cloud provider and profile files are present
        profile_str = 'azure-config:'
        provider = 'azure'
        providers = self.run_cloud('--list-providers')
        if profile_str not in providers:
            self.skipTest(
                'Configuration file for {0} was not found. Check {0}.conf files '
                'in tests/integration/files/conf/cloud.*.d/ to run these tests.'
                .format(provider)
            )

        # check if subscription_id and certificate_path are present in provider file
        provider_path = os.path.join(integration.FILES,
                            'conf',
                            'cloud.providers.d',
                            provider + '.conf')
        provider_config = cloud_providers_config(provider_path)
        sub_id = provider_config['azure-config']['azure']['subscription_id']
        cert_path = provider_config['azure-config']['azure']['certificate_path']
        if sub_id == '' or cert_path == '':
            self.skipTest(
                'A subscription_id and certificate_path must be provided to run '
                'these tests. Check '
                'tests/integration/files/conf/cloud.providers.d/{0}.conf'.format(
                    provider
                )
            )

        # check if ssh_username, ssh_password, and media_link are present
        # in the azure configuration file
        profile_path = os.path.join(integration.FILES,
                            'conf',
                            'cloud.profiles.d',
                            provider + '.conf')
        profile_config = cloud_providers_config(profile_path)
        ssh_user = profile_config['azure-test']['azure-config']['ssh_username']
        ssh_pass = profile_config['azure-test']['azure-config']['ssh_password']
        media_link = profile_config['azure-test']['azure-config']['media_link']

        if ssh_user == '' or ssh_pass == '' or media_link == '':
            self.skipTest(
                'An ssh_username, ssh_password, and media_link must be provided to run '
                'these tests. One or more of these elements is missing. Check '
                'tests/integration/files/conf/cloud.profiles.d/{0}.conf'.format(
                    provider
                )
            )

    def test_instance(self):
        '''
        Test creating an instance on Azure
        '''
        # create the instance
        instance = self.run_cloud('-p azure-test {0}'.format(INSTANCE_NAME))
        ret_str = '        {0}'.format(INSTANCE_NAME)

        # check if instance installed salt and returned correctly
        try:
            self.assertIn(ret_str, instance)
        except AssertionError:
            self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME))
            raise

        # delete the instance
        delete = self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME))
        not_deleted = 'No machines were found to be destroyed'
        try:
            self.assertNotEqual(not_deleted, delete)
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
    from integration import run_tests
    run_tests(AzureTest)
