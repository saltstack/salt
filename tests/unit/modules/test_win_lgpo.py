# -*- coding: utf-8 -*-
'''
:codeauthor: Shane Lee <slee@saltstack.com>
'''

# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Testing Libs
from tests.support.unit import TestCase

# Import Salt Libs
import salt.modules.win_lgpo as win_lgpo


class WinSystemTestCase(TestCase):
    '''
    Test cases for salt.modules.win_lgpo
    '''
    encoded_null = chr(0).encode('utf-16-le')

    def test__encode_string(self):
        '''
        ``_encode_string`` should return a null terminated ``utf-16-le`` encoded
        string when a string value is passed
        '''
        encoded_value = b''.join(['Salt is awesome'.encode('utf-16-le'),
                                  self.encoded_null])
        value = win_lgpo._encode_string('Salt is awesome')
        self.assertEqual(value, encoded_value)

    def test__encode_string_empty_string(self):
        '''
        ``_encode_string`` should return an encoded null when an empty string
        value is passed
        '''
        value = win_lgpo._encode_string('')
        self.assertEqual(value, self.encoded_null)

    def test__encode_string_error(self):
        '''
        ``_encode_string`` should raise an error if a non-string value is passed
        '''
        self.assertRaises(TypeError, win_lgpo._encode_string, [1])
        test_list = ['item1', 'item2']
        self.assertRaises(TypeError, win_lgpo._encode_string, [test_list])
        test_dict = {'key1': 'value1', 'key2': 'value2'}
        self.assertRaises(TypeError, win_lgpo._encode_string, [test_dict])

    def test__encode_string_none(self):
        '''
        ``_encode_string`` should return an encoded null when ``None`` is passed
        '''
        value = win_lgpo._encode_string(None)
        self.assertEqual(value, self.encoded_null)

    def test__multi_string_get_transform_list(self):
        '''
        ``_multi_string_get_transform`` should return the list when a list is
        passed
        '''
        test_value = ['Spongebob', 'Squarepants']
        value = win_lgpo._policy_info._multi_string_get_transform(item=test_value)
        self.assertEqual(value, test_value)

    def test__multi_string_get_transform_none(self):
        '''
        ``_multi_string_get_transform`` should return "Not Defined" when
        ``None`` is passed
        '''
        test_value = None
        value = win_lgpo._policy_info._multi_string_get_transform(item=test_value)
        self.assertEqual(value, 'Not Defined')

    def test__multi_string_get_transform_invalid(self):
        '''
        ``_multi_string_get_transform`` should return "Not Defined" when
        ``None`` is passed
        '''
        test_value = 'Some String'
        value = win_lgpo._policy_info._multi_string_get_transform(item=test_value)
        self.assertEqual(value, 'Invalid Value')

    def test__multi_string_put_transform_list(self):
        '''
        ``_multi_string_put_transform`` should return the list when a list is
        passed
        '''
        test_value = ['Spongebob', 'Squarepants']
        value = win_lgpo._policy_info._multi_string_put_transform(item=test_value)
        self.assertEqual(value, test_value)

    def test__multi_string_put_transform_none(self):
        '''
        ``_multi_string_put_transform`` should return ``None`` when
        "Not Defined" is passed
        '''
        test_value = "Not Defined"
        value = win_lgpo._policy_info._multi_string_put_transform(item=test_value)
        self.assertEqual(value, None)

    def test__multi_string_put_transform_list_from_string(self):
        '''
        ``_multi_string_put_transform`` should return a list when a comma
        delimited string is passed
        '''
        test_value = "Spongebob,Squarepants"
        value = win_lgpo._policy_info._multi_string_put_transform(item=test_value)
        self.assertEqual(value, ['Spongebob', 'Squarepants'])

    def test__multi_string_put_transform_invalid(self):
        '''
        ``_multi_string_put_transform`` should return "Invalid" value if neither
        string nor list is passed
        '''
        test_value = None
        value = win_lgpo._policy_info._multi_string_put_transform(item=test_value)
        self.assertEqual(value, "Invalid Value")
