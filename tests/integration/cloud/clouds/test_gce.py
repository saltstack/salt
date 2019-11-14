# -*- coding: utf-8 -*-
'''
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
    :codeauthor: Tomas Sirny <tsirny@gmail.com>
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.integration.cloud.helpers.cloud_test_base import CloudTest

TIMEOUT = 800


class GCETest(CloudTest):
    '''
    Integration tests for the GCE cloud provider in Salt-Cloud
    '''
    PROVIDER = 'gce'
    REQUIRED_PROVIDER_CONFIG_ITEMS = ('project', 'service_account_email_address', 'service_account_private_key')
    EXTRA_PROFILE = 'gce-test-extra'

    def test_instance(self):
        '''
        Tests creating and deleting an instance on GCE
        '''
        self.assertCreateInstance(timeout=TIMEOUT)
        self.assertDestroyInstance()

    def test_instance_extra(self):
        '''
        Tests creating and deleting an instance on GCE
        '''
        self.assertCreateInstance(profile=self.EXTRA_PROFILE, timeout=TIMEOUT)
        self.assertDestroyInstance()
