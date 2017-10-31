# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
import io

# Import Salt libs
import salt.config
import salt.daemons.masterapi as masterapi

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    patch,
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON
)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class AutoKeyTest(TestCase):
    '''
    Test for the salt.daemons.masterapi.AutoKey class
    '''

    def setUp(self):
        opts = salt.config.master_config(None)
        self.auto_key = masterapi.AutoKey(opts)

    def _test_check_autosign_grains(self,
                                    test_func,
                                    file_content=u'test_value',
                                    file_name=u'test_grain',
                                    autosign_grains_dir=u'test_dir',
                                    permissions_ret=True):
        '''
        Helper function for testing autosign_grains().

        Patches ``os.walk`` to return only ``file_name`` and ``salt.utils.files.fopen`` to open a
        mock file with ``file_content`` as content. Optionally sets ``opts`` values.
        Then executes test_func. The ``os.walk`` and ``salt.utils.files.fopen`` mock objects
        are passed to the function as arguments.
        '''
        if autosign_grains_dir:
            self.auto_key.opts[u'autosign_grains_dir'] = autosign_grains_dir
        mock_file = io.StringIO(file_content)
        mock_dirs = [(None, None, [file_name])]

        with patch('os.walk', MagicMock(return_value=mock_dirs)) as mock_walk, \
             patch('salt.utils.files.fopen', MagicMock(return_value=mock_file)) as mock_open, \
             patch('salt.daemons.masterapi.AutoKey.check_permissions',
                MagicMock(return_value=permissions_ret)) as mock_permissions:
            test_func(mock_walk, mock_open, mock_permissions)

    def test_check_autosign_grains_no_grains(self):
        '''
        Asserts that autosigning from grains fails when no grain values are passed.
        '''
        def test_func(mock_walk, mock_open, mock_permissions):
            self.assertFalse(self.auto_key.check_autosign_grains(None))
            self.assertEqual(mock_walk.call_count, 0)
            self.assertEqual(mock_open.call_count, 0)
            self.assertEqual(mock_permissions.call_count, 0)

            self.assertFalse(self.auto_key.check_autosign_grains({}))
            self.assertEqual(mock_walk.call_count, 0)
            self.assertEqual(mock_open.call_count, 0)
            self.assertEqual(mock_permissions.call_count, 0)

        self._test_check_autosign_grains(test_func)

    def test_check_autosign_grains_no_autosign_grains_dir(self):
        '''
        Asserts that autosigning from grains fails when the \'autosign_grains_dir\' config option
        is undefined.
        '''
        def test_func(mock_walk, mock_open, mock_permissions):
            self.assertFalse(self.auto_key.check_autosign_grains({u'test_grain': u'test_value'}))
            self.assertEqual(mock_walk.call_count, 0)
            self.assertEqual(mock_open.call_count, 0)
            self.assertEqual(mock_permissions.call_count, 0)

        self._test_check_autosign_grains(test_func, autosign_grains_dir=None)

    def test_check_autosign_grains_accept(self):
        '''
        Asserts that autosigning from grains passes when a matching grain value is in an
        autosign_grain file.
        '''
        def test_func(*args):
            self.assertTrue(self.auto_key.check_autosign_grains({u'test_grain': u'test_value'}))

        file_content = u'#test_ignore\ntest_value'
        self._test_check_autosign_grains(test_func, file_content=file_content)

    def test_check_autosign_grains_accept_not(self):
        '''
        Asserts that autosigning from grains fails when the grain value is not in the
        autosign_grain files.
        '''
        def test_func(*args):
            self.assertFalse(self.auto_key.check_autosign_grains({u'test_grain': u'test_invalid'}))

        file_content = u'#test_invalid\ntest_value'
        self._test_check_autosign_grains(test_func, file_content=file_content)

    def test_check_autosign_grains_invalid_file_permissions(self):
        '''
        Asserts that autosigning from grains fails when the grain file has the wrong permissions.
        '''
        def test_func(*args):
            self.assertFalse(self.auto_key.check_autosign_grains({u'test_grain': u'test_value'}))

        file_content = u'#test_ignore\ntest_value'
        self._test_check_autosign_grains(test_func, file_content=file_content, permissions_ret=False)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class LocalFuncsTestCase(TestCase):
    '''
    TestCase for salt.daemons.masterapi.LocalFuncs class
    '''

    def setUp(self):
        opts = salt.config.master_config(None)
        self.local_funcs = masterapi.LocalFuncs(opts, 'test-key')

    # runner tests

    def test_runner_token_not_authenticated(self):
        '''
        Asserts that a TokenAuthenticationError is returned when the token can't authenticate.
        '''
        mock_ret = {u'error': {u'name': u'TokenAuthenticationError',
                               u'message': u'Authentication failure of type "token" occurred.'}}
        ret = self.local_funcs.runner({u'token': u'asdfasdfasdfasdf'})
        self.assertDictEqual(mock_ret, ret)

    def test_runner_token_authorization_error(self):
        '''
        Asserts that a TokenAuthenticationError is returned when the token authenticates, but is
        not authorized.
        '''
        token = u'asdfasdfasdfasdf'
        load = {u'token': token, u'fun': u'test.arg', u'kwarg': {}}
        mock_token = {u'token': token, u'eauth': u'foo', u'name': u'test'}
        mock_ret = {u'error': {u'name': u'TokenAuthenticationError',
                               u'message': u'Authentication failure of type "token" occurred '
                                           u'for user test.'}}

        with patch('salt.auth.LoadAuth.authenticate_token', MagicMock(return_value=mock_token)), \
             patch('salt.auth.LoadAuth.get_auth_list', MagicMock(return_value=[])):
            ret = self.local_funcs.runner(load)

        self.assertDictEqual(mock_ret, ret)

    def test_runner_token_salt_invocation_error(self):
        '''
        Asserts that a SaltInvocationError is returned when the token authenticates, but the
        command is malformed.
        '''
        token = u'asdfasdfasdfasdf'
        load = {u'token': token, u'fun': u'badtestarg', u'kwarg': {}}
        mock_token = {u'token': token, u'eauth': u'foo', u'name': u'test'}
        mock_ret = {u'error': {u'name': u'SaltInvocationError',
                               u'message': u'A command invocation error occurred: Check syntax.'}}

        with patch('salt.auth.LoadAuth.authenticate_token', MagicMock(return_value=mock_token)), \
             patch('salt.auth.LoadAuth.get_auth_list', MagicMock(return_value=['testing'])):
            ret = self.local_funcs.runner(load)

        self.assertDictEqual(mock_ret, ret)

    def test_runner_eauth_not_authenticated(self):
        '''
        Asserts that an EauthAuthenticationError is returned when the user can't authenticate.
        '''
        mock_ret = {u'error': {u'name': u'EauthAuthenticationError',
                               u'message': u'Authentication failure of type "eauth" occurred for '
                                           u'user UNKNOWN.'}}
        ret = self.local_funcs.runner({u'eauth': u'foo'})
        self.assertDictEqual(mock_ret, ret)

    def test_runner_eauth_authorization_error(self):
        '''
        Asserts that an EauthAuthenticationError is returned when the user authenticates, but is
        not authorized.
        '''
        load = {u'eauth': u'foo', u'username': u'test', u'fun': u'test.arg', u'kwarg': {}}
        mock_ret = {u'error': {u'name': u'EauthAuthenticationError',
                               u'message': u'Authentication failure of type "eauth" occurred for '
                                           u'user test.'}}
        with patch('salt.auth.LoadAuth.authenticate_eauth', MagicMock(return_value=True)), \
             patch('salt.auth.LoadAuth.get_auth_list', MagicMock(return_value=[])):
            ret = self.local_funcs.runner(load)

        self.assertDictEqual(mock_ret, ret)

    def test_runner_eauth_salt_invocation_error(self):
        '''
        Asserts that an EauthAuthenticationError is returned when the user authenticates, but the
        command is malformed.
        '''
        load = {u'eauth': u'foo', u'username': u'test', u'fun': u'bad.test.arg.func', u'kwarg': {}}
        mock_ret = {u'error': {u'name': u'SaltInvocationError',
                               u'message': u'A command invocation error occurred: Check syntax.'}}
        with patch('salt.auth.LoadAuth.authenticate_eauth', MagicMock(return_value=True)), \
             patch('salt.auth.LoadAuth.get_auth_list', MagicMock(return_value=['testing'])):
            ret = self.local_funcs.runner(load)

        self.assertDictEqual(mock_ret, ret)

    # wheel tests

    def test_wheel_token_not_authenticated(self):
        '''
        Asserts that a TokenAuthenticationError is returned when the token can't authenticate.
        '''
        mock_ret = {u'error': {u'name': u'TokenAuthenticationError',
                               u'message': u'Authentication failure of type "token" occurred.'}}
        ret = self.local_funcs.wheel({u'token': u'asdfasdfasdfasdf'})
        self.assertDictEqual(mock_ret, ret)

    def test_wheel_token_authorization_error(self):
        '''
        Asserts that a TokenAuthenticationError is returned when the token authenticates, but is
        not authorized.
        '''
        token = u'asdfasdfasdfasdf'
        load = {u'token': token, u'fun': u'test.arg', u'kwarg': {}}
        mock_token = {u'token': token, u'eauth': u'foo', u'name': u'test'}
        mock_ret = {u'error': {u'name': u'TokenAuthenticationError',
                               u'message': u'Authentication failure of type "token" occurred '
                                           u'for user test.'}}

        with patch('salt.auth.LoadAuth.authenticate_token', MagicMock(return_value=mock_token)), \
             patch('salt.auth.LoadAuth.get_auth_list', MagicMock(return_value=[])):
            ret = self.local_funcs.wheel(load)

        self.assertDictEqual(mock_ret, ret)

    def test_wheel_token_salt_invocation_error(self):
        '''
        Asserts that a SaltInvocationError is returned when the token authenticates, but the
        command is malformed.
        '''
        token = u'asdfasdfasdfasdf'
        load = {u'token': token, u'fun': u'badtestarg', u'kwarg': {}}
        mock_token = {u'token': token, u'eauth': u'foo', u'name': u'test'}
        mock_ret = {u'error': {u'name': u'SaltInvocationError',
                               u'message': u'A command invocation error occurred: Check syntax.'}}

        with patch('salt.auth.LoadAuth.authenticate_token', MagicMock(return_value=mock_token)), \
             patch('salt.auth.LoadAuth.get_auth_list', MagicMock(return_value=['testing'])):
            ret = self.local_funcs.wheel(load)

        self.assertDictEqual(mock_ret, ret)

    def test_wheel_eauth_not_authenticated(self):
        '''
        Asserts that an EauthAuthenticationError is returned when the user can't authenticate.
        '''
        mock_ret = {u'error': {u'name': u'EauthAuthenticationError',
                               u'message': u'Authentication failure of type "eauth" occurred for '
                                           u'user UNKNOWN.'}}
        ret = self.local_funcs.wheel({u'eauth': u'foo'})
        self.assertDictEqual(mock_ret, ret)

    def test_wheel_eauth_authorization_error(self):
        '''
        Asserts that an EauthAuthenticationError is returned when the user authenticates, but is
        not authorized.
        '''
        load = {u'eauth': u'foo', u'username': u'test', u'fun': u'test.arg', u'kwarg': {}}
        mock_ret = {u'error': {u'name': u'EauthAuthenticationError',
                               u'message': u'Authentication failure of type "eauth" occurred for '
                                           u'user test.'}}
        with patch('salt.auth.LoadAuth.authenticate_eauth', MagicMock(return_value=True)), \
             patch('salt.auth.LoadAuth.get_auth_list', MagicMock(return_value=[])):
            ret = self.local_funcs.wheel(load)

        self.assertDictEqual(mock_ret, ret)

    def test_wheel_eauth_salt_invocation_error(self):
        '''
        Asserts that an EauthAuthenticationError is returned when the user authenticates, but the
        command is malformed.
        '''
        load = {u'eauth': u'foo', u'username': u'test', u'fun': u'bad.test.arg.func', u'kwarg': {}}
        mock_ret = {u'error': {u'name': u'SaltInvocationError',
                               u'message': u'A command invocation error occurred: Check syntax.'}}
        with patch('salt.auth.LoadAuth.authenticate_eauth', MagicMock(return_value=True)), \
             patch('salt.auth.LoadAuth.get_auth_list', MagicMock(return_value=['testing'])):
            ret = self.local_funcs.wheel(load)

        self.assertDictEqual(mock_ret, ret)

    def test_wheel_user_not_authenticated(self):
        '''
        Asserts that an UserAuthenticationError is returned when the user can't authenticate.
        '''
        mock_ret = {u'error': {u'name': u'UserAuthenticationError',
                               u'message': u'Authentication failure of type "user" occurred for '
                                           u'user UNKNOWN.'}}
        ret = self.local_funcs.wheel({})
        self.assertDictEqual(mock_ret, ret)

    # publish tests

    def test_publish_user_is_blacklisted(self):
        '''
        Asserts that an empty string is returned when the user has been blacklisted.
        '''
        with patch('salt.acl.PublisherACL.user_is_blacklisted', MagicMock(return_value=True)):
            self.assertEqual(u'', self.local_funcs.publish({u'user': u'foo', u'fun': u'test.arg'}))

    def test_publish_cmd_blacklisted(self):
        '''
        Asserts that an empty string returned when the command has been blacklisted.
        '''
        with patch('salt.acl.PublisherACL.user_is_blacklisted', MagicMock(return_value=False)), \
                patch('salt.acl.PublisherACL.cmd_is_blacklisted', MagicMock(return_value=True)):
            self.assertEqual(u'', self.local_funcs.publish({u'user': u'foo', u'fun': u'test.arg'}))

    def test_publish_token_not_authenticated(self):
        '''
        Asserts that an empty string is returned when the token can't authenticate.
        '''
        load = {u'user': u'foo', u'fun': u'test.arg', u'tgt': u'test_minion',
                u'kwargs': {u'token': u'asdfasdfasdfasdf'}}
        with patch('salt.acl.PublisherACL.user_is_blacklisted', MagicMock(return_value=False)), \
                patch('salt.acl.PublisherACL.cmd_is_blacklisted', MagicMock(return_value=False)):
            self.assertEqual(u'', self.local_funcs.publish(load))

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
            self.assertEqual(u'', self.local_funcs.publish(load))

    def test_publish_eauth_not_authenticated(self):
        '''
        Asserts that an empty string is returned when the user can't authenticate.
        '''
        load = {u'user': u'test', u'fun': u'test.arg', u'tgt': u'test_minion',
                u'kwargs': {u'eauth': u'foo'}}
        with patch('salt.acl.PublisherACL.user_is_blacklisted', MagicMock(return_value=False)), \
                patch('salt.acl.PublisherACL.cmd_is_blacklisted', MagicMock(return_value=False)):
            self.assertEqual(u'', self.local_funcs.publish(load))

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
            self.assertEqual(u'', self.local_funcs.publish(load))

    def test_publish_user_not_authenticated(self):
        '''
        Asserts that an empty string is returned when the user can't authenticate.
        '''
        load = {u'user': u'test', u'fun': u'test.arg', u'tgt': u'test_minion'}
        with patch('salt.acl.PublisherACL.user_is_blacklisted', MagicMock(return_value=False)), \
                patch('salt.acl.PublisherACL.cmd_is_blacklisted', MagicMock(return_value=False)):
            self.assertEqual(u'', self.local_funcs.publish(load))

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
            self.assertEqual(u'', self.local_funcs.publish(load))

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
            self.assertEqual(u'', self.local_funcs.publish(load))
