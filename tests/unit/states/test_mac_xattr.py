# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Libs
import salt.states.mac_xattr as xattr

# Import Salt Testing Libs
from tests.support.unit import TestCase
from tests.support.mock import (
    MagicMock,
    patch
)

xattr.__salt__ = {}


class XAttrTestCase(TestCase):

    @patch('os.path.exists')
    def test_exists_not(self, exists_mock):
        '''
            Test adding an attribute when it doesn't exist
        '''
        expected = {
            'changes': {'key': 'value'},
            'comment': '',
            'name': '/path/to/file',
            'result': True
        }

        exists_mock.return_value = True

        list_mock = MagicMock(return_value={'other.id': 'value2'})
        write_mock = MagicMock()
        with patch.dict(xattr.__salt__, {'xattr.list': list_mock,
                                         'xattr.write': write_mock}):
            out = xattr.exists('/path/to/file', ['key=value'])

            list_mock.assert_called_once_with('/path/to/file')
            write_mock.assert_called_once_with('/path/to/file', 'key', 'value', False)
            self.assertEqual(out, expected)

    @patch('os.path.exists')
    def test_exists_change(self, exists_mock):
        '''
            Test changing and attribute value
        '''
        expected = {
            'changes': {'key': 'other_value'},
            'comment': '',
            'name': '/path/to/file',
            'result': True
        }

        exists_mock.return_value = True

        list_mock = MagicMock(return_value={'key': 'value'})
        write_mock = MagicMock()
        with patch.dict(xattr.__salt__, {'xattr.list': list_mock,
                                         'xattr.write': write_mock}):
            out = xattr.exists('/path/to/file', ['key=other_value'])

            list_mock.assert_called_once_with('/path/to/file')
            write_mock.assert_called_once_with('/path/to/file', 'key', 'other_value', False)
            self.assertEqual(out, expected)

    @patch('os.path.exists')
    def test_exists_already(self, exists_mock):
        '''
            Test that having the same value does nothing
        '''
        expected = {
            'changes': {},
            'comment': 'All values existed correctly.',
            'name': '/path/to/file',
            'result': True
        }

        exists_mock.return_value = True

        list_mock = MagicMock(return_value={'key': 'value'})
        write_mock = MagicMock()
        with patch.dict(xattr.__salt__, {'xattr.list': list_mock,
                                         'xattr.write': write_mock}):
            out = xattr.exists('/path/to/file', ['key=value'])

            list_mock.assert_called_once_with('/path/to/file')
            assert not write_mock.called
            self.assertEqual(out, expected)

    @patch('os.path.exists')
    def test_delete(self, exists_mock):
        '''
            Test deleting an attribute from a file
        '''
        expected = {
            'changes': {'key': 'delete'},
            'comment': '',
            'name': '/path/to/file',
            'result': True
        }

        exists_mock.return_value = True

        list_mock = MagicMock(return_value={'key': 'value2'})
        delete_mock = MagicMock()
        with patch.dict(xattr.__salt__, {'xattr.list': list_mock,
                                         'xattr.delete': delete_mock}):
            out = xattr.delete('/path/to/file', ['key'])

            list_mock.assert_called_once_with('/path/to/file')
            delete_mock.assert_called_once_with('/path/to/file', 'key')
            self.assertEqual(out, expected)

    @patch('os.path.exists')
    def test_delete_not(self, exists_mock):
        '''
            Test deleting an attribute that doesn't exist from a file
        '''
        expected = {
            'changes': {},
            'comment': 'All attributes were already deleted.',
            'name': '/path/to/file',
            'result': True
        }

        exists_mock.return_value = True

        list_mock = MagicMock(return_value={'other.key': 'value2'})
        delete_mock = MagicMock()
        with patch.dict(xattr.__salt__, {'xattr.list': list_mock,
                                         'xattr.delete': delete_mock}):
            out = xattr.delete('/path/to/file', ['key'])

            list_mock.assert_called_once_with('/path/to/file')
            assert not delete_mock.called
            self.assertEqual(out, expected)
