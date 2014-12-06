# -*- coding: utf-8 -*-

import copy

# Import Salt Testing libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt libs
from salt.utils import dictupdate


class UtilDictupdateTestCase(TestCase):

    dict1 = {'A': 'B', 'C': {'D': 'E', 'F': {'G': 'H', 'I': 'J'}}}

    def test_update(self):

        # level 1 value changes
        mdict = copy.deepcopy(self.dict1)
        mdict['A'] = 'Z'
        res = dictupdate.update(copy.deepcopy(self.dict1), {'A': 'Z'})
        self.assertEqual(res, mdict)

        # level 2 value changes
        mdict = copy.deepcopy(self.dict1)
        mdict['C']['D'] = 'Z'
        res = dictupdate.update(copy.deepcopy(self.dict1), {'C': {'D': 'Z'}})
        self.assertEqual(res, mdict)

        # level 3 value changes
        mdict = copy.deepcopy(self.dict1)
        mdict['C']['F']['G'] = 'Z'
        res = dictupdate.update(
            copy.deepcopy(self.dict1),
            {'C': {'F': {'G': 'Z'}}}
        )
        self.assertEqual(res, mdict)

        # replace a sub-dictionary
        mdict = copy.deepcopy(self.dict1)
        mdict['C'] = 'Z'
        res = dictupdate.update(copy.deepcopy(self.dict1), {'C': 'Z'})
        self.assertEqual(res, mdict)

        # add a new scalar value
        mdict = copy.deepcopy(self.dict1)
        mdict['Z'] = 'Y'
        res = dictupdate.update(copy.deepcopy(self.dict1), {'Z': 'Y'})
        self.assertEqual(res, mdict)

        # add a dictionary
        mdict = copy.deepcopy(self.dict1)
        mdict['Z'] = {'Y': 'X'}
        res = dictupdate.update(copy.deepcopy(self.dict1), {'Z': {'Y': 'X'}})
        self.assertEqual(res, mdict)

        # add a nested dictionary
        mdict = copy.deepcopy(self.dict1)
        mdict['Z'] = {'Y': {'X': 'W'}}
        res = dictupdate.update(
            copy.deepcopy(self.dict1),
            {'Z': {'Y': {'X': 'W'}}}
        )
        self.assertEqual(res, mdict)

if __name__ == '__main__':
    from integration import run_tests
    run_tests(UtilDictupdateTestCase, needs_daemon=False)
