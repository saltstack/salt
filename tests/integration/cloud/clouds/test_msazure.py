# -*- coding: utf-8 -*-
'''
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

# Import Salt Testing Libs
from tests.integration.cloud.helpers.cloud_test_base import TIMEOUT, CloudTest
from tests.support.unit import skipIf

# Import Salt Libs
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
    PROVIDER = 'azure'
    REQUIRED_PROVIDER_CONFIG_ITEMS = ('subscription_id', 'certificate_path', 'ssh_username', 'ssh_password', 'media_link')

    def test_instance(self):
        '''
        Test creating an instance on Azure
        '''
        # check if instance with salt installed returned
        ret_val = self.run_cloud('-p azure-test {0}'.format(self.instance_name), timeout=TIMEOUT)
        self.assertInstanceExists(ret_val)

        self.assertDestroyInstance()
