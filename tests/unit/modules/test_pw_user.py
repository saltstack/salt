# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.modules.pw_user as pw_user
from salt.exceptions import CommandExecutionError
try:
    import pwd
    HAS_PWD = True
except ImportError:
    HAS_PWD = False


@skipIf(not HAS_PWD, 'These tests can only run on systems with the python pwd module')
@skipIf(NO_MOCK, NO_MOCK_REASON)
class PwUserTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.pw_user
    '''
    def setup_loader_modules(self):
        return {pw_user: {}}

    def test_add(self):
        '''
        Test for adding a user
        '''
        with patch.dict(pw_user.__grains__, {'os_family': 'RedHat'}):
            mock = MagicMock(return_value=0)
            with patch.dict(pw_user.__salt__, {'cmd.retcode': mock}):
                self.assertTrue(pw_user.add('a'))

    def test_delete(self):
        '''
        Test for deleting a user
        '''
        mock = MagicMock(return_value=0)
        with patch.dict(pw_user.__salt__, {'cmd.retcode': mock}):
            self.assertTrue(pw_user.delete('A'))

    def test_getent(self):
        '''
        Test if user.getent already have a value
        '''
        mock_user = 'saltdude'

        class MockData(object):
            pw_name = mock_user

        with patch('pwd.getpwall', MagicMock(return_value=[MockData()])):
            with patch.dict(pw_user.__context__, {'user.getent': mock_user}):
                self.assertEqual(pw_user.getent(), mock_user)

                with patch.object(pw_user, 'info', MagicMock(return_value=mock_user)):
                    self.assertEqual(pw_user.getent(True)[0], mock_user)

    def test_chuid(self):
        '''
        Test if user id given is same as previous id
        '''
        mock = MagicMock(return_value={'uid': 'A'})
        with patch.object(pw_user, 'info', mock):
            self.assertTrue(pw_user.chuid('name', 'A'))

        mock = MagicMock(return_value=None)
        with patch.dict(pw_user.__salt__, {'cmd.run': mock}):
            mock = MagicMock(side_effect=[{'uid': 'A'}, {'uid': 'A'}])
            with patch.object(pw_user, 'info', mock):
                self.assertFalse(pw_user.chuid('name', 'B'))

        mock = MagicMock(return_value=None)
        with patch.dict(pw_user.__salt__, {'cmd.run': mock}):
            mock = MagicMock(side_effect=[{'uid': 'A'}, {'uid': 'B'}])
            with patch.object(pw_user, 'info', mock):
                self.assertTrue(pw_user.chuid('name', 'A'))

    def test_chgid(self):
        '''
        Test if group id given is same as previous id
        '''
        mock = MagicMock(return_value={'gid': 1})
        with patch.object(pw_user, 'info', mock):
            self.assertTrue(pw_user.chgid('name', 1))

        mock = MagicMock(return_value=None)
        with patch.dict(pw_user.__salt__, {'cmd.run': mock}):
            mock = MagicMock(side_effect=[{'gid': 2}, {'gid': 2}])
            with patch.object(pw_user, 'info', mock):
                self.assertFalse(pw_user.chgid('name', 1))

        mock = MagicMock(return_value=None)
        with patch.dict(pw_user.__salt__, {'cmd.run': mock}):
            mock = MagicMock(side_effect=[{'gid': 1}, {'gid': 2}])
            with patch.object(pw_user, 'info', mock):
                self.assertTrue(pw_user.chgid('name', 1))

    def test_chshell(self):
        '''
        Test if shell given is same as previous shell
        '''
        mock = MagicMock(return_value={'shell': 'A'})
        with patch.object(pw_user, 'info', mock):
            self.assertTrue(pw_user.chshell('name', 'A'))

        mock = MagicMock(return_value=None)
        with patch.dict(pw_user.__salt__, {'cmd.run': mock}):
            mock = MagicMock(side_effect=[{'shell': 'B'}, {'shell': 'B'}])
            with patch.object(pw_user, 'info', mock):
                self.assertFalse(pw_user.chshell('name', 'A'))

        mock = MagicMock(return_value=None)
        with patch.dict(pw_user.__salt__, {'cmd.run': mock}):
            mock = MagicMock(side_effect=[{'shell': 'A'}, {'shell': 'B'}])
            with patch.object(pw_user, 'info', mock):
                self.assertTrue(pw_user.chshell('name', 'A'))

    def test_chhome(self):
        '''
        Test if home directory given is same as previous home directory
        '''
        mock = MagicMock(return_value={'home': 'A'})
        with patch.object(pw_user, 'info', mock):
            self.assertTrue(pw_user.chhome('name', 'A'))

        mock = MagicMock(return_value=None)
        with patch.dict(pw_user.__salt__, {'cmd.run': mock}):
            mock = MagicMock(side_effect=[{'home': 'B'}, {'home': 'B'}])
            with patch.object(pw_user, 'info', mock):
                self.assertFalse(pw_user.chhome('name', 'A'))

        mock = MagicMock(return_value=None)
        with patch.dict(pw_user.__salt__, {'cmd.run': mock}):
            mock = MagicMock(side_effect=[{'home': 'A'}, {'home': 'B'}])
            with patch.object(pw_user, 'info', mock):
                self.assertTrue(pw_user.chhome('name', 'A'))

    def test_chgroups(self):
        '''
        Test if no group needs to be added
        '''
        mock = MagicMock(return_value=False)
        with patch.dict(pw_user.__salt__, {'cmd.retcode': mock}):
            mock = MagicMock(return_value=['a', 'b', 'c', 'd'])
            with patch.object(pw_user, 'list_groups', mock):
                self.assertTrue(pw_user.chgroups('name', 'a, b, c, d'))

        mock = MagicMock(return_value=False)
        with patch.dict(pw_user.__salt__, {'cmd.retcode': mock}):
            mock = MagicMock(return_value=['a', 'b'])
            with patch.object(pw_user, 'list_groups', mock):
                self.assertTrue(pw_user.chgroups('name', 'a, b, c'))

    def test_chfullname(self):
        '''
        Change the user's Full Name
        '''
        mock = MagicMock(return_value=False)
        with patch.object(pw_user, '_get_gecos', mock):
            self.assertFalse(pw_user.chfullname('name', 'fullname'))

        mock = MagicMock(return_value={'fullname': 'fullname'})
        with patch.object(pw_user, '_get_gecos', mock):
            self.assertTrue(pw_user.chfullname('name', 'fullname'))

        mock = MagicMock(return_value={'fullname': u'Unicøde name ①③②'})
        with patch.object(pw_user, '_get_gecos', mock):
            self.assertTrue(pw_user.chfullname('name', u'Unicøde name ①③②'))

        mock = MagicMock(return_value={'fullname': 'fullname'})
        with patch.object(pw_user, '_get_gecos', mock):
            mock = MagicMock(return_value=None)
            with patch.dict(pw_user.__salt__, {'cmd.run': mock}):
                mock = MagicMock(return_value={'fullname': 'fullname2'})
                with patch.object(pw_user, 'info', mock):
                    self.assertFalse(pw_user.chfullname('name', 'fullname1'))

        mock = MagicMock(return_value={'fullname': 'fullname2'})
        with patch.object(pw_user, '_get_gecos', mock):
            mock = MagicMock(return_value=None)
            with patch.dict(pw_user.__salt__, {'cmd.run': mock}):
                mock = MagicMock(return_value={'fullname': 'fullname2'})
                with patch.object(pw_user, 'info', mock):
                    self.assertFalse(pw_user.chfullname('name', 'fullname1'))

    def test_chroomnumber(self):
        '''
        Change the user's Room Number
        '''
        mock = MagicMock(return_value=False)
        with patch.object(pw_user, '_get_gecos', mock):
            self.assertFalse(pw_user.chroomnumber('name', 1))

        mock = MagicMock(return_value={'roomnumber': u'Unicøde room ①③②'})
        with patch.object(pw_user, '_get_gecos', mock):
            self.assertTrue(pw_user.chroomnumber('name', u'Unicøde room ①③②'))

        mock = MagicMock(return_value={'roomnumber': '1'})
        with patch.object(pw_user, '_get_gecos', mock):
            self.assertTrue(pw_user.chroomnumber('name', 1))

        mock = MagicMock(return_value={'roomnumber': '2'})
        with patch.object(pw_user, '_get_gecos', mock):
            mock = MagicMock(return_value=None)
            with patch.dict(pw_user.__salt__, {'cmd.run': mock}):
                mock = MagicMock(return_value={'roomnumber': '3'})
                with patch.object(pw_user, 'info', mock):
                    self.assertFalse(pw_user.chroomnumber('name', 1))

        mock = MagicMock(return_value={'roomnumber': '3'})
        with patch.object(pw_user, '_get_gecos', mock):
            mock = MagicMock(return_value=None)
            with patch.dict(pw_user.__salt__, {'cmd.run': mock}):
                mock = MagicMock(return_value={'roomnumber': '3'})
                with patch.object(pw_user, 'info', mock):
                    self.assertFalse(pw_user.chroomnumber('name', 1))

    def test_chworkphone(self):
        '''
        Change the user's Work Phone
        '''
        mock = MagicMock(return_value=False)
        with patch.object(pw_user, '_get_gecos', mock):
            self.assertFalse(pw_user.chworkphone('name', 1))

        mock = MagicMock(return_value={'workphone': '1'})
        with patch.object(pw_user, '_get_gecos', mock):
            self.assertTrue(pw_user.chworkphone('name', 1))

        mock = MagicMock(return_value={'workphone': u'Unicøde phone number ①③②'})
        with patch.object(pw_user, '_get_gecos', mock):
            self.assertTrue(pw_user.chworkphone('name', u'Unicøde phone number ①③②'))

        mock = MagicMock(return_value={'workphone': '2'})
        with patch.object(pw_user, '_get_gecos', mock):
            mock = MagicMock(return_value=None)
            with patch.dict(pw_user.__salt__, {'cmd.run': mock}):
                mock = MagicMock(return_value={'workphone': '3'})
                with patch.object(pw_user, 'info', mock):
                    self.assertFalse(pw_user.chworkphone('name', 1))

        mock = MagicMock(return_value={'workphone': '3'})
        with patch.object(pw_user, '_get_gecos', mock):
            mock = MagicMock(return_value=None)
            with patch.dict(pw_user.__salt__, {'cmd.run': mock}):
                mock = MagicMock(return_value={'workphone': '3'})
                with patch.object(pw_user, 'info', mock):
                    self.assertFalse(pw_user.chworkphone('name', 1))

    def test_chhomephone(self):
        '''
        Change the user's Home Phone
        '''
        mock = MagicMock(return_value=False)
        with patch.object(pw_user, '_get_gecos', mock):
            self.assertFalse(pw_user.chhomephone('name', 1))

        mock = MagicMock(return_value={'homephone': '1'})
        with patch.object(pw_user, '_get_gecos', mock):
            self.assertTrue(pw_user.chhomephone('name', 1))

        mock = MagicMock(return_value={'homephone': u'Unicøde phone number ①③②'})
        with patch.object(pw_user, '_get_gecos', mock):
            self.assertTrue(pw_user.chhomephone('name', u'Unicøde phone number ①③②'))

        mock = MagicMock(return_value={'homephone': '2'})
        with patch.object(pw_user, '_get_gecos', mock):
            mock = MagicMock(return_value=None)
            with patch.dict(pw_user.__salt__, {'cmd.run': mock}):
                mock = MagicMock(return_value={'homephone': '3'})
                with patch.object(pw_user, 'info', mock):
                    self.assertFalse(pw_user.chhomephone('name', 1))

        mock = MagicMock(return_value={'homephone': '3'})
        with patch.object(pw_user, '_get_gecos', mock):
            mock = MagicMock(return_value=None)
            with patch.dict(pw_user.__salt__, {'cmd.run': mock}):
                mock = MagicMock(return_value={'homephone': '3'})
                with patch.object(pw_user, 'info', mock):
                    self.assertFalse(pw_user.chhomephone('name', 1))

    def test_info(self):
        '''
        Return user information
        '''
        self.assertEqual(pw_user.info('name'), {})

        mock = MagicMock(return_value=pwd.struct_passwd(('_TEST_GROUP',
                                                         '*',
                                                         83,
                                                         83,
                                                         'AMaViS Daemon',
                                                         '/var/virusmails',
                                                         '/usr/bin/false')))
        with patch.object(pwd, 'getpwnam', mock):
            mock = MagicMock(return_value='Group Name')
            with patch.object(pw_user, 'list_groups', mock):
                self.assertEqual(pw_user.info('name')['name'], '_TEST_GROUP')

    def test_list_groups(self):
        '''
        Return a list of groups the named user belongs to
        '''
        mock_group = 'saltgroup'

        with patch('salt.utils.user.get_group_list', MagicMock(return_value=[mock_group])):
            self.assertEqual(pw_user.list_groups('name'), [mock_group])

    def test_list_users(self):
        '''
        Return a list of all users
        '''
        mock_user = 'saltdude'

        class MockData(object):
            pw_name = mock_user

        with patch('pwd.getpwall', MagicMock(return_value=[MockData()])):
            self.assertEqual(pw_user.list_users(), [mock_user])

    def test_rename(self):
        '''
        Change the username for a named user
        '''
        mock = MagicMock(return_value=False)
        with patch.object(pw_user, 'info', mock):
            self.assertRaises(CommandExecutionError, pw_user.rename, 'name', 1)

        mock = MagicMock(return_value=True)
        with patch.object(pw_user, 'info', mock):
            self.assertRaises(CommandExecutionError, pw_user.rename, 'name', 1)

        mock = MagicMock(return_value=None)
        with patch.dict(pw_user.__salt__, {'cmd.run': mock}):
            mock = MagicMock(side_effect=[{'name': ''},
                                          False, {'name': 'name'}])
            with patch.object(pw_user, 'info', mock):
                self.assertTrue(pw_user.rename('name', 'name'))

        mock = MagicMock(return_value=None)
        with patch.dict(pw_user.__salt__, {'cmd.run': mock}):
            mock = MagicMock(side_effect=[{'name': ''}, False, {'name': ''}])
            with patch.object(pw_user, 'info', mock):
                self.assertFalse(pw_user.rename('name', 'name'))
