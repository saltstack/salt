import salt.pillar.pepa as pepa

try:
    from salt.utils.odict import OrderedDict
except ImportError:
    from collections import OrderedDict


def test_repeated_keys():
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
    assert result == expected_result
