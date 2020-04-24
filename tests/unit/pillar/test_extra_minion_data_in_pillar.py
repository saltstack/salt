# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
from salt.pillar import extra_minion_data_in_pillar

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock
from tests.support.unit import TestCase


class ExtraMinionDataInPillarTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.pillar.extra_minion_data_in_pillar
    """

    def setup_loader_modules(self):
        return {extra_minion_data_in_pillar: {"__virtual__": True}}

    def setUp(self):
        self.pillar = MagicMock()
        self.extra_minion_data = {
            "key1": {"subkey1": "value1"},
            "key2": {"subkey2": {"subsubkey2": "value2"}},
            "key3": "value3",
            "key4": {"subkey4": "value4"},
        }

    def test_extra_values_none_or_empty(self):
        ret = extra_minion_data_in_pillar.ext_pillar(
            "fake_id", self.pillar, "fake_include", None
        )
        self.assertEqual(ret, {})
        ret = extra_minion_data_in_pillar.ext_pillar(
            "fake_id", self.pillar, "fake_include", {}
        )
        self.assertEqual(ret, {})

    def test_include_all(self):
        for include_all in ["*", "<all>"]:
            ret = extra_minion_data_in_pillar.ext_pillar(
                "fake_id", self.pillar, include_all, self.extra_minion_data
            )
            self.assertEqual(ret, self.extra_minion_data)

    def test_include_specific_keys(self):
        # Tests partially existing key, key with and without subkey,
        ret = extra_minion_data_in_pillar.ext_pillar(
            "fake_id",
            self.pillar,
            include=["key1:subkey1", "key2:subkey3", "key3", "key4"],
            extra_minion_data=self.extra_minion_data,
        )
        self.assertEqual(
            ret,
            {
                "key1": {"subkey1": "value1"},
                "key3": "value3",
                "key4": {"subkey4": "value4"},
            },
        )
