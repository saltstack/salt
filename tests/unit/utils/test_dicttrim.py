# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.unit import TestCase

# Import Salt libs
import salt.utils.dicttrim as dicttrimmer

import logging
log = logging.getLogger(__name__)


class DictTrimTestCase(TestCase):

    def setUp(self):
        self.old_dict = {'a': 'b', 'c': 'x' * 10000}
        self.new_dict = {'a': 'b', 'c': 'VALUE_TRIMMED'}

    def test_trim_dict(self):
        ret = dicttrimmer.trim_dict(self.old_dict, 1000)
        self.assertEqual(ret, self.new_dict)


class RecursiveDictTrimTestCase(TestCase):

    def setUp(self):
        self.old_dict = {'a': {'b': 1, 'c': 2, 'e': 'x' * 10000, 'f': '3'}}
        self.new_dict = {'a': {'b': 1, 'c': 2, 'e': 'VALUE_TRIMMED', 'f': '3'}}

    def test_trim_dict(self):
        ret = dicttrimmer.trim_dict(self.old_dict, 1000)
        self.assertEqual(ret, self.new_dict)
