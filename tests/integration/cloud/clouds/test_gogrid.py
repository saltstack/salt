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


@skipIf(True, 'waiting on bug report fixes from #13365')
@expensiveTest
class GoGridTest(ShellCase):
    '''
    Integration tests for the GoGrid cloud provider in Salt-Cloud
    '''
    PROVIDER = 'gogrid'
    REQUIRED_CONFIG_ITEMS = ('apikey', 'sharedsecret')

    def test_instance(self):
        '''
        Clean up after tests
        '''
        query = self.run_cloud('--query')
        ret_str = '        {0}:'.format(INSTANCE_NAME)

        self.assertDestroyInstance()
