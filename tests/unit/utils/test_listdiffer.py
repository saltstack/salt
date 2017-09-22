# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.unit import TestCase

# Import Salt libs
from salt.utils.listdiffer import list_diff

from salt.utils import dictdiffer
NONE = dictdiffer.RecursiveDictDiffer.NONE_VALUE


class ListDictDifferTestCase(TestCase):

    def setUp(self):
        old_list = [{'key': 1, 'value': 'foo1', 'int_value': 101},
                    {'key': 2, 'value': 'foo2', 'int_value': 102},
                    {'key': 3, 'value': 'foo3', 'int_value': 103}]
        new_list = [{'key': 1, 'value': 'foo1', 'int_value': 101},
                    {'key': 2, 'value': 'foo2', 'int_value': 112},
                    {'key': 5, 'value': 'foo5', 'int_value': 105}]
        self.list_diff = list_diff(old_list, new_list, key='key')

    def tearDown(self):
        for attrname in ('list_diff',):
            try:
                delattr(self, attrname)
            except AttributeError:
                continue

    def test_added(self):
        self.assertEqual(self.list_diff.added,
                         [{'key': 5, 'value': 'foo5', 'int_value': 105}])

    def test_removed(self):
        self.assertEqual(self.list_diff.removed,
                         [{'key': 3, 'value': 'foo3', 'int_value': 103}])

    def test_diffs(self):
        self.assertEqual(self.list_diff.diffs,
                         [{2: {'int_value': {'new': 112, 'old': 102}}},
                          # Added items
                          {5: {'int_value': {'new': 105, 'old': NONE},
                               'key': {'new': 5, 'old': NONE},
                               'value': {'new': 'foo5', 'old': NONE}}},
                          # Removed items
                          {3: {'int_value': {'new': NONE, 'old': 103},
                               'key': {'new': NONE, 'old': 3},
                               'value': {'new': NONE, 'old': 'foo3'}}}])

    def test_new_values(self):
        self.assertEqual(self.list_diff.new_values,
                         [{'key': 2, 'int_value': 112},
                          {'key': 5, 'value': 'foo5', 'int_value': 105}])

    def test_old_values(self):
        self.assertEqual(self.list_diff.old_values,
                         [{'key': 2, 'int_value': 102},
                          {'key': 3, 'value': 'foo3', 'int_value': 103}])

    def test_changed_all(self):
        self.assertEqual(self.list_diff.changed(selection='all'),
                         ['key.2.int_value', 'key.5.int_value', 'key.5.value',
                          'key.3.int_value', 'key.3.value'])

    def test_changed_intersect(self):
        self.assertEqual(self.list_diff.changed(selection='intersect'),
                         ['key.2.int_value'])

    def test_changes_str(self):
        self.assertEqual(self.list_diff.changes_str,
                         '\tidentified by key 2:\n'
                         '\tint_value from 102 to 112\n'
                         '\tidentified by key 3:\n'
                         '\twill be removed\n'
                         '\tidentified by key 5:\n'
                         '\twill be added\n')

    def test_changes_str2(self):
        self.assertEqual(self.list_diff.changes_str2,
                         '  key=2 (updated):\n'
                         '    int_value from 102 to 112\n'
                         '  key=3 (removed)\n'
                         '  key=5 (added): {\'int_value\': 105, \'key\': 5, '
                         '\'value\': \'foo5\'}')
