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
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import win_useradd

# Globals
win_useradd.__salt__ = {}
win_useradd.__context__ = {}


class MockClient(object):
    '''
    Mock MockClient class
    '''
    AccountDisabled = False
    objectSID = True
    description = 'salt'
    homeDirectory = '/home/salt'
    primaryGroupID = 'foo'
    userAccountControl = True
    scriptPath = '/etc/salt'
    profilePath = '/etc/salt_prof'
    DisplayName = 'SaltStack'
    sAMAccountName = 'salt_acc'
    flag = None

    def __init__(self):
        self.name_space = None
        self.nul = None
        self.name = None
        self.flag_a = None
        self.flag_b = None
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
        return MockClient()

    @staticmethod
    def SetInfo():
        """
        Mock of SetInfo method
        """
        return True

    def Put(self, flag_a, flag_b):
        """
        Mock of Put method
        """
        self.flag_a = flag_a
        self.flag_b = flag_b
        return True

    @staticmethod
    def UserFlags():
        """
        Mock of UserFlags method
        """
        return 'UserFlags'

    @staticmethod
    def LoginScript():
        """
        Mock of LoginScript method
        """
        return True

    @staticmethod
    def FullName():
        """
        Mock of FullName method
        """
        return True

    @staticmethod
    def Name():
        """
        Mock of Name method
        """
        return True

    @staticmethod
    def Profile():
        """
        Mock of Profile method
        """
        return True

    @staticmethod
    def groups():
        """
        Mock of groups method
        """
        return []

    def SetPassword(self, passwd):
        """
        Mock of SetPassword method
        """
        self.passwd = passwd
        return True


class win32com(object):
    '''
    Mock Win32com class
    '''
    def __init__(self):
        self.client = MockClient()


class pythoncom(object):
    '''
    Mock pythoncom class
    '''
    @staticmethod
    def CoInitialize():
        '''
        Mock CoInitialize method
        '''
        return pythoncom()


class com_error(Exception):
    """
    Mock of com_error
    """
    pass


class pywintypes(object):
    '''
    Mock pywintypes class
    '''
    def __init__(self):
        self.com_error = com_error
        self.obj = None

    def SID(self, obj):
        """
        Mock of SID method
        """
        self.obj = obj
        return True


class win32netcon(object):
    '''
    Mock win32netcon class
    '''
    UF_ACCOUNTDISABLE = True
    UF_DONT_EXPIRE_PASSWD = True


class win32security(object):
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

win_useradd.pythoncom = pythoncom()
win_useradd.win32com = win32com()
win_useradd.pywintypes = pywintypes()
win_useradd.win32netcon = win32netcon()
win_useradd.win32security = win32security()


@skipIf(NO_MOCK, NO_MOCK_REASON)
class WinUserAddTestCase(TestCase):
    '''
    Test cases for salt.modules.win_useradd
    '''
    # 'add' function tests: 1

    def test_add(self):
        '''
        Test if it add a user to the minion.
        '''
        with patch.object(win_useradd, 'info', MagicMock(return_value=True)):
            self.assertDictEqual(win_useradd.add('salt'),
                                 {'comment': ['The user salt already exists.'],
                                  'changes': [], 'name': 'salt',
                                  'result': None})

    # 'delete' function tests: 1

    def test_delete(self):
        '''
        Test if it remove a user from the minion.
        '''
        with patch.object(win_useradd, 'info', MagicMock(return_value=False)):
            self.assertDictEqual(win_useradd.delete('salt'),
                                 {'comment': 'The user salt does not exists.',
                                  'changes': [], 'name': 'salt',
                                  'result': None})

    # 'disable' function tests: 1

    def test_disable(self):
        '''
        Test if it disable a user account.
        '''
        self.assertDictEqual(win_useradd.disable('salt'),
                             {'comment': '',
                              'changes': 'User salt is now disabled.',
                              'name': 'salt',
                              'result': True})

    # 'enable' function tests: 1

    def test_enable(self):
        '''
        Test if it enable a user account.
        '''
        self.assertDictEqual(win_useradd.enable('salt'),
                             {'comment': '',
                              'changes': 'User salt is now enabled.',
                              'name': 'salt',
                              'result': True})

    # 'passwordneverexpires' function tests: 1

    def test_passwordneverexpires(self):
        '''
        Test if it set a user's password to never expire.
        '''
        chan = 'Password for user dc=salt is now set to never expire.'
        MockClient.flag = 0
        self.assertDictEqual(win_useradd.passwordneverexpires('dc=salt'),
                             {'changes': chan, 'comment': '', 'name': 'dc=salt',
                              'result': True})

    # 'requirepasswordchange' function tests: 1

    def test_requirepasswordchange(self):
        '''
        Test if it expire a user's password
        (i.e. require it to change on next logon).
        '''
        chan = 'Password must be changed at next logon for salt is now set.'
        MockClient.flag = 0
        self.assertDictEqual(win_useradd.requirepasswordchange('salt'),
                             {'comment': '',
                              'changes': chan,
                              'name': 'salt',
                              'result': True})

    # 'setpassword' function tests: 1

    def test_setpassword(self):
        '''
        Test if it set a user's password.
        '''
        chan = ['Successfully set password for user salt']
        self.assertDictEqual(win_useradd.setpassword('salt', 'salt@123'),
                             {'comment': '',
                              'changes': chan,
                              'name': 'salt',
                              'result': True})

    # 'addgroup' function tests: 1

    def test_addgroup(self):
        '''
        Test if it add user to a group.
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(win_useradd.__salt__, {'group.adduser': mock}):
            self.assertTrue(win_useradd.addgroup('salt', 'saltgroup'))

    # 'removegroup' function tests: 1

    def test_removegroup(self):
        '''
        Test if it remove user from a group.
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(win_useradd.__salt__, {'group.deluser': mock}):
            self.assertTrue(win_useradd.removegroup('salt', 'saltgroup'))

    # 'chhome' function tests: 1

    def test_chhome(self):
        '''
        Test if it change the home directory of the user.
        '''
        chan = ('Successfully changed user salt\'s'
                ' home directory from "/home/salt" to "/home/salt"')
        self.assertDictEqual(win_useradd.chhome('salt', '/home/salt'),
                             {'comment': '',
                              'changes': chan,
                              'name': 'salt',
                              'result': True})

    # 'chprofile' function tests: 1

    def test_chprofile(self):
        '''
        Test if it change the profile directory of the user.
        '''
        with patch.object(win_useradd, 'info', MagicMock(return_value=False)):
            self.assertDictEqual(win_useradd.chprofile('salt', 'salt_prof'),
                                 {'comment':
                                  'The user salt does not appear to exist.',
                                  'changes': [],
                                  'name': 'salt',
                                  'result': False})

    # 'chfullname' function tests: 1

    def test_chfullname(self):
        '''
        Test if it change the full name of the user.
        '''
        with patch.object(win_useradd, 'info', MagicMock(return_value=False)):
            self.assertDictEqual(win_useradd.chfullname('salt', 'SaltStack'),
                                 {'comment':
                                  'The user salt does not appear to exist.',
                                  'changes': [],
                                  'name': 'salt',
                                  'result': False})

    # 'chgroups' function tests: 1

    def test_chgroups(self):
        '''
        Test if it change the groups this user belongs to,
        add append to append the specified groups.
        '''
        with patch.object(win_useradd, 'info',
                          MagicMock(return_value={'groups': []})):
            with patch.object(win_useradd, '_fixlocaluser',
                              MagicMock(return_value='salt\admin')):
                mock = MagicMock(return_value={'result': True})
                with patch.dict(win_useradd.__salt__, {'group.adduser': mock}):
                    self.assertDictEqual(win_useradd.chgroups('salt',
                                                              'SaltStack'),
                                         {'changes':
                                          {'Groups Added': ['salt\x07dmin'],
                                           'Groups Removed': []},
                                          'comment': [],
                                          'name': 'salt',
                                          'result': True})

    # 'info' function tests: 1

    def test_info(self):
        '''
        Test if it return user information.
        '''
        self.assertDictEqual(win_useradd.info('dc=salt'),
                             {'active': False,
                              'comment': 'salt',
                              'fullname': 'SaltStack',
                              'gid': 'foo',
                              'groups': [],
                              'home': '/home/salt',
                              'logonscript': '/etc/salt',
                              'name': 'salt_acc',
                              'profile': '/etc/salt_prof',
                              'uid': True})

    # 'list_groups' function tests: 1

    def test_list_groups(self):
        '''
        Test if it return a list of groups the named user belongs to.
        '''
        with patch.object(win_useradd, 'info',
                          MagicMock(side_effect=[{'groups':
                                                  ['saltGroup', 'root']}, {}])):
            self.assertListEqual(win_useradd.list_groups('salt'),
                                 ['root', 'saltGroup'])
            self.assertFalse(win_useradd.list_groups('salt'))

    # 'getent' function tests: 1

    def test_getent(self):
        '''
        Test if it return the list of all info for all users.
        '''
        with patch.dict(win_useradd.__context__, {'user.getent': True}):
            self.assertTrue(win_useradd.getent())

        with patch.dict(win_useradd.__context__, {'user.getent': False}):
            mock_lst = MagicMock(return_value=['salt'])
            mock_info = MagicMock(return_value='salt')
            with patch.dict(win_useradd.__salt__, {'user.list_users': mock_lst,
                                                   'user.info': mock_info}):
                self.assertListEqual(win_useradd.getent(True), ['salt'])

    # 'list_users' function tests: 1

    def test_list_users(self):
        '''
        Test if it return a list of users on Windows.
        '''
        MockClient.flag = 1
        self.assertListEqual(win_useradd.list_users(), [])

    # 'rename' function tests: 1

    def test_rename(self):
        '''
        Test if it change the username for a named user.
        '''
        com = 'The user salt does not appear to exist.'
        with patch.object(win_useradd, 'info', MagicMock(return_value=False)):
            self.assertDictEqual(win_useradd.rename('salt', 'SaltStack'),
                                 {'changes': [],
                                  'comment': com,
                                  'result': False})


if __name__ == '__main__':
    from integration import run_tests
    run_tests(WinUserAddTestCase, needs_daemon=False)
