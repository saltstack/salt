# -*- coding: utf-8 -*-
"""
Unit tests for salt.utils.compat.py
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
import salt.utils.compat

# Import Salt Testing libs
from tests.support.unit import TestCase

class CompatUtilsTestCase(TestCase):
    def test_cmp(self):
        # int x == int y
        ret = salt.utils.compat.cmp(1, 1)
        self.assertEqual(0, ret)

        # int x < int y 
        ret = salt.utils.compat.cmp(1, 2)
        self.assertEqual(-1, ret)

        # int x > int y
        ret = salt.utils.compat.cmp(2, 1)
        self.assertEqual(1, ret)

        # dict x == dict y
        dict1 = {'foo': 'bar', 'baz': 'qux'}
        dict2 = {'baz': 'qux', 'foo': 'bar'}
        ret = salt.utils.compat.cmp(dict1, dict2)
        self.assertEqual(0, ret)

        # dict x != dict y
        dict1 = {'foo': 'bar', 'baz': 'qux'}
        dict2 = {'foobar': 'bar', 'baz': 'qux'}
        ret = salt.utils.compat.cmp(dict1, dict2)
        self.assertEqual(-1, ret)

        # dict x != int y
        dict1 = {'foo': 'bar', 'baz': 'qux'}
        self.assertRaises(TypeError, salt.utils.compat.cmp, dict1, 1)
