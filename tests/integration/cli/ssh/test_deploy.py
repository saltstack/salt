# -*- coding: utf-8 -*-
'''
salt-ssh testing
'''
# Import Python libs
from __future__ import absolute_import


class TestSSH(object):
    '''
    Test general salt-ssh functionality
    '''
    def test_ping(self, session_salt_ssh):
        '''
        Test a simple ping
        '''
        cmd = session_salt_ssh.run_sync('test.ping')
        assert cmd.json is True, 'Ping did not return true'
