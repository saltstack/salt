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
from tests.support.case import ShellCase
from tests.support.paths import FILES
from tests.support.unit import skipIf
from tests.support.helpers import expensiveTest

# Import Salt Libs
from salt.config import cloud_providers_config
from salt.utils.versions import LooseVersion

# Import Third-Party Libs
from salt.ext.six.moves import range

TIMEOUT = 500

try:
    import azure  # pylint: disable=unused-import
    HAS_AZURE = True
except ImportError:
    HAS_AZURE = False

if HAS_AZURE and not hasattr(azure, '__version__'):
    import azure.common


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
PROVIDER_NAME = 'azure'
PROFILE_NAME = 'azure-test'
REQUIRED_AZURE = '0.11.1'


def __has_required_azure():
    '''
    Returns True/False if the required version of the Azure SDK is installed.
    '''
    if HAS_AZURE:
        if hasattr(azure, '__version__'):
            version = LooseVersion(azure.__version__)
        else:
            version = LooseVersion(azure.common.__version__)

        if REQUIRED_AZURE <= version:
            return True
    return False


@skipIf(HAS_AZURE is False, 'These tests require the Azure Python SDK to be installed.')
@skipIf(__has_required_azure() is False, 'The Azure Python SDK must be >= 0.11.1.')
class AzureTest(ShellCase):
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
        provider_str = 'azure-config'
        providers = self.run_cloud('--list-providers')
        if provider_str + ':' not in providers:
            self.skipTest(
                'Configuration file for {0} was not found. Check {0}.conf files '
                'in tests/integration/files/conf/cloud.*.d/ to run these tests.'
                .format(PROVIDER_NAME)
            )

        # check if subscription_id and certificate_path are present in provider file
        provider_config = cloud_providers_config(
            os.path.join(
                FILES,
                'conf',
                'cloud.providers.d',
                PROVIDER_NAME + '.conf'
            )
        )
        sub_id = provider_config[provider_str][PROVIDER_NAME]['subscription_id']
        cert_path = provider_config[provider_str][PROVIDER_NAME]['certificate_path']
        if sub_id == '' or cert_path == '':
            self.skipTest(
                'A subscription_id and certificate_path must be provided to run '
                'these tests. Check '
                'tests/integration/files/conf/cloud.providers.d/{0}.conf'.format(
                    PROVIDER_NAME
                )
            )

        # check if ssh_username, ssh_password, and media_link are present
        # in the azure configuration file
        ssh_user = provider_config[provider_str][PROVIDER_NAME]['ssh_username']
        ssh_pass = provider_config[provider_str][PROVIDER_NAME]['ssh_password']
        media_link = provider_config[provider_str][PROVIDER_NAME]['media_link']

        if ssh_user == '' or ssh_pass == '' or media_link == '':
            self.skipTest(
                'An ssh_username, ssh_password, and media_link must be provided to run '
                'these tests. One or more of these elements is missing. Check '
                'tests/integration/files/conf/cloud.profiles.d/{0}.conf'.format(
                    PROVIDER_NAME
                )
            )

    def test_instance(self):
        '''
        Test creating an instance on Azure
        '''
        # check if instance with salt installed returned
        try:
            self.assertIn(
                INSTANCE_NAME,
                [i.strip() for i in self.run_cloud(
                    '-p {0} {1}'.format(
                        PROFILE_NAME,
                        INSTANCE_NAME
                    ), timeout=TIMEOUT
                )]
            )
        except AssertionError:
            self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME),
                           timeout=TIMEOUT)
            raise

        # delete the instance
        try:
            self.assertIn(
                INSTANCE_NAME + ':',
                [i.strip() for i in self.run_cloud(
                    '-d {0} --assume-yes'.format(
                        INSTANCE_NAME
                    ), timeout=TIMEOUT
                )]
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
            self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME),
                           timeout=TIMEOUT)
