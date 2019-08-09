# -*- coding: utf-8 -*-
'''
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import logging

# Import Salt Testing Libs
from tests.integration.cloud.helpers.cloud_test_base import TIMEOUT, CloudTest
from tests.support.paths import FILES
from tests.support.unit import skipIf
from tests.support.helpers import expensiveTest

# Import Salt Libs
from salt.config import cloud_providers_config
from salt.utils.versions import LooseVersion
from salt.ext.six.moves import range

TIMEOUT = 1000

try:
    import azure  # pylint: disable=unused-import

    HAS_AZURE = True
except ImportError:
    HAS_AZURE = False

if HAS_AZURE and not hasattr(azure, '__version__'):
    import azure.common

# Create the cloud instance name to be used throughout the tests
INSTANCE_NAME = generate_random_name('CLOUD-TEST-')
PROVIDER_NAME = 'azurearm'
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

        if LooseVersion(REQUIRED_AZURE) <= version:
            return True
    return False


@skipIf(True, 'MSAzure will be deprecated in favor of azurearm')
@skipIf(HAS_AZURE is False, 'These tests require the Azure Python SDK to be installed.')
@skipIf(__has_required_azure() is False, 'The Azure Python SDK must be >= 0.11.1.')
class AzureTest(CloudTest):
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
        if sub_id == '':
            self.skipTest(
                'A subscription_id and certificate_path must be provided to run '
                'these tests. Check '
                'tests/integration/files/conf/cloud.providers.d/{0}.conf'.format(
                    PROVIDER_NAME
                )
            )

    def test_instance(self):
        '''
        Test creating an instance on Azure
        '''
        # check if instance with salt installed returned
        ret_val = self.run_cloud('-p {0} {1}'.format(PROFILE_NAME, self.instance_name), timeout=TIMEOUT)
        self.assertInstanceExists(ret_val)

        self._destroy_instance()
