# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''

# Import python libs
from __future__ import absolute_import
import pwd

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import MagicMock, patch, NO_MOCK, NO_MOCK_REASON

# Import Salt Libs
import salt.modules.mac_user as mac_user
from salt.exceptions import SaltInvocationError, CommandExecutionError


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MacUserTestCase(TestCase, LoaderModuleMockMixin):
    '''
    TestCase for the salt.modules.mac_user modules
    '''

    def setup_loader_modules(self):
        return {mac_user: {}}

    mock_pwall = [pwd.struct_passwd(('_amavisd', '*', 83, 83, 'AMaViS Daemon',
                                    '/var/virusmails', '/usr/bin/false')),
                  pwd.struct_passwd(('_appleevents', '*', 55, 55,
                                     'AppleEvents Daemon',
                                    '/var/empty', '/usr/bin/false')),
                  pwd.struct_passwd(('_appowner', '*', 87, 87,
                                     'Application Owner',
                                     '/var/empty', '/usr/bin/false'))]
    mock_info_ret = {'shell': '/bin/bash', 'name': 'test', 'gid': 4376,
                     'groups': ['TEST_GROUP'], 'home': '/Users/foo',
                     'fullname': 'TEST USER', 'uid': 4376}

    @classmethod
    def tearDownClass(cls):
        for attrname in ('mock_pwall', 'mock_info_ret'):
            delattr(cls, attrname)

    @skipIf(True, 'Waiting on some clarifications from bug report #10594')
    def _test_flush_dscl_cache(self):
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
            with patch.dict(mac_user.__grains__,
                            {'kernel': 'Darwin', 'osrelease': '10.9.1',
                             'osrelease_info': (10, 9, 1)}):
                self.assertEqual(mac_user._dscl(['username', 'UniqueID', 501]),
                                 {'pid': 4948,
                                  'retcode': 0,
                                  'stderr': '',
                                  'stdout': ''})

    def test_first_avail_uid(self):
        '''
        Tests the availability of the next uid
        '''
        with patch('pwd.getpwall', MagicMock(return_value=self.mock_pwall)):
            self.assertEqual(mac_user._first_avail_uid(), 501)

    # 'add' function tests: 4
    # Only tested error handling
    # Full functionality tests covered in integration testing

    def test_add_user_exists(self):
        '''
        Tests if the user exists or not
        '''
        with patch('salt.modules.mac_user.info', MagicMock(return_value=self.mock_info_ret)):
            self.assertRaises(CommandExecutionError, mac_user.add, 'test')

    def test_add_whitespace(self):
        '''
        Tests if there is whitespace in the user name
        '''
        with patch('salt.modules.mac_user.info', MagicMock(return_value={})):
            self.assertRaises(SaltInvocationError, mac_user.add, 'foo bar')

    def test_add_uid_int(self):
        '''
        Tests if the uid is an int
        '''
        with patch('salt.modules.mac_user.info', MagicMock(return_value={})):
            self.assertRaises(SaltInvocationError, mac_user.add, 'foo', 'foo')

    def test_add_gid_int(self):
        '''
        Tests if the gid is an int
        '''
        with patch('salt.modules.mac_user.info', MagicMock(return_value={})):
            self.assertRaises(SaltInvocationError, mac_user.add, 'foo', 20, 'foo')

    # 'delete' function tests: 2
    # Only tested pure logic of function
    # Full functionality tests covered in integration testing

    def test_delete_whitespace(self):
        '''
        Tests if there is whitespace in the user name
        '''
        self.assertRaises(SaltInvocationError, mac_user.delete, 'foo bar')

    def test_delete_user_exists(self):
        '''
        Tests if the user exists or not
        '''
        with patch('salt.modules.mac_user.info', MagicMock(return_value={})):
            self.assertTrue(mac_user.delete('foo'))

    def test_getent(self):
        '''
        Tests the list of information for all users
        '''
        with patch('pwd.getpwall', MagicMock(return_value=self.mock_pwall)), \
                patch('salt.modules.mac_user.list_groups',
                      MagicMock(return_value=['TEST_GROUP'])):
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

    # 'chuid' function tests: 3
    # Only tested pure logic of function
    # Full functionality tests covered in integration testing

    def test_chuid_int(self):
        '''
        Tests if the uid is an int
        '''
        self.assertRaises(SaltInvocationError, mac_user.chuid, 'foo', 'foo')

    def test_chuid_user_exists(self):
        '''
        Tests if the user exists or not
        '''
        with patch('salt.modules.mac_user.info', MagicMock(return_value={})):
            self.assertRaises(CommandExecutionError, mac_user.chuid, 'foo', 4376)

    def test_chuid_same_uid(self):
        '''
        Tests if the user's uid is the same as as the argument
        '''
        with patch('salt.modules.mac_user.info', MagicMock(return_value=self.mock_info_ret)):
            self.assertTrue(mac_user.chuid('foo', 4376))

    # 'chgid' function tests: 3
    # Only tested pure logic of function
    # Full functionality tests covered in integration testing

    def test_chgid_int(self):
        '''
        Tests if the gid is an int
        '''
        self.assertRaises(SaltInvocationError, mac_user.chgid, 'foo', 'foo')

    def test_chgid_user_exists(self):
        '''
        Tests if the user exists or not
        '''
        with patch('salt.modules.mac_user.info', MagicMock(return_value={})):
            self.assertRaises(CommandExecutionError, mac_user.chgid, 'foo', 4376)

    def test_chgid_same_gid(self):
        '''
        Tests if the user's gid is the same as as the argument
        '''
        with patch('salt.modules.mac_user.info', MagicMock(return_value=self.mock_info_ret)):
            self.assertTrue(mac_user.chgid('foo', 4376))

    # 'chshell' function tests: 2
    # Only tested pure logic of function
    # Full functionality tests covered in integration testing

    def test_chshell_user_exists(self):
        '''
        Tests if the user exists or not
        '''
        with patch('salt.modules.mac_user.info', MagicMock(return_value={})):
            self.assertRaises(CommandExecutionError, mac_user.chshell,
                              'foo', '/bin/bash')

    def test_chshell_same_shell(self):
        '''
        Tests if the user's shell is the same as the argument
        '''
        with patch('salt.modules.mac_user.info', MagicMock(return_value=self.mock_info_ret)):
            self.assertTrue(mac_user.chshell('foo', '/bin/bash'))

    # 'chhome' function tests: 2
    # Only tested pure logic of function
    # Full functionality tests covered in integration testing

    def test_chhome_user_exists(self):
        '''
        Test if the user exists or not
        '''
        with patch('salt.modules.mac_user.info', MagicMock(return_value={})):
            self.assertRaises(CommandExecutionError, mac_user.chhome,
                              'foo', '/Users/foo')

    def test_chhome_same_home(self):
        '''
        Tests if the user's home is the same as the argument
        '''
        with patch('salt.modules.mac_user.info', MagicMock(return_value=self.mock_info_ret)):
            self.assertTrue(mac_user.chhome('foo', '/Users/foo'))

    # 'chfullname' function tests: 2
    # Only tested pure logic of function
    # Full functionality tests covered in integration testing

    def test_chfullname_user_exists(self):
        '''
        Tests if the user exists or not
        '''
        with patch('salt.modules.mac_user.info', MagicMock(return_value={})):
            self.assertRaises(CommandExecutionError, mac_user.chfullname,
                              'test', 'TEST USER')

    def test_chfullname_same_name(self):
        '''
        Tests if the user's full name is the same as the argument
        '''
        with patch('salt.modules.mac_user.info', MagicMock(return_value=self.mock_info_ret)):
            self.assertTrue(mac_user.chfullname('test', 'TEST USER'))

    # 'chgroups' function tests: 3
    # Only tested pure logic of function
    # Full functionality tests covered in integration testing

    def test_chgroups_user_exists(self):
        '''
        Tests if the user exists or not
        '''
        with patch('salt.modules.mac_user.info', MagicMock(return_value={})):
            self.assertRaises(CommandExecutionError, mac_user.chgroups,
                              'foo', 'wheel,root')

    def test_chgroups_bad_groups(self):
        '''
        Test if there is white space in groups argument
        '''
        with patch('salt.modules.mac_user.info', MagicMock(return_value=self.mock_info_ret)):
            self.assertRaises(SaltInvocationError, mac_user.chgroups,
                              'test', 'bad group')

    def test_chgroups_same_desired(self):
        '''
        Tests if the user's list of groups is the same as the arguments
        '''
        mock_primary = MagicMock(return_value='wheel')
        with patch.dict(mac_user.__salt__, {'file.gid_to_group': mock_primary}), \
                patch('salt.modules.mac_user.info', MagicMock(return_value=self.mock_info_ret)), \
                patch('salt.modules.mac_user.list_groups',
                      MagicMock(return_value=('wheel', 'root'))):
            self.assertTrue(mac_user.chgroups('test', 'wheel,root'))

    def test_info(self):
        '''
        Tests the return of user information
        '''
        mock_pwnam = pwd.struct_passwd(('test', '*', 0, 0, 'TEST USER',
                                        '/var/test', '/bin/bash'))
        ret = {'shell': '/bin/bash', 'name': 'test', 'gid': 0,
               'groups': ['_TEST_GROUP'], 'home': '/var/test',
               'fullname': 'TEST USER', 'uid': 0}
        with patch('pwd.getpwnam', MagicMock(return_value=mock_pwnam)), \
                patch('salt.modules.mac_user.list_groups',
                      MagicMock(return_value=['_TEST_GROUP'])):
            self.assertEqual(mac_user.info('root'), ret)

    def test_format_info(self):
        '''
        Tests the formatting of returned user information
        '''
        data = pwd.struct_passwd(('_TEST_GROUP', '*', 83, 83, 'AMaViS Daemon',
                                  '/var/virusmails', '/usr/bin/false'))
        ret = {'shell': '/usr/bin/false', 'name': '_TEST_GROUP', 'gid': 83,
                     'groups': ['_TEST_GROUP'], 'home': '/var/virusmails',
                     'fullname': 'AMaViS Daemon', 'uid': 83}
        with patch('salt.modules.mac_user.list_groups',
                   MagicMock(return_value=['_TEST_GROUP'])):
            self.assertEqual(mac_user._format_info(data), ret)

    def test_list_users(self):
        '''
        Tests the list of all users
        '''
        with patch('pwd.getpwall', MagicMock(return_value=self.mock_pwall)):
            ret = ['_amavisd', '_appleevents', '_appowner']
            self.assertEqual(mac_user.list_users(), ret)
