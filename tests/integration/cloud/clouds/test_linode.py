# -*- coding: utf-8 -*-
'''
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals



@skipIf(WAR_ROOM_SKIP, 'WAR ROOM TEMPORARY SKIP')
@expensiveTest
class LinodeTest(ShellCase):
    '''
    Integration tests for the Linode cloud provider in Salt-Cloud
    '''

    PROVIDER = 'linode'
    REQUIRED_CONFIG_ITEMS = ('apikey', 'password')

    def test_instance(self):
        '''
        Clean up after tests
        '''
        query = self.run_cloud('--query')
        ret_str = '        {0}:'.format(INSTANCE_NAME)

        self.assertDestroyInstance()
