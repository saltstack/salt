# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import MagicMock, patch

# Import Salt Libs
from salt.modules import mac_user
from salt.exceptions import SaltInvocationError, CommandExecutionError

# Import python Libs
import pwd
import grp


class MacUserTestCase(TestCase):
    '''
    TestCase for the salt.modules.mac_user modules
    '''

    mac_user.__context__ = {}
    mac_user.__grains__ = {}
    mac_user.__salt__ = {}

    mock_pwall = [pwd.struct_passwd(('_amavisd', '*', 83, 83, 'AMaViS Daemon',
                                    '/var/virusmails', '/usr/bin/false')),
                  pwd.struct_passwd(('_appleevents', '*', 55, 55,
                                     'AppleEvents Daemon',
                                    '/var/empty', '/usr/bin/false')),
                  pwd.struct_passwd(('_appowner', '*', 87, 87,
                                     'Application Owner',
                                     '/var/empty', '/usr/bin/false'))]
    mock_pwnam = pwd.struct_passwd(('_TEST_GROUP', '*', 83, 83, 'AMaViS Daemon',
                                    '/var/virusmails', '/usr/bin/false'))
    mock_getgrgid = grp.struct_group(('_TEST_GROUP', '*', 83, []))
    mock_getgrall = [grp.struct_group(('accessibility', '*', 90, [])),
                     grp.struct_group(('admin', '*', 80, ['root', 'admin']))]
    mock_info_ret = {'shell': '/bin/bash', 'name': 'test', 'gid': 4376,
                     'groups': ['TEST_GROUP'], 'home': '/var/test',
                     'fullname': 'TEST USER', 'uid': 4376}

    def test_osmajor(self):
        '''
        Tests version of OS X
        '''
        with patch.dict(mac_user.__grains__, {'kernel': 'Darwin',
                                              'osrelease': '10.9.1'}):
            self.assertEqual(mac_user._osmajor(), 10.9)

    @skipIf(True, 'Waiting on some clarifications from bug report')
    def test_flush_dscl_cache(self):
        # TODO: Implement tests after clarifications come in
        pass

    def test_dscl(self):
        '''
        Tests the creation of a dscl node
        '''
        mac_mock = MagicMock(return_value={'pid': 4948,
                                           'retcode': 0,
                                           'stderr': '',
                                           'stdout': ''})
        with patch.dict(mac_user.__salt__, {'cmd.run_all': mac_mock}):
            with patch.dict(mac_user.__grains__, {'kernel': 'Darwin',
                                                  'osrelease': '10.9.1'}):
                self.assertEqual(mac_user._dscl('username'), {'pid': 4948,
                                                              'retcode': 0,
                                                              'stderr': '',
                                                              'stdout': ''})

    @patch('pwd.getpwall', MagicMock(return_value=mock_pwall))
    def test_first_avail_uid(self):
        '''
        Tests the availability of the next uid
        '''
        self.assertEqual(mac_user._first_avail_uid(), 501)

    @skipIf(True, 'Test not implemented yet')
    def test_add(self):
        # TODO: Implement this guy last
        pass

    @skipIf(True, 'Test not implemented yet')
    def test_delete(self):
        # TODO: Implement after chgroups is tested
        pass

    @patch('pwd.getpwall', MagicMock(return_value=mock_pwall))
    @patch('salt.modules.mac_user.list_groups',
           MagicMock(return_value=['TEST_GROUP']))
    def test_getent(self):
        '''
        Tests the list of information for all users
        '''
        ret = [{'shell': '/usr/bin/false', 'name': '_amavisd', 'gid': 83,
                'groups': ['TEST_GROUP'], 'home': '/var/virusmails',
                'fullname': 'AMaViS Daemon', 'uid': 83},
               {'shell': '/usr/bin/false', 'name': '_appleevents', 'gid': 55,
                'groups': ['TEST_GROUP'], 'home': '/var/empty',
                'fullname': 'AppleEvents Daemon', 'uid': 55},
               {'shell': '/usr/bin/false', 'name': '_appowner', 'gid': 87,
                'groups': ['TEST_GROUP'], 'home': '/var/empty',
                'fullname': 'Application Owner', 'uid': 87}]
        self.assertEqual(mac_user.getent(), ret)

    def test_chuid_int(self):
        '''
        Tests if the uid is an int
        '''
        with self.assertRaises(SaltInvocationError):
            mac_user.chuid('foo', 'foo')

    @patch('salt.modules.mac_user.info', MagicMock(return_value={}))
    def test_chuid_user_exists(self):
        '''
        Tests if the user exists or not
        '''
        with self.assertRaises(CommandExecutionError):
            mac_user.chuid('foo', 4376)

    @patch('salt.modules.mac_user.info', MagicMock(return_value=mock_info_ret))
    def test_chuid_same_uid(self):
        '''
        Tests if the user's uid is the same as as the argument
        '''
        self.assertTrue(mac_user.chuid('foo', 4376))

    def test_chgid_int(self):
        '''
        Tests if the gid is an int
        '''
        with self.assertRaises(SaltInvocationError):
            mac_user.chgid('foo', 'foo')

    @patch('salt.modules.mac_user.info', MagicMock(return_value={}))
    def test_chgid_user_exists(self):
        '''
        Tests if the user exists or not
        '''
        with self.assertRaises(CommandExecutionError):
            mac_user.chgid('foo', 4376)

    @patch('salt.modules.mac_user.info', MagicMock(return_value=mock_info_ret))
    def test_chgid_same_gid(self):
        '''
        Tests if the user's gid is the same as as the argument
        '''
        self.assertTrue(mac_user.chgid('foo', 4376))

    @patch('salt.modules.mac_user.list_groups',
           MagicMock(return_value=['_TEST_GROUP']))
    def test_info(self):
        '''
        Tests the return of user information
        '''
        mock_pwnam = pwd.struct_passwd(('test', '*', 0, 0, 'TEST USER',
                                        '/var/test', '/bin/bash'))
        ret = {'shell': '/bin/bash', 'name': 'test', 'gid': 0,
               'groups': ['_TEST_GROUP'], 'home': '/var/test',
               'fullname': 'TEST USER', 'uid': 0}
        with patch('pwd.getpwnam', MagicMock(return_value=mock_pwnam)):
            self.assertEqual(mac_user.info('root'), ret)

    @patch('salt.modules.mac_user.list_groups',
           MagicMock(return_value=['_TEST_GROUP']))
    def test_format_info(self):
        '''
        Tests the formatting of returned user information
        '''
        data = pwd.struct_passwd(('_TEST_GROUP', '*', 83, 83, 'AMaViS Daemon',
                                  '/var/virusmails', '/usr/bin/false'))
        ret = {'shell': '/usr/bin/false', 'name': '_TEST_GROUP', 'gid': 83,
                     'groups': ['_TEST_GROUP'], 'home': '/var/virusmails',
                     'fullname': 'AMaViS Daemon', 'uid': 83}
        self.assertEqual(mac_user._format_info(data), ret)

    @patch('pwd.getpwnam', MagicMock(return_value=mock_pwnam))
    @patch('grp.getgrgid', MagicMock(return_value=mock_getgrgid))
    @patch('grp.getgrall', MagicMock(return_value=mock_getgrall))
    def test_list_groups(self):
        '''
        Tests the list of groups the user belongs to
        '''
        self.assertEqual(mac_user.list_groups('name'), ['_TEST_GROUP'])

    @patch('pwd.getpwall', MagicMock(return_value=mock_pwall))
    def test_list_users(self):
        '''
        Tests the list of all users
        '''
        ret = ['_amavisd', '_appleevents', '_appowner']
        self.assertEqual(mac_user.list_users(), ret)
