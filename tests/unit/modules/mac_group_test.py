# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''

# Import Salt Testing Libs
from salttesting import TestCase
from salttesting.mock import MagicMock, patch

# Import Salt Libs
from salt.modules import mac_group
from salt.exceptions import SaltInvocationError, CommandExecutionError

# Import python Libs
import grp


class MacGroupTestCase(TestCase):
    '''
    TestCase for the salt.modules.mac_group module
    '''
    mock_group = {'passwd': '*', 'gid': 0, 'name': 'wheel', 'members': ['root']}
    mock_getgrall = [grp.struct_group(('foo', '*', 20, ['test']))]

     # 'add' function tests: 4
     #  Only tested error handling
     #  Full functionality tests covered in integration testing

    @patch('salt.modules.mac_group.info', MagicMock(return_value=mock_group))
    def test_add_group_exists(self):
        '''
        Tests if the group already exists or not
        '''
        self.assertRaises(CommandExecutionError, mac_group.add, 'wheel')

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

    def test_format_info(self):
        '''
        Tests the formatting of returned group information
        '''
        data = grp.struct_group(('wheel', '*', 0, ['root']))
        ret = {'passwd': '*', 'gid': 0, 'name': 'wheel', 'members': ['root']}
        self.assertEqual(mac_group._format_info(data), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MacGroupTestCase, needs_daemon=False)
