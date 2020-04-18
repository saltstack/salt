# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import copy

# Import Salt libs
import salt.utils.dictupdate as dictupdate
from salt.exceptions import SaltInvocationError
from salt.utils.odict import OrderedDict

# Import Salt Testing libs
from tests.support.unit import TestCase


class UtilDictupdateTestCase(TestCase):

    dict1 = {"A": "B", "C": {"D": "E", "F": {"G": "H", "I": "J"}}}

    def test_update(self):

        # level 1 value changes
        mdict = copy.deepcopy(self.dict1)
        mdict["A"] = "Z"
        res = dictupdate.update(copy.deepcopy(self.dict1), {"A": "Z"})
        self.assertEqual(res, mdict)

        # level 1 value changes (list replacement)
        mdict = copy.deepcopy(self.dict1)
        mdict["A"] = [1, 2]
        res = dictupdate.update(copy.deepcopy(mdict), {"A": [2, 3]}, merge_lists=False)
        mdict["A"] = [2, 3]
        self.assertEqual(res, mdict)

        # level 1 value changes (list merge)
        mdict = copy.deepcopy(self.dict1)
        mdict["A"] = [1, 2]
        res = dictupdate.update(copy.deepcopy(mdict), {"A": [3, 4]}, merge_lists=True)
        mdict["A"] = [1, 2, 3, 4]
        self.assertEqual(res, mdict)

        # level 1 value changes (list merge, remove duplicates, preserve order)
        mdict = copy.deepcopy(self.dict1)
        mdict["A"] = [1, 2]
        res = dictupdate.update(
            copy.deepcopy(mdict), {"A": [4, 3, 2, 1]}, merge_lists=True
        )
        mdict["A"] = [1, 2, 4, 3]
        self.assertEqual(res, mdict)

        # level 2 value changes
        mdict = copy.deepcopy(self.dict1)
        mdict["C"]["D"] = "Z"
        res = dictupdate.update(copy.deepcopy(self.dict1), {"C": {"D": "Z"}})
        self.assertEqual(res, mdict)

        # level 2 value changes (list replacement)
        mdict = copy.deepcopy(self.dict1)
        mdict["C"]["D"] = ["a", "b"]
        res = dictupdate.update(
            copy.deepcopy(mdict), {"C": {"D": ["c", "d"]}}, merge_lists=False
        )
        mdict["C"]["D"] = ["c", "d"]
        self.assertEqual(res, mdict)

        # level 2 value changes (list merge)
        mdict = copy.deepcopy(self.dict1)
        mdict["C"]["D"] = ["a", "b"]
        res = dictupdate.update(
            copy.deepcopy(mdict), {"C": {"D": ["c", "d"]}}, merge_lists=True
        )
        mdict["C"]["D"] = ["a", "b", "c", "d"]
        self.assertEqual(res, mdict)

        # level 2 value changes (list merge, remove duplicates, preserve order)
        mdict = copy.deepcopy(self.dict1)
        mdict["C"]["D"] = ["a", "b"]
        res = dictupdate.update(
            copy.deepcopy(mdict), {"C": {"D": ["d", "c", "b", "a"]}}, merge_lists=True
        )
        mdict["C"]["D"] = ["a", "b", "d", "c"]
        self.assertEqual(res, mdict)

        # level 3 value changes
        mdict = copy.deepcopy(self.dict1)
        mdict["C"]["F"]["G"] = "Z"
        res = dictupdate.update(copy.deepcopy(self.dict1), {"C": {"F": {"G": "Z"}}})
        self.assertEqual(res, mdict)

        # level 3 value changes (list replacement)
        mdict = copy.deepcopy(self.dict1)
        mdict["C"]["F"]["G"] = ["a", "b"]
        res = dictupdate.update(
            copy.deepcopy(mdict), {"C": {"F": {"G": ["c", "d"]}}}, merge_lists=False
        )
        mdict["C"]["F"]["G"] = ["c", "d"]
        self.assertEqual(res, mdict)

        # level 3 value changes (list merge)
        mdict = copy.deepcopy(self.dict1)
        mdict["C"]["F"]["G"] = ["a", "b"]
        res = dictupdate.update(
            copy.deepcopy(mdict), {"C": {"F": {"G": ["c", "d"]}}}, merge_lists=True
        )
        mdict["C"]["F"]["G"] = ["a", "b", "c", "d"]
        self.assertEqual(res, mdict)

        # level 3 value changes (list merge, remove duplicates, preserve order)
        mdict = copy.deepcopy(self.dict1)
        mdict["C"]["F"]["G"] = ["a", "b"]
        res = dictupdate.update(
            copy.deepcopy(mdict),
            {"C": {"F": {"G": ["d", "c", "b", "a"]}}},
            merge_lists=True,
        )
        mdict["C"]["F"]["G"] = ["a", "b", "d", "c"]
        self.assertEqual(res, mdict)

        # replace a sub-dictionary
        mdict = copy.deepcopy(self.dict1)
        mdict["C"] = "Z"
        res = dictupdate.update(copy.deepcopy(self.dict1), {"C": "Z"})
        self.assertEqual(res, mdict)

        # add a new scalar value
        mdict = copy.deepcopy(self.dict1)
        mdict["Z"] = "Y"
        res = dictupdate.update(copy.deepcopy(self.dict1), {"Z": "Y"})
        self.assertEqual(res, mdict)

        # add a dictionary
        mdict = copy.deepcopy(self.dict1)
        mdict["Z"] = {"Y": "X"}
        res = dictupdate.update(copy.deepcopy(self.dict1), {"Z": {"Y": "X"}})
        self.assertEqual(res, mdict)

        # add a nested dictionary
        mdict = copy.deepcopy(self.dict1)
        mdict["Z"] = {"Y": {"X": "W"}}
        res = dictupdate.update(copy.deepcopy(self.dict1), {"Z": {"Y": {"X": "W"}}})
        self.assertEqual(res, mdict)


class UtilDictMergeTestCase(TestCase):

    dict1 = {"A": "B", "C": {"D": "E", "F": {"G": "H", "I": "J"}}}

    def test_merge_overwrite_traditional(self):
        """
        Test traditional overwrite, wherein a key in the second dict overwrites a key in the first
        """
        mdict = copy.deepcopy(self.dict1)
        mdict["A"] = "b"
        ret = dictupdate.merge_overwrite(copy.deepcopy(self.dict1), {"A": "b"})
        self.assertEqual(mdict, ret)

    def test_merge_overwrite_missing_source_key(self):
        """
        Test case wherein the overwrite strategy is used but a key in the second dict is
        not present in the first
        """
        mdict = copy.deepcopy(self.dict1)
        mdict["D"] = "new"
        ret = dictupdate.merge_overwrite(copy.deepcopy(self.dict1), {"D": "new"})
        self.assertEqual(mdict, ret)

    def test_merge_aggregate_traditional(self):
        """
        Test traditional aggregation, where a val from dict2 overwrites one
        present in dict1
        """
        mdict = copy.deepcopy(self.dict1)
        mdict["A"] = "b"
        ret = dictupdate.merge_overwrite(copy.deepcopy(self.dict1), {"A": "b"})
        self.assertEqual(mdict, ret)

    def test_merge_list_traditional(self):
        """
        Test traditional list merge, where a key present in dict2 will be converted
        to a list
        """
        mdict = copy.deepcopy(self.dict1)
        mdict["A"] = ["B", "b"]
        ret = dictupdate.merge_list(copy.deepcopy(self.dict1), {"A": "b"})
        self.assertEqual(mdict, ret)

    def test_merge_list_append(self):
        """
        This codifies the intended behaviour that items merged into a dict val that is already
        a list that those items will *appended* to the list, and not magically merged in
        """
        mdict = copy.deepcopy(self.dict1)
        mdict["A"] = ["B", "b", "c"]

        # Prepare a modified copy of dict1 that has a list as a val for the key of 'A'
        mdict1 = copy.deepcopy(self.dict1)
        mdict1["A"] = ["B"]
        ret = dictupdate.merge_list(mdict1, {"A": ["b", "c"]})
        self.assertEqual(
            {"A": [["B"], ["b", "c"]], "C": {"D": "E", "F": {"I": "J", "G": "H"}}}, ret
        )


class UtilDeepDictUpdateTestCase(TestCase):

    dict1 = {"A": "B", "C": {"D": "E", "F": {"G": "H", "I": "J"}}}

    def test_deep_set_overwrite(self):
        """
        Test overwriting an existing value.
        """
        mdict = copy.deepcopy(self.dict1)
        res = dictupdate.set_dict_key_value(mdict, "C:F", "foo")
        self.assertEqual({"A": "B", "C": {"D": "E", "F": "foo"}}, res)
        # Verify modify-in-place
        self.assertEqual({"A": "B", "C": {"D": "E", "F": "foo"}}, mdict)

        # Test using alternative delimiter
        res = dictupdate.set_dict_key_value(
            mdict, "C/F", {"G": "H", "I": "J"}, delimiter="/"
        )
        self.assertEqual(self.dict1, res)

        # Test without using a delimiter in the keys
        res = dictupdate.set_dict_key_value(mdict, "C", None)
        self.assertEqual({"A": "B", "C": None}, res)

    def test_deep_set_create(self):
        """
        Test creating new nested keys.
        """
        mdict = copy.deepcopy(self.dict1)
        res = dictupdate.set_dict_key_value(mdict, "K:L:M", "Q")
        self.assertEqual(
            {
                "A": "B",
                "C": {"D": "E", "F": {"G": "H", "I": "J"}},
                "K": {"L": {"M": "Q"}},
            },
            res,
        )

    def test_deep_set_ordered_dicts(self):
        """
        Test creating new nested ordereddicts.
        """
        res = dictupdate.set_dict_key_value({}, "A:B", "foo", ordered_dict=True)
        self.assertEqual({"A": OrderedDict([("B", "foo")])}, res)

    def test_deep_append(self):
        """
        Test appending to a list.
        """
        sdict = {"bar": {"baz": [1, 2]}}
        res = dictupdate.append_dict_key_value(sdict, "bar:baz", 42)
        self.assertEqual({"bar": {"baz": [1, 2, 42]}}, res)
        # Append with alternate delimiter
        res = dictupdate.append_dict_key_value(sdict, "bar~baz", 43, delimiter="~")
        self.assertEqual({"bar": {"baz": [1, 2, 42, 43]}}, res)
        # Append to a not-yet existing list
        res = dictupdate.append_dict_key_value({}, "foo:bar:baz", 42)
        self.assertEqual({"foo": {"bar": {"baz": [42]}}}, res)

    def test_deep_extend(self):
        """
        Test extending a list.
        Note that the provided value (to extend with) will be coerced to a list
        if this is not already a list. This can cause unexpected behaviour.
        """
        sdict = {"bar": {"baz": [1, 2]}}
        res = dictupdate.extend_dict_key_value(sdict, "bar:baz", [42, 42])
        self.assertEqual({"bar": {"baz": [1, 2, 42, 42]}}, res)

        # Extend a not-yet existing list
        res = dictupdate.extend_dict_key_value({}, "bar:baz:qux", [42])
        self.assertEqual({"bar": {"baz": {"qux": [42]}}}, res)

        # Extend with a dict (remember, foo has been updated in the first test)
        res = dictupdate.extend_dict_key_value(sdict, "bar:baz", {"qux": "quux"})
        self.assertEqual({"bar": {"baz": [1, 2, 42, 42, "qux"]}}, res)

    def test_deep_extend_illegal_addition(self):
        """
        Test errorhandling extending lists with illegal types.
        """
        # Extend with an illegal type
        for extend_with in [42, None]:
            with self.assertRaisesRegex(
                SaltInvocationError,
                r"Cannot extend {} with a {}." "".format(type([]), type(extend_with)),
            ):
                dictupdate.extend_dict_key_value({}, "foo", extend_with)

    def test_deep_extend_illegal_source(self):
        """
        Test errorhandling extending things that are not a list.
        """
        # Extend an illegal type
        for extend_this in [{}, 42, "bar"]:
            with self.assertRaisesRegex(
                SaltInvocationError,
                r"The last key contains a {}, which cannot extend."
                "".format(type(extend_this)),
            ):
                dictupdate.extend_dict_key_value({"foo": extend_this}, "foo", [42])

    def test_deep_update(self):
        """
        Test updating a (sub)dict.
        """
        mdict = copy.deepcopy(self.dict1)
        res = dictupdate.update_dict_key_value(
            mdict, "C:F", {"foo": "bar", "qux": "quux"}
        )
        self.assertEqual(
            {
                "A": "B",
                "C": {"D": "E", "F": {"G": "H", "I": "J", "foo": "bar", "qux": "quux"}},
            },
            res,
        )

        # Test updating a non-existing subkey
        res = dictupdate.update_dict_key_value({}, "foo:bar:baz", {"qux": "quux"})
        self.assertEqual({"foo": {"bar": {"baz": {"qux": "quux"}}}}, res)
        # Test updating a non-existing subkey, with a different delimiter
        res = dictupdate.update_dict_key_value(
            {}, "foo bar baz", {"qux": "quux"}, delimiter=" "
        )
        self.assertEqual({"foo": {"bar": {"baz": {"qux": "quux"}}}}, res)

    def test_deep_update_illegal_update(self):
        """
        Test errorhandling updating a (sub)dict with illegal types.
        """
        # Update with an illegal type
        for update_with in [42, None, [42], "bar"]:
            with self.assertRaisesRegex(
                SaltInvocationError,
                r"Cannot update {} with a {}." "".format(type({}), type(update_with)),
            ):
                dictupdate.update_dict_key_value({}, "foo", update_with)
        # Again, but now using OrderedDicts
        for update_with in [42, None, [42], "bar"]:
            with self.assertRaisesRegex(
                SaltInvocationError,
                r"Cannot update {} with a {}."
                "".format(type(OrderedDict()), type(update_with)),
            ):
                dictupdate.update_dict_key_value(
                    {}, "foo", update_with, ordered_dict=True
                )
