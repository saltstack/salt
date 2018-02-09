# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
from functools import wraps
import io
import stat

# Import Salt libs
import salt.config
import salt.daemons.masterapi as masterapi
import salt.utils.platform

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    patch,
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON
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
            if salt.utils.platform.is_windows():
                with patch('salt.utils.platform.is_windows', MagicMock(return_value=True)):
                    func(self)
            else:
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
        opts = salt.config.master_config(None)
        opts['user'] = 'test_user'
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
        if salt.utils.platform.is_windows():
            self.assertTrue(self.auto_key.check_permissions('testfile'))
        else:
            self.assertFalse(self.auto_key.check_permissions('testfile'))

    @patch_check_permissions()
    def test_check_permissions_group_can_write_not_permissive(self):
        '''
        Assert that a file is accepted, when group can write to it and perkissive_pki_access=False
        '''
        self.stats['testfile'] = {'mode': gen_permissions('w', 'w', ''), 'gid': 1}
        if salt.utils.platform.is_windows():
            self.assertTrue(self.auto_key.check_permissions('testfile'))
        else:
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
        if salt.utils.platform.is_windows():
            self.assertTrue(self.auto_key.check_permissions('testfile'))
        else:
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

    def _test_check_autosign_grains(self,
                                    test_func,
                                    file_content='test_value',
                                    file_name='test_grain',
                                    autosign_grains_dir='test_dir',
                                    permissions_ret=True):
        '''
        Helper function for testing autosign_grains().

        Patches ``os.walk`` to return only ``file_name`` and ``salt.utils.files.fopen`` to open a
        mock file with ``file_content`` as content. Optionally sets ``opts`` values.
        Then executes test_func. The ``os.walk`` and ``salt.utils.files.fopen`` mock objects
        are passed to the function as arguments.
        '''
        if autosign_grains_dir:
            self.auto_key.opts['autosign_grains_dir'] = autosign_grains_dir
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
            self.assertFalse(self.auto_key.check_autosign_grains({'test_grain': 'test_value'}))
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
            self.assertTrue(self.auto_key.check_autosign_grains({'test_grain': 'test_value'}))

        file_content = '#test_ignore\ntest_value'
        self._test_check_autosign_grains(test_func, file_content=file_content)

    def test_check_autosign_grains_accept_not(self):
        '''
        Asserts that autosigning from grains fails when the grain value is not in the
        autosign_grain files.
        '''
        def test_func(*args):
            self.assertFalse(self.auto_key.check_autosign_grains({'test_grain': 'test_invalid'}))

        file_content = '#test_invalid\ntest_value'
        self._test_check_autosign_grains(test_func, file_content=file_content)

    def test_check_autosign_grains_invalid_file_permissions(self):
        '''
        Asserts that autosigning from grains fails when the grain file has the wrong permissions.
        '''
        def test_func(*args):
            self.assertFalse(self.auto_key.check_autosign_grains({'test_grain': 'test_value'}))

        file_content = '#test_ignore\ntest_value'
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
        mock_ret = {'error': {'name': 'TokenAuthenticationError',
                              'message': 'Authentication failure of type "token" occurred.'}}
        ret = self.local_funcs.runner({'token': 'asdfasdfasdfasdf'})
        self.assertDictEqual(mock_ret, ret)

    def test_runner_token_authorization_error(self):
        '''
        Asserts that a TokenAuthenticationError is returned when the token authenticates, but is
        not authorized.
        '''
        token = 'asdfasdfasdfasdf'
        load = {'token': token, 'fun': 'test.arg', 'kwarg': {}}
        mock_token = {'token': token, 'eauth': 'foo', 'name': 'test'}
        mock_ret = {'error': {'name': 'TokenAuthenticationError',
                              'message': 'Authentication failure of type "token" occurred '
                                         'for user test.'}}

        with patch('salt.auth.LoadAuth.authenticate_token', MagicMock(return_value=mock_token)), \
             patch('salt.auth.LoadAuth.get_auth_list', MagicMock(return_value=[])):
            ret = self.local_funcs.runner(load)

        self.assertDictEqual(mock_ret, ret)

    def test_runner_token_salt_invocation_error(self):
        '''
        Asserts that a SaltInvocationError is returned when the token authenticates, but the
        command is malformed.
        '''
        token = 'asdfasdfasdfasdf'
        load = {'token': token, 'fun': 'badtestarg', 'kwarg': {}}
        mock_token = {'token': token, 'eauth': 'foo', 'name': 'test'}
        mock_ret = {'error': {'name': 'SaltInvocationError',
                              'message': 'A command invocation error occurred: Check syntax.'}}

        with patch('salt.auth.LoadAuth.authenticate_token', MagicMock(return_value=mock_token)), \
             patch('salt.auth.LoadAuth.get_auth_list', MagicMock(return_value=['testing'])):
            ret = self.local_funcs.runner(load)

        self.assertDictEqual(mock_ret, ret)

    def test_runner_eauth_not_authenticated(self):
        '''
        Asserts that an EauthAuthenticationError is returned when the user can't authenticate.
        '''
        mock_ret = {'error': {'name': 'EauthAuthenticationError',
                              'message': 'Authentication failure of type "eauth" occurred for '
                                         'user UNKNOWN.'}}
        ret = self.local_funcs.runner({'eauth': 'foo'})
        self.assertDictEqual(mock_ret, ret)

    def test_runner_eauth_authorization_error(self):
        '''
        Asserts that an EauthAuthenticationError is returned when the user authenticates, but is
        not authorized.
        '''
        load = {'eauth': 'foo', 'username': 'test', 'fun': 'test.arg', 'kwarg': {}}
        mock_ret = {'error': {'name': 'EauthAuthenticationError',
                              'message': 'Authentication failure of type "eauth" occurred for '
                                         'user test.'}}
        with patch('salt.auth.LoadAuth.authenticate_eauth', MagicMock(return_value=True)), \
             patch('salt.auth.LoadAuth.get_auth_list', MagicMock(return_value=[])):
            ret = self.local_funcs.runner(load)

        self.assertDictEqual(mock_ret, ret)

    def test_runner_eauth_salt_invocation_error(self):
        '''
        Asserts that an EauthAuthenticationError is returned when the user authenticates, but the
        command is malformed.
        '''
        load = {'eauth': 'foo', 'username': 'test', 'fun': 'bad.test.arg.func', 'kwarg': {}}
        mock_ret = {'error': {'name': 'SaltInvocationError',
                              'message': 'A command invocation error occurred: Check syntax.'}}
        with patch('salt.auth.LoadAuth.authenticate_eauth', MagicMock(return_value=True)), \
             patch('salt.auth.LoadAuth.get_auth_list', MagicMock(return_value=['testing'])):
            ret = self.local_funcs.runner(load)

        self.assertDictEqual(mock_ret, ret)

    # wheel tests

    def test_wheel_token_not_authenticated(self):
        '''
        Asserts that a TokenAuthenticationError is returned when the token can't authenticate.
        '''
        mock_ret = {'error': {'name': 'TokenAuthenticationError',
                              'message': 'Authentication failure of type "token" occurred.'}}
        ret = self.local_funcs.wheel({'token': 'asdfasdfasdfasdf'})
        self.assertDictEqual(mock_ret, ret)

    def test_wheel_token_authorization_error(self):
        '''
        Asserts that a TokenAuthenticationError is returned when the token authenticates, but is
        not authorized.
        '''
        token = 'asdfasdfasdfasdf'
        load = {'token': token, 'fun': 'test.arg', 'kwarg': {}}
        mock_token = {'token': token, 'eauth': 'foo', 'name': 'test'}
        mock_ret = {'error': {'name': 'TokenAuthenticationError',
                              'message': 'Authentication failure of type "token" occurred '
                                         'for user test.'}}

        with patch('salt.auth.LoadAuth.authenticate_token', MagicMock(return_value=mock_token)), \
             patch('salt.auth.LoadAuth.get_auth_list', MagicMock(return_value=[])):
            ret = self.local_funcs.wheel(load)

        self.assertDictEqual(mock_ret, ret)

    def test_wheel_token_salt_invocation_error(self):
        '''
        Asserts that a SaltInvocationError is returned when the token authenticates, but the
        command is malformed.
        '''
        token = 'asdfasdfasdfasdf'
        load = {'token': token, 'fun': 'badtestarg', 'kwarg': {}}
        mock_token = {'token': token, 'eauth': 'foo', 'name': 'test'}
        mock_ret = {'error': {'name': 'SaltInvocationError',
                              'message': 'A command invocation error occurred: Check syntax.'}}

        with patch('salt.auth.LoadAuth.authenticate_token', MagicMock(return_value=mock_token)), \
             patch('salt.auth.LoadAuth.get_auth_list', MagicMock(return_value=['testing'])):
            ret = self.local_funcs.wheel(load)

        self.assertDictEqual(mock_ret, ret)

    def test_wheel_eauth_not_authenticated(self):
        '''
        Asserts that an EauthAuthenticationError is returned when the user can't authenticate.
        '''
        mock_ret = {'error': {'name': 'EauthAuthenticationError',
                              'message': 'Authentication failure of type "eauth" occurred for '
                                         'user UNKNOWN.'}}
        ret = self.local_funcs.wheel({'eauth': 'foo'})
        self.assertDictEqual(mock_ret, ret)

    def test_wheel_eauth_authorization_error(self):
        '''
        Asserts that an EauthAuthenticationError is returned when the user authenticates, but is
        not authorized.
        '''
        load = {'eauth': 'foo', 'username': 'test', 'fun': 'test.arg', 'kwarg': {}}
        mock_ret = {'error': {'name': 'EauthAuthenticationError',
                              'message': 'Authentication failure of type "eauth" occurred for '
                                         'user test.'}}
        with patch('salt.auth.LoadAuth.authenticate_eauth', MagicMock(return_value=True)), \
             patch('salt.auth.LoadAuth.get_auth_list', MagicMock(return_value=[])):
            ret = self.local_funcs.wheel(load)

        self.assertDictEqual(mock_ret, ret)

    def test_wheel_eauth_salt_invocation_error(self):
        '''
        Asserts that an EauthAuthenticationError is returned when the user authenticates, but the
        command is malformed.
        '''
        load = {'eauth': 'foo', 'username': 'test', 'fun': 'bad.test.arg.func', 'kwarg': {}}
        mock_ret = {'error': {'name': 'SaltInvocationError',
                              'message': 'A command invocation error occurred: Check syntax.'}}
        with patch('salt.auth.LoadAuth.authenticate_eauth', MagicMock(return_value=True)), \
             patch('salt.auth.LoadAuth.get_auth_list', MagicMock(return_value=['testing'])):
            ret = self.local_funcs.wheel(load)

        self.assertDictEqual(mock_ret, ret)

    def test_wheel_user_not_authenticated(self):
        '''
        Asserts that an UserAuthenticationError is returned when the user can't authenticate.
        '''
        mock_ret = {'error': {'name': 'UserAuthenticationError',
                              'message': 'Authentication failure of type "user" occurred for '
                                         'user UNKNOWN.'}}
        ret = self.local_funcs.wheel({})
        self.assertDictEqual(mock_ret, ret)

    # publish tests

    def test_publish_user_is_blacklisted(self):
        '''
        Asserts that an AuthorizationError is returned when the user has been blacklisted.
        '''
        mock_ret = {'error': {'name': 'AuthorizationError',
                              'message': 'Authorization error occurred.'}}
        with patch('salt.acl.PublisherACL.user_is_blacklisted', MagicMock(return_value=True)):
            self.assertEqual(mock_ret, self.local_funcs.publish({'user': 'foo', 'fun': 'test.arg'}))

    def test_publish_cmd_blacklisted(self):
        '''
        Asserts that an AuthorizationError is returned when the command has been blacklisted.
        '''
        mock_ret = {'error': {'name': 'AuthorizationError',
                              'message': 'Authorization error occurred.'}}
        with patch('salt.acl.PublisherACL.user_is_blacklisted', MagicMock(return_value=False)), \
                patch('salt.acl.PublisherACL.cmd_is_blacklisted', MagicMock(return_value=True)):
            self.assertEqual(mock_ret, self.local_funcs.publish({'user': 'foo', 'fun': 'test.arg'}))

    def test_publish_token_not_authenticated(self):
        '''
        Asserts that an AuthenticationError is returned when the token can't authenticate.
        '''
        load = {'user': 'foo', 'fun': 'test.arg', 'tgt': 'test_minion',
                'kwargs': {'token': 'asdfasdfasdfasdf'}}
        mock_ret = {'error': {'name': 'AuthenticationError',
                              'message': 'Authentication error occurred.'}}
        with patch('salt.acl.PublisherACL.user_is_blacklisted', MagicMock(return_value=False)), \
                patch('salt.acl.PublisherACL.cmd_is_blacklisted', MagicMock(return_value=False)):
            self.assertEqual(mock_ret, self.local_funcs.publish(load))

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
            self.assertEqual(mock_ret, self.local_funcs.publish(load))

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
            self.assertEqual(mock_ret, self.local_funcs.publish(load))

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
            self.assertEqual(mock_ret, self.local_funcs.publish(load))

    def test_publish_user_not_authenticated(self):
        '''
        Asserts that an AuthenticationError is returned when the user can't authenticate.
        '''
        load = {'user': 'test', 'fun': 'test.arg', 'tgt': 'test_minion'}
        mock_ret = {'error': {'name': 'AuthenticationError',
                              'message': 'Authentication error occurred.'}}
        with patch('salt.acl.PublisherACL.user_is_blacklisted', MagicMock(return_value=False)), \
                patch('salt.acl.PublisherACL.cmd_is_blacklisted', MagicMock(return_value=False)):
            self.assertEqual(mock_ret, self.local_funcs.publish(load))

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
            self.assertEqual(mock_ret, self.local_funcs.publish(load))

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
            self.assertEqual(mock_ret, self.local_funcs.publish(load))


class FakeCache(object):

    def __init__(self):
        self.data = {}

    def store(self, bank, key, value):
        self.data[bank, key] = value

    def fetch(self, bank, key):
        return self.data[bank, key]


class RemoteFuncsTestCase(TestCase):
    '''
    TestCase for salt.daemons.masterapi.RemoteFuncs class
    '''

    def setUp(self):
        opts = salt.config.master_config(None)
        self.funcs = masterapi.RemoteFuncs(opts)
        self.funcs.cache = FakeCache()

    def test_mine_get(self, tgt_type_key='tgt_type'):
        '''
        Asserts that ``mine_get`` gives the expected results.

        Actually this only tests that:

        - the correct check minions method is called
        - the correct cache key is subsequently used
        '''
        self.funcs.cache.store('minions/webserver', 'mine',
                               dict(ip_addr='2001:db8::1:3'))
        with patch('salt.utils.minions.CkMinions._check_compound_minions',
                   MagicMock(return_value=(dict(
                       minions=['webserver'],
                       missing=[])))):
            ret = self.funcs._mine_get(
                {
                    'id': 'requester_minion',
                    'tgt': 'G@roles:web',
                    'fun': 'ip_addr',
                    tgt_type_key: 'compound',
                }
            )
        self.assertDictEqual(ret, dict(webserver='2001:db8::1:3'))

    def test_mine_get_pre_nitrogen_compat(self):
        '''
        Asserts that pre-Nitrogen API key ``expr_form`` is still accepted.

        This is what minions before Nitrogen would issue.
        '''
        self.test_mine_get(tgt_type_key='expr_form')
