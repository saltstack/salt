# -*- coding: utf-8 -*-
"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import inspect

# Import Salt Libs
import salt.modules.defaults as defaults

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class DefaultsTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.defaults
    """

    def setup_loader_modules(self):
        return {defaults: {}}

    def test_get_mock(self):
        """
        Test if it execute a defaults client run and return a dict
        """
        with patch.object(inspect, "stack", MagicMock(return_value=[])), patch(
            "salt.modules.defaults.get",
            MagicMock(return_value={"users": {"root": [0]}}),
        ):
            self.assertEqual(defaults.get("core:users:root"), {"users": {"root": [0]}})

    def test_merge_with_list_merging(self):
        """
        Test deep merging of dicts with merge_lists enabled.
        """

        src_dict = {
            "string_key": "string_val_src",
            "list_key": ["list_val_src"],
            "dict_key": {"dict_key_src": "dict_val_src"},
        }

        dest_dict = {
            "string_key": "string_val_dest",
            "list_key": ["list_val_dest"],
            "dict_key": {"dict_key_dest": "dict_val_dest"},
        }

        merged_dict = {
            "string_key": "string_val_src",
            "list_key": ["list_val_dest", "list_val_src"],
            "dict_key": {
                "dict_key_dest": "dict_val_dest",
                "dict_key_src": "dict_val_src",
            },
        }

        defaults.merge(dest_dict, src_dict, merge_lists=True)
        self.assertEqual(dest_dict, merged_dict)

    def test_merge_without_list_merging(self):
        """
        Test deep merging of dicts with merge_lists disabled.
        """

        src = {
            "string_key": "string_val_src",
            "list_key": ["list_val_src"],
            "dict_key": {"dict_key_src": "dict_val_src"},
        }

        dest = {
            "string_key": "string_val_dest",
            "list_key": ["list_val_dest"],
            "dict_key": {"dict_key_dest": "dict_val_dest"},
        }

        merged = {
            "string_key": "string_val_src",
            "list_key": ["list_val_src"],
            "dict_key": {
                "dict_key_dest": "dict_val_dest",
                "dict_key_src": "dict_val_src",
            },
        }

        defaults.merge(dest, src, merge_lists=False)
        self.assertEqual(dest, merged)

    def test_merge_not_in_place(self):
        """
        Test deep merging of dicts not in place.
        """

        src = {"nested_dict": {"A": "A"}}

        dest = {"nested_dict": {"B": "B"}}

        dest_orig = {"nested_dict": {"B": "B"}}

        merged = {"nested_dict": {"A": "A", "B": "B"}}

        final = defaults.merge(dest, src, in_place=False)
        self.assertEqual(dest, dest_orig)
        self.assertEqual(final, merged)

    def test_deepcopy(self):
        """
        Test a deep copy of object.
        """

        src = {"A": "A", "B": "B"}

        dist = defaults.deepcopy(src)
        dist.update({"C": "C"})

        result = {"A": "A", "B": "B", "C": "C"}

        self.assertFalse(src == dist)
        self.assertTrue(dist == result)

    def test_update_in_place(self):
        """
        Test update with defaults values in place.
        """

        group01 = {
            "defaults": {"enabled": True, "extra": ["test", "stage"]},
            "nodes": {"host01": {"index": "foo", "upstream": "bar"}},
        }

        host01 = {
            "enabled": True,
            "index": "foo",
            "upstream": "bar",
            "extra": ["test", "stage"],
        }

        defaults.update(group01["nodes"], group01["defaults"])
        self.assertEqual(group01["nodes"]["host01"], host01)
