# -*- coding: utf-8 -*-
'''
:codeauthor: :email:`Shane Lee <slee@saltstack.com>`
'''
# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function
import os

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.modules.win_file as win_file
from salt.exceptions import CommandExecutionError
import salt.utils.platform


@skipIf(NO_MOCK, NO_MOCK_REASON)
class WinFileTestCase(TestCase):
    '''
        Test cases for salt.modules.win_file
    '''
    FAKE_RET = {'fake': 'ret data'}
    if salt.utils.platform.is_windows():
        FAKE_PATH = os.sep.join(['C:', 'path', 'does', 'not', 'exist'])
    else:
        FAKE_PATH = os.sep.join(['path', 'does', 'not', 'exist'])

    def test_issue_43328_stats(self):
        '''
        Make sure that a CommandExecutionError is raised if the file does NOT
        exist
        '''
        with patch('os.path.exists', return_value=False):
            self.assertRaises(CommandExecutionError,
                              win_file.stats,
                              self.FAKE_PATH)

    def test_issue_43328_check_perms_no_ret(self):
        '''
        Make sure that a CommandExecutionError is raised if the file does NOT
        exist
        '''
        with patch('os.path.exists', return_value=False):
            self.assertRaises(
                CommandExecutionError, win_file.check_perms, self.FAKE_PATH)
