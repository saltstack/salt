# -*- coding: utf-8 -*-
'''
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
'''

# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch
)

# Import Salt Libs
import salt.modules.win_shadow as win_shadow
from salt.exceptions import CommandExecutionError


try:
    import win32security
    import winerror

    class WinError(win32security.error):
        def __init__(self):
            self.winerror = 0
            self.strerror = ''

    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


class WinShadowTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.win_shadow
    '''
    def setup_loader_modules(self):
        modules_globals = {
            win_shadow: {
                '__salt__': {
                    #'user.info': MagicMock(return_value=True),
                    'user.update': MagicMock(return_value=True)}}}
        return modules_globals

    def test_info(self):
        '''
        Test if it return information for the specified user
        '''
        mock_info = MagicMock(return_value={'name': 'SALT',
                                            'password_changed': '',
                                            'expiration_date': ''})
        expected = {'name': 'SALT',
                    'passwd': 'Unavailable',
                    'lstchg': '',
                    'min': '',
                    'max': '',
                    'warn': '',
                    'inact': '',
                    'expire': ''}
        with patch.dict(win_shadow.__salt__, {'user.info': mock_info}):
            self.assertDictEqual(win_shadow.info('SALT'), expected)

    @skipIf(not HAS_WIN32, 'Requires win32 libraries')
    def test_set_password(self):
        '''
        Test if it set the password for a named user.
        '''
        mock_cmd = MagicMock(return_value={'retcode': False})
        mock_info = MagicMock(return_value={'name': 'SALT',
                                            'password_changed': '',
                                            'expiration_date': ''})
        with patch.dict(win_shadow.__salt__, {'cmd.run_all': mock_cmd,
                                              'user.info': mock_info}):
            self.assertTrue(win_shadow.set_password('root', 'mysecretpassword'))

    @skipIf(not HAS_WIN32, 'Requires win32 libraries')
    def test_verify_password_valid(self):
        '''
        Test verify_password with a valid password
        '''
        mock_info = MagicMock(return_value={'name': 'SALT',
                                                 'password_changed': '',
                                                 'expiration_date': ''})
        mock_logon_user = MagicMock()
        with patch.dict(win_shadow.__salt__, {'user.info': mock_info}), \
                patch('salt.modules.win_shadow.win32security.LogonUser',
                      mock_logon_user):
            self.assertTrue(
                win_shadow.verify_password(name='spongebob',
                                           password='P@ssW0rd'))

    @skipIf(not HAS_WIN32, 'Requires win32 libraries')
    def test_verify_password_invalid(self):
        '''
        Test verify_password with an invalid password
        '''
        mock_user_info = MagicMock(return_value={'account_locked': False})

        win_error = WinError()
        win_error.winerror = 1326

        mock_logon_user = MagicMock(side_effect=win_error)

        with patch.dict(win_shadow.__salt__, {'user.info': mock_user_info}), \
                patch('salt.modules.win_shadow.win32security.LogonUser',
                      mock_logon_user):
            self.assertFalse(
                win_shadow.verify_password(name='spongebob',
                                           password='P@ssW0rd'))

    @skipIf(not HAS_WIN32, 'Requires win32 libraries')
    def test_verify_password_invalid_account_gets_locked(self):
        '''
        Test verify_password with an invalid password that locks the account
        '''
        mock_info = MagicMock(side_effect=[{'account_locked': False},
                                           {'account_locked': True}])
        mock_update = MagicMock(return_value=True)

        win_error = WinError()
        win_error.winerror = winerror.ERROR_LOGON_FAILURE

        mock_logon_user = MagicMock(side_effect=win_error)

        with patch.dict(win_shadow.__salt__, {'user.info': mock_info}), \
                patch.dict(win_shadow.__salt__, {'user.update': mock_update}), \
                patch('salt.modules.win_shadow.win32security.LogonUser',
                      mock_logon_user):
            ret = win_shadow.verify_password(name='spongebob',
                                             password='P@ssW0rd')
            mock_update.called_once_with('spongebob', unlock_account=True)
            self.assertFalse(ret)

    @skipIf(not HAS_WIN32, 'Requires win32 libraries')
    def test_verify_password_disabled_account(self):
        '''
        Test verify_password where LogonUser encounters another error
        '''
        mock_info = MagicMock(return_value={'account_locked': False})

        win_error = WinError()
        win_error.winerror = winerror.ERROR_ACCOUNT_DISABLED

        mock_logon_user = MagicMock(side_effect=win_error)

        with patch.dict(win_shadow.__salt__, {'user.info': mock_info}), \
                patch('salt.modules.win_shadow.win32security.LogonUser',
                      mock_logon_user):
            ret = win_shadow.verify_password(name='spongebob',
                                             password='P@ssW0rd')
            self.assertTrue(ret)

    @skipIf(not HAS_WIN32, 'Requires win32 libraries')
    def test_verify_password_locked_account(self):
        '''
        Test verify_password where LogonUser encounters another error
        '''
        mock_info = MagicMock(return_value={'account_locked': False})

        win_error = WinError()
        win_error.winerror = winerror.ERROR_ACCOUNT_LOCKED_OUT

        mock_logon_user = MagicMock(side_effect=win_error)

        with patch.dict(win_shadow.__salt__, {'user.info': mock_info}), \
             patch('salt.modules.win_shadow.win32security.LogonUser',
                   mock_logon_user):
            with self.assertRaises(CommandExecutionError):
                win_shadow.verify_password(name='spongebob',
                                           password='P@ssW0rd')

    @skipIf(not HAS_WIN32, 'Requires win32 libraries')
    def test_verify_password_unknown_error(self):
        '''
        Test verify_password where LogonUser encounters another error
        '''
        mock_info = MagicMock(return_value={'account_locked': False})

        win_error = WinError()
        win_error.winerror = 7

        mock_logon_user = MagicMock(side_effect=win_error)

        with patch.dict(win_shadow.__salt__, {'user.info': mock_info}), \
                patch('salt.modules.win_shadow.win32security.LogonUser',
                      mock_logon_user):
            with self.assertRaises(CommandExecutionError):
                win_shadow.verify_password(name='spongebob',
                                           password='P@ssW0rd')
