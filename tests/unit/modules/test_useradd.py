# -*- coding: utf-8 -*-
'''
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
try:
    import pwd
    HAS_PWD = True
except ImportError:
    HAS_PWD = False

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
import salt.modules.useradd as useradd
from salt.exceptions import CommandExecutionError


@skipIf(NO_MOCK, NO_MOCK_REASON)
class UserAddTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.useradd
    '''
    def setup_loader_modules(self):
        return {useradd: {}}

    @classmethod
    def setUpClass(cls):
        cls.mock_pwall = {'gid': 0,
                          'groups': ['root'],
                          'home': '/root',
                          'name': 'root',
                          'passwd': 'x',
                          'shell': '/bin/bash',
                          'uid': 0,
                          'fullname': 'root',
                          'roomnumber': '',
                          'workphone': '',
                          'homephone': '',
                          'other': ''}

    @classmethod
    def tearDownClass(cls):
        del cls.mock_pwall

    # 'add' function tests: 1

    def test_add(self):
        '''
        Test for adding a user
        '''
        with patch.dict(useradd.__grains__, {'kernel': 'OpenBSD'}):
            mock_primary = MagicMock(return_value='Salt')
            with patch.dict(useradd.__salt__,
                            {'file.gid_to_group': mock_primary}):
                mock = MagicMock(return_value={'retcode': 0})
                with patch.dict(useradd.__salt__, {'cmd.run_all': mock}):
                    self.assertTrue(useradd.add('Salt'))

                mock = MagicMock(return_value={'retcode': 1})
                with patch.dict(useradd.__salt__, {'cmd.run_all': mock}):
                    self.assertFalse(useradd.add('Salt'))

    # 'getent' function tests: 2

    @skipIf(HAS_PWD is False, 'The pwd module is not available')
    def test_getent(self):
        '''
        Test if user.getent already have a value
        '''
        with patch('salt.modules.useradd.__context__', MagicMock(return_value='Salt')):
            self.assertTrue(useradd.getent())

    @skipIf(HAS_PWD is False, 'The pwd module is not available')
    def test_getent_user(self):
        '''
        Tests the return information on all users
        '''
        with patch('pwd.getpwall', MagicMock(return_value=[''])):
            ret = [{'gid': 0,
                    'groups': ['root'],
                    'home': '/root',
                    'name': 'root',
                    'passwd': 'x',
                    'shell': '/bin/bash',
                    'uid': 0,
                    'fullname': 'root',
                    'roomnumber': '',
                    'workphone': '',
                    'homephone': '',
                    'other': ''}]
            with patch('salt.modules.useradd._format_info', MagicMock(return_value=self.mock_pwall)):
                self.assertEqual(useradd.getent(), ret)

    # 'chuid' function tests: 1

    def test_chuid(self):
        '''
        Test if the uid of a user change
        '''
        mock = MagicMock(return_value={'uid': 11})
        with patch.object(useradd, 'info', mock):
            self.assertTrue(useradd.chuid('name', 11))

        mock_run = MagicMock(return_value=None)
        with patch.dict(useradd.__salt__, {'cmd.run': mock_run}):
            mock = MagicMock(side_effect=[{'uid': 11}, {'uid': 11}])
            with patch.object(useradd, 'info', mock):
                self.assertFalse(useradd.chuid('name', 22))

        with patch.dict(useradd.__salt__, {'cmd.run': mock_run}):
            mock = MagicMock(side_effect=[{'uid': 11}, {'uid': 22}])
            with patch.object(useradd, 'info', mock):
                self.assertTrue(useradd.chuid('name', 11))

    # 'chgid' function tests: 1

    def test_chgid(self):
        '''
        Test the default group of the user
        '''
        mock = MagicMock(return_value={'gid': 11})
        with patch.object(useradd, 'info', mock):
            self.assertTrue(useradd.chgid('name', 11))

        mock_run = MagicMock(return_value=None)
        with patch.dict(useradd.__salt__, {'cmd.run': mock_run}):
            mock = MagicMock(side_effect=[{'gid': 22}, {'gid': 22}])
            with patch.object(useradd, 'info', mock):
                self.assertFalse(useradd.chgid('name', 11))

        with patch.dict(useradd.__salt__, {'cmd.run': mock_run}):
            mock = MagicMock(side_effect=[{'gid': 11}, {'gid': 22}])
            with patch.object(useradd, 'info', mock):
                self.assertTrue(useradd.chgid('name', 11))

    # 'chshell' function tests: 1

    def test_chshell(self):
        '''
        Test the default shell of user
        '''
        mock = MagicMock(return_value={'shell': '/bin/bash'})
        with patch.object(useradd, 'info', mock):
            self.assertTrue(useradd.chshell('name', '/bin/bash'))

        mock_run = MagicMock(return_value=None)
        with patch.dict(useradd.__salt__, {'cmd.run': mock_run}):
            mock = MagicMock(side_effect=[{'shell': '/bin/bash'},
                                          {'shell': '/bin/bash'}])
            with patch.object(useradd, 'info', mock):
                self.assertFalse(useradd.chshell('name', '/usr/bash'))

        with patch.dict(useradd.__salt__, {'cmd.run': mock_run}):
            mock = MagicMock(side_effect=[{'shell': '/bin/bash'},
                                          {'shell': '/usr/bash'}])
            with patch.object(useradd, 'info', mock):
                self.assertTrue(useradd.chshell('name', '/bin/bash'))

    # 'chhome' function tests: 1

    def test_chhome(self):
        '''
        Test if home directory given is same as previous home directory
        '''
        mock = MagicMock(return_value={'home': '/root'})
        with patch.object(useradd, 'info', mock):
            self.assertTrue(useradd.chhome('name', '/root'))

        mock = MagicMock(return_value=None)
        with patch.dict(useradd.__salt__, {'cmd.run': mock}):
            mock = MagicMock(side_effect=[{'home': '/root'}, {'home': '/root'}])
            with patch.object(useradd, 'info', mock):
                self.assertFalse(useradd.chhome('name', '/user'))

        mock = MagicMock(return_value=None)
        with patch.dict(useradd.__salt__, {'cmd.run': mock}):
            mock = MagicMock(side_effect=[{'home': '/root'}, {'home': '/root'}])
            with patch.object(useradd, 'info', mock):
                self.assertTrue(useradd.chhome('name', '/root'))

    # 'chgroups' function tests: 1

    def test_chgroups(self):
        '''
        Test if user groups changed
        '''
        mock = MagicMock(return_value=['wheel', 'root'])
        with patch.object(useradd, 'list_groups', mock):
            self.assertTrue(useradd.chgroups('foo', 'wheel,root'))

        mock = MagicMock(return_value=['wheel', 'root'])
        with patch.object(useradd, 'list_groups', mock):
            with patch.dict(useradd.__grains__, {'kernel': 'OpenBSD'}):
                mock_runall = MagicMock(return_value={'retcode': False,
                                                      'stderr': ''})
                with patch.dict(useradd.__salt__, {'cmd.run_all': mock_runall}):
                    self.assertTrue(useradd.chgroups('foo', 'wheel,test,root'))

                mock_runall = MagicMock(return_value={'retcode': True,
                                                      'stderr': ''})
                with patch.dict(useradd.__salt__, {'cmd.run_all': mock_runall}):
                    self.assertFalse(useradd.chgroups('foo', 'wheel,test,root'))

    # 'chfullname' function tests: 1

    def test_chfullname(self):
        '''
        Test if the user's Full Name is changed
        '''
        mock = MagicMock(return_value=False)
        with patch.object(useradd, '_get_gecos', mock):
            self.assertFalse(useradd.chfullname('Salt', 'SaltStack'))

        mock = MagicMock(return_value={'fullname': 'SaltStack'})
        with patch.object(useradd, '_get_gecos', mock):
            self.assertTrue(useradd.chfullname('Salt', 'SaltStack'))

        mock = MagicMock(return_value={'fullname': 'SaltStack'})
        with patch.object(useradd, '_get_gecos', mock):
            mock = MagicMock(return_value=None)
            with patch.dict(useradd.__salt__, {'cmd.run': mock}):
                mock = MagicMock(return_value={'fullname': 'SaltStack2'})
                with patch.object(useradd, 'info', mock):
                    self.assertFalse(useradd.chfullname('Salt', 'SaltStack1'))

        mock = MagicMock(return_value={'fullname': 'SaltStack2'})
        with patch.object(useradd, '_get_gecos', mock):
            mock = MagicMock(return_value=None)
            with patch.dict(useradd.__salt__, {'cmd.run': mock}):
                mock = MagicMock(return_value={'fullname': 'SaltStack2'})
                with patch.object(useradd, 'info', mock):
                    self.assertFalse(useradd.chfullname('Salt', 'SaltStack1'))

    # 'chroomnumber' function tests: 1

    def test_chroomnumber(self):
        '''
        Test if the user's Room Number is changed
        '''
        mock = MagicMock(return_value=False)
        with patch.object(useradd, '_get_gecos', mock):
            self.assertFalse(useradd.chroomnumber('salt', 1))

        mock = MagicMock(return_value={'roomnumber': '1'})
        with patch.object(useradd, '_get_gecos', mock):
            self.assertTrue(useradd.chroomnumber('salt', 1))

        mock = MagicMock(return_value={'roomnumber': '2'})
        with patch.object(useradd, '_get_gecos', mock):
            mock = MagicMock(return_value=None)
            with patch.dict(useradd.__salt__, {'cmd.run': mock}):
                mock = MagicMock(return_value={'roomnumber': '3'})
                with patch.object(useradd, 'info', mock):
                    self.assertFalse(useradd.chroomnumber('salt', 1))

        mock = MagicMock(return_value={'roomnumber': '3'})
        with patch.object(useradd, '_get_gecos', mock):
            mock = MagicMock(return_value=None)
            with patch.dict(useradd.__salt__, {'cmd.run': mock}):
                mock = MagicMock(return_value={'roomnumber': '3'})
                with patch.object(useradd, 'info', mock):
                    self.assertFalse(useradd.chroomnumber('salt', 1))

    # 'chworkphone' function tests: 1

    def test_chworkphone(self):
        '''
        Test if the user's Work Phone is changed
        '''
        mock = MagicMock(return_value=False)
        with patch.object(useradd, '_get_gecos', mock):
            self.assertFalse(useradd.chworkphone('salt', 1))

        mock = MagicMock(return_value={'workphone': '1'})
        with patch.object(useradd, '_get_gecos', mock):
            self.assertTrue(useradd.chworkphone('salt', 1))

        mock = MagicMock(return_value={'workphone': '2'})
        with patch.object(useradd, '_get_gecos', mock):
            mock = MagicMock(return_value=None)
            with patch.dict(useradd.__salt__, {'cmd.run': mock}):
                mock = MagicMock(return_value={'workphone': '3'})
                with patch.object(useradd, 'info', mock):
                    self.assertFalse(useradd.chworkphone('salt', 1))

        mock = MagicMock(return_value={'workphone': '3'})
        with patch.object(useradd, '_get_gecos', mock):
            mock = MagicMock(return_value=None)
            with patch.dict(useradd.__salt__, {'cmd.run': mock}):
                mock = MagicMock(return_value={'workphone': '3'})
                with patch.object(useradd, 'info', mock):
                    self.assertFalse(useradd.chworkphone('salt', 1))

    # 'chhomephone' function tests: 1

    def test_chhomephone(self):
        '''
        Test if the user's Home Phone is changed
        '''
        mock = MagicMock(return_value=False)
        with patch.object(useradd, '_get_gecos', mock):
            self.assertFalse(useradd.chhomephone('salt', 1))

        mock = MagicMock(return_value={'homephone': '1'})
        with patch.object(useradd, '_get_gecos', mock):
            self.assertTrue(useradd.chhomephone('salt', 1))

        mock = MagicMock(return_value={'homephone': '2'})
        with patch.object(useradd, '_get_gecos', mock):
            mock = MagicMock(return_value=None)
            with patch.dict(useradd.__salt__, {'cmd.run': mock}):
                mock = MagicMock(return_value={'homephone': '3'})
                with patch.object(useradd, 'info', mock):
                    self.assertFalse(useradd.chhomephone('salt', 1))

        mock = MagicMock(return_value={'homephone': '3'})
        with patch.object(useradd, '_get_gecos', mock):
            mock = MagicMock(return_value=None)
            with patch.dict(useradd.__salt__, {'cmd.run': mock}):
                mock = MagicMock(return_value={'homephone': '3'})
                with patch.object(useradd, 'info', mock):
                    self.assertFalse(useradd.chhomephone('salt', 1))

    # 'chother' function tests: 1

    def test_chother(self):
        '''
        Test if the user's other GECOS attribute is changed
        '''
        mock = MagicMock(return_value=False)
        with patch.object(useradd, '_get_gecos', mock):
            self.assertFalse(useradd.chother('salt', 1))

        mock = MagicMock(return_value={'other': 'foobar'})
        with patch.object(useradd, '_get_gecos', mock):
            self.assertTrue(useradd.chother('salt', 'foobar'))

        mock = MagicMock(return_value={'other': 'foobar2'})
        with patch.object(useradd, '_get_gecos', mock):
            mock = MagicMock(return_value=None)
            with patch.dict(useradd.__salt__, {'cmd.run': mock}):
                mock = MagicMock(return_value={'other': 'foobar3'})
                with patch.object(useradd, 'info', mock):
                    self.assertFalse(useradd.chother('salt', 'foobar'))

        mock = MagicMock(return_value={'other': 'foobar3'})
        with patch.object(useradd, '_get_gecos', mock):
            mock = MagicMock(return_value=None)
            with patch.dict(useradd.__salt__, {'cmd.run': mock}):
                mock = MagicMock(return_value={'other': 'foobar3'})
                with patch.object(useradd, 'info', mock):
                    self.assertFalse(useradd.chother('salt', 'foobar'))

    # 'info' function tests: 1

    @skipIf(HAS_PWD is False, 'The pwd module is not available')
    def test_info(self):
        '''
        Test the user information
        '''
        self.assertEqual(useradd.info('username-that-doesnt-exist'), {})

        mock = MagicMock(return_value=pwd.struct_passwd(('_TEST_GROUP',
                                                         '*',
                                                         83,
                                                         83,
                                                         'AMaViS Daemon',
                                                         '/var/virusmails',
                                                         '/usr/bin/false')))
        with patch.object(pwd, 'getpwnam', mock):
            self.assertEqual(useradd.info('username-that-doesnt-exist')['name'], '_TEST_GROUP')

    # 'list_groups' function tests: 1

    def test_list_groups(self):
        '''
        Test if it return a list of groups the named user belongs to
        '''
        with patch('salt.utils.user.get_group_list', MagicMock(return_value='Salt')):
            self.assertEqual(useradd.list_groups('name'), 'Salt')

    # 'list_users' function tests: 1

    @skipIf(HAS_PWD is False, 'The pwd module is not available')
    def test_list_users(self):
        '''
        Test if it returns a list of all users
        '''
        self.assertTrue(useradd.list_users())

    # 'list_users' function tests: 1

    def test_rename(self):
        '''
        Test if the username for a named user changed
        '''
        mock = MagicMock(return_value=False)
        with patch.object(useradd, 'info', mock):
            self.assertRaises(CommandExecutionError, useradd.rename, 'salt', 1)

        mock = MagicMock(return_value=True)
        with patch.object(useradd, 'info', mock):
            self.assertRaises(CommandExecutionError, useradd.rename, 'salt', 1)

        mock = MagicMock(return_value=None)
        with patch.dict(useradd.__salt__, {'cmd.run': mock}):
            mock = MagicMock(side_effect=[False, {'name': ''},
                                          {'name': 'salt'}])
            with patch.object(useradd, 'info', mock):
                self.assertTrue(useradd.rename('name', 'salt'))

        mock = MagicMock(return_value=None)
        with patch.dict(useradd.__salt__, {'cmd.run': mock}):
            mock = MagicMock(side_effect=[False, {'name': ''},
                                          {'name': ''}])
            with patch.object(useradd, 'info', mock):
                self.assertFalse(useradd.rename('salt', 'salt'))

    def test_build_gecos_field(self):
        '''
        Test if gecos fields are built correctly (removing trailing commas)
        '''
        test_gecos = {'fullname': 'Testing',
                      'roomnumber': 1234,
                      'workphone': 22222,
                      'homephone': 99999}
        expected_gecos_fields = 'Testing,1234,22222,99999'
        self.assertEqual(useradd._build_gecos(test_gecos), expected_gecos_fields)
        test_gecos.pop('roomnumber')
        test_gecos.pop('workphone')
        expected_gecos_fields = 'Testing,,,99999'
        self.assertEqual(useradd._build_gecos(test_gecos), expected_gecos_fields)
        test_gecos.pop('homephone')
        expected_gecos_fields = 'Testing'
        self.assertEqual(useradd._build_gecos(test_gecos), expected_gecos_fields)
