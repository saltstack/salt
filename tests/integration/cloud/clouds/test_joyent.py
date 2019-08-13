# -*- coding: utf-8 -*-
'''
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.unit import skipIf

# Create the cloud instance name to be used throughout the tests
from tests.integration.cloud.helpers.cloud_test_base import CloudTest, TIMEOUT

PROVIDER_NAME = 'joyent'


@skipIf(True, 'Joyent is EOL as of November 9th, 2019.  It will no longer be supported in salt-cloud')
class JoyentTest(CloudTest):
    '''
    Integration tests for the Joyent cloud provider in Salt-Cloud
    '''
    PROVIDER = 'joyent'
    REQUIRED_PROVIDER_CONFIG_ITEMS = ('user', 'password', 'private_key', 'keyname')

    def test_instance(self):
        '''
        Test creating and deleting instance on Joyent
        '''
        ret_str = self.run_cloud('-p joyent-test {0}'.format(self.instance_name), timeout=TIMEOUT)
        self.assertInstanceExists(ret_str)

        self._destroy_instance()
