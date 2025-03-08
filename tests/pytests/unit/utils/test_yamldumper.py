"""
    Unit tests for salt.utils.yamldumper
"""

import pytest

from collections import OrderedDict, defaultdict

import salt.utils.yamldumper
from salt.utils.context import NamespacedDictWrapper
from salt.utils.odict import HashableOrderedDict

from yaml.constructor import ConstructorError


def test_yaml_dump():
    """
    Test yaml.dump a dict
    """
    data = {"foo": "bar"}
    exp_yaml = "{foo: bar}\n"

    assert salt.utils.yamldumper.dump(data) == exp_yaml

    assert salt.utils.yamldumper.dump(
        data, default_flow_style=False
    ) == exp_yaml.replace("{", "").replace("}", "")


def test_yaml_safe_dump():
    """
    Test yaml.safe_dump a dict
    """
    data = {"foo": "bar"}
    assert salt.utils.yamldumper.safe_dump(data) == "{foo: bar}\n"

    assert (
        salt.utils.yamldumper.safe_dump(data, default_flow_style=False) == "foo: bar\n"
    )


def test_yaml_ordered_dump():
    """
    Test yaml.dump with OrderedDict
    """
    data = OrderedDict([("foo", "bar"), ("baz", "qux")])
    exp_yaml = "{foo: bar, baz: qux}\n"
    assert (
        salt.utils.yamldumper.dump(data, Dumper=salt.utils.yamldumper.OrderedDumper)
        == exp_yaml
    )


def test_yaml_safe_ordered_dump():
    """
    Test yaml.safe_dump with OrderedDict
    """
    data = OrderedDict([("foo", "bar"), ("baz", "qux")])
    exp_yaml = "{foo: bar, baz: qux}\n"
    assert salt.utils.yamldumper.safe_dump(data) == exp_yaml


def test_yaml_indent_safe_ordered_dump():
    """
    Test yaml.dump with IndentedSafeOrderedDumper
    """
    data = OrderedDict([("foo", ["bar", "baz"]), ("qux", "quux")])
    # Account for difference in SafeDumper vs CSafeDumper
    if salt.utils.yamldumper.SafeDumper.__name__ == "SafeDumper":
        exp_yaml = "foo:\n  - bar\n  - baz\nqux: quux\n"
    else:
        exp_yaml = "foo:\n- bar\n- baz\nqux: quux\n"
    assert (
        salt.utils.yamldumper.dump(
            data,
            Dumper=salt.utils.yamldumper.IndentedSafeOrderedDumper,
            default_flow_style=False,
        )
        == exp_yaml
    )


def test_yaml_defaultdict_dump():
    """
    Test yaml.dump with defaultdict
    """
    data = defaultdict(list)
    data["foo"].append("bar")
    exp_yaml = "foo: [bar]\n"
    assert salt.utils.yamldumper.safe_dump(data) == exp_yaml


def test_yaml_namespaced_dict_wrapper_dump():
    """
    Test yaml.dump with NamespacedDictWrapper
    """
    data = NamespacedDictWrapper({"test": {"foo": "bar"}}, "test")
    exp_yaml = (
        "!!python/object/new:salt.utils.context.NamespacedDictWrapper\n"
        "dictitems: {foo: bar}\n"
        "state:\n"
        "  _NamespacedDictWrapper__dict:\n"
        "    test: {foo: bar}\n"
        "  pre_keys: !!python/tuple [test]\n"
    )
    assert salt.utils.yamldumper.dump(data) == exp_yaml


def test_yaml_undefined_dump():
    """
    Test yaml.safe_dump with None
    """
    data = {"foo": None}
    exp_yaml = "{foo: null}\n"
    assert salt.utils.yamldumper.safe_dump(data) == exp_yaml


def test_yaml_hashable_ordered_dict_dump():
    """
    Test yaml.dump with HashableOrderedDict
    """
    data = HashableOrderedDict([("foo", "bar"), ("baz", "qux")])
    exp_yaml = "{foo: bar, baz: qux}\n"
    assert (
        salt.utils.yamldumper.dump(data, Dumper=salt.utils.yamldumper.OrderedDumper)
        == exp_yaml
    )


def test_allow_duplicate_includes():
    """
    Test allow_duplicate_includes=True
    """
    yaml_data = """
    include:
      - foo
      - bar
    include:
      - foo
      - bar
    """
    opts = {"allow_duplicate_includes": True}
    loader = salt.utils.yamlloader.SaltYamlSafeLoader(yaml_data, opts=opts)
    data = loader.get_single_data()

    assert data == {
        "include": ["foo", "bar"],
    }


def test_allow_duplicate_includes_false():
    """
    Test allow_duplicate_includes=False
    """
    yaml_data = """
    include:
      - foo
      - bar
    include:
      - foo
      - bar
    """
    opts = {"allow_duplicate_includes": False}

    with pytest.raises(ConstructorError, match="found conflicting ID 'include'"):
        loader = salt.utils.yamlloader.SaltYamlSafeLoader(yaml_data, opts=opts)
        loader.get_single_data()
