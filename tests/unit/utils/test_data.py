# -*- coding: utf-8 -*-
'''
Tests for salt.utils.data
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

# Import Salt libs
import salt.utils.data
import salt.utils.data
from salt.utils.odict import OrderedDict
from tests.support.unit import TestCase, skipIf, LOREM_IPSUM
from tests.support.mock import patch, NO_MOCK, NO_MOCK_REASON
from salt.ext.six.moves import builtins  # pylint: disable=import-error,redefined-builtin

log = logging.getLogger(__name__)
_b = lambda x: x.encode('utf-8')
# Some randomized data that will not decode
BYTES = b'\x9c\xb1\xf7\xa3'
# This is an example of a unicode string with й constructed using two separate
# code points. Do not modify it.
EGGS = '\u044f\u0438\u0306\u0446\u0430'


class DataTestCase(TestCase):
    test_data = [
        'unicode_str',
        _b('питон'),
        123,
        456.789,
        True,
        False,
        None,
        EGGS,
        BYTES,
        [123, 456.789, _b('спам'), True, False, None, EGGS, BYTES],
        (987, 654.321, _b('яйца'), EGGS, None, (True, EGGS, BYTES)),
        {_b('str_key'): _b('str_val'),
         None: True,
         123: 456.789,
         EGGS: BYTES,
         _b('subdict'): {'unicode_key': EGGS,
                         _b('tuple'): (123, 'hello', _b('world'), True, EGGS, BYTES),
                         _b('list'): [456, _b('спам'), False, EGGS, BYTES]}},
        OrderedDict([(_b('foo'), 'bar'), (123, 456), (EGGS, BYTES)])
    ]

    def test_sorted_ignorecase(self):
        test_list = ['foo', 'Foo', 'bar', 'Bar']
        expected_list = ['bar', 'Bar', 'foo', 'Foo']
        self.assertEqual(
            salt.utils.data.sorted_ignorecase(test_list), expected_list)

    def test_mysql_to_dict(self):
        test_mysql_output = ['+----+------+-----------+------+---------+------+-------+------------------+',
                             '| Id | User | Host      | db   | Command | Time | State | Info             |',
                             '+----+------+-----------+------+---------+------+-------+------------------+',
                             '|  7 | root | localhost | NULL | Query   |    0 | init  | show processlist |',
                             '+----+------+-----------+------+---------+------+-------+------------------+']

        ret = salt.utils.data.mysql_to_dict(test_mysql_output, 'Info')
        expected_dict = {
            'show processlist': {'Info': 'show processlist', 'db': 'NULL', 'State': 'init', 'Host': 'localhost',
                                 'Command': 'Query', 'User': 'root', 'Time': 0, 'Id': 7}}

        self.assertDictEqual(ret, expected_dict)

    def test_subdict_match(self):
        test_two_level_dict = {'foo': {'bar': 'baz'}}
        test_two_level_comb_dict = {'foo': {'bar': 'baz:woz'}}
        test_two_level_dict_and_list = {
            'abc': ['def', 'ghi', {'lorem': {'ipsum': [{'dolor': 'sit'}]}}],
        }
        test_three_level_dict = {'a': {'b': {'c': 'v'}}}

        self.assertTrue(
            salt.utils.data.subdict_match(
                test_two_level_dict, 'foo:bar:baz'
            )
        )
        # In test_two_level_comb_dict, 'foo:bar' corresponds to 'baz:woz', not
        # 'baz'. This match should return False.
        self.assertFalse(
            salt.utils.data.subdict_match(
                test_two_level_comb_dict, 'foo:bar:baz'
            )
        )
        # This tests matching with the delimiter in the value part (in other
        # words, that the path 'foo:bar' corresponds to the string 'baz:woz').
        self.assertTrue(
            salt.utils.data.subdict_match(
                test_two_level_comb_dict, 'foo:bar:baz:woz'
            )
        )
        # This would match if test_two_level_comb_dict['foo']['bar'] was equal
        # to 'baz:woz:wiz', or if there was more deep nesting. But it does not,
        # so this should return False.
        self.assertFalse(
            salt.utils.data.subdict_match(
                test_two_level_comb_dict, 'foo:bar:baz:woz:wiz'
            )
        )
        # This tests for cases when a key path corresponds to a list. The
        # value part 'ghi' should be successfully matched as it is a member of
        # the list corresponding to key path 'abc'. It is somewhat a
        # duplication of a test within test_traverse_dict_and_list, but
        # salt.utils.data.subdict_match() does more than just invoke
        # salt.utils.traverse_list_and_dict() so this particular assertion is a
        # sanity check.
        self.assertTrue(
            salt.utils.data.subdict_match(
                test_two_level_dict_and_list, 'abc:ghi'
            )
        )
        # This tests the use case of a dict embedded in a list, embedded in a
        # list, embedded in a dict. This is a rather absurd case, but it
        # confirms that match recursion works properly.
        self.assertTrue(
            salt.utils.data.subdict_match(
                test_two_level_dict_and_list, 'abc:lorem:ipsum:dolor:sit'
            )
        )
        # Test four level dict match for reference
        self.assertTrue(
            salt.utils.data.subdict_match(
                test_three_level_dict, 'a:b:c:v'
            )
        )
        self.assertFalse(
        # Test regression in 2015.8 where 'a:c:v' would match 'a:b:c:v'
            salt.utils.data.subdict_match(
                test_three_level_dict, 'a:c:v'
            )
        )
        # Test wildcard match
        self.assertTrue(
            salt.utils.data.subdict_match(
                test_three_level_dict, 'a:*:c:v'
            )
        )

    def test_traverse_dict(self):
        test_two_level_dict = {'foo': {'bar': 'baz'}}

        self.assertDictEqual(
            {'not_found': 'nope'},
            salt.utils.data.traverse_dict(
                test_two_level_dict, 'foo:bar:baz', {'not_found': 'nope'}
            )
        )
        self.assertEqual(
            'baz',
            salt.utils.data.traverse_dict(
                test_two_level_dict, 'foo:bar', {'not_found': 'not_found'}
            )
        )

    def test_traverse_dict_and_list(self):
        test_two_level_dict = {'foo': {'bar': 'baz'}}
        test_two_level_dict_and_list = {
            'foo': ['bar', 'baz', {'lorem': {'ipsum': [{'dolor': 'sit'}]}}]
        }

        # Check traversing too far: salt.utils.data.traverse_dict_and_list() returns
        # the value corresponding to a given key path, and baz is a value
        # corresponding to the key path foo:bar.
        self.assertDictEqual(
            {'not_found': 'nope'},
            salt.utils.data.traverse_dict_and_list(
                test_two_level_dict, 'foo:bar:baz', {'not_found': 'nope'}
            )
        )
        # Now check to ensure that foo:bar corresponds to baz
        self.assertEqual(
            'baz',
            salt.utils.data.traverse_dict_and_list(
                test_two_level_dict, 'foo:bar', {'not_found': 'not_found'}
            )
        )
        # Check traversing too far
        self.assertDictEqual(
            {'not_found': 'nope'},
            salt.utils.data.traverse_dict_and_list(
                test_two_level_dict_and_list, 'foo:bar', {'not_found': 'nope'}
            )
        )
        # Check index 1 (2nd element) of list corresponding to path 'foo'
        self.assertEqual(
            'baz',
            salt.utils.data.traverse_dict_and_list(
                test_two_level_dict_and_list, 'foo:1', {'not_found': 'not_found'}
            )
        )
        # Traverse a couple times into dicts embedded in lists
        self.assertEqual(
            'sit',
            salt.utils.data.traverse_dict_and_list(
                test_two_level_dict_and_list,
                'foo:lorem:ipsum:dolor',
                {'not_found': 'not_found'}
            )
        )

    def test_compare_dicts(self):
        ret = salt.utils.data.compare_dicts(old={'foo': 'bar'}, new={'foo': 'bar'})
        self.assertEqual(ret, {})

        ret = salt.utils.data.compare_dicts(old={'foo': 'bar'}, new={'foo': 'woz'})
        expected_ret = {'foo': {'new': 'woz', 'old': 'bar'}}
        self.assertDictEqual(ret, expected_ret)

    def test_decode(self):
        '''
        NOTE: This uses the lambda "_b" defined above in the global scope,
        which encodes a string to a bytestring, assuming utf-8.
        '''
        expected = [
            'unicode_str',
            'питон',
            123,
            456.789,
            True,
            False,
            None,
            'яйца',
            BYTES,
            [123, 456.789, 'спам', True, False, None, 'яйца', BYTES],
            (987, 654.321, 'яйца', 'яйца', None, (True, 'яйца', BYTES)),
            {'str_key': 'str_val',
             None: True,
             123: 456.789,
             'яйца': BYTES,
             'subdict': {'unicode_key': 'яйца',
                         'tuple': (123, 'hello', 'world', True, 'яйца', BYTES),
                         'list': [456, 'спам', False, 'яйца', BYTES]}},
            OrderedDict([('foo', 'bar'), (123, 456), ('яйца', BYTES)])
        ]

        ret = salt.utils.data.decode(
            self.test_data,
            encoding='utf-8',
            keep=True,
            normalize=True,
            preserve_dict_class=True,
            preserve_tuples=True)
        self.assertEqual(ret, expected)

        # The binary data in the data structure should fail to decode, even
        # using the fallback, and raise an exception.
        self.assertRaises(
            UnicodeDecodeError,
            salt.utils.data.decode,
            self.test_data,
            encoding='utf-8',
            keep=False,
            normalize=True,
            preserve_dict_class=True,
            preserve_tuples=True)

        # Now munge the expected data so that we get what we would expect if we
        # disable preservation of dict class and tuples
        expected[10] = [987, 654.321, 'яйца', 'яйца', None, [True, 'яйца', BYTES]]
        expected[11]['subdict']['tuple'] = [123, 'hello', 'world', True, 'яйца', BYTES]
        expected[12] = {'foo': 'bar', 123: 456, 'яйца': BYTES}

        ret = salt.utils.data.decode(
            self.test_data,
            encoding='utf-8',
            keep=True,
            normalize=True,
            preserve_dict_class=False,
            preserve_tuples=False)
        self.assertEqual(ret, expected)

        # Now test single non-string, non-data-structure items, these should
        # return the same value when passed to this function
        for item in (123, 4.56, True, False, None):
            log.debug('Testing decode of %s', item)
            self.assertEqual(salt.utils.data.decode(item), item)

        # Test single strings (not in a data structure)
        self.assertEqual(salt.utils.data.decode('foo'), 'foo')
        self.assertEqual(salt.utils.data.decode(_b('bar')), 'bar')
        self.assertEqual(salt.utils.data.decode(EGGS, normalize=True), 'яйца')
        self.assertEqual(salt.utils.data.decode(EGGS, normalize=False), EGGS)

        # Test binary blob
        self.assertEqual(salt.utils.data.decode(BYTES, keep=True), BYTES)
        self.assertRaises(
            UnicodeDecodeError,
            salt.utils.data.decode,
            BYTES,
            keep=False)

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_decode_fallback(self):
        '''
        Test fallback to utf-8
        '''
        with patch.object(builtins, '__salt_system_encoding__', 'ascii'):
            self.assertEqual(salt.utils.data.decode(_b('яйца')), 'яйца')

    def test_encode(self):
        '''
        NOTE: This uses the lambda "_b" defined above in the global scope,
        which encodes a string to a bytestring, assuming utf-8.
        '''
        expected = [
            _b('unicode_str'),
            _b('питон'),
            123,
            456.789,
            True,
            False,
            None,
            _b(EGGS),
            BYTES,
            [123, 456.789, _b('спам'), True, False, None, _b(EGGS), BYTES],
            (987, 654.321, _b('яйца'), _b(EGGS), None, (True, _b(EGGS), BYTES)),
            {_b('str_key'): _b('str_val'),
             None: True,
             123: 456.789,
             _b(EGGS): BYTES,
             _b('subdict'): {_b('unicode_key'): _b(EGGS),
                             _b('tuple'): (123, _b('hello'), _b('world'), True, _b(EGGS), BYTES),
                             _b('list'): [456, _b('спам'), False, _b(EGGS), BYTES]}},
             OrderedDict([(_b('foo'), _b('bar')), (123, 456), (_b(EGGS), BYTES)])
        ]

        # Both keep=True and keep=False should work because the BYTES data is
        # already bytes.
        ret = salt.utils.data.encode(
            self.test_data,
            keep=True,
            preserve_dict_class=True,
            preserve_tuples=True)
        self.assertEqual(ret, expected)
        ret = salt.utils.data.encode(
            self.test_data,
            keep=False,
            preserve_dict_class=True,
            preserve_tuples=True)
        self.assertEqual(ret, expected)

        # Now munge the expected data so that we get what we would expect if we
        # disable preservation of dict class and tuples
        expected[10] = [987, 654.321, _b('яйца'), _b(EGGS), None, [True, _b(EGGS), BYTES]]
        expected[11][_b('subdict')][_b('tuple')] = [
            123, _b('hello'), _b('world'), True, _b(EGGS), BYTES
        ]
        expected[12] = {_b('foo'): _b('bar'), 123: 456, _b(EGGS): BYTES}

        ret = salt.utils.data.encode(
            self.test_data,
            keep=True,
            preserve_dict_class=False,
            preserve_tuples=False)
        self.assertEqual(ret, expected)
        ret = salt.utils.data.encode(
            self.test_data,
            keep=False,
            preserve_dict_class=False,
            preserve_tuples=False)
        self.assertEqual(ret, expected)

        # Now test single non-string, non-data-structure items, these should
        # return the same value when passed to this function
        for item in (123, 4.56, True, False, None):
            log.debug('Testing encode of %s', item)
            self.assertEqual(salt.utils.data.encode(item), item)

        # Test single strings (not in a data structure)
        self.assertEqual(salt.utils.data.encode('foo'), _b('foo'))
        self.assertEqual(salt.utils.data.encode(_b('bar')), _b('bar'))

        # Test binary blob, nothing should happen even when keep=False since
        # the data is already bytes
        self.assertEqual(salt.utils.data.encode(BYTES, keep=True), BYTES)
        self.assertEqual(salt.utils.data.encode(BYTES, keep=False), BYTES)

    def test_encode_keep(self):
        '''
        Whereas we tested the keep argument in test_decode, it is much easier
        to do a more comprehensive test of keep in its own function where we
        can force the encoding.
        '''
        unicode_str = 'питон'
        encoding = 'ascii'

        # Test single string
        self.assertEqual(
            salt.utils.data.encode(unicode_str, encoding, keep=True),
            unicode_str)
        self.assertRaises(
            UnicodeEncodeError,
            salt.utils.data.encode,
            unicode_str,
            encoding,
            keep=False)

        data = [
            unicode_str,
            [b'foo', [unicode_str], {b'key': unicode_str}, (unicode_str,)],
            {b'list': [b'foo', unicode_str],
             b'dict': {b'key': unicode_str},
             b'tuple': (b'foo', unicode_str)},
            ([b'foo', unicode_str], {b'key': unicode_str}, (unicode_str,))
        ]

        # Since everything was a bytestring aside from the bogus data, the
        # return data should be identical. We don't need to test recursive
        # decoding, that has already been tested in test_encode.
        self.assertEqual(
            salt.utils.data.encode(data, encoding,
                                   keep=True, preserve_tuples=True),
            data
        )
        self.assertRaises(
            UnicodeEncodeError,
            salt.utils.data.encode,
            data,
            encoding,
            keep=False,
            preserve_tuples=True)

        for index, item in enumerate(data):
            self.assertEqual(
                salt.utils.data.encode(data[index], encoding,
                                       keep=True, preserve_tuples=True),
                data[index]
            )
            self.assertRaises(
                UnicodeEncodeError,
                salt.utils.data.encode,
                data[index],
                encoding,
                keep=False,
                preserve_tuples=True)

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_encode_fallback(self):
        '''
        Test fallback to utf-8
        '''
        with patch.object(builtins, '__salt_system_encoding__', 'ascii'):
            self.assertEqual(salt.utils.data.encode('яйца'), _b('яйца'))
        with patch.object(builtins, '__salt_system_encoding__', 'CP1252'):
            self.assertEqual(salt.utils.data.encode('Ψ'), _b('Ψ'))

    def test_repack_dict(self):
        list_of_one_element_dicts = [{'dict_key_1': 'dict_val_1'},
                                     {'dict_key_2': 'dict_val_2'},
                                     {'dict_key_3': 'dict_val_3'}]
        expected_ret = {'dict_key_1': 'dict_val_1',
                        'dict_key_2': 'dict_val_2',
                        'dict_key_3': 'dict_val_3'}
        ret = salt.utils.data.repack_dictlist(list_of_one_element_dicts)
        self.assertDictEqual(ret, expected_ret)

        # Try with yaml
        yaml_key_val_pair = '- key1: val1'
        ret = salt.utils.data.repack_dictlist(yaml_key_val_pair)
        self.assertDictEqual(ret, {'key1': 'val1'})

        # Make sure we handle non-yaml junk data
        ret = salt.utils.data.repack_dictlist(LOREM_IPSUM)
        self.assertDictEqual(ret, {})

    def test_stringify(self):
        self.assertRaises(TypeError, salt.utils.data.stringify, 9)
        self.assertEqual(
            salt.utils.data.stringify(['one', 'two', str('three'), 4, 5]),  # future lint: disable=blacklisted-function
            ['one', 'two', 'three', '4', '5']
        )
