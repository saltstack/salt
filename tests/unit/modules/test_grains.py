# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import copy

# Import Salt Testing libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt libs
from salt.exceptions import SaltException
from salt.modules import grains as grainsmod
from salt.utils import dictupdate

# Import 3rd-party libs
from salt.utils.odict import OrderedDict

grainsmod.__opts__ = {
  'conf_file': '/tmp/__salt_test_grains',
  'cachedir':  '/tmp/__salt_test_grains_cache_dir'
}

grainsmod.__salt__ = {}


@patch.dict(grainsmod.__salt__, {'saltutil.refresh_grains': MagicMock()})
@skipIf(NO_MOCK, NO_MOCK_REASON)
class GrainsModuleTestCase(TestCase):

    def test_filter_by(self):
        grainsmod.__grains__ = {
            'os_family': 'MockedOS',
            '1': '1',
            '2': '2',
            'roles': ['A', 'B'],
        }

        dict1 = {'A': 'B', 'C': {'D': {'E': 'F', 'G': 'H'}}}
        dict2 = {
            'default': {
                'A': 'B',
                'C': {
                    'D': 'E'
                },
            },
            '1': {
                'A': 'X',
            },
            '2': {
                'C': {
                    'D': 'H',
                },
            },
            'MockedOS': {
                'A': 'Z',
            },
        }

        mdict1 = {'D': {'E': 'I'}, 'J': 'K'}
        mdict2 = {'A': 'Z'}
        mdict3 = {'C': {'D': 'J'}}

        # test None result with non existent grain and no default
        res = grainsmod.filter_by(dict1, grain='xxx')
        self.assertIs(res, None)

        # test None result with os_family grain and no matching result
        res = grainsmod.filter_by(dict1)
        self.assertIs(res, None)

        # test with non existent grain, and a given default key
        res = grainsmod.filter_by(dict1, grain='xxx', default='C')
        self.assertEqual(res, {'D': {'E': 'F', 'G': 'H'}})

        # add a merge dictionary, F disappears
        res = grainsmod.filter_by(dict1, grain='xxx', merge=mdict1, default='C')
        self.assertEqual(res, {'D': {'E': 'I', 'G': 'H'}, 'J': 'K'})
        # dict1 was altered, reestablish
        dict1 = {'A': 'B', 'C': {'D': {'E': 'F', 'G': 'H'}}}

        # default is not present in dict1, check we only have merge in result
        res = grainsmod.filter_by(dict1, grain='xxx', merge=mdict1, default='Z')
        self.assertEqual(res, mdict1)

        # default is not present in dict1, and no merge, should get None
        res = grainsmod.filter_by(dict1, grain='xxx', default='Z')
        self.assertIs(res, None)

        #test giving a list as merge argument raise exception
        self.assertRaises(
            SaltException,
            grainsmod.filter_by,
            dict1,
            'xxx',
            ['foo'],
            'C'
        )

        #Now, re-test with an existing grain (os_family), but with no match.
        res = grainsmod.filter_by(dict1)
        self.assertIs(res, None)
        res = grainsmod.filter_by(dict1, default='C')
        self.assertEqual(res, {'D': {'E': 'F', 'G': 'H'}})
        res = grainsmod.filter_by(dict1, merge=mdict1, default='C')
        self.assertEqual(res, {'D': {'E': 'I', 'G': 'H'}, 'J': 'K'})
        # dict1 was altered, reestablish
        dict1 = {'A': 'B', 'C': {'D': {'E': 'F', 'G': 'H'}}}
        res = grainsmod.filter_by(dict1, merge=mdict1, default='Z')
        self.assertEqual(res, mdict1)
        res = grainsmod.filter_by(dict1, default='Z')
        self.assertIs(res, None)
        # this one is in fact a traceback in updatedict, merging a string with a dictionary
        self.assertRaises(
            TypeError,
            grainsmod.filter_by,
            dict1,
            merge=mdict1,
            default='A'
        )

        #Now, re-test with a matching grain.
        dict1 = {'A': 'B', 'MockedOS': {'D': {'E': 'F', 'G': 'H'}}}
        res = grainsmod.filter_by(dict1)
        self.assertEqual(res, {'D': {'E': 'F', 'G': 'H'}})
        res = grainsmod.filter_by(dict1, default='A')
        self.assertEqual(res, {'D': {'E': 'F', 'G': 'H'}})
        res = grainsmod.filter_by(dict1, merge=mdict1, default='A')
        self.assertEqual(res, {'D': {'E': 'I', 'G': 'H'}, 'J': 'K'})
        # dict1 was altered, reestablish
        dict1 = {'A': 'B', 'MockedOS': {'D': {'E': 'F', 'G': 'H'}}}
        res = grainsmod.filter_by(dict1, merge=mdict1, default='Z')
        self.assertEqual(res, {'D': {'E': 'I', 'G': 'H'}, 'J': 'K'})
        # dict1 was altered, reestablish
        dict1 = {'A': 'B', 'MockedOS': {'D': {'E': 'F', 'G': 'H'}}}
        res = grainsmod.filter_by(dict1, default='Z')
        self.assertEqual(res, {'D': {'E': 'F', 'G': 'H'}})

        # Test when grain value is a list
        dict1 = {'A': 'B', 'C': {'D': {'E': 'F', 'G': 'H'}}}
        res = grainsmod.filter_by(dict1, grain='roles', default='C')
        self.assertEqual(res, 'B')
        # Test default when grain value is a list
        dict1 = {'Z': 'B', 'C': {'D': {'E': 'F', 'G': 'H'}}}
        res = grainsmod.filter_by(dict1, grain='roles', default='C')
        self.assertEqual(res, {'D': {'E': 'F', 'G': 'H'}})

        # Test with wildcard pattern in the lookup_dict keys
        dict1 = {'*OS': 'B', 'C': {'D': {'E': 'F', 'G': 'H'}}}
        res = grainsmod.filter_by(dict1)
        self.assertEqual(res, 'B')
        # Test with non-strings in lookup_dict keys
        # Issue #38094
        dict1 = {1: 2, 3: {4: 5}, '*OS': 'B'}
        res = grainsmod.filter_by(dict1)
        self.assertEqual(res, 'B')
        # Test with sequence pattern with roles
        dict1 = {'Z': 'B', '[BC]': {'D': {'E': 'F', 'G': 'H'}}}
        res = grainsmod.filter_by(dict1, grain='roles', default='Z')
        self.assertEqual(res, {'D': {'E': 'F', 'G': 'H'}})

        # Base tests
        # NOTE: these may fail to detect errors if dictupdate.update() is broken
        # but then the unit test for dictupdate.update() should fail and expose
        # that.  The purpose of these tests is it validate the logic of how
        # in filter_by() processes its arguments.

        # Test with just the base
        res = grainsmod.filter_by(dict2, grain='xxx', default='xxx', base='default')
        self.assertEqual(res, dict2['default'])

        # Test the base with the OS grain look-up
        res = grainsmod.filter_by(dict2, default='xxx', base='default')
        self.assertEqual(
            res,
            dictupdate.update(copy.deepcopy(dict2['default']), dict2['MockedOS'])
        )

        # Test the base with default
        res = grainsmod.filter_by(dict2, grain='xxx', base='default')
        self.assertEqual(res, dict2['default'])

        res = grainsmod.filter_by(dict2, grain='1', base='default')
        self.assertEqual(
            res,
            dictupdate.update(copy.deepcopy(dict2['default']), dict2['1'])
        )

        res = grainsmod.filter_by(dict2, base='default', merge=mdict2)
        self.assertEqual(
            res,
            dictupdate.update(
                dictupdate.update(
                    copy.deepcopy(dict2['default']),
                    dict2['MockedOS']),
                mdict2
            )
        )

        res = grainsmod.filter_by(dict2, base='default', merge=mdict3)
        self.assertEqual(
            res,
            dictupdate.update(
                dictupdate.update(
                    copy.deepcopy(dict2['default']),
                    dict2['MockedOS']),
                mdict3
            )
        )

    def test_append_not_a_list(self):
        # Failing append to an existing string, without convert
        grainsmod.__grains__ = {'b': 'bval'}
        res = grainsmod.append('b', 'd')
        self.assertEqual(res, 'The key b is not a valid list')
        self.assertEqual(grainsmod.__grains__, {'b': 'bval'})

        # Failing append to an existing dict
        grainsmod.__grains__ = {'b': {'b1': 'bval1'}}
        res = grainsmod.append('b', 'd')
        self.assertEqual(res, 'The key b is not a valid list')
        self.assertEqual(grainsmod.__grains__, {'b': {'b1': 'bval1'}})

    def test_append_already_in_list(self):
        # Append an existing value
        grainsmod.__grains__ = {'a_list': ['a', 'b', 'c'], 'b': 'bval'}
        res = grainsmod.append('a_list', 'b')
        self.assertEqual(res, 'The val b was already in the list a_list')
        self.assertEqual(grainsmod.__grains__, {'a_list': ['a', 'b', 'c'], 'b': 'bval'})

    def test_append_ok(self):
        # Append to an existing list
        grainsmod.__grains__ = {'a_list': ['a', 'b', 'c'], 'b': 'bval'}
        res = grainsmod.append('a_list', 'd')
        self.assertEqual(res, {'a_list': ['a', 'b', 'c', 'd']})
        self.assertEqual(grainsmod.__grains__, {'a_list': ['a', 'b', 'c', 'd'], 'b': 'bval'})

        # Append to an non existing list
        grainsmod.__grains__ = {'b': 'bval'}
        res = grainsmod.append('a_list', 'd')
        self.assertEqual(res, {'a_list': ['d']})
        self.assertEqual(grainsmod.__grains__, {'a_list': ['d'], 'b': 'bval'})

        # Append to an existing string, with convert
        grainsmod.__grains__ = {'b': 'bval'}
        res = grainsmod.append('b', 'd', convert=True)
        self.assertEqual(res, {'b': ['bval', 'd']})
        self.assertEqual(grainsmod.__grains__, {'b': ['bval', 'd']})

        # Append to an existing dict, with convert
        grainsmod.__grains__ = {'b': {'b1': 'bval1'}}
        res = grainsmod.append('b', 'd', convert=True)
        self.assertEqual(res, {'b': [{'b1': 'bval1'}, 'd']})
        self.assertEqual(grainsmod.__grains__, {'b': [{'b1': 'bval1'}, 'd']})

    def test_append_nested_not_a_list(self):
        # Failing append to an existing string, without convert
        grainsmod.__grains__ = {'a': {'b': 'bval'}}
        res = grainsmod.append('a:b', 'd')
        self.assertEqual(res, 'The key a:b is not a valid list')
        self.assertEqual(grainsmod.__grains__, {'a': {'b': 'bval'}})

        # Failing append to an existing dict
        grainsmod.__grains__ = {'a': {'b': {'b1': 'bval1'}}}
        res = grainsmod.append('a:b', 'd')
        self.assertEqual(res, 'The key a:b is not a valid list')
        self.assertEqual(grainsmod.__grains__, {'a': {'b': {'b1': 'bval1'}}})

    def test_append_nested_already_in_list(self):
        # Append an existing value
        grainsmod.__grains__ = {'a': {'a_list': ['a', 'b', 'c'], 'b': 'bval'}}
        res = grainsmod.append('a:a_list', 'b')
        self.assertEqual(res, 'The val b was already in the list a:a_list')
        self.assertEqual(grainsmod.__grains__, {'a': {'a_list': ['a', 'b', 'c'], 'b': 'bval'}})

    def test_append_nested_ok(self):
        # Append to an existing list
        grainsmod.__grains__ = {'a': {'a_list': ['a', 'b', 'c'], 'b': 'bval'}}
        res = grainsmod.append('a:a_list', 'd')
        self.assertEqual(res, {'a': {'a_list': ['a', 'b', 'c', 'd'], 'b': 'bval'}})
        self.assertEqual(grainsmod.__grains__, {'a': {'a_list': ['a', 'b', 'c', 'd'], 'b': 'bval'}})

        # Append to an non existing list
        grainsmod.__grains__ = {'a': {'b': 'bval'}}
        res = grainsmod.append('a:a_list', 'd')
        self.assertEqual(res, {'a': {'a_list': ['d'], 'b': 'bval'}})
        self.assertEqual(grainsmod.__grains__, {'a': {'a_list': ['d'], 'b': 'bval'}})

        # Append to an existing string, with convert
        grainsmod.__grains__ = {'a': {'b': 'bval'}}
        res = grainsmod.append('a:b', 'd', convert=True)
        self.assertEqual(res, {'a': {'b': ['bval', 'd']}})
        self.assertEqual(grainsmod.__grains__, {'a': {'b': ['bval', 'd']}})

        # Append to an existing dict, with convert
        grainsmod.__grains__ = {'a': {'b': {'b1': 'bval1'}}}
        res = grainsmod.append('a:b', 'd', convert=True)
        self.assertEqual(res, {'a': {'b': [{'b1': 'bval1'}, 'd']}})
        self.assertEqual(grainsmod.__grains__, {'a': {'b': [{'b1': 'bval1'}, 'd']}})

    def test_append_to_an_element_of_a_list(self):
        # Append to an element in a list
        # It currently fails silently
        grainsmod.__grains__ = {'a': ['b', 'c']}
        res = grainsmod.append('a:b', 'd')
        self.assertEqual(res, {'a': ['b', 'c']})
        self.assertEqual(grainsmod.__grains__, {'a': ['b', 'c']})

    def test_set_value_already_set(self):
        # Set a grain to the same simple value
        grainsmod.__grains__ = {'a': 12, 'c': 8}
        res = grainsmod.set('a', 12)
        self.assertTrue(res['result'])
        self.assertEqual(res['comment'], 'Grain is already set')
        self.assertEqual(grainsmod.__grains__, {'a': 12, 'c': 8})

        # Set a grain to the same complex value
        grainsmod.__grains__ = {'a': ['item', 12], 'c': 8}
        res = grainsmod.set('a', ['item', 12])
        self.assertTrue(res['result'])
        self.assertEqual(res['comment'], 'Grain is already set')
        self.assertEqual(grainsmod.__grains__, {'a': ['item', 12], 'c': 8})

        # Set a key to the same simple value in a nested grain
        grainsmod.__grains__ = {'a': 'aval', 'b': {'nested': 'val'}, 'c': 8}
        res = grainsmod.set('b,nested', 'val', delimiter=',')
        self.assertTrue(res['result'])
        self.assertEqual(res['comment'], 'Grain is already set')
        self.assertEqual(grainsmod.__grains__, {'a': 'aval',
                                                'b': {'nested': 'val'},
                                                'c': 8})

    def test_set_fail_replacing_existing_complex_key(self):
        # Fails to set a complex value without 'force'
        grainsmod.__grains__ = {'a': 'aval', 'c': 8}
        res = grainsmod.set('a', ['item', 12])
        self.assertFalse(res['result'])
        self.assertEqual(res['comment'], 'The key \'a\' exists and the given value is a '
                            + 'dict or a list. Use \'force=True\' to overwrite.')
        self.assertEqual(grainsmod.__grains__, {'a': 'aval', 'c': 8})

        # Fails to overwrite a complex value without 'force'
        grainsmod.__grains__ = {'a': ['item', 12], 'c': 8}
        res = grainsmod.set('a', ['item', 14])
        self.assertFalse(res['result'])
        self.assertEqual(res['comment'], 'The key \'a\' exists but is a dict or a list. '
                            + 'Use \'force=True\' to overwrite.')
        self.assertEqual(grainsmod.__grains__, {'a': ['item', 12], 'c': 8})

        # Fails to overwrite a complex value without 'force' in a nested grain
        grainsmod.__grains__ = {'a': 'aval',
                                'b': ['l1', {'l2': ['val1']}],
                                'c': 8}
        res = grainsmod.set('b,l2', 'val2', delimiter=',')
        self.assertFalse(res['result'])
        self.assertEqual(res['comment'], 'The key \'b,l2\' exists but is a dict or a '
                            + 'list. Use \'force=True\' to overwrite.')
        self.assertEqual(grainsmod.__grains__, {'a': 'aval',
                                                'b': ['l1', {'l2': ['val1']}],
                                                'c': 8})

    def test_set_nested_fails_replace_simple_value(self):
        # Fails to replace a simple value with a new dictionary consisting
        # of the specified key and value
        grainsmod.__grains__ = {'a': 'aval', 'b': 'l1', 'c': 8}
        res = grainsmod.set('b,l3', 'val3', delimiter=',')
        self.assertFalse(res['result'])
        self.assertEqual(res['comment'], 'The key \'b\' value is \'l1\', which is '
                            + 'different from the provided key \'l3\'. '
                            + 'Use \'force=True\' to overwrite.')
        self.assertEqual(grainsmod.__grains__, {'a': 'aval', 'b': 'l1', 'c': 8})

    def test_set_simple_value(self):
        grainsmod.__grains__ = {'a': ['b', 'c'], 'c': 8}
        res = grainsmod.set('b', 'bval')
        self.assertTrue(res['result'])
        self.assertEqual(res['changes'], {'b': 'bval'})
        self.assertEqual(grainsmod.__grains__, {'a': ['b', 'c'],
                                                'b': 'bval',
                                                'c': 8})

    def test_set_replace_value(self):
        grainsmod.__grains__ = {'a': 'aval', 'c': 8}
        res = grainsmod.set('a', 12)
        self.assertTrue(res['result'])
        self.assertEqual(res['changes'], {'a': 12})
        self.assertEqual(grainsmod.__grains__, {'a': 12, 'c': 8})

    def test_set_None_ok(self):
        grainsmod.__grains__ = {'a': 'aval', 'c': 8}
        res = grainsmod.set('b', None)
        self.assertTrue(res['result'])
        self.assertEqual(res['changes'], {'b': None})
        self.assertEqual(grainsmod.__grains__, {'a': 'aval', 'b': None, 'c': 8})

    def test_set_None_ok_destructive(self):
        grainsmod.__grains__ = {'a': 'aval', 'c': 8}
        res = grainsmod.set('b', None, destructive=True)
        self.assertTrue(res['result'])
        self.assertEqual(res['changes'], {'b': None})
        self.assertEqual(grainsmod.__grains__, {'a': 'aval', 'c': 8})

    def test_set_None_replace_ok(self):
        grainsmod.__grains__ = {'a': 'aval', 'c': 8}
        res = grainsmod.set('a', None)
        self.assertTrue(res['result'])
        self.assertEqual(res['changes'], {'a': None})
        self.assertEqual(grainsmod.__grains__, {'a': None, 'c': 8})

    def test_set_None_force_destructive(self):
        grainsmod.__grains__ = {'a': 'aval', 'c': 8}
        res = grainsmod.set('a', None, force=True, destructive=True)
        self.assertTrue(res['result'])
        self.assertEqual(res['changes'], {'a': None})
        self.assertEqual(grainsmod.__grains__, {'c': 8})

    def test_set_replace_value_was_complex_force(self):
        grainsmod.__grains__ = {'a': ['item', 12], 'c': 8}
        res = grainsmod.set('a', 'aval', force=True)
        self.assertTrue(res['result'])
        self.assertEqual(res['changes'], {'a': 'aval'})
        self.assertEqual(grainsmod.__grains__, {'a': 'aval', 'c': 8})

    def test_set_complex_value_force(self):
        grainsmod.__grains__ = {'a': 'aval', 'c': 8}
        res = grainsmod.set('a', ['item', 12], force=True)
        self.assertTrue(res['result'])
        self.assertEqual(res['changes'], {'a': ['item', 12]})
        self.assertEqual(grainsmod.__grains__, {'a': ['item', 12], 'c': 8})

    def test_set_nested_create(self):
        grainsmod.__grains__ = {'a': 'aval', 'c': 8}
        res = grainsmod.set('b,nested', 'val', delimiter=',')
        self.assertTrue(res['result'])
        self.assertEqual(res['changes'], {'b': {'nested': 'val'}})
        self.assertEqual(grainsmod.__grains__, {'a': 'aval',
                                                'b': {'nested': 'val'},
                                                'c': 8})

    def test_set_nested_update_dict(self):
        grainsmod.__grains__ = {'a': 'aval', 'b': {'nested': 'val'}, 'c': 8}
        res = grainsmod.set('b,nested', 'val2', delimiter=',')
        self.assertTrue(res['result'])
        self.assertEqual(res['changes'], {'b': {'nested': 'val2'}})
        self.assertEqual(grainsmod.__grains__, {'a': 'aval',
                                                'b': {'nested': 'val2'},
                                                'c': 8})

    def test_set_nested_update_dict_remove_key(self):
        grainsmod.__grains__ = {'a': 'aval', 'b': {'nested': 'val'}, 'c': 8}
        res = grainsmod.set('b,nested', None, delimiter=',', destructive=True)
        self.assertTrue(res['result'])
        self.assertEqual(res['changes'], {'b': {}})
        self.assertEqual(grainsmod.__grains__, {'a': 'aval', 'b': {}, 'c': 8})

    def test_set_nested_update_dict_new_key(self):
        grainsmod.__grains__ = {'a': 'aval', 'b': {'nested': 'val'}, 'c': 8}
        res = grainsmod.set('b,b2', 'val2', delimiter=',')
        self.assertTrue(res['result'])
        self.assertEqual(res['changes'], {'b': {'b2': 'val2', 'nested': 'val'}})
        self.assertEqual(grainsmod.__grains__, {'a': 'aval',
                                                'b': {'b2': 'val2',
                                                      'nested': 'val'},
                                                'c': 8})

    def test_set_nested_list_replace_key(self):
        grainsmod.__grains__ = {'a': 'aval', 'b': ['l1', 'l2', 'l3'], 'c': 8}
        res = grainsmod.set('b,l2', 'val2', delimiter=',')
        self.assertTrue(res['result'])
        self.assertEqual(res['changes'], {'b': ['l1', {'l2': 'val2'}, 'l3']})
        self.assertEqual(grainsmod.__grains__, {'a': 'aval',
                                                'b': ['l1', {'l2': 'val2'}, 'l3'],
                                                'c': 8})

    def test_set_nested_list_update_dict_key(self):
        grainsmod.__grains__ = {'a': 'aval', 'b': ['l1', {'l2': 'val1'}], 'c': 8}
        res = grainsmod.set('b,l2', 'val2', delimiter=',')
        self.assertTrue(res['result'])
        self.assertEqual(res['changes'], {'b': ['l1', {'l2': 'val2'}]})
        self.assertEqual(grainsmod.__grains__, {'a': 'aval',
                                                'b': ['l1', {'l2': 'val2'}],
                                                'c': 8})

    def test_set_nested_list_update_dict_key_overwrite(self):
        grainsmod.__grains__ = {'a': 'aval',
                                'b': ['l1', {'l2': ['val1']}],
                                'c': 8}
        res = grainsmod.set('b,l2', 'val2', delimiter=',', force=True)
        self.assertTrue(res['result'])
        self.assertEqual(res['changes'], {'b': ['l1', {'l2': 'val2'}]})
        self.assertEqual(grainsmod.__grains__, {'a': 'aval',
                                                'b': ['l1', {'l2': 'val2'}],
                                                'c': 8})

    def test_set_nested_list_append_dict_key(self):
        grainsmod.__grains__ = {'a': 'aval',
                                'b': ['l1', {'l2': 'val2'}],
                                'c': 8}
        res = grainsmod.set('b,l3', 'val3', delimiter=',')
        self.assertTrue(res['result'])
        self.assertEqual(res['changes'], {'b': ['l1', {'l2': 'val2'}, {'l3': 'val3'}]})
        self.assertEqual(grainsmod.__grains__, {'a': 'aval',
                                                'b': ['l1',
                                                      {'l2': 'val2'},
                                                      {'l3': 'val3'}],
                                                'c': 8})

    def test_set_nested_existing_value_is_the_key(self):
        grainsmod.__grains__ = {'a': 'aval', 'b': 'l3', 'c': 8}
        res = grainsmod.set('b,l3', 'val3', delimiter=',')
        self.assertTrue(res['result'])
        self.assertEqual(res['changes'], {'b': {'l3': 'val3'}})
        self.assertEqual(grainsmod.__grains__, {'a': 'aval',
                                                'b': {'l3': 'val3'},
                                                'c': 8})

    def test_set_nested_existing_value_overwrite(self):
        grainsmod.__grains__ = {'a': 'aval', 'b': 'l1', 'c': 8}
        res = grainsmod.set('b,l3', 'val3', delimiter=',', force=True)
        self.assertTrue(res['result'])
        self.assertEqual(res['changes'], {'b': {'l3': 'val3'}})
        self.assertEqual(grainsmod.__grains__, {'a': 'aval',
                                                'b': {'l3': 'val3'},
                                                'c': 8})

    def test_set_deeply_nested_update(self):
        grainsmod.__grains__ = {'a': 'aval',
                                'b': {'l1': ['l21', 'l22', {'l23': 'l23val'}]},
                                'c': 8}
        res = grainsmod.set('b,l1,l23', 'val', delimiter=',')
        self.assertTrue(res['result'])
        self.assertEqual(res['changes'], {'b': {'l1': ['l21', 'l22', {'l23': 'val'}]}})
        self.assertEqual(grainsmod.__grains__, {'a': 'aval',
                                                'b': {'l1': ['l21',
                                                             'l22',
                                                             {'l23': 'val'}]},
                                                'c': 8})

    def test_set_deeply_nested_create(self):
        grainsmod.__grains__ = {'a': 'aval',
                                'b': {'l1': ['l21', 'l22', {'l23': 'l23val'}]},
                                'c': 8}
        res = grainsmod.set('b,l1,l24,l241', 'val', delimiter=',')
        self.assertTrue(res['result'])
        self.assertEqual(res['changes'], {'b': {'l1': ['l21',
                                            'l22',
                                            {'l23': 'l23val'},
                                            {'l24': {'l241': 'val'}}]}})
        self.assertEqual(grainsmod.__grains__, {'a': 'aval',
                                                'b': {'l1': [
                                                    'l21',
                                                    'l22',
                                                    {'l23': 'l23val'},
                                                    {'l24': {'l241': 'val'}}]},
                                                'c': 8})

    def test_get_ordered(self):
        grainsmod.__grains__ = OrderedDict([
                                ('a', 'aval'),
                                ('b', OrderedDict([
                                    ('z', 'zval'),
                                    ('l1', ['l21',
                                            'l22',
                                            OrderedDict([('l23', 'l23val')])])
                                    ])),
                                ('c', 8)])
        res = grainsmod.get('b')
        self.assertEqual(type(res), OrderedDict)
        # Check that order really matters
        self.assertTrue(res == OrderedDict([
                                  ('z', 'zval'),
                                  ('l1', ['l21',
                                          'l22',
                                          OrderedDict([('l23', 'l23val')])]),
                                  ]))
        self.assertFalse(res == OrderedDict([
                                  ('l1', ['l21',
                                          'l22',
                                          OrderedDict([('l23', 'l23val')])]),
                                  ('z', 'zval'),
                                  ]))

    def test_get_unordered(self):
        grainsmod.__grains__ = OrderedDict([
                                ('a', 'aval'),
                                ('b', OrderedDict([
                                    ('z', 'zval'),
                                    ('l1', ['l21',
                                            'l22',
                                            OrderedDict([('l23', 'l23val')])])
                                    ])),
                                ('c', 8)])
        res = grainsmod.get('b', ordered=False)
        self.assertEqual(type(res), dict)
        # Check that order doesn't matter
        self.assertTrue(res == OrderedDict([
                                  ('l1', ['l21',
                                          'l22',
                                          OrderedDict([('l23', 'l23val')])]),
                                  ('z', 'zval'),
                                  ]))
