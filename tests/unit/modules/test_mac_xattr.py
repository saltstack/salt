# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase
from tests.support.mock import MagicMock, patch

# Import Salt Libs
from salt.exceptions import CommandExecutionError
import salt.modules.mac_xattr as xattr
import salt.utils.mac_utils


class XAttrTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        return {xattr: {}}

    def test_list(self):
        '''
        Test xattr.list
        '''
        expected = {'spongebob': 'squarepants',
                    'squidward': 'patrick'}
        with patch.object(xattr, 'read', MagicMock(side_effect=['squarepants',
                                                                'patrick'])), \
                patch('salt.utils.mac_utils.execute_return_result',
                      MagicMock(return_value='spongebob\nsquidward')):
            self.assertEqual(xattr.list_('path/to/file'), expected)

    def test_list_missing(self):
        '''
        Test listing attributes of a missing file
        '''
        with patch('salt.utils.mac_utils.execute_return_result',
                   MagicMock(side_effect=CommandExecutionError('No such file'))):
            self.assertRaises(CommandExecutionError, xattr.list_, '/path/to/file')

    def test_read(self):
        '''
        Test reading a specific attribute from a file
        '''
        with patch('salt.utils.mac_utils.execute_return_result',
                   MagicMock(return_value='expected results')):
            self.assertEqual(xattr.read('/path/to/file', 'com.attr'),
                             'expected results')

    def test_read_hex(self):
        '''
        Test reading a specific attribute from a file
        '''
        with patch.object(salt.utils.mac_utils, 'execute_return_result',
                          MagicMock(return_value='expected results')) as mock:
            self.assertEqual(
                xattr.read('/path/to/file', 'com.attr', **{'hex': True}),
                'expected results'
            )
            mock.assert_called_once_with(
                ['xattr', '-p', '-x', 'com.attr', '/path/to/file'])

    def test_read_missing(self):
        '''
        Test reading a specific attribute from a file
        '''
        with patch('salt.utils.mac_utils.execute_return_result',
                   MagicMock(side_effect=CommandExecutionError('No such file'))):
            self.assertRaises(CommandExecutionError,
                              xattr.read,
                              '/path/to/file',
                              'attribute')

    def test_write(self):
        '''
        Test writing a specific attribute to a file
        '''
        mock_cmd = MagicMock(return_value='squarepants')
        with patch.object(xattr, 'read', mock_cmd), \
                patch('salt.utils.mac_utils.execute_return_success',
                      MagicMock(return_value=True)):
            self.assertTrue(xattr.write('/path/to/file',
                                        'spongebob',
                                        'squarepants'))

    def test_write_missing(self):
        '''
        Test writing a specific attribute to a file
        '''
        with patch('salt.utils.mac_utils.execute_return_success',
                   MagicMock(side_effect=CommandExecutionError('No such file'))):
            self.assertRaises(CommandExecutionError,
                              xattr.write,
                              '/path/to/file',
                              'attribute',
                              'value')

    def test_delete(self):
        '''
        Test deleting a specific attribute from a file
        '''
        mock_cmd = MagicMock(return_value={'spongebob': 'squarepants'})
        with patch.object(xattr, 'list_', mock_cmd), \
                patch('salt.utils.mac_utils.execute_return_success',
                      MagicMock(return_value=True)):
            self.assertTrue(xattr.delete('/path/to/file', 'attribute'))

    def test_delete_missing(self):
        '''
        Test deleting a specific attribute from a file
        '''
        with patch('salt.utils.mac_utils.execute_return_success',
                   MagicMock(side_effect=CommandExecutionError('No such file'))):
            self.assertRaises(CommandExecutionError,
                              xattr.delete,
                              '/path/to/file',
                              'attribute')

    def test_clear(self):
        '''
        Test clearing all attributes on a file
        '''
        mock_cmd = MagicMock(return_value={})
        with patch.object(xattr, 'list_', mock_cmd), \
                patch('salt.utils.mac_utils.execute_return_success',
                      MagicMock(return_value=True)):
            self.assertTrue(xattr.clear('/path/to/file'))

    def test_clear_missing(self):
        '''
        Test clearing all attributes on a file
        '''
        with patch('salt.utils.mac_utils.execute_return_success',
                   MagicMock(side_effect=CommandExecutionError('No such file'))):
            self.assertRaises(CommandExecutionError, xattr.clear, '/path/to/file')
