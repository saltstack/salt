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
    MagicMock,
    Mock,
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
        Test adding a new group
        '''
        info = MagicMock(return_value=False)
        with patch.object(win_groupadd, 'info', info),\
             patch.object(win_groupadd, '_get_computer_object', Mock()):
            self.assertDictEqual(win_groupadd.add('foo'),
                                 {'changes': ['Successfully created group foo'],
                                  'name': 'foo',
                                  'result': True,
                                  'comment': ''})

    def test_add_group_exists(self):
        '''
        Test adding a new group if the group already exists
        '''
        info = MagicMock(return_value={'name': 'foo',
                                       'passwd': None,
                                       'gid': None,
                                       'members': ['HOST\\spongebob']})
        with patch.object(win_groupadd, 'info', info),\
             patch.object(win_groupadd, '_get_computer_object', Mock()):
            self.assertDictEqual(win_groupadd.add('foo'),
                                 {'changes': [], 'name': 'foo', 'result': None,
                                  'comment': 'The group foo already exists.'})

    def test_add_error(self):
        '''
        Test adding a group and encountering an error
        '''
        class CompObj(object):
            def Create(self, type, name):
                raise pywintypes.com_error(-2147352567, 'Exception occurred.', (0, None, 'C', None, 0, -2146788248), None)

        compobj_mock = MagicMock(return_value=CompObj())

        info = MagicMock(return_value=False)
        with patch.object(win_groupadd, 'info', info),\
             patch.object(win_groupadd, '_get_computer_object', compobj_mock):
            self.assertDictEqual(win_groupadd.add('foo'),
                                 {'changes': [],
                                  'name': 'foo',
                                  'result': False,
                                  'comment': 'Failed to create group foo. C'})

    # 'delete' function tests: 1

    def test_delete(self):
        '''
        Test removing a group
        '''
        info = MagicMock(return_value={'name': 'foo',
                                       'passwd': None,
                                       'gid': None,
                                       'members': ['HOST\\spongebob']})
        with patch.object(win_groupadd, 'info', info), \
             patch.object(win_groupadd, '_get_computer_object', Mock()):
            self.assertDictEqual(
                win_groupadd.delete('foo'),
                {'changes': ['Successfully removed group foo'],
                 'name': 'foo',
                 'result': True,
                 'comment': ''})

    def test_delete_no_group(self):
        '''
        Test removing a group that doesn't exists
        '''
        info = MagicMock(return_value=False)
        with patch.object(win_groupadd, 'info', info), \
             patch.object(win_groupadd, '_get_computer_object', Mock()):
            self.assertDictEqual(win_groupadd.delete('foo'),
                                 {'changes': [], 'name': 'foo', 'result': None,
                                  'comment': 'The group foo does not exists.'})

    def test_delete_error(self):
        '''
        Test removing a group and encountering an error
        '''
        class CompObj(object):
            def Delete(self, type, name):
                raise pywintypes.com_error(-2147352567, 'Exception occurred.', (0, None, 'C', None, 0, -2146788248), None)

        compobj_mock = MagicMock(return_value=CompObj())

        info = MagicMock(return_value={'name': 'foo',
                                       'passwd': None,
                                       'gid': None,
                                       'members': ['HOST\\spongebob']})
        with patch.object(win_groupadd, 'info', info),\
             patch.object(win_groupadd, '_get_computer_object', compobj_mock):
            self.assertDictEqual(
                win_groupadd.delete('foo'),
                {'changes': [],
                 'name': 'foo',
                 'result': False,
                 'comment': 'Failed to remove group foo.  C'})


    # 'info' function tests: 1

    def test_info(self):
        '''
        Test if it return information about a group.
        '''
        members = MagicMock(return_value=['HOST\\steve'])
        with patch.object(win_groupadd, '_get_group_object', Mock()), \
             patch.object(win_groupadd, '_get_group_members', members):
            self.assertDictEqual(win_groupadd.info('salt'),
                                 {'gid': None,
                                  'members': ['user1'],
                                  'passwd': None,
                                  'name': 'salt'})

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
        Test adding a user to a group
        '''
        members = MagicMock(return_value=['HOST\\steve'])
        with patch.object(win_groupadd, '_get_group_object', Mock()),\
                patch.object(win_groupadd, '_get_group_members', members),\
                patch('salt.utils.win_functions.get_sam_name', return_value='HOST\\spongebob'):
            self.assertDictEqual(
                win_groupadd.adduser('foo', 'spongebob'),
                {'changes': {'Users Added': ['spongebob']},
                 'comment': '',
                 'name': 'foo',
                 'result': True})

    def test_add_user_already_exists(self):
        '''
        Test adding a user that already exists
        '''
        members = MagicMock(return_value=['HOST\\steve'])
        with patch.object(win_groupadd, '_get_group_object', Mock()), \
             patch.object(win_groupadd, '_get_group_members', members), \
             patch('salt.utils.win_functions.get_sam_name', return_value='HOST\\spongebob'):
            self.assertDictEqual(
                win_groupadd.adduser('foo', 'spongebob'),
                {'changes': {'Users Added': ['spongebob']},
                 'comment': '',
                 'name': 'foo',
                 'result': True})

    def test_add_user_error(self):
        '''
        Test adding a user and encountering an error
        '''
        # Create mock group object
        class GroupObj(object):
            def Add(self, name):
                raise pywintypes.com_error(-2147352567, 'Exception occurred.', (0, None, 'C', None, 0, -2146788248), None)

        groupobj_mock = MagicMock(return_value=GroupObj())
        members = MagicMock(return_value=['HOST\\steve'])
        with patch.object(win_groupadd, '_get_group_object', groupobj_mock):
            with patch.object(win_groupadd, '_get_group_members', members):
                comt = ('Failed to add username to group foo.  C')
                self.assertDictEqual(
                    win_groupadd.adduser('foo', 'username'),
                    {'changes': {'Users Added': []},
                     'name': 'foo',
                     'comment': comt,
                     'result': False})

    # 'deluser' function tests: 1

    def test_deluser(self):
        '''
        Test removing a user from a group
        '''
        # Test removing a user
        members = MagicMock(return_value=['HOST\\spongebob'])
        with patch.object(win_groupadd, '_get_group_object', Mock()), \
             patch.object(win_groupadd, '_get_group_members', members), \
             patch('salt.utils.win_functions.get_sam_name', return_value='HOST\\spongebob'):
            ret = {'changes': {'Users Removed': ['spongebob']},
                   'comment': '',
                   'name': 'foo', 'result': True}
            self.assertDictEqual(win_groupadd.deluser('foo', 'spongebob'), ret)

    def test_deluser_no_user(self):
        '''
        Test removing a user from a group and that user is not a member of the
        group
        '''

        # Test removing a user that's not in the group
        members = MagicMock(return_value=['HOST\\steve'])
        with patch.object(win_groupadd, '_get_group_object', Mock()), \
                patch.object(win_groupadd, '_get_group_members', members), \
                patch('salt.utils.win_functions.get_sam_name', return_value='HOST\\spongebob'):
            ret = {'changes': {'Users Removed': []},
                   'comment': 'User username is not a member of foo',
                   'name': 'foo', 'result': None}
            self.assertDictEqual(win_groupadd.deluser('foo', 'username'), ret)

    def test_deluser_error(self):
        '''
        Test removing a user and encountering an error
        '''
        class GroupObj(object):
            def Remove(self, name):
                raise pywintypes.com_error(-2147352567, 'Exception occurred.', (0, None, 'C', None, 0, -2146788248), None)

        groupobj_mock = MagicMock(return_value=GroupObj())

        members = MagicMock(return_value=['HOST\\spongebob'])
        with patch.object(win_groupadd, '_get_group_object', groupobj_mock), \
                patch.object(win_groupadd, '_get_group_members', members), \
                patch('salt.utils.win_functions.get_sam_name', return_value='HOST\\spongebob'):
            comt = ('Failed to remove spongebob from group foo.  C')
            self.assertDictEqual(
                win_groupadd.deluser('foo', 'spongebob'),
                {'changes': {'Users Removed': []},
                 'name': 'foo',
                 'comment': comt,
                 'result': False})

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
