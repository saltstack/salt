# -*- coding: utf-8 -*-
'''
:codeauthor: :email:`Shane Lee <slee@saltstack.com>`
'''
# Import Python Libs
from __future__ import absolute_import
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
import salt.utils


@skipIf(NO_MOCK, NO_MOCK_REASON)
class WinFileTestCase(TestCase):
    '''
        Test cases for salt.modules.win_file
    '''
    FAKE_RET = {'fake': 'ret data'}
    if salt.utils.is_windows():
        FAKE_PATH = os.sep.join(['C:', 'path', 'does', 'not', 'exist'])
    else:
        FAKE_PATH = os.sep.join(['path', 'does', 'not', 'exist'])

    def test_issue_43328_stats(self):
        '''
        Make sure that an empty dictionary is returned if the file doesn't exist
        '''
        with patch('os.path.exists', return_value=False):
            ret = win_file.stats(self.FAKE_PATH)
            self.assertEqual(ret, {})

    def test_issue_43328_check_perms_ret_passed(self):
        '''
        Make sure that ret is returned if the file doesn't exist and ret is
        passed
        '''
        with patch('os.path.exists', return_value=False):
            ret = win_file.check_perms(self.FAKE_PATH, ret=self.FAKE_RET)
            self.assertEqual(ret, self.FAKE_RET)

    def test_issue_43328_check_perms_no_ret(self):
        '''
        Make sure that a CommandExecutionError is raised if the file doesn't
        exist and ret is NOT passed
        '''
        with patch('os.path.exists', return_value=False):
            self.assertRaises(
                CommandExecutionError, win_file.check_perms, self.FAKE_PATH)
