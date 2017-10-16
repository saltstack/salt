# -*- coding: utf-8 -*-
'''
Tests for salt.utils.data
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt libs
import salt.utils.data
from tests.support.unit import TestCase, LOREM_IPSUM


class DataTestCase(TestCase):
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

    def test_decode_list(self):
        test_data = [u'unicode_str', [u'unicode_item_in_list', 'second_item_in_list'], {'dict_key': u'dict_val'}]
        expected_ret = ['unicode_str', ['unicode_item_in_list', 'second_item_in_list'], {'dict_key': 'dict_val'}]
        ret = salt.utils.data.decode_list(test_data)
        self.assertEqual(ret, expected_ret)

    def test_decode_dict(self):
        test_data = {u'test_unicode_key': u'test_unicode_val',
                     'test_list_key': ['list_1', u'unicode_list_two'],
                     u'test_dict_key': {'test_sub_dict_key': 'test_sub_dict_val'}}
        expected_ret = {'test_unicode_key': 'test_unicode_val',
                        'test_list_key': ['list_1', 'unicode_list_two'],
                        'test_dict_key': {'test_sub_dict_key': 'test_sub_dict_val'}}
        ret = salt.utils.data.decode_dict(test_data)
        self.assertDictEqual(ret, expected_ret)

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
