# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import

# Import Salt Libs
from salt import acl

# Import Salt Testing Libs
from tests.support.unit import TestCase


class ClientACLTestCase(TestCase):
    '''
    Unit tests for salt.acl.ClientACL
    '''
    def setUp(self):
        self.blacklist = {
            'users': ['joker', 'penguin', '*bad_*', 'blocked_.*', '^Homer$'],
            'modules': ['cmd.run', 'test.fib', 'rm-rf.*'],
        }

    def test_user_is_blacklisted(self):
        '''
        test user_is_blacklisted
        '''
        client_acl = acl.PublisherACL(self.blacklist)

        self.assertTrue(client_acl.user_is_blacklisted('joker'))
        self.assertTrue(client_acl.user_is_blacklisted('penguin'))
        self.assertTrue(client_acl.user_is_blacklisted('bad_'))
        self.assertTrue(client_acl.user_is_blacklisted('bad_user'))
        self.assertTrue(client_acl.user_is_blacklisted('bad_*'))
        self.assertTrue(client_acl.user_is_blacklisted('user_bad_'))
        self.assertTrue(client_acl.user_is_blacklisted('blocked_'))
        self.assertTrue(client_acl.user_is_blacklisted('blocked_user'))
        self.assertTrue(client_acl.user_is_blacklisted('blocked_.*'))
        self.assertTrue(client_acl.user_is_blacklisted('Homer'))

        self.assertFalse(client_acl.user_is_blacklisted('batman'))
        self.assertFalse(client_acl.user_is_blacklisted('robin'))
        self.assertFalse(client_acl.user_is_blacklisted('bad'))
        self.assertFalse(client_acl.user_is_blacklisted('blocked'))
        self.assertFalse(client_acl.user_is_blacklisted('NotHomer'))
        self.assertFalse(client_acl.user_is_blacklisted('HomerSimpson'))

    def test_cmd_is_blacklisted(self):
        '''
        test cmd_is_blacklisted
        '''
        client_acl = acl.PublisherACL(self.blacklist)

        self.assertTrue(client_acl.cmd_is_blacklisted('cmd.run'))
        self.assertTrue(client_acl.cmd_is_blacklisted('test.fib'))
        self.assertTrue(client_acl.cmd_is_blacklisted('rm-rf.root'))

        self.assertFalse(client_acl.cmd_is_blacklisted('cmd.shell'))
        self.assertFalse(client_acl.cmd_is_blacklisted('test.versions'))
        self.assertFalse(client_acl.cmd_is_blacklisted('arm-rf.root'))

        self.assertTrue(client_acl.cmd_is_blacklisted(['cmd.run', 'state.sls']))
        self.assertFalse(client_acl.cmd_is_blacklisted(['state.highstate', 'state.sls']))
