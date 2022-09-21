import salt.pillar.pepa as pepa
from tests.support.unit import TestCase

try:
    from salt.utils.odict import OrderedDict
except ImportError:
    from collections import OrderedDict


class PepaPillarTestCase(TestCase):
    def test_repeated_keys(self):
        expected_result = {
            "foo": {
                "bar": {
                    "foo": True,
                    "baz": True,
                },
            },
        }
        data = OrderedDict(
            [
                ("foo..bar..foo", True),
                ("foo..bar..baz", True),
            ]
        )
        result = pepa.key_value_to_tree(data)
        self.assertDictEqual(result, expected_result)
