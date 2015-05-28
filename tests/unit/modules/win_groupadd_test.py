# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import win_groupadd

win_groupadd.__context__ = {}


class Mockpythoncom(object):
    '''
    Mock pythoncom class
    '''
    @staticmethod
    def CoInitialize():
        '''
        Mock CoInitialize method
        '''
        return Mockpythoncom()


class MockClient(object):
    '''
    Mock MockClient class
    '''
    objectSID = True
    flag = None
    cn = 'salt'

    def __init__(self):
        self.name_space = None
        self.nul = None
        self.name = None
        self.passwd = None

    def Dispatch(self, name_space):
        """
        Mock of Dispatch method
        """
        self.name_space = name_space
        return MockClient()

    def GetObject(self, nul, name):
        """
        Mock of GetObject method
        """
        self.nul = nul
        self.name = name
        if self.flag == 1:
            return None
        elif self.flag == 2:
            raise MockComError
        elif self.flag == 3:
            return [MockClient()]
        return MockClient()

    @staticmethod
    def Name():
        """
        Mock of Name method
        """
        return True

    @staticmethod
    def members():
        """
        Mock of members method
        """
        return []

    @staticmethod
    def Delete(group, groupName):
        """
        Mock of Delete method
        """
        return (group, groupName)

    @staticmethod
    def Add(username):
        """
        Mock of Delete method
        """
        return username


class Mockwin32com(object):
    '''
    Mock Win32com class
    '''
    def __init__(self):
        self.client = MockClient()


class Mockwin32security(object):
    '''
    Mock win32security class
    '''
    def __init__(self):
        self.obj = None

    def ConvertSidToStringSid(self, obj):
        """
        Mock of ConvertSidToStringSid method
        """
        self.obj = obj
        return True


class MockComError(Exception):
    """
    Mock of com_error
    """
    pass


class Mockpywintypes(object):
    '''
    Mock pywintypes class
    '''
    def __init__(self):
        self.com_error = MockComError
        self.obj = None

    def SID(self, obj):
        """
        Mock of SID method
        """
        self.obj = obj
        return True

win_groupadd.win32com = Mockwin32com()
win_groupadd.win32security = Mockwin32security()
win_groupadd.pythoncom = Mockpythoncom()
win_groupadd.pywintypes = Mockpywintypes()


@skipIf(NO_MOCK, NO_MOCK_REASON)
class WinGroupTestCase(TestCase):
    '''
    Test cases for salt.modules.win_groupadd
    '''
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
                             {'changes': ['Successfully removed group foo'],
                              'comment': '', 'name': 'foo', 'result': True})

    # 'info' function tests: 1

    def test_info(self):
        '''
        Test if it return information about a group.
        '''
        MockClient.flag = None
        self.assertDictEqual(win_groupadd.info('dc=salt'),
                             {'gid': True, 'members': [], 'name': 'salt',
                              'passwd': None})

        MockClient.cn = None
        self.assertFalse(win_groupadd.info('dc=salt'))

        MockClient.flag = 2
        self.assertFalse(win_groupadd.info('dc=salt'))

    # 'getent' function tests: 1

    def test_getent(self):
        '''
        Test if it return info on all groups
        '''
        with patch.dict(win_groupadd.__context__, {'group.getent': True}):
            self.assertTrue(win_groupadd.getent())

#         MockClient.flag = 3
#         self.assertEqual(win_groupadd.getent(), '')

    # 'adduser' function tests: 1

    def test_adduser(self):
        '''
        Test if it add a user to a group
        '''
        self.assertDictEqual(win_groupadd.adduser('dc=foo', 'dc=username'),
                             {'changes': {'Users Added': ['dc=username']},
                              'comment': '', 'name': 'dc=foo', 'result': True})

    # 'deluser' function tests: 1

    def test_deluser(self):
        '''
        Test if it remove a user to a group
        '''
        ret = {'changes': {'Users Removed': []},
               'comment': 'User dc=username is not a member of dc=foo',
               'name': 'dc=foo', 'result': None}

        self.assertDictEqual(win_groupadd.deluser('dc=foo', 'dc=username'), ret)

    # 'members' function tests: 1

    def test_members(self):
        '''
        Test if it remove a user to a group
        '''
        comment = 'Group dc=foo does not appear to exist.'

        ret = {'name': 'dc=foo', 'result': False, 'comment': comment,
               'changes': {'Users Added': [], 'Users Removed': []}}

        self.assertDictEqual(win_groupadd.members('dc=foo',
                                                  'dc=user1,dc=user2,dc=user3'),
                             ret)

        comment = 'Members is not a list object'
        ret.update({'comment': [comment]})
        self.assertDictEqual(win_groupadd.members('dc=foo', 1), ret)

    # 'list_groups' function tests: 1

    def test_list_groups(self):
        '''
        Test if it return a list of groups on Windows
        '''
        self.assertListEqual(win_groupadd.list_groups(True), [])


if __name__ == '__main__':
    from integration import run_tests
    run_tests(WinGroupTestCase, needs_daemon=False)
