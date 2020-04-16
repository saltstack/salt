# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

from collections import OrderedDict

# Import Salt Libs
import salt.pillar.pepa as pepa

# Import Salt Testing libs
from tests.support.unit import TestCase


class PepaPillarTestCase(TestCase):
    def test_repeated_keys(self):
        # fmt: off
        expected_result = {
            "foo": {
                "bar": {
                    "foo": True,
                    "baz": True,
                },
            },
        }
        data = OrderedDict([
            ('foo..bar..foo', True),
            ('foo..bar..baz', True),
        ])
        # fmt: on
        result = pepa.key_value_to_tree(data)
        self.assertDictEqual(result, expected_result)
