# -*- coding: utf-8 -*-
'''
:codeauthor: Shane Lee <slee@saltstack.com>
'''
# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function
import os
import tempfile

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)
from tests.support.helpers import destructiveTest

# Import Salt Libs
import salt.modules.win_file as win_file
import salt.utils.platform
import salt.utils.win_functions
import salt.utils.win_dacl
from salt.exceptions import CommandExecutionError


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
                '__utils__': {'dacl.set_perms': salt.utils.win_dacl.set_perms}
            }
        }

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


@destructiveTest
@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not salt.utils.platform.is_windows(), 'Requires Pywin32 libraries')
class WinFileCheckPermsTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for the check_perms function in salt.modules.win_file
    '''
    temp_file = ''
    current_user = ''

    def setup_loader_modules(self):
        self.current_user = salt.utils.win_functions.get_current_user(False)
        return {
            win_file: {
                '__opts__': {'test': False},
            }
        }

    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_file.close()
        salt.utils.win_dacl.set_owner(obj_name=self.temp_file.name,
                                      principal=self.current_user)
        salt.utils.win_dacl.set_inheritance(obj_name=self.temp_file.name,
                                            enabled=True)
        self.assertEqual(
            salt.utils.win_dacl.get_owner(obj_name=self.temp_file.name),
            self.current_user)

    def tearDown(self):
        os.remove(self.temp_file.name)

    def test_check_perms_set_owner_test_true(self):
        '''
        Test setting the owner of a file with test=True
        '''
        expected = {'comment': '',
                    'changes': {'owner': 'Administrators'},
                    'name': self.temp_file.name,
                    'result': None}
        with patch.dict(win_file.__opts__, {'test': True}):
            ret = win_file.check_perms(path=self.temp_file.name,
                                       owner='Administrators',
                                       inheritance=None)
            self.assertDictEqual(expected, ret)

    def test_check_perms_set_owner(self):
        '''
        Test setting the owner of a file
        '''
        expected = {'comment': '',
                    'changes': {'owner': 'Administrators'},
                    'name': self.temp_file.name,
                    'result': True}
        ret = win_file.check_perms(path=self.temp_file.name,
                                   owner='Administrators',
                                   inheritance=None)
        self.assertDictEqual(expected, ret)

    def test_check_perms_deny_test_true(self):
        '''
        Test setting deny perms on a file with test=True
        '''
        expected = {'comment': '',
                    'changes': {'deny_perms': {'Users': {'perms': 'read_execute'}}},
                    'name': self.temp_file.name,
                    'result': None}
        with patch.dict(win_file.__opts__, {'test': True}):
            ret = win_file.check_perms(
                path=self.temp_file.name,
                deny_perms={'Users': {'perms': 'read_execute'}},
                inheritance=None)
            self.assertDictEqual(expected, ret)

    def test_check_perms_deny(self):
        '''
        Test setting deny perms on a file
        '''
        expected = {'comment': '',
                    'changes': {
                        'deny_perms': {'Users': {'perms': 'read_execute'}}},
                    'name': self.temp_file.name,
                    'result': True}
        ret = win_file.check_perms(
            path=self.temp_file.name,
            deny_perms={'Users': {'perms': 'read_execute'}},
            inheritance=None)
        self.assertDictEqual(expected, ret)

    def test_check_perms_grant_test_true(self):
        '''
        Test setting grant perms on a file with test=True
        '''
        expected = {'comment': '',
                    'changes': {'grant_perms': {'Users': {'perms': 'read_execute'}}},
                    'name': self.temp_file.name,
                    'result': None}
        with patch.dict(win_file.__opts__, {'test': True}):
            ret = win_file.check_perms(
                path=self.temp_file.name,
                grant_perms={'Users': {'perms': 'read_execute'}},
                inheritance=None)
            self.assertDictEqual(expected, ret)

    def test_check_perms_grant(self):
        '''
        Test setting grant perms on a file
        '''
        expected = {'comment': '',
                    'changes': {
                        'grant_perms': {'Users': {'perms': 'read_execute'}}},
                    'name': self.temp_file.name,
                    'result': True}
        ret = win_file.check_perms(
            path=self.temp_file.name,
            grant_perms={'Users': {'perms': 'read_execute'}},
            inheritance=None)
        self.assertDictEqual(expected, ret)

    def test_check_perms_inheritance_false_test_true(self):
        '''
        Test setting inheritance to False with test=True
        '''
        expected = {'comment': '',
                    'changes': {'inheritance': False},
                    'name': self.temp_file.name,
                    'result': None}
        with patch.dict(win_file.__opts__, {'test': True}):
            ret = win_file.check_perms(path=self.temp_file.name,
                                       inheritance=False)
            self.assertDictEqual(expected, ret)

    def test_check_perms_inheritance_false(self):
        '''
        Test setting inheritance to False
        '''
        expected = {'comment': '',
                    'changes': {'inheritance': False},
                    'name': self.temp_file.name,
                    'result': True}
        ret = win_file.check_perms(path=self.temp_file.name,
                                   inheritance=False)
        self.assertDictEqual(expected, ret)

    def test_check_perms_inheritance_true(self):
        '''
        Test setting inheritance to true when it's already true (default)
        '''
        expected = {'comment': '',
                    'changes': {},
                    'name': self.temp_file.name,
                    'result': True}
        ret = win_file.check_perms(path=self.temp_file.name,
                                   inheritance=True)
        self.assertDictEqual(expected, ret)

    def test_check_perms_reset_test_true(self):
        '''
        Test resetting perms with test=True. This shows minimal changes
        '''
        # Turn off inheritance
        salt.utils.win_dacl.set_inheritance(obj_name=self.temp_file.name,
                                            enabled=False,
                                            clear=True)
        # Set some permissions
        salt.utils.win_dacl.set_permissions(obj_name=self.temp_file.name,
                                            principal='Administrator',
                                            permissions='full_control')
        expected = {'comment': '',
                    'changes': {
                        'grant_perms': {
                            'Administrators': {'perms': 'full_control'},
                            'Users': {'perms': 'read_execute'}},
                        'remove_perms': {
                            'Administrator': {
                                'grant': {'applies to': 'Not Inherited (file)',
                                          'inherited': False,
                                          'permissions': ['Full control']}}}},
                    'name': self.temp_file.name,
                    'result': None}
        with patch.dict(win_file.__opts__, {'test': True}):
            ret = win_file.check_perms(
                path=self.temp_file.name,
                grant_perms={'Users': {'perms': 'read_execute'},
                             'Administrators': {'perms': 'full_control'}},
                inheritance=False,
                reset=True)
            self.assertDictEqual(expected, ret)

    def test_check_perms_reset(self):
        '''
        Test resetting perms on a File
        '''
        # Turn off inheritance
        salt.utils.win_dacl.set_inheritance(obj_name=self.temp_file.name,
                                            enabled=False,
                                            clear=True)
        # Set some permissions
        salt.utils.win_dacl.set_permissions(obj_name=self.temp_file.name,
                                            principal='Administrator',
                                            permissions='full_control')
        expected = {'comment': '',
                    'changes': {
                        'grant_perms': {
                            'Administrators': {'perms': 'full_control'},
                            'Users': {'perms': 'read_execute'}},
                        'remove_perms': {
                            'Administrator': {
                                'grant': {'applies to': 'Not Inherited (file)',
                                          'inherited': False,
                                          'permissions': ['Full control']}}}},
                    'name': self.temp_file.name,
                    'result': True}
        ret = win_file.check_perms(
            path=self.temp_file.name,
            grant_perms={'Users': {'perms': 'read_execute'},
                         'Administrators': {'perms': 'full_control'}},
            inheritance=False,
            reset=True)
        self.assertDictEqual(expected, ret)
