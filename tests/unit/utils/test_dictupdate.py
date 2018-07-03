# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import copy

# Import Salt Testing libs
from tests.support.unit import TestCase

# Import Salt libs
import salt.utils.dictupdate as dictupdate


class UtilDictupdateTestCase(TestCase):

    dict1 = {'A': 'B', 'C': {'D': 'E', 'F': {'G': 'H', 'I': 'J'}}}

    def test_update(self):

        # level 1 value changes
        mdict = copy.deepcopy(self.dict1)
        mdict['A'] = 'Z'
        res = dictupdate.update(copy.deepcopy(self.dict1), {'A': 'Z'})
        self.assertEqual(res, mdict)

        # level 1 value changes (list replacement)
        mdict = copy.deepcopy(self.dict1)
        mdict['A'] = [1, 2]
        res = dictupdate.update(copy.deepcopy(mdict), {'A': [2, 3]},
                                merge_lists=False)
        mdict['A'] = [2, 3]
        self.assertEqual(res, mdict)

        # level 1 value changes (list merge)
        mdict = copy.deepcopy(self.dict1)
        mdict['A'] = [1, 2]
        res = dictupdate.update(copy.deepcopy(mdict), {'A': [3, 4]},
                                merge_lists=True)
        mdict['A'] = [1, 2, 3, 4]
        self.assertEqual(res, mdict)

        # level 1 value changes (list merge, remove duplicates, preserve order)
        mdict = copy.deepcopy(self.dict1)
        mdict['A'] = [1, 2]
        res = dictupdate.update(copy.deepcopy(mdict), {'A': [4, 3, 2, 1]},
                                merge_lists=True)
        mdict['A'] = [1, 2, 4, 3]
        self.assertEqual(res, mdict)

        # level 2 value changes
        mdict = copy.deepcopy(self.dict1)
        mdict['C']['D'] = 'Z'
        res = dictupdate.update(copy.deepcopy(self.dict1), {'C': {'D': 'Z'}})
        self.assertEqual(res, mdict)

        # level 2 value changes (list replacement)
        mdict = copy.deepcopy(self.dict1)
        mdict['C']['D'] = ['a', 'b']
        res = dictupdate.update(copy.deepcopy(mdict), {'C': {'D': ['c', 'd']}},
                                merge_lists=False)
        mdict['C']['D'] = ['c', 'd']
        self.assertEqual(res, mdict)

        # level 2 value changes (list merge)
        mdict = copy.deepcopy(self.dict1)
        mdict['C']['D'] = ['a', 'b']
        res = dictupdate.update(copy.deepcopy(mdict), {'C': {'D': ['c', 'd']}},
                                merge_lists=True)
        mdict['C']['D'] = ['a', 'b', 'c', 'd']
        self.assertEqual(res, mdict)

        # level 2 value changes (list merge, remove duplicates, preserve order)
        mdict = copy.deepcopy(self.dict1)
        mdict['C']['D'] = ['a', 'b']
        res = dictupdate.update(copy.deepcopy(mdict),
                                {'C': {'D': ['d', 'c', 'b', 'a']}},
                                merge_lists=True)
        mdict['C']['D'] = ['a', 'b', 'd', 'c']
        self.assertEqual(res, mdict)

        # level 3 value changes
        mdict = copy.deepcopy(self.dict1)
        mdict['C']['F']['G'] = 'Z'
        res = dictupdate.update(
            copy.deepcopy(self.dict1),
            {'C': {'F': {'G': 'Z'}}}
        )
        self.assertEqual(res, mdict)

        # level 3 value changes (list replacement)
        mdict = copy.deepcopy(self.dict1)
        mdict['C']['F']['G'] = ['a', 'b']
        res = dictupdate.update(copy.deepcopy(mdict),
            {'C': {'F': {'G': ['c', 'd']}}}, merge_lists=False)
        mdict['C']['F']['G'] = ['c', 'd']
        self.assertEqual(res, mdict)

        # level 3 value changes (list merge)
        mdict = copy.deepcopy(self.dict1)
        mdict['C']['F']['G'] = ['a', 'b']
        res = dictupdate.update(copy.deepcopy(mdict),
            {'C': {'F': {'G': ['c', 'd']}}}, merge_lists=True)
        mdict['C']['F']['G'] = ['a', 'b', 'c', 'd']
        self.assertEqual(res, mdict)

        # level 3 value changes (list merge, remove duplicates, preserve order)
        mdict = copy.deepcopy(self.dict1)
        mdict['C']['F']['G'] = ['a', 'b']
        res = dictupdate.update(copy.deepcopy(mdict),
            {'C': {'F': {'G': ['d', 'c', 'b', 'a']}}}, merge_lists=True)
        mdict['C']['F']['G'] = ['a', 'b', 'd', 'c']
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


class UtilDictMergeTestCase(TestCase):

    dict1 = {'A': 'B', 'C': {'D': 'E', 'F': {'G': 'H', 'I': 'J'}}}

    def test_merge_overwrite_traditional(self):
        '''
        Test traditional overwrite, wherein a key in the second dict overwrites a key in the first
        '''
        mdict = copy.deepcopy(self.dict1)
        mdict['A'] = 'b'
        ret = dictupdate.merge_overwrite(copy.deepcopy(self.dict1), {'A': 'b'})
        self.assertEqual(mdict, ret)

    def test_merge_overwrite_missing_source_key(self):
        '''
        Test case wherein the overwrite strategy is used but a key in the second dict is
        not present in the first
        '''
        mdict = copy.deepcopy(self.dict1)
        mdict['D'] = 'new'
        ret = dictupdate.merge_overwrite(copy.deepcopy(self.dict1), {'D': 'new'})
        self.assertEqual(mdict, ret)

    def test_merge_aggregate_traditional(self):
        '''
        Test traditional aggregation, where a val from dict2 overwrites one
        present in dict1
        '''
        mdict = copy.deepcopy(self.dict1)
        mdict['A'] = 'b'
        ret = dictupdate.merge_overwrite(copy.deepcopy(self.dict1), {'A': 'b'})
        self.assertEqual(mdict, ret)

    def test_merge_list_traditional(self):
        '''
        Test traditional list merge, where a key present in dict2 will be converted
        to a list
        '''
        mdict = copy.deepcopy(self.dict1)
        mdict['A'] = ['B', 'b']
        ret = dictupdate.merge_list(copy.deepcopy(self.dict1), {'A': 'b'})
        self.assertEqual(mdict, ret)

    def test_merge_list_append(self):
        '''
        This codifies the intended behaviour that items merged into a dict val that is already
        a list that those items will *appended* to the list, and not magically merged in
        '''
        mdict = copy.deepcopy(self.dict1)
        mdict['A'] = ['B', 'b', 'c']

        # Prepare a modified copy of dict1 that has a list as a val for the key of 'A'
        mdict1 = copy.deepcopy(self.dict1)
        mdict1['A'] = ['B']
        ret = dictupdate.merge_list(mdict1, {'A': ['b', 'c']})
        self.assertEqual({'A': [['B'], ['b', 'c']], 'C': {'D': 'E', 'F': {'I': 'J', 'G': 'H'}}}, ret)
