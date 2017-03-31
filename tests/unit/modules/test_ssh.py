# -*- coding: utf-8 -*-

# import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.modules.ssh as ssh
from salt.exceptions import CommandExecutionError


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SSHAuthKeyTestCase(TestCase, LoaderModuleMockMixin):
    '''
    TestCase for salt.modules.ssh
    '''
    def setup_loader_modules(self):
        return {
            ssh: {
                '__salt__': {
                    'user.info': lambda u: getattr(self, 'user_info_mock', None),
                }
            }
        }

    def tearDown(self):
        try:
            delattr(self, 'user_info_mock')
        except AttributeError:
            pass

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

    def test_set_auth_key_invalid(self):
        self.user_info_mock = {'home': '/dev/null'}
        # Inserting invalid public key should be rejected
        invalid_key = 'AAAAB3NzaC1kc3MAAACBAL0sQ9fJ5bYTEyY'  # missing padding
        self.assertEqual(ssh.set_auth_key('user', invalid_key), 'Invalid public key')
