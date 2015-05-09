# -*- coding: utf-8 -*-

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
from salt.modules import config

grainsmod.__opts__ = {
  'conf_file': '/tmp/__salt_test_grains',
  'cachedir':  '/tmp/__salt_test_grains_cache_dir'
}

grainsmod.__salt__ = {}

@skipIf(NO_MOCK, NO_MOCK_REASON)
class GrainsModuleTestCase(TestCase):

    def test_filter_by(self):
        grainsmod.__grains__ = {
          'os_family': 'MockedOS'
        }

        dict1 = {'A': 'B', 'C': {'D': {'E': 'F', 'G': 'H'}}}
        mdict = {'D': {'E': 'I'}, 'J': 'K'}

        # test None result with non existent grain and no default
        res = grainsmod.filter_by(dict1, grain='xxx')
        self.assertIs(res, None)

        # test None result with os_family grain and no matching result
        res = grainsmod.filter_by(dict1)
        self.assertIs(res, None)

        # test with non existent grain, and a given default key
        res = grainsmod.filter_by(dict1, grain='xxx', default='C')
        self.assertEqual(res, {'D': {'E': 'F', 'G': 'H'}})

        # add a merge dictionnary, F disapears
        res = grainsmod.filter_by(dict1, grain='xxx', merge=mdict, default='C')
        self.assertEqual(res, {'D': {'E': 'I', 'G': 'H'}, 'J': 'K'})
        # dict1 was altered, restablish
        dict1 = {'A': 'B', 'C': {'D': {'E': 'F', 'G': 'H'}}}

        # default is not present in dict1, check we only have merge in result
        res = grainsmod.filter_by(dict1, grain='xxx', merge=mdict, default='Z')
        self.assertEqual(res, mdict)

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
        res = grainsmod.filter_by(dict1, merge=mdict, default='C')
        self.assertEqual(res, {'D': {'E': 'I', 'G': 'H'}, 'J': 'K'})
        # dict1 was altered, restablish
        dict1 = {'A': 'B', 'C': {'D': {'E': 'F', 'G': 'H'}}}
        res = grainsmod.filter_by(dict1, merge=mdict, default='Z')
        self.assertEqual(res, mdict)
        res = grainsmod.filter_by(dict1, default='Z')
        self.assertIs(res, None)
        # this one is in fact a traceback in updatedict, merging a string with a dictionnary
        self.assertRaises(
            TypeError,
            grainsmod.filter_by,
            dict1,
            merge=mdict,
            default='A'
        )

        #Now, re-test with a matching grain.
        dict1 = {'A': 'B', 'MockedOS': {'D': {'E': 'F', 'G': 'H'}}}
        res = grainsmod.filter_by(dict1)
        self.assertEqual(res, {'D': {'E': 'F', 'G': 'H'}})
        res = grainsmod.filter_by(dict1, default='A')
        self.assertEqual(res, {'D': {'E': 'F', 'G': 'H'}})
        res = grainsmod.filter_by(dict1, merge=mdict, default='A')
        self.assertEqual(res, {'D': {'E': 'I', 'G': 'H'}, 'J': 'K'})
        # dict1 was altered, restablish
        dict1 = {'A': 'B', 'MockedOS': {'D': {'E': 'F', 'G': 'H'}}}
        res = grainsmod.filter_by(dict1, merge=mdict, default='Z')
        self.assertEqual(res, {'D': {'E': 'I', 'G': 'H'}, 'J': 'K'})
        # dict1 was altered, restablish
        dict1 = {'A': 'B', 'MockedOS': {'D': {'E': 'F', 'G': 'H'}}}
        res = grainsmod.filter_by(dict1, default='Z')
        self.assertEqual(res, {'D': {'E': 'F', 'G': 'H'}})


    @patch.dict(grainsmod.__salt__, {'saltutil.sync_grains': MagicMock()})
    def test_append(self):
        # grains {'a_list': ['a', 'b', 'c'], 'a': {'nested': {'list': ['1', '2', '3']}, 'aa': 'val'}}

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
        # the whole grains should now be
        # check the whole grains
        self.assertEqual(grainsmod.__grains__, {'a_list': ['d'], 'b': 'bval'})

        # Append to an existing string, without convert
        grainsmod.__grains__ = {'b': 'bval'}
        res = grainsmod.append('b', 'd')
        # check the result
        self.assertEqual(res, 'The key b is not a valid list')
        # the whole grains should now be
        # check the whole grains
        self.assertEqual(grainsmod.__grains__, {'b': 'bval'})

        # Append to an existing string, with convert
        grainsmod.__grains__ = {'b': 'bval'}
        res = grainsmod.append('b', 'd', convert=True)
        # check the result
        self.assertEqual(res, {'b': ['bval', 'd']})
        # the whole grains should now be
        # check the whole grains
        self.assertEqual(grainsmod.__grains__, {'b': ['bval', 'd']})



if __name__ == '__main__':
    from integration import run_tests
    run_tests(GrainsModuleTestCase, needs_daemon=False)
