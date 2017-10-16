# -*- coding: utf-8 -*-
'''
Tests for salt.utils.data
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt libs
import salt.utils.data
from tests.support.unit import TestCase


class DataTestCase(TestCase):
    def test_sorted_ignorecase(self):
        test_list = ['foo', 'Foo', 'bar', 'Bar']
        expected_list = ['bar', 'Bar', 'foo', 'Foo']
        self.assertEqual(
            salt.utils.data.sorted_ignorecase(test_list), expected_list)
