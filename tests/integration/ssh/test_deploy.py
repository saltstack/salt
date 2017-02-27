# -*- coding: utf-8 -*-
'''
salt-ssh testing
'''
# Import Python libs
from __future__ import absolute_import

# Import salt testing libs
from tests.support.unit import skipIf
import tests.integration as integration


@skipIf(True, 'Not ready for production')
class SSHTest(integration.SSHCase):
    '''
    Test general salt-ssh functionality
    '''
    def test_ping(self):
        '''
        Test a simple ping
        '''
        ret = self.run_function('test.ping')
        self.assertTrue(ret, 'Ping did not return true')
