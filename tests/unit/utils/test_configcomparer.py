import copy

import salt.utils.configcomparer as configcomparer
from tests.support.unit import TestCase


class UtilConfigcomparerTestCase(TestCase):

    base_config = {
        "attr1": "value1",
        "attr2": ["item1", "item2", "item3"],
        "attr3": [],
        "attr4": {},
        "attr5": {"subattr1": "value1", "subattr2": ["item1"]},
    }

    def test_compare_and_update_config(self):

        # empty config
        to_update = copy.deepcopy(self.base_config)
        changes = {}
        configcomparer.compare_and_update_config(
            {},
            to_update,
            changes,
        )
        self.assertEqual({}, changes)
        self.assertEqual(self.base_config, to_update)

        # simple, new value
        to_update = copy.deepcopy(self.base_config)
        changes = {}
        configcomparer.compare_and_update_config(
            {"attrx": "value1"},
            to_update,
            changes,
        )
        self.assertEqual(
            {"attrx": {"new": "value1", "old": None}},
            changes,
        )
        self.assertEqual("value1", to_update["attrx"])
        self.assertEqual("value1", to_update["attr1"])
        # simple value
        to_update = copy.deepcopy(self.base_config)
        changes = {}
        configcomparer.compare_and_update_config(
            {"attr1": "value2"},
            to_update,
            changes,
        )
        self.assertEqual(
            {"attr1": {"new": "value2", "old": "value1"}},
            changes,
        )
        self.assertEqual("value2", to_update["attr1"])
        self.assertEqual(
            {
                "attr1": "value2",
                "attr2": ["item1", "item2", "item3"],
                "attr3": [],
                "attr4": {},
                "attr5": {"subattr1": "value1", "subattr2": ["item1"]},
            },
            to_update,
        )

        # empty list
        to_update = copy.deepcopy(self.base_config)
        changes = {}
        configcomparer.compare_and_update_config(
            {"attr3": []},
            to_update,
            changes,
        )
        self.assertEqual({}, changes)
        self.assertEqual(self.base_config, to_update)

        # list value (add)
        to_update = copy.deepcopy(self.base_config)
        changes = {}
        configcomparer.compare_and_update_config(
            {"attr2": ["item1", "item2", "item3", "item4"]},
            to_update,
            changes,
        )
        self.assertEqual(
            {"attr2[3]": {"new": "item4", "old": None}},
            changes,
        )
        self.assertEqual(
            {
                "attr1": "value1",
                "attr2": ["item1", "item2", "item3", "item4"],
                "attr3": [],
                "attr4": {},
                "attr5": {"subattr1": "value1", "subattr2": ["item1"]},
            },
            to_update,
        )

        # list value (remove and modify)
        to_update = copy.deepcopy(self.base_config)
        changes = {}
        configcomparer.compare_and_update_config(
            {"attr2": ["itemx", "item2"]},
            to_update,
            changes,
        )
        self.assertEqual(
            {
                "attr2[0]": {"new": "itemx", "old": "item1"},
                "attr2[2]": {"new": None, "old": "item3"},
            },
            changes,
        )
        self.assertEqual(
            {
                "attr1": "value1",
                "attr2": ["itemx", "item2"],
                "attr3": [],
                "attr4": {},
                "attr5": {"subattr1": "value1", "subattr2": ["item1"]},
            },
            to_update,
        )

        # empty dict
        to_update = copy.deepcopy(self.base_config)
        changes = {}
        configcomparer.compare_and_update_config(
            {"attr4": {}},
            to_update,
            changes,
        )
        self.assertEqual({}, changes)
        self.assertEqual(self.base_config, to_update)

        # dict value (add)
        to_update = copy.deepcopy(self.base_config)
        changes = {}
        configcomparer.compare_and_update_config(
            {"attr5": {"subattr3": "value1"}},
            to_update,
            changes,
        )
        self.assertEqual(
            {"attr5.subattr3": {"new": "value1", "old": None}},
            changes,
        )
        self.assertEqual(
            {
                "attr1": "value1",
                "attr2": ["item1", "item2", "item3"],
                "attr3": [],
                "attr4": {},
                "attr5": {
                    "subattr1": "value1",
                    "subattr2": ["item1"],
                    "subattr3": "value1",
                },
            },
            to_update,
        )

        # dict value (remove and modify)
        to_update = copy.deepcopy(self.base_config)
        changes = {}
        configcomparer.compare_and_update_config(
            {"attr5": {"subattr1": "value2", "subattr2": ["item1", "item2"]}},
            to_update,
            changes,
        )
        self.assertEqual(
            {
                "attr5.subattr1": {"new": "value2", "old": "value1"},
                "attr5.subattr2[1]": {"new": "item2", "old": None},
            },
            changes,
        )
        self.assertEqual(
            {
                "attr1": "value1",
                "attr2": ["item1", "item2", "item3"],
                "attr3": [],
                "attr4": {},
                "attr5": {"subattr1": "value2", "subattr2": ["item1", "item2"]},
            },
            to_update,
        )
