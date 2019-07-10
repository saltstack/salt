# -*- coding: utf-8 -*-
'''
:codeauthor: Shane Lee <slee@saltstack.com>
'''
# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function
import os
import tempfile
from collections import namedtuple

# Import Salt Testing Libs
from tests.support.helpers import destructiveTest
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import patch, NO_MOCK, NO_MOCK_REASON
from tests.support.unit import TestCase, skipIf
from tests.support.mock import MagicMock

# Import Salt Libs
import salt.utils.win_functions
import salt.modules.win_file as win_file
import salt.utils.win_dacl as win_dacl
import salt.modules.temp as temp
import salt.utils.platform
from salt.exceptions import CommandExecutionError


class DummyStat(object):
    st_mode = 33188
    st_ino = 115331251
    st_dev = 44
    st_nlink = 1
    st_uid = 99200001
    st_gid = 99200001
    st_size = 41743
    st_atime = 1552661253
    st_mtime = 1552661253
    st_ctime = 1552661253


WindowsVersion = namedtuple('WinowsVersion', 'major minor')
winver = WindowsVersion(major=10, minor=0)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class WinFileTestCase(TestCase, LoaderModuleMockMixin):
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
                '__utils__': {'dacl.set_perms': win_dacl.set_perms}
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

    @skipIf(True, 'WAR ROOM TEMPORARY SKIP')
    @destructiveTest
    @skipIf(not salt.utils.platform.is_windows(), 'Skip on Non-Windows systems')
    def test_issue_52002_check_file_remove_symlink(self):
        '''
        Make sure that directories including symlinks or symlinks can be removed
        '''
        base = temp.dir(prefix='base-')
        target = os.path.join(base, 'child 1', 'target\\')
        symlink = os.path.join(base, 'child 2', 'link')
        try:
            # Create environment
            self.assertFalse(win_file.directory_exists(target))
            self.assertFalse(win_file.directory_exists(symlink))
            self.assertTrue(win_file.makedirs_(target))
            self.assertTrue(win_file.makedirs_(symlink))
            self.assertTrue(win_file.symlink(target, symlink))
            self.assertTrue(win_file.directory_exists(symlink))
            self.assertTrue(win_file.is_link(symlink))
            # Test removal of directory containing symlink
            self.assertTrue(win_file.remove(base))
            self.assertFalse(win_file.directory_exists(base))
        finally:
            if os.path.exists(base):
                win_file.remove(base)


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
                '__utils__': {'dacl.check_perms': win_dacl.check_perms},
            },
            win_dacl: {
                '__opts__': {'test': False},
            }
        }

    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_file.close()
        win_dacl.set_owner(obj_name=self.temp_file.name,
                           principal=self.current_user)
        win_dacl.set_inheritance(obj_name=self.temp_file.name,
                                 enabled=True)
        self.assertEqual(
            win_dacl.get_owner(obj_name=self.temp_file.name),
            self.current_user)

    def tearDown(self):
        os.remove(self.temp_file.name)

    def test_check_perms_set_owner_test_true(self):
        '''
        Test setting the owner of a file with test=True
        '''
        with patch.dict(win_file.__opts__, {'test': True}), \
                patch.dict(win_dacl.__opts__, {'test': True}):
            expected = {'comment': '',
                        'changes': {'owner': 'Administrators'},
                        'name': self.temp_file.name,
                        'result': None}
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
                    'changes': {'perms': {'Users': {'deny': 'read_execute'}}},
                    'name': self.temp_file.name,
                    'result': None}
        with patch.dict(win_dacl.__opts__, {'test': True}):
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
                    'changes': {'perms': {'Users': {'deny': 'read_execute'}}},
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
                    'changes': {'perms': {'Users': {'grant': 'read_execute'}}},
                    'name': self.temp_file.name,
                    'result': None}
        with patch.dict(win_dacl.__opts__, {'test': True}):
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
                    'changes': {'perms': {'Users': {'grant': 'read_execute'}}},
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
        with patch.dict(win_dacl.__opts__, {'test': True}):
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
        win_dacl.set_inheritance(obj_name=self.temp_file.name,
                                 enabled=False,
                                 clear=True)
        # Set some permissions
        win_dacl.set_permissions(obj_name=self.temp_file.name,
                                 principal='Administrator',
                                 permissions='full_control')
        expected = {'comment': '',
                    'changes': {
                        'perms': {
                            'Administrators': {'grant': 'full_control'},
                            'Users': {'grant': 'read_execute'}},
                        'remove_perms': {
                            'Administrator': {
                                'grant': {'applies to': 'Not Inherited (file)',
                                          'permissions': 'Full control'}}}},
                    'name': self.temp_file.name,
                    'result': None}
        with patch.dict(win_dacl.__opts__, {'test': True}):
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
        win_dacl.set_inheritance(obj_name=self.temp_file.name,
                                 enabled=False,
                                 clear=True)
        # Set some permissions
        win_dacl.set_permissions(obj_name=self.temp_file.name,
                                 principal='Administrator',
                                 permissions='full_control')
        expected = {'comment': '',
                    'changes': {
                        'perms': {
                            'Administrators': {'grant': 'full_control'},
                            'Users': {'grant': 'read_execute'}},
                        'remove_perms': {
                            'Administrator': {
                                'grant': {'applies to': 'Not Inherited (file)',
                                          'permissions': 'Full control'}}}},
                    'name': self.temp_file.name,
                    'result': True}
        ret = win_file.check_perms(
            path=self.temp_file.name,
            grant_perms={'Users': {'perms': 'read_execute'},
                         'Administrators': {'perms': 'full_control'}},
            inheritance=False,
            reset=True)
        self.assertDictEqual(expected, ret)

    def test_stat(self):
        with patch('os.path.exists', MagicMock(return_value=True)), \
                patch('sys.getwindowsversion', MagicMock(return_value=winver)), \
                patch('salt.modules.win_file._resolve_symlink', MagicMock(side_effect=lambda path: path)), \
                patch('salt.modules.win_file.get_uid', MagicMock(return_value=1)), \
                patch('salt.modules.win_file.uid_to_user', MagicMock(return_value='dummy')), \
                patch('salt.modules.win_file.get_pgid', MagicMock(return_value=1)), \
                patch('salt.modules.win_file.gid_to_group', MagicMock(return_value='dummy')), \
                patch('os.stat', MagicMock(return_value=DummyStat())):
            ret = win_file.stats('dummy', None, True)
            self.assertEqual(ret['mode'], '0644')
            self.assertEqual(ret['type'], 'file')
