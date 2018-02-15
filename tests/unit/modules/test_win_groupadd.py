# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function

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
import salt.utils.win_functions

# Import Other Libs
# pylint: disable=unused-import
try:
    import win32com
    import pythoncom
    import pywintypes
    PYWINTYPES_ERROR = pywintypes.com_error(
        -1234, 'Exception occurred.', (0, None, 'C', None, 0, -4321), None)
    HAS_WIN_LIBS = True
except ImportError:
    HAS_WIN_LIBS = False
# pylint: enable=unused-import


class MockMember(object):
    def __init__(self, name):
        self.ADSPath = name


class MockGroupObj(object):
    def __init__(self, ads_name, ads_users):
        self._members = [MockMember(x) for x in ads_users]
        self.Name = ads_name

    def members(self):
        return self._members

    def Add(self, name):
        '''
        This should be a no-op unless we want to test raising an error, in
        which case this should be overridden in a subclass.
        '''
        pass

    def Remove(self, name):
        '''
        This should be a no-op unless we want to test raising an error, in
        which case this should be overridden in a subclass.
        '''
        pass


if not NO_MOCK:
    sam_mock = MagicMock(side_effect=lambda x: 'HOST\\' + x)


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
                raise PYWINTYPES_ERROR

        compobj_mock = MagicMock(return_value=CompObj())

        info = MagicMock(return_value=False)
        with patch.object(win_groupadd, 'info', info),\
             patch.object(win_groupadd, '_get_computer_object', compobj_mock):
            self.assertDictEqual(win_groupadd.add('foo'),
                                 {'changes': [],
                                  'name': 'foo',
                                  'result': False,
                                  'comment': 'Failed to create group foo. C'})

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
                raise PYWINTYPES_ERROR

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

    def test_info(self):
        '''
        Test if it return information about a group.
        '''
        groupobj_mock = MagicMock(return_value=MockGroupObj('salt', ['WinNT://HOST/steve']))
        with patch.object(win_groupadd, '_get_group_object', groupobj_mock):
            self.assertDictEqual(win_groupadd.info('salt'),
                                 {'gid': None,
                                  'members': ['HOST\\steve'],
                                  'passwd': None,
                                  'name': 'salt'})

    def test_getent(self):
        groupobj_mock = MagicMock(
            return_value=[
                MockGroupObj('salt', ['WinNT://HOST/steve']),
                MockGroupObj('salty', ['WinNT://HOST/spongebob'])])
        mock_g_to_g = MagicMock(side_effect=[1, 2])
        with patch.object(win_groupadd, '_get_all_groups', groupobj_mock),\
             patch.dict(win_groupadd.__salt__, {'file.group_to_gid': mock_g_to_g}):
            self.assertListEqual(
                win_groupadd.getent(),
                [
                    {'gid': 1, 'members': ['HOST\\steve'], 'name': 'salt', 'passwd': 'x'},
                    {'gid': 2, 'members': ['HOST\\spongebob'], 'name': 'salty', 'passwd': 'x'}
                ])

    def test_getent_context(self):
        '''
        Test group.getent is using the values in __context__
        '''
        with patch.dict(win_groupadd.__context__, {'group.getent': True}):
            self.assertTrue(win_groupadd.getent())

    def test_adduser(self):
        '''
        Test adding a user to a group
        '''
        groupobj_mock = MagicMock(return_value=MockGroupObj('foo', ['WinNT://HOST/steve']))
        with patch.object(win_groupadd, '_get_group_object', groupobj_mock), \
                patch.object(salt.utils.win_functions, 'get_sam_name', sam_mock):
            self.assertDictEqual(
                win_groupadd.adduser('foo', 'spongebob'),
                {'changes': {'Users Added': ['HOST\\spongebob']},
                 'comment': '',
                 'name': 'foo',
                 'result': True})

    def test_adduser_already_exists(self):
        '''
        Test adding a user that already exists
        '''
        groupobj_mock = MagicMock(return_value=MockGroupObj('foo', ['WinNT://HOST/steve']))
        with patch.object(win_groupadd, '_get_group_object', groupobj_mock), \
                patch.object(salt.utils.win_functions, 'get_sam_name', sam_mock):
            self.assertDictEqual(
                win_groupadd.adduser('foo', 'steve'),
                {'changes': {'Users Added': []},
                 'comment': 'User HOST\\steve is already a member of foo',
                 'name': 'foo',
                 'result': None})

    def test_adduser_error(self):
        '''
        Test adding a user and encountering an error
        '''
        # Create mock group object with mocked Add function which raises the
        # exception we need in order to test the error case.
        class GroupObj(MockGroupObj):
            def Add(self, name):
                raise PYWINTYPES_ERROR

        groupobj_mock = MagicMock(return_value=GroupObj('foo', ['WinNT://HOST/steve']))
        with patch.object(win_groupadd, '_get_group_object', groupobj_mock), \
                patch.object(salt.utils.win_functions, 'get_sam_name', sam_mock):
            self.assertDictEqual(
                win_groupadd.adduser('foo', 'username'),
                {'changes': {'Users Added': []},
                 'name': 'foo',
                 'comment': 'Failed to add HOST\\username to group foo.  C',
                 'result': False})

    def test_adduser_group_does_not_exist(self):
        groupobj_mock = MagicMock(side_effect=PYWINTYPES_ERROR)
        with patch.object(win_groupadd, '_get_group_object', groupobj_mock), \
             patch.object(salt.utils.win_functions, 'get_sam_name', sam_mock):
            self.assertDictEqual(
                win_groupadd.adduser('foo', 'spongebob'),
                {'changes': {'Users Added': []},
                 'name': 'foo',
                 'comment': 'Failure accessing group foo. C',
                 'result': False})

    def test_deluser(self):
        '''
        Test removing a user from a group
        '''
        # Test removing a user
        groupobj_mock = MagicMock(return_value=MockGroupObj('foo', ['WinNT://HOST/spongebob']))
        with patch.object(win_groupadd, '_get_group_object', groupobj_mock), \
                patch.object(salt.utils.win_functions, 'get_sam_name', sam_mock):
            ret = {'changes': {'Users Removed': ['spongebob']},
                   'comment': '',
                   'name': 'foo',
                   'result': True}
            self.assertDictEqual(win_groupadd.deluser('foo', 'spongebob'), ret)

    def test_deluser_no_user(self):
        '''
        Test removing a user from a group and that user is not a member of the
        group
        '''
        groupobj_mock = MagicMock(return_value=MockGroupObj('foo', ['WinNT://HOST/steve']))
        with patch.object(win_groupadd, '_get_group_object', groupobj_mock), \
                patch.object(salt.utils.win_functions, 'get_sam_name', sam_mock):
            ret = {'changes': {'Users Removed': []},
                   'comment': 'User spongebob is not a member of foo',
                   'name': 'foo',
                   'result': None}
            self.assertDictEqual(win_groupadd.deluser('foo', 'spongebob'), ret)

    def test_deluser_error(self):
        '''
        Test removing a user and encountering an error
        '''
        class GroupObj(MockGroupObj):
            def Remove(self, name):
                raise PYWINTYPES_ERROR

        groupobj_mock = MagicMock(return_value=GroupObj('foo', ['WinNT://HOST/spongebob']))
        with patch.object(win_groupadd, '_get_group_object', groupobj_mock), \
                patch.object(salt.utils.win_functions, 'get_sam_name', sam_mock):
            self.assertDictEqual(
                win_groupadd.deluser('foo', 'spongebob'),
                {'changes': {'Users Removed': []},
                 'name': 'foo',
                 'comment': 'Failed to remove spongebob from group foo.  C',
                 'result': False})

    def test_deluser_group_does_not_exist(self):
        groupobj_mock = MagicMock(side_effect=PYWINTYPES_ERROR)
        with patch.object(win_groupadd, '_get_group_object', groupobj_mock), \
             patch.object(salt.utils.win_functions, 'get_sam_name', sam_mock):
            self.assertDictEqual(
                win_groupadd.deluser('foo', 'spongebob'),
                {'changes': {'Users Removed': []},
                 'name': 'foo',
                 'comment': 'Failure accessing group foo. C',
                 'result': False})

    def test_members(self):
        '''
        Test adding a list of members to a group, all existing users removed
        '''
        groupobj_mock = MagicMock(return_value=MockGroupObj('foo', ['WinNT://HOST/steve']))
        with patch.object(win_groupadd, '_get_group_object', groupobj_mock), \
             patch.object(salt.utils.win_functions, 'get_sam_name', sam_mock):
            self.assertDictEqual(
                win_groupadd.members('foo', 'spongebob,patrick,squidward'),
                {'changes': {
                    'Users Added': ['HOST\\patrick', 'HOST\\spongebob', 'HOST\\squidward'],
                    'Users Removed': ['HOST\\steve']
                },
                'comment': [],
                'name': 'foo',
                'result': True})

    def test_members_correct_membership(self):
        '''
        Test adding a list of users where the list of users already exists
        '''
        members_list = ['WinNT://HOST/spongebob',
                        'WinNT://HOST/squidward',
                        'WinNT://HOST/patrick']
        groupobj_mock = MagicMock(return_value=MockGroupObj('foo', members_list))
        with patch.object(win_groupadd, '_get_group_object', groupobj_mock), \
             patch.object(salt.utils.win_functions, 'get_sam_name', sam_mock):
            self.assertDictEqual(
                win_groupadd.members('foo', 'spongebob,patrick,squidward'),
                {'changes': {'Users Added': [], 'Users Removed': []},
                 'comment': ['foo membership is correct'],
                 'name': 'foo',
                 'result': None})

    def test_members_group_does_not_exist(self):
        '''
        Test adding a list of users where the group does not exist
        '''
        groupobj_mock = MagicMock(side_effect=PYWINTYPES_ERROR)
        with patch.object(win_groupadd, '_get_group_object', groupobj_mock), \
             patch.object(salt.utils.win_functions, 'get_sam_name', sam_mock):
            self.assertDictEqual(
                win_groupadd.members('foo', 'spongebob'),
                {'changes': {'Users Added': [], 'Users Removed': []},
                 'comment': ['Failure accessing group foo.  C'],
                 'name': 'foo',
                 'result': False})

    def test_members_fail_to_remove(self):
        '''
        Test adding a list of members and fail to remove members not in the list
        '''
        class GroupObj(MockGroupObj):
            def Remove(self, name):
                raise PYWINTYPES_ERROR

        groupobj_mock = MagicMock(return_value=GroupObj('foo', ['WinNT://HOST/spongebob']))
        with patch.object(win_groupadd, '_get_group_object', groupobj_mock), \
             patch.object(salt.utils.win_functions, 'get_sam_name', sam_mock):
            self.assertDictEqual(
                win_groupadd.members('foo', 'patrick'),
                {'changes': {'Users Added': ['HOST\\patrick'], 'Users Removed': []},
                 'comment': ['Failed to remove HOST\\spongebob from foo.  C'],
                 'name': 'foo',
                 'result': False})

    def test_members_fail_to_add(self):
        '''
        Test adding a list of members and failing to add
        '''
        class GroupObj(MockGroupObj):
            def Add(self, name):
                raise PYWINTYPES_ERROR

        groupobj_mock = MagicMock(return_value=GroupObj('foo', ['WinNT://HOST/spongebob']))
        with patch.object(win_groupadd, '_get_group_object', groupobj_mock), \
             patch.object(salt.utils.win_functions, 'get_sam_name', sam_mock):
            self.assertDictEqual(
                win_groupadd.members('foo', 'patrick'),
                {'changes': {'Users Added': [], 'Users Removed': ['HOST\\spongebob']},
                 'comment': ['Failed to add HOST\\patrick to foo.  C'],
                 'name': 'foo',
                 'result': False})

    def test_list_groups(self):
        '''
        Test that list groups returns a list of groups by name
        '''
        groupobj_mock = MagicMock(
            return_value=[
                MockGroupObj('salt', ['WinNT://HOST/steve']),
                MockGroupObj('salty', ['WinNT://HOST/Administrator'])])
        with patch.object(win_groupadd, '_get_all_groups', groupobj_mock):
            self.assertListEqual(win_groupadd.list_groups(),
                                 ['salt', 'salty'])

    def test_list_groups_context(self):
        '''
        Test group.list_groups is using the values in __context__
        '''
        with patch.dict(win_groupadd.__context__, {'group.list_groups': True}):
            self.assertTrue(win_groupadd.list_groups())
