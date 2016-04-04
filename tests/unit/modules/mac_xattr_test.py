# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import MagicMock, patch

ensure_in_syspath('../../')

# Import Salt Libs
from salt.exceptions import CommandExecutionError
from salt.modules import mac_xattr as xattr
import salt.utils.mac_utils

xattr.__salt__ = {}


class XAttrTestCase(TestCase):

    @patch('salt.utils.mac_utils.execute_return_result',
           MagicMock(return_value='spongebob\nsquidward'))
    def test_list(self):
        '''
        Test xattr.list
        '''
        expected = {'spongebob': 'squarepants',
                    'squidward': 'patrick'}
        with patch.object(xattr, 'read', MagicMock(side_effect=['squarepants',
                                                                'patrick'])):
            self.assertEqual(xattr.list('path/to/file'), expected)

    @patch('salt.utils.mac_utils.execute_return_result',
           MagicMock(side_effect=CommandExecutionError('No such file')))
    def test_list_missing(self):
        '''
        Test listing attributes of a missing file
        '''
        self.assertRaises(CommandExecutionError, xattr.list, '/path/to/file')

    @patch('salt.utils.mac_utils.execute_return_result',
           MagicMock(return_value='expected results'))
    def test_read(self):
        '''
        Test reading a specific attribute from a file
        '''
        self.assertEqual(xattr.read('/path/to/file', 'com.attr'),
                         'expected results')

    def test_read_hex(self):
        '''
        Test reading a specific attribute from a file
        '''
        with patch.object(salt.utils.mac_utils, 'execute_return_result',
                          MagicMock(return_value='expected results')) as mock:
            self.assertEqual(xattr.read('/path/to/file', 'com.attr', True),
                             'expected results')
            mock.assert_called_once_with('xattr -p -x "com.attr" "/path/to/file"')

    @patch('salt.utils.mac_utils.execute_return_result',
           MagicMock(side_effect=CommandExecutionError('No such file')))
    def test_read_missing(self):
        '''
        Test reading a specific attribute from a file
        '''
        self.assertRaises(CommandExecutionError,
                          xattr.read,
                          '/path/to/file',
                          'attribute')

    @patch('salt.utils.mac_utils.execute_return_success',
           MagicMock(return_value=True))
    def test_write(self):
        '''
        Test writing a specific attribute to a file
        '''
        mock_cmd = MagicMock(return_value='squarepants')
        with patch.object(xattr, 'read', mock_cmd):
            self.assertTrue(xattr.write('/path/to/file',
                                        'spongebob',
                                        'squarepants'))

    @patch('salt.utils.mac_utils.execute_return_success',
           MagicMock(side_effect=CommandExecutionError('No such file')))
    def test_write_missing(self):
        '''
        Test writing a specific attribute to a file
        '''
        self.assertRaises(CommandExecutionError,
                          xattr.write,
                          '/path/to/file',
                          'attribute',
                          'value')

    @patch('salt.utils.mac_utils.execute_return_success',
           MagicMock(return_value=True))
    def test_delete(self):
        '''
        Test deleting a specific attribute from a file
        '''
        mock_cmd = MagicMock(return_value={'spongebob': 'squarepants'})
        with patch.object(xattr, 'list', mock_cmd):
            self.assertTrue(xattr.delete('/path/to/file', 'attribute'))

    @patch('salt.utils.mac_utils.execute_return_success',
           MagicMock(side_effect=CommandExecutionError('No such file')))
    def test_delete_missing(self):
        '''
        Test deleting a specific attribute from a file
        '''
        self.assertRaises(CommandExecutionError,
                          xattr.delete,
                          '/path/to/file',
                          'attribute')

    @patch('salt.utils.mac_utils.execute_return_success',
           MagicMock(return_value=True))
    def test_clear(self):
        '''
        Test clearing all attributes on a file
        '''
        mock_cmd = MagicMock(return_value={})
        with patch.object(xattr, 'list', mock_cmd):
            self.assertTrue(xattr.clear('/path/to/file'))

    @patch('salt.utils.mac_utils.execute_return_success',
           MagicMock(side_effect=CommandExecutionError('No such file')))
    def test_clear_missing(self):
        '''
        Test clearing all attributes on a file
        '''
        self.assertRaises(CommandExecutionError, xattr.clear, '/path/to/file')


if __name__ == '__main__':
    from integration import run_tests
    run_tests(XAttrTestCase, needs_daemon=False)
