# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import

# Import Salt Libs
from salt import acl

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
)
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ClientACLTestCase(TestCase):
    '''
    Unit tests for salt.acl.ClientACL
    '''
    def setUp(self):
        self.blacklist = {
            'users': ['joker', 'penguin'],
            'modules': ['cmd.run', 'test.fib'],
        }

    def test_user_is_blacklisted(self):
        '''
        test user_is_blacklisted
        '''
        client_acl = acl.PublisherACL(self.blacklist)

        self.assertTrue(client_acl.user_is_blacklisted('joker'))
        self.assertTrue(client_acl.user_is_blacklisted('penguin'))

        self.assertFalse(client_acl.user_is_blacklisted('batman'))
        self.assertFalse(client_acl.user_is_blacklisted('robin'))

    def test_cmd_is_blacklisted(self):
        '''
        test cmd_is_blacklisted
        '''
        client_acl = acl.PublisherACL(self.blacklist)

        self.assertTrue(client_acl.cmd_is_blacklisted('cmd.run'))
        self.assertTrue(client_acl.cmd_is_blacklisted('test.fib'))

        self.assertFalse(client_acl.cmd_is_blacklisted('cmd.shell'))
        self.assertFalse(client_acl.cmd_is_blacklisted('test.versions'))

        self.assertTrue(client_acl.cmd_is_blacklisted(['cmd.run', 'state.sls']))
        self.assertFalse(client_acl.cmd_is_blacklisted(['state.highstate', 'state.sls']))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ClientACLTestCase, needs_daemon=False)
