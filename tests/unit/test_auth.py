# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Mike Place <mp@saltstack.com>`
'''

# Import pytohn libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import patch, call, NO_MOCK, NO_MOCK_REASON, MagicMock

# Import Salt libraries
import salt.master
from tests.support.case import ModuleCase
from salt import auth
import salt.utils.platform


@skipIf(NO_MOCK, NO_MOCK_REASON)
class LoadAuthTestCase(TestCase):

    def setUp(self):  # pylint: disable=W0221
        patches = (
            ('salt.payload.Serial', None),
            ('salt.loader.auth', dict(return_value={'pam.auth': 'fake_func_str', 'pam.groups': 'fake_groups_function_str'})),
            ('salt.loader.eauth_tokens', dict(return_value={'localfs.mk_token': 'fake_func_mktok',
                                                            'localfs.get_token': 'fake_func_gettok',
                                                            'localfs.rm_roken': 'fake_func_rmtok'}))
        )
        for mod, mock in patches:
            if mock:
                patcher = patch(mod, **mock)
            else:
                patcher = patch(mod)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.lauth = auth.LoadAuth({})  # Load with empty opts

    def test_load_name(self):
        valid_eauth_load = {'username': 'test_user',
                            'show_timeout': False,
                            'test_password': '',
                            'eauth': 'pam'}

        # Test a case where the loader auth doesn't have the auth type
        without_auth_type = dict(valid_eauth_load)
        without_auth_type.pop('eauth')
        ret = self.lauth.load_name(without_auth_type)
        self.assertEqual(ret, '', "Did not bail when the auth loader didn't have the auth type.")

        # Test a case with valid params
        with patch('salt.utils.args.arg_lookup',
                   MagicMock(return_value={'args': ['username', 'password']})) as format_call_mock:
            expected_ret = call('fake_func_str')
            ret = self.lauth.load_name(valid_eauth_load)
            format_call_mock.assert_has_calls((expected_ret,), any_order=True)
            self.assertEqual(ret, 'test_user')

    def test_get_groups(self):
        valid_eauth_load = {'username': 'test_user',
                            'show_timeout': False,
                            'test_password': '',
                            'eauth': 'pam'}
        with patch('salt.utils.args.format_call') as format_call_mock:
            expected_ret = call('fake_groups_function_str', {
                'username': 'test_user',
                'test_password': '',
                'show_timeout': False,
                'eauth': 'pam'
                }, expected_extra_kws=auth.AUTH_INTERNAL_KEYWORDS)
            self.lauth.get_groups(valid_eauth_load)
            format_call_mock.assert_has_calls((expected_ret,), any_order=True)


class MasterACLTestCase(ModuleCase):
    '''
    A class to check various aspects of the publisher ACL system
    '''

    def setUp(self):
        self.fire_event_mock = MagicMock(return_value='dummy_tag')
        self.addCleanup(delattr, self, 'fire_event_mock')
        opts = self.get_temp_config('master')

        patches = (
            ('zmq.Context', MagicMock()),
            ('salt.payload.Serial.dumps', MagicMock()),
            ('salt.master.tagify', MagicMock()),
            ('salt.utils.event.SaltEvent.fire_event', self.fire_event_mock),
            ('salt.auth.LoadAuth.time_auth', MagicMock(return_value=True)),
            ('salt.minion.MasterMinion', MagicMock()),
            ('salt.utils.verify.check_path_traversal', MagicMock()),
            ('salt.client.get_local_client', MagicMock(return_value=opts['conf_file'])),
        )
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)

        opts['publisher_acl'] = {}
        opts['publisher_acl_blacklist'] = {}
        opts['master_job_cache'] = ''
        opts['sign_pub_messages'] = False
        opts['con_cache'] = ''
        opts['external_auth'] = {}
        opts['external_auth']['pam'] = \
            {'test_user': [{'*': ['test.ping']},
                           {'minion_glob*': ['foo.bar']},
                           {'minion_func_test': ['func_test.*']}],
             'test_group%': [{'*': ['test.echo']}],
             'test_user_mminion': [{'target_minion': ['test.ping']}],
             '*': [{'my_minion': ['my_mod.my_func']}],
             'test_user_func': [{'*': [{'test.echo': {'args': ['MSG:.*']}},
                                       {'test.echo': {'kwargs': {'text': 'KWMSG:.*',
                                                                 'anything': '.*',
                                                                 'none': None}}},
                                       {'my_mod.*': {'args': ['a.*', 'b.*'],
                                                     'kwargs': {'kwa': 'kwa.*',
                                                                'kwb': 'kwb'}}}]},
                                {'minion1': [{'test.echo': {'args': ['TEST',
                                                                     None,
                                                                     'TEST.*']}},
                                             {'test.empty': {}}]}
                                ]
             }
        self.clear = salt.master.ClearFuncs(opts, MagicMock())
        self.addCleanup(delattr, self, 'clear')

        # overwrite the _send_pub method so we don't have to serialize MagicMock
        self.clear._send_pub = lambda payload: True

        # make sure to return a JID, instead of a mock
        self.clear.mminion.returners = {'.prep_jid': lambda x: 1}

        self.valid_clear_load = {'tgt_type': 'glob',
                                'jid': '',
                                'cmd': 'publish',
                                'tgt': 'test_minion',
                                'kwargs':
                                    {'username': 'test_user',
                                     'password': 'test_password',
                                     'show_timeout': False,
                                     'eauth': 'pam',
                                     'show_jid': False},
                                'ret': '',
                                'user': 'test_user',
                                'key': '',
                                'arg': '',
                                'fun': 'test.ping',
                                }
        self.addCleanup(delattr, self, 'valid_clear_load')

    @skipIf(salt.utils.platform.is_windows(), 'PAM eauth not available on Windows')
    def test_master_publish_name(self):
        '''
        Test to ensure a simple name can auth against a given function.
        This tests to ensure test_user can access test.ping but *not* sys.doc
        '''
        _check_minions_return = {'minions': ['some_minions'], 'missing': []}
        with patch('salt.utils.minions.CkMinions.check_minions', MagicMock(return_value=_check_minions_return)):
            # Can we access test.ping?
            self.clear.publish(self.valid_clear_load)
            self.assertEqual(self.fire_event_mock.call_args[0][0]['fun'], 'test.ping')

            # Are we denied access to sys.doc?
            sys_doc_load = self.valid_clear_load
            sys_doc_load['fun'] = 'sys.doc'
            self.clear.publish(sys_doc_load)
            self.assertNotEqual(self.fire_event_mock.call_args[0][0]['fun'], 'sys.doc')  # If sys.doc were to fire, this would match

    def test_master_publish_group(self):
        '''
        Tests to ensure test_group can access test.echo but *not* sys.doc
        '''
        _check_minions_return = {'minions': ['some_minions'], 'missing': []}
        with patch('salt.utils.minions.CkMinions.check_minions', MagicMock(return_value=_check_minions_return)):
            self.valid_clear_load['kwargs']['user'] = 'new_user'
            self.valid_clear_load['fun'] = 'test.echo'
            self.valid_clear_load['arg'] = 'hello'
            with patch('salt.auth.LoadAuth.get_groups', return_value=['test_group', 'second_test_group']):
                self.clear.publish(self.valid_clear_load)
            # Did we fire test.echo?
            self.assertEqual(self.fire_event_mock.call_args[0][0]['fun'], 'test.echo')

            # Request sys.doc
            self.valid_clear_load['fun'] = 'sys.doc'
            # Did we fire it?
            self.assertNotEqual(self.fire_event_mock.call_args[0][0]['fun'], 'sys.doc')

    def test_master_publish_some_minions(self):
        '''
        Tests to ensure we can only target minions for which we
        have permission with publisher acl.

        Note that in order for these sorts of tests to run correctly that
        you should NOT patch check_minions!
        '''
        self.valid_clear_load['kwargs']['username'] = 'test_user_mminion'
        self.valid_clear_load['user'] = 'test_user_mminion'
        self.clear.publish(self.valid_clear_load)
        self.assertEqual(self.fire_event_mock.mock_calls, [])

    def test_master_not_user_glob_all(self):
        '''
        Test to ensure that we DO NOT access to a given
        function to all users with publisher acl. ex:

        '*':
            my_minion:
                - my_func

        Yes, this seems like a bit of a no-op test but it's
        here to document that this functionality
        is NOT supported currently.

        WARNING: Do not patch this wit
        '''
        self.valid_clear_load['kwargs']['username'] = 'NOT_A_VALID_USERNAME'
        self.valid_clear_load['user'] = 'NOT_A_VALID_USERNAME'
        self.valid_clear_load['fun'] = 'test.ping'
        self.clear.publish(self.valid_clear_load)
        self.assertEqual(self.fire_event_mock.mock_calls, [])

    @skipIf(salt.utils.platform.is_windows(), 'PAM eauth not available on Windows')
    def test_master_minion_glob(self):
        '''
        Test to ensure we can allow access to a given
        function for a user to a subset of minions
        selected by a glob. ex:

        test_user:
            'minion_glob*':
              - glob_mod.glob_func

        This test is a bit tricky, because ultimately the real functionality
        lies in what's returned from check_minions, but this checks a limited
        amount of logic on the way there as well. Note the inline patch.
        '''
        requested_function = 'foo.bar'
        requested_tgt = 'minion_glob1'
        self.valid_clear_load['tgt'] = requested_tgt
        self.valid_clear_load['fun'] = requested_function
        _check_minions_return = {'minions': ['minion_glob1'], 'missing': []}
        with patch('salt.utils.minions.CkMinions.check_minions', MagicMock(return_value=_check_minions_return)):  # Assume that there is a listening minion match
            self.clear.publish(self.valid_clear_load)
        self.assertTrue(self.fire_event_mock.called, 'Did not fire {0} for minion tgt {1}'.format(requested_function, requested_tgt))
        self.assertEqual(self.fire_event_mock.call_args[0][0]['fun'], requested_function, 'Did not fire {0} for minion glob'.format(requested_function))

    def test_master_function_glob(self):
        '''
        Test to ensure that we can allow access to a given
        set of functions in an execution module as selected
        by a glob. ex:

        my_user:
            my_minion:
                'test.*'
        '''
        # Unimplemented
        pass

    @skipIf(salt.utils.platform.is_windows(), 'PAM eauth not available on Windows')
    def test_args_empty_spec(self):
        '''
        Test simple arg restriction allowed.

        'test_user_func':
            minion1:
                - test.empty:
        '''
        _check_minions_return = {'minions': ['minion1'], 'missing': []}
        with patch('salt.utils.minions.CkMinions.check_minions', MagicMock(return_value=_check_minions_return)):
            self.valid_clear_load['kwargs'].update({'username': 'test_user_func'})
            self.valid_clear_load.update({'user': 'test_user_func',
                                          'tgt': 'minion1',
                                          'fun': 'test.empty',
                                          'arg': ['TEST']})
            self.clear.publish(self.valid_clear_load)
            self.assertEqual(self.fire_event_mock.call_args[0][0]['fun'], 'test.empty')

    @skipIf(salt.utils.platform.is_windows(), 'PAM eauth not available on Windows')
    def test_args_simple_match(self):
        '''
        Test simple arg restriction allowed.

        'test_user_func':
            minion1:
                - test.echo:
                    args:
                        - 'TEST'
                        - 'TEST.*'
        '''
        _check_minions_return = {'minions': ['minion1'], 'missing': []}
        with patch('salt.utils.minions.CkMinions.check_minions', MagicMock(return_value=_check_minions_return)):
            self.valid_clear_load['kwargs'].update({'username': 'test_user_func'})
            self.valid_clear_load.update({'user': 'test_user_func',
                                          'tgt': 'minion1',
                                          'fun': 'test.echo',
                                          'arg': ['TEST', 'any', 'TEST ABC']})
            self.clear.publish(self.valid_clear_load)
            self.assertEqual(self.fire_event_mock.call_args[0][0]['fun'], 'test.echo')

    @skipIf(salt.utils.platform.is_windows(), 'PAM eauth not available on Windows')
    def test_args_more_args(self):
        '''
        Test simple arg restriction allowed to pass unlisted args.

        'test_user_func':
            minion1:
                - test.echo:
                    args:
                        - 'TEST'
                        - 'TEST.*'
        '''
        _check_minions_return = {'minions': ['minion1'], 'missing': []}
        with patch('salt.utils.minions.CkMinions.check_minions', MagicMock(return_value=_check_minions_return)):
            self.valid_clear_load['kwargs'].update({'username': 'test_user_func'})
            self.valid_clear_load.update({'user': 'test_user_func',
                                          'tgt': 'minion1',
                                          'fun': 'test.echo',
                                          'arg': ['TEST',
                                                  'any',
                                                  'TEST ABC',
                                                  'arg 3',
                                                  {'kwarg1': 'val1',
                                                   '__kwarg__': True}]})
            self.clear.publish(self.valid_clear_load)
            self.assertEqual(self.fire_event_mock.call_args[0][0]['fun'], 'test.echo')

    def test_args_simple_forbidden(self):
        '''
        Test simple arg restriction forbidden.

        'test_user_func':
            minion1:
                - test.echo:
                    args:
                        - 'TEST'
                        - 'TEST.*'
        '''
        _check_minions_return = {'minions': ['minion1'], 'missing': []}
        with patch('salt.utils.minions.CkMinions.check_minions', MagicMock(return_value=_check_minions_return)):
            self.valid_clear_load['kwargs'].update({'username': 'test_user_func'})
            # Wrong last arg
            self.valid_clear_load.update({'user': 'test_user_func',
                                          'tgt': 'minion1',
                                          'fun': 'test.echo',
                                          'arg': ['TEST', 'any', 'TESLA']})
            self.clear.publish(self.valid_clear_load)
            self.assertEqual(self.fire_event_mock.mock_calls, [])
            # Wrong first arg
            self.valid_clear_load['arg'] = ['TES', 'any', 'TEST1234']
            self.clear.publish(self.valid_clear_load)
            self.assertEqual(self.fire_event_mock.mock_calls, [])
            # Missing the last arg
            self.valid_clear_load['arg'] = ['TEST', 'any']
            self.clear.publish(self.valid_clear_load)
            self.assertEqual(self.fire_event_mock.mock_calls, [])
            # No args
            self.valid_clear_load['arg'] = []
            self.clear.publish(self.valid_clear_load)
            self.assertEqual(self.fire_event_mock.mock_calls, [])

    @skipIf(salt.utils.platform.is_windows(), 'PAM eauth not available on Windows')
    def test_args_kwargs_match(self):
        '''
        Test simple kwargs restriction allowed.

        'test_user_func':
            '*':
                - test.echo:
                    kwargs:
                        text: 'KWMSG:.*'
        '''
        _check_minions_return = {'minions': ['some_minions'], 'missing': []}
        with patch('salt.utils.minions.CkMinions.check_minions', MagicMock(return_value=_check_minions_return)):
            self.valid_clear_load['kwargs'].update({'username': 'test_user_func'})
            self.valid_clear_load.update({'user': 'test_user_func',
                                          'tgt': '*',
                                          'fun': 'test.echo',
                                          'arg': [{'text': 'KWMSG: a message',
                                                   'anything': 'hello all',
                                                   'none': 'hello none',
                                                   '__kwarg__': True}]})
            self.clear.publish(self.valid_clear_load)
            self.assertEqual(self.fire_event_mock.call_args[0][0]['fun'], 'test.echo')

    def test_args_kwargs_mismatch(self):
        '''
        Test simple kwargs restriction allowed.

        'test_user_func':
            '*':
                - test.echo:
                    kwargs:
                        text: 'KWMSG:.*'
        '''
        _check_minions_return = {'minions': ['some_minions'], 'missing': []}
        with patch('salt.utils.minions.CkMinions.check_minions', MagicMock(return_value=_check_minions_return)):
            self.valid_clear_load['kwargs'].update({'username': 'test_user_func'})
            self.valid_clear_load.update({'user': 'test_user_func',
                                          'tgt': '*',
                                          'fun': 'test.echo'})
            # Wrong kwarg value
            self.valid_clear_load['arg'] = [{'text': 'KWMSG a message',
                                             'anything': 'hello all',
                                             'none': 'hello none',
                                             '__kwarg__': True}]
            self.clear.publish(self.valid_clear_load)
            self.assertEqual(self.fire_event_mock.mock_calls, [])
            # Missing kwarg value
            self.valid_clear_load['arg'] = [{'anything': 'hello all',
                                             'none': 'hello none',
                                             '__kwarg__': True}]
            self.clear.publish(self.valid_clear_load)
            self.assertEqual(self.fire_event_mock.mock_calls, [])
            self.valid_clear_load['arg'] = [{'__kwarg__': True}]
            self.clear.publish(self.valid_clear_load)
            self.assertEqual(self.fire_event_mock.mock_calls, [])
            self.valid_clear_load['arg'] = [{}]
            self.clear.publish(self.valid_clear_load)
            self.assertEqual(self.fire_event_mock.mock_calls, [])
            self.valid_clear_load['arg'] = []
            self.clear.publish(self.valid_clear_load)
            self.assertEqual(self.fire_event_mock.mock_calls, [])
            # Missing kwarg allowing any value
            self.valid_clear_load['arg'] = [{'text': 'KWMSG: a message',
                                             'none': 'hello none',
                                             '__kwarg__': True}]
            self.clear.publish(self.valid_clear_load)
            self.assertEqual(self.fire_event_mock.mock_calls, [])
            self.valid_clear_load['arg'] = [{'text': 'KWMSG: a message',
                                             'anything': 'hello all',
                                             '__kwarg__': True}]
            self.clear.publish(self.valid_clear_load)
            self.assertEqual(self.fire_event_mock.mock_calls, [])

    @skipIf(salt.utils.platform.is_windows(), 'PAM eauth not available on Windows')
    def test_args_mixed_match(self):
        '''
        Test mixed args and kwargs restriction allowed.

        'test_user_func':
            '*':
                - 'my_mod.*':
                    args:
                        - 'a.*'
                        - 'b.*'
                    kwargs:
                        'kwa': 'kwa.*'
                        'kwb': 'kwb'
        '''
        _check_minions_return = {'minions': ['some_minions'], 'missing': []}
        with patch('salt.utils.minions.CkMinions.check_minions', MagicMock(return_value=_check_minions_return)):
            self.valid_clear_load['kwargs'].update({'username': 'test_user_func'})
            self.valid_clear_load.update({'user': 'test_user_func',
                                          'tgt': '*',
                                          'fun': 'my_mod.some_func',
                                          'arg': ['alpha',
                                                  'beta',
                                                  'gamma',
                                                  {'kwa': 'kwarg #1',
                                                   'kwb': 'kwb',
                                                   'one_more': 'just one more',
                                                   '__kwarg__': True}]})
            self.clear.publish(self.valid_clear_load)
            self.assertEqual(self.fire_event_mock.call_args[0][0]['fun'],
                             'my_mod.some_func')

    def test_args_mixed_mismatch(self):
        '''
        Test mixed args and kwargs restriction forbidden.

        'test_user_func':
            '*':
                - 'my_mod.*':
                    args:
                        - 'a.*'
                        - 'b.*'
                    kwargs:
                        'kwa': 'kwa.*'
                        'kwb': 'kwb'
        '''
        _check_minions_return = {'minions': ['some_minions'], 'missing': []}
        with patch('salt.utils.minions.CkMinions.check_minions', MagicMock(return_value=_check_minions_return)):
            self.valid_clear_load['kwargs'].update({'username': 'test_user_func'})
            self.valid_clear_load.update({'user': 'test_user_func',
                                          'tgt': '*',
                                          'fun': 'my_mod.some_func'})
            # Wrong arg value
            self.valid_clear_load['arg'] = ['alpha',
                                            'gamma',
                                            {'kwa': 'kwarg #1',
                                             'kwb': 'kwb',
                                             'one_more': 'just one more',
                                             '__kwarg__': True}]
            self.clear.publish(self.valid_clear_load)
            self.assertEqual(self.fire_event_mock.mock_calls, [])
            # Wrong kwarg value
            self.valid_clear_load['arg'] = ['alpha',
                                            'beta',
                                            'gamma',
                                            {'kwa': 'kkk',
                                             'kwb': 'kwb',
                                             'one_more': 'just one more',
                                             '__kwarg__': True}]
            self.clear.publish(self.valid_clear_load)
            self.assertEqual(self.fire_event_mock.mock_calls, [])
            # Missing arg
            self.valid_clear_load['arg'] = ['alpha',
                                            {'kwa': 'kwarg #1',
                                             'kwb': 'kwb',
                                             'one_more': 'just one more',
                                             '__kwarg__': True}]
            self.clear.publish(self.valid_clear_load)
            self.assertEqual(self.fire_event_mock.mock_calls, [])
            # Missing kwarg
            self.valid_clear_load['arg'] = ['alpha',
                                            'beta',
                                            'gamma',
                                            {'kwa': 'kwarg #1',
                                             'one_more': 'just one more',
                                             '__kwarg__': True}]
            self.clear.publish(self.valid_clear_load)
            self.assertEqual(self.fire_event_mock.mock_calls, [])


class AuthACLTestCase(ModuleCase):
    '''
    A class to check various aspects of the publisher ACL system
    '''
    def setUp(self):
        self.auth_check_mock = MagicMock(return_value=True)
        opts = self.get_temp_config('master')

        patches = (
            ('salt.minion.MasterMinion', MagicMock()),
            ('salt.utils.verify.check_path_traversal', MagicMock()),
            ('salt.utils.minions.CkMinions.auth_check', self.auth_check_mock),
            ('salt.auth.LoadAuth.time_auth', MagicMock(return_value=True)),
            ('salt.client.get_local_client', MagicMock(return_value=opts['conf_file'])),
        )
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(delattr, self, 'auth_check_mock')

        opts['publisher_acl'] = {}
        opts['publisher_acl_blacklist'] = {}
        opts['master_job_cache'] = ''
        opts['sign_pub_messages'] = False
        opts['con_cache'] = ''
        opts['external_auth'] = {}
        opts['external_auth']['pam'] = {'test_user': [{'alpha_minion': ['test.ping']}]}

        self.clear = salt.master.ClearFuncs(opts, MagicMock())
        self.addCleanup(delattr, self, 'clear')

        # overwrite the _send_pub method so we don't have to serialize MagicMock
        self.clear._send_pub = lambda payload: True

        # make sure to return a JID, instead of a mock
        self.clear.mminion.returners = {'.prep_jid': lambda x: 1}

        self.valid_clear_load = {'tgt_type': 'glob',
                                 'jid': '',
                                 'cmd': 'publish',
                                 'tgt': 'test_minion',
                                 'kwargs':
                                     {'username': 'test_user',
                                      'password': 'test_password',
                                      'show_timeout': False,
                                      'eauth': 'pam',
                                      'show_jid': False},
                                 'ret': '',
                                 'user': 'test_user',
                                 'key': '',
                                 'arg': '',
                                 'fun': 'test.ping',
                                 }
        self.addCleanup(delattr, self, 'valid_clear_load')

    @skipIf(salt.utils.platform.is_windows(), 'PAM eauth not available on Windows')
    def test_acl_simple_allow(self):
        self.clear.publish(self.valid_clear_load)
        self.assertEqual(self.auth_check_mock.call_args[0][0],
                         [{'alpha_minion': ['test.ping']}])

    def test_acl_simple_deny(self):
        with patch('salt.auth.LoadAuth.get_auth_list', MagicMock(return_value=[{'beta_minion': ['test.ping']}])):
            self.clear.publish(self.valid_clear_load)
            self.assertEqual(self.auth_check_mock.call_args[0][0],
                             [{'beta_minion': ['test.ping']}])
