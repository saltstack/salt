# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Libs
from salt.modules import mac_xattr as xattr

# Import Salt Testing Libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    MagicMock,
    patch,
    call
)

ensure_in_syspath('../../')

xattr.__salt__ = {}


class XAttrTestCase(TestCase):

    def test_list_attrs(self):
        '''
            Test listing all of the extended attributes of a file
        '''
        expected = {'com.test': 'first', 'com.other': 'second'}
        mock = MagicMock(side_effect=['com.test\ncom.other', 'first', 'second'])
        with patch.dict(xattr.__salt__, {'cmd.run': mock}):
            out = xattr.list('/path/to/file')

            calls = [
                call('xattr "/path/to/file"'),
                call('xattr -p  "com.test" "/path/to/file"'),
                call('xattr -p  "com.other" "/path/to/file"')
            ]
            mock.assert_has_calls(calls)
            self.assertEqual(out, expected)

    def test_list_attrs_hex(self):
        '''
            Test listing all of the extended attributes of a file with hex
        '''
        expected = {'com.test': 'first', 'com.other': 'second'}
        mock = MagicMock(side_effect=['com.test\ncom.other', 'first', 'second'])
        with patch.dict(xattr.__salt__, {'cmd.run': mock}):
            out = xattr.list('/path/to/file', True)

            calls = [
                call('xattr "/path/to/file"'),
                call('xattr -p -x "com.test" "/path/to/file"'),
                call('xattr -p -x "com.other" "/path/to/file"')
            ]
            mock.assert_has_calls(calls)
            self.assertEqual(out, expected)

    def test_list_attrs_missing(self):
        '''
            Test listing attributes of a missing file
        '''

        mock = MagicMock(return_value='No such file')
        with patch.dict(xattr.__salt__, {'cmd.run': mock}):
            out = xattr.list('/path/to/file')
            mock.assert_called_once_with('xattr "/path/to/file"')
            self.assertIsNone(out)

    def test_read_attrs(self):
        '''
            Test reading a specific attribute from a file
        '''
        expected = "out"
        mock = MagicMock(return_value=expected)
        with patch.dict(xattr.__salt__, {'cmd.run': mock}):
            out = xattr.read('/path/to/file', 'com.attr')

            mock.assert_called_once_with('xattr -p  "com.attr" "/path/to/file"')
            self.assertEqual(out, expected)

    def test_read_attrs_hex(self):
        '''
            Test reading a specific attribute from a file with hex
        '''
        expected = "out"
        mock = MagicMock(return_value=expected)
        with patch.dict(xattr.__salt__, {'cmd.run': mock}):
            out = xattr.read('/path/to/file', 'com.attr', True)

            mock.assert_called_once_with('xattr -p -x "com.attr" "/path/to/file"')
            self.assertEqual(out, expected)

    def test_write_attrs(self):
        '''
            Test writing a specific attribute to a file
        '''
        expected = "out"
        mock = MagicMock(return_value=expected)
        with patch.dict(xattr.__salt__, {'cmd.run': mock}):
            out = xattr.write('/path/to/file', 'com.attr', 'value')

            mock.assert_called_once_with('xattr -w  "com.attr" "value" "/path/to/file"')
            self.assertEqual(out, expected)

    def test_delete_attrs(self):
        '''
            Test deleting a specific attribute from a file
        '''
        expected = "out"
        mock = MagicMock(return_value=expected)
        with patch.dict(xattr.__salt__, {'cmd.run': mock}):
            out = xattr.delete('/path/to/file', 'com.attr')

            mock.assert_called_once_with('xattr -d "com.attr" "/path/to/file"')
            self.assertEqual(out, expected)

    def test_clear_attrs(self):
        '''
            Test clearing all attributes on a file
        '''
        expected = "out"
        mock = MagicMock(return_value=expected)
        with patch.dict(xattr.__salt__, {'cmd.run': mock}):
            out = xattr.clear('/path/to/file')

            mock.assert_called_once_with('xattr -c "/path/to/file"')
            self.assertEqual(out, expected)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(XAttrTestCase, needs_daemon=False)
