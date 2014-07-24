# -*- coding: utf-8 -*-
'''
salt-ssh testing
'''
import integration
from salttesting import skipIf


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
