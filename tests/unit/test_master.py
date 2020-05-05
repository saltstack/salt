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


class TransportMethodsTest(TestCase):

    def test_transport_methods(self):

        class Foo(salt.master.TransportMethods):
            expose_methods = ['bar']

            def bar(self):
                pass

            def bang(self):
                pass

        foo = Foo()
        assert foo.get_method('bar') is not None
        assert foo.get_method('bang') is None

    def test_aes_funcs_white(self):
        '''
        Validate methods exposed on AESFuncs exist and are callable
        '''
        opts = salt.config.master_config(None)
        aes_funcs = salt.master.AESFuncs(opts)
        for name in aes_funcs.expose_methods:
            func = getattr(aes_funcs, name, None)
            assert callable(func)

    def test_aes_funcs_black(self):
        '''
        Validate methods on AESFuncs that should not be called remotely
        '''
        opts = salt.config.master_config(None)
        aes_funcs = salt.master.AESFuncs(opts)
        # Any callable that should not explicitly be allowed should be added
        # here.
        blacklist_methods = [
            '_AESFuncs__setup_fileserver',
            '_AESFuncs__verify_load',
            '_AESFuncs__verify_minion',
            '_AESFuncs__verify_minion_publish',
            '__class__',
            '__delattr__',
            '__dir__',
            '__eq__',
            '__format__',
            '__ge__',
            '__getattribute__',
            '__gt__',
            '__hash__',
            '__init__',
            '__init_subclass__',
            '__le__',
            '__lt__',
            '__ne__',
            '__new__',
            '__reduce__',
            '__reduce_ex__',
            '__repr__',
            '__setattr__',
            '__sizeof__',
            '__str__',
            '__subclasshook__',
            'get_method',
            'run_func',

        ]
        for name in dir(aes_funcs):
            if name in aes_funcs.expose_methods:
                continue
            if not callable(getattr(aes_funcs, name)):
                continue
            assert name in blacklist_methods, name

    def test_clear_funcs_white(self):
        '''
        Validate methods exposed on ClearFuncs exist and are callable
        '''
        opts = salt.config.master_config(None)
        clear_funcs = salt.master.ClearFuncs(opts, {})
        for name in clear_funcs.expose_methods:
            func = getattr(clear_funcs, name, None)
            assert callable(func)

    def test_clear_funcs_black(self):
        '''
        Validate methods on ClearFuncs that should not be called remotely
        '''
        opts = salt.config.master_config(None)
        clear_funcs = salt.master.ClearFuncs(opts, {})
        blacklist_methods = [
            '__class__',
            '__delattr__',
            '__dir__',
            '__eq__',
            '__format__',
            '__ge__',
            '__getattribute__',
            '__gt__',
            '__hash__',
            '__init__',
            '__init_subclass__',
            '__le__',
            '__lt__',
            '__ne__',
            '__new__',
            '__reduce__',
            '__reduce_ex__',
            '__repr__',
            '__setattr__',
            '__sizeof__',
            '__str__',
            '__subclasshook__',
            '_prep_auth_info',
            '_prep_jid',
            '_prep_pub',
            '_send_pub',
            '_send_ssh_pub',
            'get_method',
        ]
        for name in dir(clear_funcs):
            if name in clear_funcs.expose_methods:
                continue
            if not callable(getattr(clear_funcs, name)):
                continue
            assert name in blacklist_methods, name


class ClearFuncsTestCase(TestCase):
    '''
    TestCase for salt.master.ClearFuncs class
    '''

    def setUp(self):
        opts = salt.config.master_config(None)
        self.clear_funcs = salt.master.ClearFuncs(opts, {})

    def tearDown(self):
        del self.clear_funcs

    def test_get_method(self):
        assert getattr(self.clear_funcs, '_send_pub', None) is not None
        assert self.clear_funcs.get_method('_send_pub') is None

    # runner tests

    def test_runner_token_not_authenticated(self):
        '''
        Asserts that a TokenAuthenticationError is returned when the token can't authenticate.
        '''
        mock_ret = {'error': {'name': 'TokenAuthenticationError',
                              'message': 'Authentication failure of type "token" occurred.'}}
        ret = self.clear_funcs.runner({'token': 'asdfasdfasdfasdf'})
        self.assertDictEqual(mock_ret, ret)

    def test_runner_token_authorization_error(self):
        '''
        Asserts that a TokenAuthenticationError is returned when the token authenticates, but is
        not authorized.
        '''
        token = 'asdfasdfasdfasdf'
        clear_load = {'token': token, 'fun': 'test.arg'}
        mock_token = {'token': token, 'eauth': 'foo', 'name': 'test'}
        mock_ret = {'error': {'name': 'TokenAuthenticationError',
                               'message': 'Authentication failure of type "token" occurred '
                                          'for user test.'}}

        with patch('salt.auth.LoadAuth.authenticate_token', MagicMock(return_value=mock_token)), \
             patch('salt.auth.LoadAuth.get_auth_list', MagicMock(return_value=[])):
            ret = self.clear_funcs.runner(clear_load)

        self.assertDictEqual(mock_ret, ret)

    def test_runner_token_salt_invocation_error(self):
        '''
        Asserts that a SaltInvocationError is returned when the token authenticates, but the
        command is malformed.
        '''
        token = 'asdfasdfasdfasdf'
        clear_load = {'token': token, 'fun': 'badtestarg'}
        mock_token = {'token': token, 'eauth': 'foo', 'name': 'test'}
        mock_ret = {'error': {'name': 'SaltInvocationError',
                              'message': 'A command invocation error occurred: Check syntax.'}}

        with patch('salt.auth.LoadAuth.authenticate_token', MagicMock(return_value=mock_token)), \
             patch('salt.auth.LoadAuth.get_auth_list', MagicMock(return_value=['testing'])):
            ret = self.clear_funcs.runner(clear_load)

        self.assertDictEqual(mock_ret, ret)

    def test_runner_eauth_not_authenticated(self):
        '''
        Asserts that an EauthAuthenticationError is returned when the user can't authenticate.
        '''
        mock_ret = {'error': {'name': 'EauthAuthenticationError',
                              'message': 'Authentication failure of type "eauth" occurred for '
                                         'user UNKNOWN.'}}
        ret = self.clear_funcs.runner({'eauth': 'foo'})
        self.assertDictEqual(mock_ret, ret)

    def test_runner_eauth_authorization_error(self):
        '''
        Asserts that an EauthAuthenticationError is returned when the user authenticates, but is
        not authorized.
        '''
        clear_load = {'eauth': 'foo', 'username': 'test', 'fun': 'test.arg'}
        mock_ret = {'error': {'name': 'EauthAuthenticationError',
                              'message': 'Authentication failure of type "eauth" occurred for '
                                         'user test.'}}
        with patch('salt.auth.LoadAuth.authenticate_eauth', MagicMock(return_value=True)), \
             patch('salt.auth.LoadAuth.get_auth_list', MagicMock(return_value=[])):
            ret = self.clear_funcs.runner(clear_load)

        self.assertDictEqual(mock_ret, ret)

    def test_runner_eauth_salt_invocation_error(self):
        '''
        Asserts that an EauthAuthenticationError is returned when the user authenticates, but the
        command is malformed.
        '''
        clear_load = {'eauth': 'foo', 'username': 'test', 'fun': 'bad.test.arg.func'}
        mock_ret = {'error': {'name': 'SaltInvocationError',
                              'message': 'A command invocation error occurred: Check syntax.'}}
        with patch('salt.auth.LoadAuth.authenticate_eauth', MagicMock(return_value=True)), \
             patch('salt.auth.LoadAuth.get_auth_list', MagicMock(return_value=['testing'])):
            ret = self.clear_funcs.runner(clear_load)

        self.assertDictEqual(mock_ret, ret)

    def test_runner_user_not_authenticated(self):
        '''
        Asserts that an UserAuthenticationError is returned when the user can't authenticate.
        '''
        mock_ret = {'error': {'name': 'UserAuthenticationError',
                              'message': 'Authentication failure of type "user" occurred'}}
        ret = self.clear_funcs.runner({})
        self.assertDictEqual(mock_ret, ret)

    # wheel tests

    def test_wheel_token_not_authenticated(self):
        '''
        Asserts that a TokenAuthenticationError is returned when the token can't authenticate.
        '''
        mock_ret = {'error': {'name': 'TokenAuthenticationError',
                              'message': 'Authentication failure of type "token" occurred.'}}
        ret = self.clear_funcs.wheel({'token': 'asdfasdfasdfasdf'})
        self.assertDictEqual(mock_ret, ret)

    def test_wheel_token_authorization_error(self):
        '''
        Asserts that a TokenAuthenticationError is returned when the token authenticates, but is
        not authorized.
        '''
        token = 'asdfasdfasdfasdf'
        clear_load = {'token': token, 'fun': 'test.arg'}
        mock_token = {'token': token, 'eauth': 'foo', 'name': 'test'}
        mock_ret = {'error': {'name': 'TokenAuthenticationError',
                              'message': 'Authentication failure of type "token" occurred '
                                         'for user test.'}}

        with patch('salt.auth.LoadAuth.authenticate_token', MagicMock(return_value=mock_token)), \
             patch('salt.auth.LoadAuth.get_auth_list', MagicMock(return_value=[])):
            ret = self.clear_funcs.wheel(clear_load)

        self.assertDictEqual(mock_ret, ret)

    def test_wheel_token_salt_invocation_error(self):
        '''
        Asserts that a SaltInvocationError is returned when the token authenticates, but the
        command is malformed.
        '''
        token = 'asdfasdfasdfasdf'
        clear_load = {'token': token, 'fun': 'badtestarg'}
        mock_token = {'token': token, 'eauth': 'foo', 'name': 'test'}
        mock_ret = {'error': {'name': 'SaltInvocationError',
                              'message': 'A command invocation error occurred: Check syntax.'}}

        with patch('salt.auth.LoadAuth.authenticate_token', MagicMock(return_value=mock_token)), \
             patch('salt.auth.LoadAuth.get_auth_list', MagicMock(return_value=['testing'])):
            ret = self.clear_funcs.wheel(clear_load)

        self.assertDictEqual(mock_ret, ret)

    def test_wheel_eauth_not_authenticated(self):
        '''
        Asserts that an EauthAuthenticationError is returned when the user can't authenticate.
        '''
        mock_ret = {'error': {'name': 'EauthAuthenticationError',
                              'message': 'Authentication failure of type "eauth" occurred for '
                                         'user UNKNOWN.'}}
        ret = self.clear_funcs.wheel({'eauth': 'foo'})
        self.assertDictEqual(mock_ret, ret)

    def test_wheel_eauth_authorization_error(self):
        '''
        Asserts that an EauthAuthenticationError is returned when the user authenticates, but is
        not authorized.
        '''
        clear_load = {'eauth': 'foo', 'username': 'test', 'fun': 'test.arg'}
        mock_ret = {'error': {'name': 'EauthAuthenticationError',
                              'message': 'Authentication failure of type "eauth" occurred for '
                                         'user test.'}}
        with patch('salt.auth.LoadAuth.authenticate_eauth', MagicMock(return_value=True)), \
             patch('salt.auth.LoadAuth.get_auth_list', MagicMock(return_value=[])):
            ret = self.clear_funcs.wheel(clear_load)

        self.assertDictEqual(mock_ret, ret)

    def test_wheel_eauth_salt_invocation_error(self):
        '''
        Asserts that an EauthAuthenticationError is returned when the user authenticates, but the
        command is malformed.
        '''
        clear_load = {'eauth': 'foo', 'username': 'test', 'fun': 'bad.test.arg.func'}
        mock_ret = {'error': {'name': 'SaltInvocationError',
                              'message': 'A command invocation error occurred: Check syntax.'}}
        with patch('salt.auth.LoadAuth.authenticate_eauth', MagicMock(return_value=True)), \
             patch('salt.auth.LoadAuth.get_auth_list', MagicMock(return_value=['testing'])):
            ret = self.clear_funcs.wheel(clear_load)

        self.assertDictEqual(mock_ret, ret)

    def test_wheel_user_not_authenticated(self):
        '''
        Asserts that an UserAuthenticationError is returned when the user can't authenticate.
        '''
        mock_ret = {'error': {'name': 'UserAuthenticationError',
                              'message': 'Authentication failure of type "user" occurred'}}
        ret = self.clear_funcs.wheel({})
        self.assertDictEqual(mock_ret, ret)

    # publish tests

    def test_publish_user_is_blacklisted(self):
        '''
        Asserts that an AuthorizationError is returned when the user has been blacklisted.
        '''
        mock_ret = {'error': {'name': 'AuthorizationError',
                              'message': 'Authorization error occurred.'}}
        with patch('salt.acl.PublisherACL.user_is_blacklisted', MagicMock(return_value=True)):
            self.assertEqual(mock_ret, self.clear_funcs.publish({'user': 'foo', 'fun': 'test.arg'}))

    def test_publish_cmd_blacklisted(self):
        '''
        Asserts that an AuthorizationError is returned when the command has been blacklisted.
        '''
        mock_ret = {'error': {'name': 'AuthorizationError',
                              'message': 'Authorization error occurred.'}}
        with patch('salt.acl.PublisherACL.user_is_blacklisted', MagicMock(return_value=False)), \
                patch('salt.acl.PublisherACL.cmd_is_blacklisted', MagicMock(return_value=True)):
            self.assertEqual(mock_ret, self.clear_funcs.publish({'user': 'foo', 'fun': 'test.arg'}))

    def test_publish_token_not_authenticated(self):
        '''
        Asserts that an AuthenticationError is returned when the token can't authenticate.
        '''
        mock_ret = {'error': {'name': 'AuthenticationError',
                              'message': 'Authentication error occurred.'}}
        load = {'user': 'foo', 'fun': 'test.arg', 'tgt': 'test_minion',
                'kwargs': {'token': 'asdfasdfasdfasdf'}}
        with patch('salt.acl.PublisherACL.user_is_blacklisted', MagicMock(return_value=False)), \
                patch('salt.acl.PublisherACL.cmd_is_blacklisted', MagicMock(return_value=False)):
            self.assertEqual(mock_ret, self.clear_funcs.publish(load))

    def test_publish_token_authorization_error(self):
        '''
        Asserts that an AuthorizationError is returned when the token authenticates, but is not
        authorized.
        '''
        token = 'asdfasdfasdfasdf'
        load = {'user': 'foo', 'fun': 'test.arg', 'tgt': 'test_minion',
                'arg': 'bar', 'kwargs': {'token': token}}
        mock_token = {'token': token, 'eauth': 'foo', 'name': 'test'}
        mock_ret = {'error': {'name': 'AuthorizationError',
                              'message': 'Authorization error occurred.'}}

        with patch('salt.acl.PublisherACL.user_is_blacklisted', MagicMock(return_value=False)), \
                patch('salt.acl.PublisherACL.cmd_is_blacklisted', MagicMock(return_value=False)), \
                patch('salt.auth.LoadAuth.authenticate_token', MagicMock(return_value=mock_token)), \
                patch('salt.auth.LoadAuth.get_auth_list', MagicMock(return_value=[])):
            self.assertEqual(mock_ret, self.clear_funcs.publish(load))

    def test_publish_eauth_not_authenticated(self):
        '''
        Asserts that an AuthenticationError is returned when the user can't authenticate.
        '''
        load = {'user': 'test', 'fun': 'test.arg', 'tgt': 'test_minion',
                'kwargs': {'eauth': 'foo'}}
        mock_ret = {'error': {'name': 'AuthenticationError',
                               'message': 'Authentication error occurred.'}}
        with patch('salt.acl.PublisherACL.user_is_blacklisted', MagicMock(return_value=False)), \
                patch('salt.acl.PublisherACL.cmd_is_blacklisted', MagicMock(return_value=False)):
            self.assertEqual(mock_ret, self.clear_funcs.publish(load))

    def test_publish_eauth_authorization_error(self):
        '''
        Asserts that an AuthorizationError is returned when the user authenticates, but is not
        authorized.
        '''
        load = {'user': 'test', 'fun': 'test.arg', 'tgt': 'test_minion',
                'kwargs': {'eauth': 'foo'}, 'arg': 'bar'}
        mock_ret = {'error': {'name': 'AuthorizationError',
                               'message': 'Authorization error occurred.'}}
        with patch('salt.acl.PublisherACL.user_is_blacklisted', MagicMock(return_value=False)), \
                patch('salt.acl.PublisherACL.cmd_is_blacklisted', MagicMock(return_value=False)), \
                patch('salt.auth.LoadAuth.authenticate_eauth', MagicMock(return_value=True)), \
                patch('salt.auth.LoadAuth.get_auth_list', MagicMock(return_value=[])):
            self.assertEqual(mock_ret, self.clear_funcs.publish(load))

    def test_publish_user_not_authenticated(self):
        '''
        Asserts that an AuthenticationError is returned when the user can't authenticate.
        '''
        load = {'user': 'test', 'fun': 'test.arg', 'tgt': 'test_minion'}
        mock_ret = {'error': {'name': 'AuthenticationError',
                              'message': 'Authentication error occurred.'}}
        with patch('salt.acl.PublisherACL.user_is_blacklisted', MagicMock(return_value=False)), \
                patch('salt.acl.PublisherACL.cmd_is_blacklisted', MagicMock(return_value=False)):
            self.assertEqual(mock_ret, self.clear_funcs.publish(load))

    def test_publish_user_authenticated_missing_auth_list(self):
        '''
        Asserts that an AuthenticationError is returned when the user has an effective user id and is
        authenticated, but the auth_list is empty.
        '''
        load = {'user': 'test', 'fun': 'test.arg', 'tgt': 'test_minion',
                'kwargs': {'user': 'test'}, 'arg': 'foo'}
        mock_ret = {'error': {'name': 'AuthenticationError',
                              'message': 'Authentication error occurred.'}}
        with patch('salt.acl.PublisherACL.user_is_blacklisted', MagicMock(return_value=False)), \
                patch('salt.acl.PublisherACL.cmd_is_blacklisted', MagicMock(return_value=False)), \
                patch('salt.auth.LoadAuth.authenticate_key', MagicMock(return_value='fake-user-key')), \
                patch('salt.utils.master.get_values_of_matching_keys', MagicMock(return_value=[])):
            self.assertEqual(mock_ret, self.clear_funcs.publish(load))

    def test_publish_user_authorization_error(self):
        '''
        Asserts that an AuthorizationError is returned when the user authenticates, but is not
        authorized.
        '''
        load = {'user': 'test', 'fun': 'test.arg', 'tgt': 'test_minion',
                'kwargs': {'user': 'test'}, 'arg': 'foo'}
        mock_ret = {'error': {'name': 'AuthorizationError',
                              'message': 'Authorization error occurred.'}}
        with patch('salt.acl.PublisherACL.user_is_blacklisted', MagicMock(return_value=False)), \
                patch('salt.acl.PublisherACL.cmd_is_blacklisted', MagicMock(return_value=False)), \
                patch('salt.auth.LoadAuth.authenticate_key', MagicMock(return_value='fake-user-key')), \
                patch('salt.utils.master.get_values_of_matching_keys', MagicMock(return_value=['test'])), \
                patch('salt.utils.minions.CkMinions.auth_check', MagicMock(return_value=False)):
            self.assertEqual(mock_ret, self.clear_funcs.publish(load))
