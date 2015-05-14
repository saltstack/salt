# -*- coding: utf-8 -*-

import copy

# Import Salt Testing libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

ensure_in_syspath('../../')

# Import Salt libs
from salt.exceptions import SaltException
from salt.modules import grains as grainsmod
from salt.utils import dictupdate

grainsmod.__opts__ = {
  'conf_file': '/tmp/__salt_test_grains',
  'cachedir':  '/tmp/__salt_test_grains_cache_dir'
}

grainsmod.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class GrainsModuleTestCase(TestCase):

    def test_filter_by(self):
        grainsmod.__grains__ = {
          'os_family': 'MockedOS',
          '1': '1',
          '2': '2',
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

    @patch.dict(grainsmod.__salt__, {'saltutil.sync_grains': MagicMock()})
    def test_append_not_a_list(self):
        # Failing append to an existing string, without convert
        grainsmod.__grains__ = {'b': 'bval'}
        res = grainsmod.append('b', 'd')
        # check the result
        self.assertEqual(res, 'The key b is not a valid list')
        # check the whole grains
        self.assertEqual(grainsmod.__grains__, {'b': 'bval'})

        # Failing append to an existing dict
        grainsmod.__grains__ = {'b': {'b1': 'bval1'}}
        res = grainsmod.append('b', 'd')
        # check the result
        self.assertEqual(res, 'The key b is not a valid list')
        # check the whole grains
        self.assertEqual(grainsmod.__grains__, {'b': {'b1': 'bval1'}})

    @patch.dict(grainsmod.__salt__, {'saltutil.sync_grains': MagicMock()})
    def test_append_already_in_list(self):
        # Append an existing value
        grainsmod.__grains__ = {'a_list': ['a', 'b', 'c'], 'b': 'bval'}
        res = grainsmod.append('a_list', 'b')
        # check the result
        self.assertEqual(res, 'The val b was already in the list a_list')
        # check the whole grains
        self.assertEqual(grainsmod.__grains__, {'a_list': ['a', 'b', 'c'], 'b': 'bval'})

    @patch.dict(grainsmod.__salt__, {'saltutil.sync_grains': MagicMock()})
    def test_append_ok(self):
        # Append to an existing list
        grainsmod.__grains__ = {'a_list': ['a', 'b', 'c'], 'b': 'bval'}
        res = grainsmod.append('a_list', 'd')
        # check the result
        self.assertEqual(res, {'a_list': ['a', 'b', 'c', 'd']})
        # check the whole grains
        self.assertEqual(grainsmod.__grains__, {'a_list': ['a', 'b', 'c', 'd'], 'b': 'bval'})

        # Append to an non existing list
        grainsmod.__grains__ = {'b': 'bval'}
        res = grainsmod.append('a_list', 'd')
        # check the result
        self.assertEqual(res, {'a_list': ['d']})
        # check the whole grains
        self.assertEqual(grainsmod.__grains__, {'a_list': ['d'], 'b': 'bval'})

        # Append to an existing string, with convert
        grainsmod.__grains__ = {'b': 'bval'}
        res = grainsmod.append('b', 'd', convert=True)
        # check the result
        self.assertEqual(res, {'b': ['bval', 'd']})
        # check the whole grains
        self.assertEqual(grainsmod.__grains__, {'b': ['bval', 'd']})

        # Append to an existing dict, with convert
        grainsmod.__grains__ = {'b': {'b1': 'bval1'}}
        res = grainsmod.append('b', 'd', convert=True)
        # check the result
        self.assertEqual(res, {'b': [{'b1': 'bval1'}, 'd']})
        # check the whole grains
        self.assertEqual(grainsmod.__grains__, {'b': [{'b1': 'bval1'}, 'd']})

    @patch.dict(grainsmod.__salt__, {'saltutil.sync_grains': MagicMock()})
    def test_append_nested_not_a_list(self):
        # Failing append to an existing string, without convert
        grainsmod.__grains__ = {'a': {'b': 'bval'}}
        res = grainsmod.append('a:b', 'd')
        # check the result
        self.assertEqual(res, 'The key a:b is not a valid list')
        # check the whole grains
        self.assertEqual(grainsmod.__grains__, {'a': {'b': 'bval'}})

        # Failing append to an existing dict
        grainsmod.__grains__ = {'a': {'b': {'b1': 'bval1'}}}
        res = grainsmod.append('a:b', 'd')
        # check the result
        self.assertEqual(res, 'The key a:b is not a valid list')
        # check the whole grains
        self.assertEqual(grainsmod.__grains__, {'a': {'b': {'b1': 'bval1'}}})

    @patch.dict(grainsmod.__salt__, {'saltutil.sync_grains': MagicMock()})
    def test_append_nested_already_in_list(self):
        # Append an existing value
        grainsmod.__grains__ = {'a': {'a_list': ['a', 'b', 'c'], 'b': 'bval'}}
        res = grainsmod.append('a:a_list', 'b')
        # check the result
        self.assertEqual(res, 'The val b was already in the list a:a_list')
        # check the whole grains
        self.assertEqual(grainsmod.__grains__, {'a': {'a_list': ['a', 'b', 'c'], 'b': 'bval'}})

    @patch.dict(grainsmod.__salt__, {'saltutil.sync_grains': MagicMock()})
    def test_append_nested_ok(self):
        # Append to an existing list
        grainsmod.__grains__ = {'a': {'a_list': ['a', 'b', 'c'], 'b': 'bval'}}
        res = grainsmod.append('a:a_list', 'd')
        # check the result
        self.assertEqual(res, {'a': {'a_list': ['a', 'b', 'c', 'd'], 'b': 'bval'}})
        # check the whole grains
        self.assertEqual(grainsmod.__grains__, {'a': {'a_list': ['a', 'b', 'c', 'd'], 'b': 'bval'}})

        # Append to an non existing list
        grainsmod.__grains__ = {'a': {'b': 'bval'}}
        res = grainsmod.append('a:a_list', 'd')
        # check the result
        self.assertEqual(res, {'a': {'a_list': ['d'], 'b': 'bval'}})
        # check the whole grains
        self.assertEqual(grainsmod.__grains__, {'a': {'a_list': ['d'], 'b': 'bval'}})

        # Append to an existing string, with convert
        grainsmod.__grains__ = {'a': {'b': 'bval'}}
        res = grainsmod.append('a:b', 'd', convert=True)
        # check the result
        self.assertEqual(res, {'a': {'b': ['bval', 'd']}})
        # check the whole grains
        self.assertEqual(grainsmod.__grains__, {'a': {'b': ['bval', 'd']}})

        # Append to an existing dict, with convert
        grainsmod.__grains__ = {'a': {'b': {'b1': 'bval1'}}}
        res = grainsmod.append('a:b', 'd', convert=True)
        # check the result
        self.assertEqual(res, {'a': {'b': [{'b1': 'bval1'}, 'd']}})
        # check the whole grains
        self.assertEqual(grainsmod.__grains__, {'a': {'b': [{'b1': 'bval1'}, 'd']}})

    @patch.dict(grainsmod.__salt__, {'saltutil.sync_grains': MagicMock()})
    def test_append_to_an_element_of_a_list(self):
        # Append to an element in a list
        # It currently fails silently
        grainsmod.__grains__ = {'a': ['b', 'c']}
        res = grainsmod.append('a:b', 'd')
        # check the result
        self.assertEqual(res, {'a': ['b', 'c']})
        # check the whole grains
        self.assertEqual(grainsmod.__grains__, {'a': ['b', 'c']})


if __name__ == '__main__':
    from integration import run_tests
    run_tests(GrainsModuleTestCase, needs_daemon=False)
