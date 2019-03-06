# -*- coding: utf-8 -*-
'''
:codeauthor: Shane Lee <slee@saltstack.com>
'''
# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function
import os

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import patch, NO_MOCK, NO_MOCK_REASON

# Import Salt Libs
import salt.modules.win_file as win_file
import salt.modules.file as default_file
import salt.modules.temp as temp
from salt.exceptions import CommandExecutionError
import salt.utils.platform
import salt.utils.win_dacl


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

    def setup_loader_modules(self):
        return {
            win_file: {
                '__opts__': {
                    'test': False}},
            default_file: {
                '__opts__': {
                    'test': False}}}

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

    def test_issue_52002_check_file_remove_symlink(self):
        '''
        Make sure that directories including symlinks or symlinks can be removed
        '''
        base = temp.dir(prefix='base')
        target = os.path.join(base, 'child 1', 'target/')
        symlink = os.path.join(base, 'child 2', 'link')
        self.assertFalse(win_file.directory_exists(target))
        self.assertFalse(win_file.directory_exists(symlink))
        self.assertTrue(default_file.makedirs_(target))
        self.assertTrue(win_file.directory_exists(symlink))
        self.assertTrue(win_file.symlink(target, symlink))
        self.assertTrue(win_file.is_link(symlink))
        self.assertTrue(win_file.remove(base))
        self.assertFalse(win_file.directory_exists(base))
