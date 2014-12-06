# -*- coding: utf-8 -*-

import copy

# Import Salt Testing libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt libs
from salt.exceptions import SaltException
from salt.modules import grains as grainsmod
from salt.utils import dictupdate

grainsmod.__grains__ = {
  'os_family': 'MockedOS',
  '1': '1',
  '2': '2',
}


class GrainsModuleTestCase(TestCase):

    def test_filter_by(self):
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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(GrainsModuleTestCase, needs_daemon=False)
