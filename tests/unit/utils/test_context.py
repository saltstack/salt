"""
tests.unit.context_test
~~~~~~~~~~~~~~~~~~~~~~~
"""

import salt.utils.json
from salt.utils.context import NamespacedDictWrapper
from tests.support.unit import TestCase


class NamespacedDictWrapperTests(TestCase):
    PREFIX = "prefix"

    def setUp(self):
        self._dict = {}

    def test_single_key(self):
        self._dict["prefix"] = {"foo": "bar"}
        w = NamespacedDictWrapper(self._dict, "prefix")
        self.assertEqual(w["foo"], "bar")

    def test_multiple_key(self):
        self._dict["prefix"] = {"foo": {"bar": "baz"}}
        w = NamespacedDictWrapper(self._dict, ("prefix", "foo"))
        self.assertEqual(w["bar"], "baz")

    def test_json_dumps_single_key(self):
        self._dict["prefix"] = {"foo": {"bar": "baz"}}
        w = NamespacedDictWrapper(self._dict, "prefix")
        self.assertEqual(salt.utils.json.dumps(w), '{"foo": {"bar": "baz"}}')

    def test_json_dumps_multiple_key(self):
        self._dict["prefix"] = {"foo": {"bar": "baz"}}
        w = NamespacedDictWrapper(self._dict, ("prefix", "foo"))
        self.assertEqual(salt.utils.json.dumps(w), '{"bar": "baz"}')
