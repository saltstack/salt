# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt libs
import salt.config
import salt.master

# Import Salt Testing Libs
from tests.support.unit import TestCase
from tests.support.mock import (
    patch,
    MagicMock,
)


class ClearFuncsTestCase(TestCase):
    '''
    TestCase for salt.master.ClearFuncs class
    '''

    def setUp(self):
        opts = salt.config.master_config(None)
        self.clear_funcs = salt.master.ClearFuncs(opts, {})

    # runner tests

    def test_runner_token_not_authenticated(self):
        '''
        Asserts that a TokenAuthenticationError is returned when the token can't authenticate.
        '''
        mock_ret = {u'error': {u'name': u'TokenAuthenticationError',
                               u'message': u'Authentication failure of type "token" occurred.'}}
        ret = self.clear_funcs.runner({u'token': u'asdfasdfasdfasdf'})
        self.assertDictEqual(mock_ret, ret)

    def test_runner_token_authorization_error(self):
        '''
        Asserts that a TokenAuthenticationError is returned when the token authenticates, but is
        not authorized.
        '''
        token = u'asdfasdfasdfasdf'
        clear_load = {u'token': token, u'fun': u'test.arg'}
        mock_token = {u'token': token, u'eauth': u'foo', u'name': u'test'}
        mock_ret = {u'error': {u'name': u'TokenAuthenticationError',
                               u'message': u'Authentication failure of type "token" occurred '
                                           u'for user test.'}}

        with patch('salt.auth.LoadAuth.authenticate_token', MagicMock(return_value=mock_token)), \
             patch('salt.auth.LoadAuth.get_auth_list', MagicMock(return_value=[])):
            ret = self.clear_funcs.runner(clear_load)

        self.assertDictEqual(mock_ret, ret)

    def test_runner_token_salt_invocation_error(self):
        '''
        Asserts that a SaltInvocationError is returned when the token authenticates, but the
        command is malformed.
        '''
        token = u'asdfasdfasdfasdf'
        clear_load = {u'token': token, u'fun': u'badtestarg'}
        mock_token = {u'token': token, u'eauth': u'foo', u'name': u'test'}
        mock_ret = {u'error': {u'name': u'SaltInvocationError',
                               u'message': u'A command invocation error occurred: Check syntax.'}}

        with patch('salt.auth.LoadAuth.authenticate_token', MagicMock(return_value=mock_token)), \
             patch('salt.auth.LoadAuth.get_auth_list', MagicMock(return_value=['testing'])):
            ret = self.clear_funcs.runner(clear_load)

        self.assertDictEqual(mock_ret, ret)

    def test_runner_eauth_not_authenticated(self):
        '''
        Asserts that an EauthAuthenticationError is returned when the user can't authenticate.
        '''
        mock_ret = {u'error': {u'name': u'EauthAuthenticationError',
                               u'message': u'Authentication failure of type "eauth" occurred for '
                                           u'user UNKNOWN.'}}
        ret = self.clear_funcs.runner({u'eauth': u'foo'})
        self.assertDictEqual(mock_ret, ret)

    def test_runner_eauth_authorization_error(self):
        '''
        Asserts that an EauthAuthenticationError is returned when the user authenticates, but is
        not authorized.
        '''
        clear_load = {u'eauth': u'foo', u'username': u'test', u'fun': u'test.arg'}
        mock_ret = {u'error': {u'name': u'EauthAuthenticationError',
                               u'message': u'Authentication failure of type "eauth" occurred for '
                                           u'user test.'}}
        with patch('salt.auth.LoadAuth.authenticate_eauth', MagicMock(return_value=True)), \
             patch('salt.auth.LoadAuth.get_auth_list', MagicMock(return_value=[])):
            ret = self.clear_funcs.runner(clear_load)

        self.assertDictEqual(mock_ret, ret)

    def test_runner_eauth_salt_invocation_error(self):
        '''
        Asserts that an EauthAuthenticationError is returned when the user authenticates, but the
        command is malformed.
        '''
        clear_load = {u'eauth': u'foo', u'username': u'test', u'fun': u'bad.test.arg.func'}
        mock_ret = {u'error': {u'name': u'SaltInvocationError',
                               u'message': u'A command invocation error occurred: Check syntax.'}}
        with patch('salt.auth.LoadAuth.authenticate_eauth', MagicMock(return_value=True)), \
             patch('salt.auth.LoadAuth.get_auth_list', MagicMock(return_value=['testing'])):
            ret = self.clear_funcs.runner(clear_load)

        self.assertDictEqual(mock_ret, ret)

    def test_runner_user_not_authenticated(self):
        '''
        Asserts that an UserAuthenticationError is returned when the user can't authenticate.
        '''
        mock_ret = {u'error': {u'name': u'UserAuthenticationError',
                               u'message': u'Authentication failure of type "user" occurred'}}
        ret = self.clear_funcs.runner({})
        self.assertDictEqual(mock_ret, ret)

    # wheel tests

    def test_wheel_token_not_authenticated(self):
        '''
        Asserts that a TokenAuthenticationError is returned when the token can't authenticate.
        '''
        mock_ret = {u'error': {u'name': u'TokenAuthenticationError',
                               u'message': u'Authentication failure of type "token" occurred.'}}
        ret = self.clear_funcs.wheel({u'token': u'asdfasdfasdfasdf'})
        self.assertDictEqual(mock_ret, ret)

    def test_wheel_token_authorization_error(self):
        '''
        Asserts that a TokenAuthenticationError is returned when the token authenticates, but is
        not authorized.
        '''
        token = u'asdfasdfasdfasdf'
        clear_load = {u'token': token, u'fun': u'test.arg'}
        mock_token = {u'token': token, u'eauth': u'foo', u'name': u'test'}
        mock_ret = {u'error': {u'name': u'TokenAuthenticationError',
                               u'message': u'Authentication failure of type "token" occurred '
                                           u'for user test.'}}

        with patch('salt.auth.LoadAuth.authenticate_token', MagicMock(return_value=mock_token)), \
             patch('salt.auth.LoadAuth.get_auth_list', MagicMock(return_value=[])):
            ret = self.clear_funcs.wheel(clear_load)

        self.assertDictEqual(mock_ret, ret)

    def test_wheel_token_salt_invocation_error(self):
        '''
        Asserts that a SaltInvocationError is returned when the token authenticates, but the
        command is malformed.
        '''
        token = u'asdfasdfasdfasdf'
        clear_load = {u'token': token, u'fun': u'badtestarg'}
        mock_token = {u'token': token, u'eauth': u'foo', u'name': u'test'}
        mock_ret = {u'error': {u'name': u'SaltInvocationError',
                               u'message': u'A command invocation error occurred: Check syntax.'}}

        with patch('salt.auth.LoadAuth.authenticate_token', MagicMock(return_value=mock_token)), \
             patch('salt.auth.LoadAuth.get_auth_list', MagicMock(return_value=['testing'])):
            ret = self.clear_funcs.wheel(clear_load)

        self.assertDictEqual(mock_ret, ret)

    def test_wheel_eauth_not_authenticated(self):
        '''
        Asserts that an EauthAuthenticationError is returned when the user can't authenticate.
        '''
        mock_ret = {u'error': {u'name': u'EauthAuthenticationError',
                               u'message': u'Authentication failure of type "eauth" occurred for '
                                           u'user UNKNOWN.'}}
        ret = self.clear_funcs.wheel({u'eauth': u'foo'})
        self.assertDictEqual(mock_ret, ret)

    def test_wheel_eauth_authorization_error(self):
        '''
        Asserts that an EauthAuthenticationError is returned when the user authenticates, but is
        not authorized.
        '''
        clear_load = {u'eauth': u'foo', u'username': u'test', u'fun': u'test.arg'}
        mock_ret = {u'error': {u'name': u'EauthAuthenticationError',
                               u'message': u'Authentication failure of type "eauth" occurred for '
                                           u'user test.'}}
        with patch('salt.auth.LoadAuth.authenticate_eauth', MagicMock(return_value=True)), \
             patch('salt.auth.LoadAuth.get_auth_list', MagicMock(return_value=[])):
            ret = self.clear_funcs.wheel(clear_load)

        self.assertDictEqual(mock_ret, ret)

    def test_wheel_eauth_salt_invocation_error(self):
        '''
        Asserts that an EauthAuthenticationError is returned when the user authenticates, but the
        command is malformed.
        '''
        clear_load = {u'eauth': u'foo', u'username': u'test', u'fun': u'bad.test.arg.func'}
        mock_ret = {u'error': {u'name': u'SaltInvocationError',
                               u'message': u'A command invocation error occurred: Check syntax.'}}
        with patch('salt.auth.LoadAuth.authenticate_eauth', MagicMock(return_value=True)), \
             patch('salt.auth.LoadAuth.get_auth_list', MagicMock(return_value=['testing'])):
            ret = self.clear_funcs.wheel(clear_load)

        self.assertDictEqual(mock_ret, ret)

    def test_wheel_user_not_authenticated(self):
        '''
        Asserts that an UserAuthenticationError is returned when the user can't authenticate.
        '''
        mock_ret = {u'error': {u'name': u'UserAuthenticationError',
                               u'message': u'Authentication failure of type "user" occurred'}}
        ret = self.clear_funcs.wheel({})
        self.assertDictEqual(mock_ret, ret)

    # publish tests

    def test_publish_user_is_blacklisted(self):
        '''
        Asserts that an empty string is returned when the user has been blacklisted.
        '''
        with patch('salt.acl.PublisherACL.user_is_blacklisted', MagicMock(return_value=True)):
            self.assertEqual(u'', self.clear_funcs.publish({u'user': u'foo', u'fun': u'test.arg'}))

    def test_publish_cmd_blacklisted(self):
        '''
        Asserts that an empty string returned when the command has been blacklisted.
        '''
        with patch('salt.acl.PublisherACL.user_is_blacklisted', MagicMock(return_value=False)), \
                patch('salt.acl.PublisherACL.cmd_is_blacklisted', MagicMock(return_value=True)):
            self.assertEqual(u'', self.clear_funcs.publish({u'user': u'foo', u'fun': u'test.arg'}))

    def test_publish_token_not_authenticated(self):
        '''
        Asserts that an empty string is returned when the token can't authenticate.
        '''
        load = {u'user': u'foo', u'fun': u'test.arg', u'tgt': u'test_minion',
                u'kwargs': {u'token': u'asdfasdfasdfasdf'}}
        with patch('salt.acl.PublisherACL.user_is_blacklisted', MagicMock(return_value=False)), \
                patch('salt.acl.PublisherACL.cmd_is_blacklisted', MagicMock(return_value=False)):
            self.assertEqual(u'', self.clear_funcs.publish(load))

    def test_publish_token_authorization_error(self):
        '''
        Asserts that an empty string is returned when the token authenticates, but is not
        authorized.
        '''
        token = u'asdfasdfasdfasdf'
        load = {u'user': u'foo', u'fun': u'test.arg', u'tgt': u'test_minion',
                u'arg': u'bar', u'kwargs': {u'token': token}}
        mock_token = {u'token': token, u'eauth': u'foo', u'name': u'test'}

        with patch('salt.acl.PublisherACL.user_is_blacklisted', MagicMock(return_value=False)), \
                patch('salt.acl.PublisherACL.cmd_is_blacklisted', MagicMock(return_value=False)), \
                patch('salt.auth.LoadAuth.authenticate_token', MagicMock(return_value=mock_token)), \
                patch('salt.auth.LoadAuth.get_auth_list', MagicMock(return_value=[])):
            self.assertEqual(u'', self.clear_funcs.publish(load))

    def test_publish_eauth_not_authenticated(self):
        '''
        Asserts that an empty string is returned when the user can't authenticate.
        '''
        load = {u'user': u'test', u'fun': u'test.arg', u'tgt': u'test_minion',
                u'kwargs': {u'eauth': u'foo'}}
        with patch('salt.acl.PublisherACL.user_is_blacklisted', MagicMock(return_value=False)), \
                patch('salt.acl.PublisherACL.cmd_is_blacklisted', MagicMock(return_value=False)):
            self.assertEqual(u'', self.clear_funcs.publish(load))

    def test_publish_eauth_authorization_error(self):
        '''
        Asserts that an empty string is returned when the user authenticates, but is not
        authorized.
        '''
        load = {u'user': u'test', u'fun': u'test.arg', u'tgt': u'test_minion',
                u'kwargs': {u'eauth': u'foo'}, u'arg': u'bar'}
        with patch('salt.acl.PublisherACL.user_is_blacklisted', MagicMock(return_value=False)), \
                patch('salt.acl.PublisherACL.cmd_is_blacklisted', MagicMock(return_value=False)), \
                patch('salt.auth.LoadAuth.authenticate_eauth', MagicMock(return_value=True)), \
                patch('salt.auth.LoadAuth.get_auth_list', MagicMock(return_value=[])):
            self.assertEqual(u'', self.clear_funcs.publish(load))

    def test_publish_user_not_authenticated(self):
        '''
        Asserts that an empty string is returned when the user can't authenticate.
        '''
        load = {u'user': u'test', u'fun': u'test.arg', u'tgt': u'test_minion'}
        with patch('salt.acl.PublisherACL.user_is_blacklisted', MagicMock(return_value=False)), \
                patch('salt.acl.PublisherACL.cmd_is_blacklisted', MagicMock(return_value=False)):
            self.assertEqual(u'', self.clear_funcs.publish(load))

    def test_publish_user_authenticated_missing_auth_list(self):
        '''
        Asserts that an empty string is returned when the user has an effective user id and is
        authenticated, but the auth_list is empty.
        '''
        load = {u'user': u'test', u'fun': u'test.arg', u'tgt': u'test_minion',
                u'kwargs': {u'user': u'test'}, u'arg': u'foo'}
        with patch('salt.acl.PublisherACL.user_is_blacklisted', MagicMock(return_value=False)), \
                patch('salt.acl.PublisherACL.cmd_is_blacklisted', MagicMock(return_value=False)), \
                patch('salt.auth.LoadAuth.authenticate_key', MagicMock(return_value='fake-user-key')), \
                patch('salt.utils.master.get_values_of_matching_keys', MagicMock(return_value=[])):
            self.assertEqual(u'', self.clear_funcs.publish(load))

    def test_publish_user_authorization_error(self):
        '''
        Asserts that an empty string is returned when the user authenticates, but is not
        authorized.
        '''
        load = {u'user': u'test', u'fun': u'test.arg', u'tgt': u'test_minion',
                u'kwargs': {u'user': u'test'}, u'arg': u'foo'}
        with patch('salt.acl.PublisherACL.user_is_blacklisted', MagicMock(return_value=False)), \
                patch('salt.acl.PublisherACL.cmd_is_blacklisted', MagicMock(return_value=False)), \
                patch('salt.auth.LoadAuth.authenticate_key', MagicMock(return_value='fake-user-key')), \
                patch('salt.utils.master.get_values_of_matching_keys', MagicMock(return_value=['test'])), \
                patch('salt.utils.minions.CkMinions.auth_check', MagicMock(return_value=False)):
            self.assertEqual(u'', self.clear_funcs.publish(load))
