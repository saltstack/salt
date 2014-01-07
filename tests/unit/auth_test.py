# -*- coding: utf-8 -*-
'''
    :codauthor: :email:`Mike Place <mp@saltstack.com>`
'''

# Import Salt Testing libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import patch, call, NO_MOCK, NO_MOCK_REASON
from salt import auth

ensure_in_syspath('../')


@skipIf(NO_MOCK, NO_MOCK_REASON)
class LoadAuthTestCase(TestCase):

    @patch('salt.payload.Serial')
    @patch('salt.loader.auth', return_value={'pam.auth': 'fake_func_str'})
    def setUp(self, auth_mock, serial_mock):  # pylint: disable=W0221
        self.lauth = auth.LoadAuth({})  # Load with empty opts

    def test_load_name(self):
        valid_eauth_load = {'username': 'test_user',
                            'show_timeout': False,
                            'test_password': '',
                            'eauth': 'pam'}

        # To to see if we bail if the eauth key isn't there
        ret = self.lauth.load_name({})
        self.assertEqual(ret, '', "Did not bail when eauth key was missing")

        # Test a case where the loader auth doesn't have the auth type
        # ret = self.lauth.load_name(valid_eauth_load)
        # self.assertEqual(ret, '', "Did not bail when the auth loader didn't have the auth type.")

        with patch('salt.utils.format_call') as format_call_mock:
            expected_ret = call('fake_func_str', {'username': 'test_user', 'test_password': '', 'show_timeout': False, 'eauth': 'pam'})
            self.lauth.load_name(valid_eauth_load)
            format_call_mock.assert_has_calls(expected_ret)
