# -*- coding: utf-8 -*-

# import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath

# Import Salt Libs
ensure_in_syspath('../../')
from salt.modules import ssh


class SSHAuthKeyPathTestCase(TestCase):
    '''
    TestCase for salt.modules.ssh module's ssh AuthorizedKeysFile path
    expansion
    '''
    def test_expand_user_token(self):
        '''
        Test if the %u token is correctly expanded
        '''
        output = ssh._expand_authorized_keys_path('/home/%u', 'user',
                '/home/user')
        self.assertEqual(output, '/home/user')

        output = ssh._expand_authorized_keys_path('/home/%h', 'user',
                '/home/user')
        self.assertEqual(output, '/home//home/user')

        output = ssh._expand_authorized_keys_path('/srv/%h/aaa/%u%%', 'user', 
                '/home/user')
        self.assertEqual(output, '/srv//home/user/aaa/user%')
