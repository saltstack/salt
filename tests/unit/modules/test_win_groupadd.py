# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.modules.win_groupadd as win_groupadd

# Import Other Libs
# pylint: disable=unused-import
try:
    import win32com
    import pythoncom
    import pywintypes
    HAS_WIN_LIBS = True
except ImportError:
    HAS_WIN_LIBS = False
# pylint: enable=unused-import


@skipIf(not HAS_WIN_LIBS, 'win_groupadd unit tests can only be run if win32com, pythoncom, and pywintypes are installed')
@skipIf(NO_MOCK, NO_MOCK_REASON)
class WinGroupTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.win_groupadd
    '''
    def setup_loader_modules(self):
        return {
            win_groupadd: {'__opts__': {'test': False}}
        }

    # 'add' function tests: 1

    def test_add(self):
        '''
        Test if it add the specified group
        '''
        self.assertDictEqual(win_groupadd.add('foo'),
                             {'changes': [], 'name': 'foo', 'result': None,
                              'comment': 'The group foo already exists.'})

    # 'delete' function tests: 1

    def test_delete(self):
        '''
        Test if it remove the specified group
        '''
        self.assertDictEqual(win_groupadd.delete('foo'),
                             {'changes': [], 'name': 'foo', 'result': None,
                              'comment': 'The group foo does not exists.'})

    # 'info' function tests: 1

    def test_info(self):
        '''
        Test if it return information about a group.
        '''
        with patch(win_groupadd.win32.client, 'flag', None):
            self.assertDictEqual(win_groupadd.info('dc=salt'),
                                 {'gid': None,
                                  'members': ['dc=\\user1'],
                                  'passwd': None,
                                  'name': 'WinNT://./dc=salt,group'})

        with patch(win_groupadd.win32.client, 'flag', 1):
            self.assertFalse(win_groupadd.info('dc=salt'))

        with patch(win_groupadd.win32.client, 'flag', 2):
            self.assertFalse(win_groupadd.info('dc=salt'))

    # 'getent' function tests: 1

    def test_getent(self):
        '''
        Test if it return info on all groups
        '''
        with patch.dict(win_groupadd.__context__, {'group.getent': True}):
            self.assertTrue(win_groupadd.getent())

    # 'adduser' function tests: 1

    def test_adduser(self):
        '''
        Test if it add a user to a group
        '''
        with patch(win_groupadd.win32.client, 'flag', None):
            self.assertDictEqual(win_groupadd.adduser('dc=foo', 'dc=\\username'),
                                 {'changes': {'Users Added': ['dc=\\username']},
                                  'comment': '', 'name': 'dc=foo', 'result': True})

        with patch(win_groupadd.win32.client, 'flag', 1):
            comt = ('Failed to add dc=\\username to group dc=foo.  C')
            self.assertDictEqual(win_groupadd.adduser('dc=foo', 'dc=\\username'),
                                 {'changes': {'Users Added': []}, 'name': 'dc=foo',
                                  'comment': comt, 'result': False})

    # 'deluser' function tests: 1

    def test_deluser(self):
        '''
        Test if it remove a user to a group
        '''
        ret = {'changes': {'Users Removed': []},
               'comment': 'User dc=\\username is not a member of dc=foo',
               'name': 'dc=foo', 'result': None}

        self.assertDictEqual(win_groupadd.deluser('dc=foo', 'dc=\\username'),
                             ret)

    # 'members' function tests: 1

    def test_members(self):
        '''
        Test if it remove a user to a group
        '''
        comment = ['Failure accessing group dc=foo.  C']
        ret = {'name': 'dc=foo', 'result': False, 'comment': comment,
               'changes': {'Users Added': [], 'Users Removed': []}}

        with patch(win_groupadd.win32.client, 'flag', 2):
            self.assertDictEqual(win_groupadd.members
                                 ('dc=foo', 'dc=\\user1,dc=\\user2,dc=\\user3'),
                                 ret)

        with patch(win_groupadd.win32.client, 'flag', 1):
            comment = ['Failed to add dc=\\user2 to dc=foo.  C',
                       'Failed to remove dc=\\user1 from dc=foo.  C']
            ret.update({'comment': comment, 'result': False})
            self.assertDictEqual(win_groupadd.members('dc=foo', 'dc=\\user2'), ret)

        with patch(win_groupadd.win32.client, 'flag', None):
            comment = ['dc=foo membership is correct']
            ret.update({'comment': comment, 'result': None})
            self.assertDictEqual(win_groupadd.members('dc=foo', 'dc=\\user1'), ret)
