# -*- coding: utf-8 -*-
'''
    :codauthor: :email:`Mike Place <mp@saltstack.com>`
'''

# Import Salt Testing libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import patch, call, NO_MOCK, NO_MOCK_REASON

# Import Salt libraries
import salt.master
from salt import auth

ensure_in_syspath('../')


@skipIf(NO_MOCK, NO_MOCK_REASON)
class LoadAuthTestCase(TestCase):

    @patch('salt.payload.Serial')
    @patch('salt.loader.auth', return_value={'pam.auth': 'fake_func_str', 'pam.groups': 'fake_groups_function_str'})
    def setUp(self, auth_mock, serial_mock):  # pylint: disable=W0221
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
        with patch('salt.utils.format_call') as format_call_mock:
            expected_ret = call('fake_func_str', {
                'username': 'test_user',
                'test_password': '',
                'show_timeout': False,
                'eauth': 'pam'
            })
            ret = self.lauth.load_name(valid_eauth_load)
            format_call_mock.assert_has_calls(expected_ret)


    def test_get_groups(self):
        valid_eauth_load = {'username': 'test_user',
                            'show_timeout': False,
                            'test_password': '',
                            'eauth': 'pam'}
        with patch('salt.utils.format_call') as format_call_mock:
            expected_ret = call('fake_groups_function_str', {
                'username': 'test_user',
                'test_password': '',
                'show_timeout': False,
                'eauth': 'pam'
                })
            self.lauth.get_groups(valid_eauth_load)
            format_call_mock.assert_has_calls(expected_ret)


@patch('salt.utils.event.tagify', return_value=[])
@patch('salt.utils.event.SaltEvent.fire_event', return_value='dummy_tag')
@patch('salt.auth.LoadAuth.time_auth', return_value=True)
@patch('salt.utils.minions.CkMinions.check_minions', return_value='')
class MasterAuthTestCase(TestCase):

    @patch('salt.minion.MasterMinion')
    def setUp(self, mminion_mock):
        self.clear = salt.master.ClearFuncs({'sock_dir': '',
                                             'conf_file': '',
                                             'transport': '',
                                             'default_include': '',
                                             'extension_modules': '',
                                             'client_acl_blacklist': {},
                                            'external_auth': {'pam': {'test_user': [{'*': ['test.ping']}], 'test_group%': [{'*': ['test.echo']}]}},
                                            'master_job_cache': '',
                                            },
                                            None, None, None)


    def test_master_publish_name(self, ck_minions_mock, time_auth_mock, fire_event_mock, tagify_mock):
        '''
        Test to ensure a simple name can auth against a given function
        '''
        valid_clear_load = {'tgt_type': 'glob',
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
                                'fun': 'test.ping'
                            }
        ret = self.clear.publish(valid_clear_load)
        expected_calls = [call('*', 'glob'), call('test_minion', 'glob'), call('test_minion', 'glob')]
        ck_minions_mock.assert_has_calls(expected_calls)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(LoadAuthTestCase, needs_daemon=False)
