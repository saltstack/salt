# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch
)

# Import Salt Libs
import salt.modules.win_shadow as win_shadow
import salt.utils

# Globals
win_shadow.__salt__ = {}


@skipIf(not salt.utils.is_windows(), 'This test case runs only on Windows systems')
class WinShadowTestCase(TestCase):
    '''
    Test cases for salt.modules.win_shadow
    '''
    # 'info' function tests: 1

    def test_info(self):
        '''
        Test if it return information for the specified user
        '''
        self.assertDictEqual(win_shadow.info('SALT'), {'name': 'SALT',
                                                       'passwd': '',
                                                       'lstchg': '',
                                                       'min': '',
                                                       'max': '',
                                                       'warn': '',
                                                       'inact': '',
                                                       'expire': ''})

    # 'set_password' function tests: 1

    def test_set_password(self):
        '''
        Test if it set the password for a named user.
        '''
        mock_cmd = MagicMock(return_value={'retcode': False})
        with patch.dict(win_shadow.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertTrue(win_shadow.set_password('root', 'mysecretpassword'))
