# -*- coding: utf-8 -*-

# import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
ensure_in_syspath('../../')
from salt.modules import ssh
from salt.exceptions import CommandExecutionError


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SSHAuthKeyTestCase(TestCase):
    '''
    TestCase for salt.modules.ssh
    '''
    def test_expand_user_token(self):
        '''
        Test if the %u, %h, and %% tokens are correctly expanded
        '''
        output = ssh._expand_authorized_keys_path('/home/%u', 'user',
                '/home/user')
        self.assertEqual(output, '/home/user')

        output = ssh._expand_authorized_keys_path('/home/%h', 'user',
                '/home/user')
        self.assertEqual(output, '/home//home/user')

        output = ssh._expand_authorized_keys_path('%h/foo', 'user',
                '/home/user')
        self.assertEqual(output, '/home/user/foo')

        output = ssh._expand_authorized_keys_path('/srv/%h/aaa/%u%%', 'user',
                '/home/user')
        self.assertEqual(output, '/srv//home/user/aaa/user%')

        user = 'dude'
        home = '/home/dude'
        path = '/home/dude%'
        self.assertRaises(CommandExecutionError, ssh._expand_authorized_keys_path, path, user, home)

        path = '/home/%dude'
        self.assertRaises(CommandExecutionError, ssh._expand_authorized_keys_path, path, user, home)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(SSHAuthKeyTestCase, needs_daemon=False)
