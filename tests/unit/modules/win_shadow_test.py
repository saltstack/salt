# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch
)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import win_shadow

# Globals
win_shadow.__salt__ = {}

# Make sure this module runs on Windows system
IS_WIN = win_shadow.__virtual__()


@skipIf(not IS_WIN, "This test case runs only on Windows system")
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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(WinShadowTestCase, needs_daemon=False)
