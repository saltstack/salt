# -*- coding: utf-8 -*-
'''
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import os

# Import Salt Testing Libs
from tests.integration.cloud.helpers.cloud_test_base import TIMEOUT as CLOUD_TIMEOUT, CloudTest
from tests.support.unit import skipIf

# Import Salt Libs
from salt.config import cloud_providers_config
from salt.utils.versions import LooseVersion

TIMEOUT = 500

try:
    import azure  # pylint: disable=unused-import
    HAS_AZURE = True
except ImportError:
    HAS_AZURE = False

if HAS_AZURE and not hasattr(azure, '__version__'):
    import azure.common

log = logging.getLogger(__name__)

TIMEOUT = CLOUD_TIMEOUT * 2
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


@skipIf(not HAS_AZURE, 'These tests require the Azure Python SDK to be installed.')
@skipIf(not __has_required_azure(), 'The Azure Python SDK must be >= 0.11.1.')
class AzureTest(CloudTest):
    '''
    Integration tests for the Azure cloud provider in Salt-Cloud
    '''
    PROVIDER = 'azurearm'
    REQUIRED_PROVIDER_CONFIG_ITEMS = ('subscription_id',)

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

        self.assertDestroyInstance()
