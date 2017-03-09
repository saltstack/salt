# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''

# Import python libs
from __future__ import absolute_import
import grp

# Import Salt Testing Libs
from tests.support.unit import TestCase
from tests.support.mock import MagicMock, patch

# Import Salt Libs
from salt.modules import mac_group
from salt.exceptions import SaltInvocationError, CommandExecutionError


class MacGroupTestCase(TestCase):
    '''
    TestCase for the salt.modules.mac_group module
    '''

    mac_group.__context__ = {}
    mac_group.__salt__ = {}

    mock_group = {'passwd': '*', 'gid': 0, 'name': 'test', 'members': ['root']}
    mock_getgrall = [grp.struct_group(('foo', '*', 20, ['test']))]

    # 'add' function tests: 6

    @patch('salt.modules.mac_group.info', MagicMock(return_value=mock_group))
    def test_add_group_exists(self):
        '''
        Tests if the group already exists or not
        '''
        self.assertRaises(CommandExecutionError, mac_group.add, 'test')

    @patch('salt.modules.mac_group.info', MagicMock(return_value={}))
    def test_add_whitespace(self):
        '''
        Tests if there is whitespace in the group name
        '''
        self.assertRaises(SaltInvocationError, mac_group.add, 'white space')

    @patch('salt.modules.mac_group.info', MagicMock(return_value={}))
    def test_add_underscore(self):
        '''
        Tests if the group name starts with an underscore or not
        '''
        self.assertRaises(SaltInvocationError, mac_group.add, '_Test')

    @patch('salt.modules.mac_group.info', MagicMock(return_value={}))
    def test_add_gid_int(self):
        '''
        Tests if the gid is an int or not
        '''
        self.assertRaises(SaltInvocationError, mac_group.add, 'foo', 'foo')

    @patch('salt.modules.mac_group.info', MagicMock(return_value={}))
    @patch('salt.modules.mac_group._list_gids', MagicMock(return_value=['3456']))
    def test_add_gid_exists(self):
        '''
        Tests if the gid is already in use or not
        '''
        self.assertRaises(CommandExecutionError, mac_group.add, 'foo', 3456)

    @patch('salt.modules.mac_group.info', MagicMock(return_value={}))
    @patch('salt.modules.mac_group._list_gids', MagicMock(return_value=[]))
    def test_add(self):
        '''
        Tests if specified group was added
        '''
        mock_ret = MagicMock(return_value=0)
        with patch.dict(mac_group.__salt__, {'cmd.retcode': mock_ret}):
            self.assertTrue(mac_group.add('test', 500))

    # 'delete' function tests: 4

    def test_delete_whitespace(self):
        '''
        Tests if there is whitespace in the group name
        '''
        self.assertRaises(SaltInvocationError, mac_group.delete, 'white space')

    def test_delete_underscore(self):
        '''
        Tests if the group name starts with an underscore or not
        '''
        self.assertRaises(SaltInvocationError, mac_group.delete, '_Test')

    @patch('salt.modules.mac_group.info', MagicMock(return_value={}))
    def test_delete_group_exists(self):
        '''
        Tests if the group to be deleted exists or not
        '''
        self.assertTrue(mac_group.delete('test'))

    @patch('salt.modules.mac_group.info', MagicMock(return_value=mock_group))
    def test_delete(self):
        '''
        Tests if the specified group was deleted
        '''
        mock_ret = MagicMock(return_value=0)
        with patch.dict(mac_group.__salt__, {'cmd.retcode': mock_ret}):
            self.assertTrue(mac_group.delete('test'))

    # 'info' function tests: 2

    def test_info_whitespace(self):
        '''
        Tests if there is whitespace in the group name
        '''
        self.assertRaises(SaltInvocationError, mac_group.info, 'white space')

    @patch('grp.getgrall', MagicMock(return_value=mock_getgrall))
    def test_info(self):
        '''
        Tests the return of group information
        '''
        ret = {'passwd': '*', 'gid': 20, 'name': 'foo', 'members': ['test']}
        self.assertEqual(mac_group.info('foo'), ret)

    # '_format_info' function tests: 1

    def test_format_info(self):
        '''
        Tests the formatting of returned group information
        '''
        data = grp.struct_group(('wheel', '*', 0, ['root']))
        ret = {'passwd': '*', 'gid': 0, 'name': 'wheel', 'members': ['root']}
        self.assertEqual(mac_group._format_info(data), ret)

    # 'getent' function tests: 1

    @patch('grp.getgrall', MagicMock(return_value=mock_getgrall))
    def test_getent(self):
        '''
        Tests the return of information on all groups
        '''
        ret = [{'passwd': '*', 'gid': 20, 'name': 'foo', 'members': ['test']}]
        self.assertEqual(mac_group.getent(), ret)

    # 'chgid' function tests: 4

    def test_chgid_gid_int(self):
        '''
        Tests if gid is an integer or not
        '''
        self.assertRaises(SaltInvocationError, mac_group.chgid, 'foo', 'foo')

    @patch('salt.modules.mac_group.info', MagicMock(return_value={}))
    def test_chgid_group_exists(self):
        '''
        Tests if the group id exists or not
        '''
        mock_pre_gid = MagicMock(return_value='')
        with patch.dict(mac_group.__salt__,
                        {'file.group_to_gid': mock_pre_gid}):
            self.assertRaises(CommandExecutionError,
                              mac_group.chgid, 'foo', 4376)

    @patch('salt.modules.mac_group.info', MagicMock(return_value=mock_group))
    def test_chgid_gid_same(self):
        '''
        Tests if the group id is the same as argument
        '''
        mock_pre_gid = MagicMock(return_value=0)
        with patch.dict(mac_group.__salt__,
                        {'file.group_to_gid': mock_pre_gid}):
            self.assertTrue(mac_group.chgid('test', 0))

    @patch('salt.modules.mac_group.info', MagicMock(return_value=mock_group))
    def test_chgid(self):
        '''
        Tests the gid for a named group was changed
        '''
        mock_pre_gid = MagicMock(return_value=0)
        mock_ret = MagicMock(return_value=0)
        with patch.dict(mac_group.__salt__,
                        {'file.group_to_gid': mock_pre_gid}):
            with patch.dict(mac_group.__salt__, {'cmd.retcode': mock_ret}):
                self.assertTrue(mac_group.chgid('test', 500))
