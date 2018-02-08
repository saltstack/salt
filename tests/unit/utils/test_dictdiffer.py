# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.unit import TestCase

# Import Salt libs
import salt.utils.dictdiffer as dictdiffer


NONE = dictdiffer.RecursiveDictDiffer.NONE_VALUE


class RecursiveDictDifferTestCase(TestCase):

    def setUp(self):
        old_dict = {'a': {'b': 1, 'c': 2, 'e': 'old_value',
                          'f': 'old_key'},
                    'j': 'value'}
        new_dict = {'a': {'b': 1, 'c': 4, 'e': 'new_value',
                          'g': 'new_key'},
                    'h': 'new_key', 'i': None,
                    'j': 'value'}
        self.recursive_diff = \
                dictdiffer.recursive_diff(old_dict, new_dict,
                                          ignore_missing_keys=False)
        self.recursive_diff_ign = dictdiffer.recursive_diff(old_dict, new_dict)

    def tearDown(self):
        for attrname in ('recursive_diff', 'recursive_diff_missing_keys'):
            try:
                delattr(self, attrname)
            except AttributeError:
                continue

    def test_added(self):
        self.assertEqual(self.recursive_diff.added(), ['a.g', 'h', 'i'])

    def test_removed(self):
        self.assertEqual(self.recursive_diff.removed(), ['a.f'])

    def test_changed_with_ignore_unset_values(self):
        self.recursive_diff.ignore_unset_values = True
        self.assertEqual(self.recursive_diff.changed(),
                         ['a.c', 'a.e'])

    def test_changed_without_ignore_unset_values(self):
        self.recursive_diff.ignore_unset_values = False
        self.assertEqual(self.recursive_diff.changed(),
                         ['a.c', 'a.e', 'a.f', 'a.g', 'h', 'i'])

    def test_unchanged(self):
        self.assertEqual(self.recursive_diff.unchanged(),
                         ['a.b', 'j'])

    def test_diffs(self):
        self.assertDictEqual(self.recursive_diff.diffs,
                             {'a': {'c': {'old': 2, 'new': 4},
                                    'e': {'old': 'old_value',
                                          'new': 'new_value'},
                                    'f': {'old': 'old_key', 'new': NONE},
                                    'g': {'old': NONE, 'new': 'new_key'}},
                              'h': {'old': NONE, 'new': 'new_key'},
                              'i': {'old': NONE, 'new': None}})
        self.assertDictEqual(self.recursive_diff_ign.diffs,
                             {'a': {'c': {'old': 2, 'new': 4},
                                    'e': {'old': 'old_value',
                                          'new': 'new_value'},
                                    'g': {'old': NONE, 'new': 'new_key'}},
                              'h': {'old': NONE, 'new': 'new_key'},
                              'i': {'old': NONE, 'new': None}})

    def test_new_values(self):
        self.assertDictEqual(self.recursive_diff.new_values,
                             {'a': {'c': 4, 'e': 'new_value',
                                    'f': NONE, 'g': 'new_key'},
                              'h': 'new_key', 'i': None})

    def test_old_values(self):
        self.assertDictEqual(self.recursive_diff.old_values,
                             {'a': {'c': 2, 'e': 'old_value',
                                    'f': 'old_key', 'g': NONE},
                              'h': NONE, 'i': NONE})

    def test_changes_str(self):
        self.assertEqual(self.recursive_diff.changes_str,
                         'a:\n'
                         '  c from 2 to 4\n'
                         '  e from \'old_value\' to \'new_value\'\n'
                         '  f from \'old_key\' to nothing\n'
                         '  g from nothing to \'new_key\'\n'
                         'h from nothing to \'new_key\'\n'
                         'i from nothing to None')
