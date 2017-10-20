# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
from functools import wraps
import stat

# Import Salt libs
import salt.config
import salt.daemons.masterapi as masterapi

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    patch,
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON,
)


def gen_permissions(owner='', group='', others=''):
    '''
    Helper method to generate file permission bits
    Usage: gen_permissions('rw', 'r', 'r')
    '''
    ret = 0
    for c in owner:
        ret |= getattr(stat, 'S_I{}USR'.format(c.upper()), 0)
    for c in group:
        ret |= getattr(stat, 'S_I{}GRP'.format(c.upper()), 0)
    for c in others:
        ret |= getattr(stat, 'S_I{}OTH'.format(c.upper()), 0)
    return ret


def patch_check_permissions(uid=1, groups=None, is_windows=False, permissive_pki=False):
    if not groups:
        groups = [uid]

    def decorator(func):
        @wraps(func)
        def wrapper(self):
            self.auto_key.opts['permissive_pki_access'] = permissive_pki
            with patch('os.stat', self.os_stat_mock), \
                 patch('os.getuid', MagicMock(return_value=uid)), \
                 patch('salt.utils.user.get_gid_list', MagicMock(return_value=groups)), \
                 patch('salt.utils.platform.is_windows', MagicMock(return_value=is_windows)):
                func(self)
        return wrapper
    return decorator


@skipIf(NO_MOCK, NO_MOCK_REASON)
class AutoKeyTest(TestCase):
    '''
    Tests for the salt.daemons.masterapi.AutoKey class
    '''

    def setUp(self):
        opts = {'user': 'test_user'}
        self.auto_key = masterapi.AutoKey(opts)
        self.stats = {}

    def os_stat_mock(self, filename):
        fmode = MagicMock()
        fstats = self.stats.get(filename, {})
        fmode.st_mode = fstats.get('mode', 0)
        fmode.st_gid = fstats.get('gid', 0)
        return fmode

    @patch_check_permissions(uid=0, is_windows=True)
    def test_check_permissions_windows(self):
        '''
        Assert that all files are accepted on windows
        '''
        self.stats['testfile'] = {'mode': gen_permissions('rwx', 'rwx', 'rwx'), 'gid': 2}
        self.assertTrue(self.auto_key.check_permissions('testfile'))

    @patch_check_permissions(permissive_pki=True)
    def test_check_permissions_others_can_write(self):
        '''
        Assert that no file is accepted, when others can write to it
        '''
        self.stats['testfile'] = {'mode': gen_permissions('', '', 'w'), 'gid': 1}
        self.assertFalse(self.auto_key.check_permissions('testfile'))

    @patch_check_permissions()
    def test_check_permissions_group_can_write_not_permissive(self):
        '''
        Assert that a file is accepted, when group can write to it and perkissive_pki_access=False
        '''
        self.stats['testfile'] = {'mode': gen_permissions('w', 'w', ''), 'gid': 1}
        self.assertFalse(self.auto_key.check_permissions('testfile'))

    @patch_check_permissions(permissive_pki=True)
    def test_check_permissions_group_can_write_permissive(self):
        '''
        Assert that a file is accepted, when group can write to it and perkissive_pki_access=True
        '''
        self.stats['testfile'] = {'mode': gen_permissions('w', 'w', ''), 'gid': 1}
        self.assertTrue(self.auto_key.check_permissions('testfile'))

    @patch_check_permissions(uid=0, permissive_pki=True)
    def test_check_permissions_group_can_write_permissive_root_in_group(self):
        '''
        Assert that a file is accepted, when group can write to it, perkissive_pki_access=False,
        salt is root and in the file owning group
        '''
        self.stats['testfile'] = {'mode': gen_permissions('w', 'w', ''), 'gid': 0}
        self.assertTrue(self.auto_key.check_permissions('testfile'))

    @patch_check_permissions(uid=0, permissive_pki=True)
    def test_check_permissions_group_can_write_permissive_root_not_in_group(self):
        '''
        Assert that no file is accepted, when group can write to it, perkissive_pki_access=False,
        salt is root and **not** in the file owning group
        '''
        self.stats['testfile'] = {'mode': gen_permissions('w', 'w', ''), 'gid': 1}
        self.assertFalse(self.auto_key.check_permissions('testfile'))

    @patch_check_permissions()
    def test_check_permissions_only_owner_can_write(self):
        '''
        Assert that a file is accepted, when only the owner can write to it
        '''
        self.stats['testfile'] = {'mode': gen_permissions('w', '', ''), 'gid': 1}
        self.assertTrue(self.auto_key.check_permissions('testfile'))

    @patch_check_permissions(uid=0)
    def test_check_permissions_only_owner_can_write_root(self):
        '''
        Assert that a file is accepted, when only the owner can write to it and salt is root
        '''
        self.stats['testfile'] = {'mode': gen_permissions('w', '', ''), 'gid': 0}
        self.assertTrue(self.auto_key.check_permissions('testfile'))


class LocalFuncsTestCase(TestCase):
    '''
    TestCase for salt.daemons.masterapi.LocalFuncs class
    '''

    def setUp(self):
        opts = salt.config.master_config(None)
        self.local_funcs = masterapi.LocalFuncs(opts, 'test-key')

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
