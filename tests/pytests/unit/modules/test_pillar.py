import pytest

import salt.modules.pillar as pillarmod
from salt.utils.odict import OrderedDict
from tests.support.mock import MagicMock, call, patch


@pytest.fixture
def pillar_value():
    pillar_value = dict(a=1, b="very secret")
    return pillar_value


@pytest.fixture
def configure_loader_modules():
    return {pillarmod: {}}


def test_obfuscate_inner_recursion():
    assert pillarmod._obfuscate_inner(
        dict(a=[1, 2], b=dict(pwd="secret", deeper=("a", 1)))
    ) == dict(a=["<int>", "<int>"], b=dict(pwd="<str>", deeper=("<str>", "<int>")))


def test_obfuscate_inner_more_types():
    assert pillarmod._obfuscate_inner(OrderedDict([("key", "value")])) == OrderedDict(
        [("key", "<str>")]
    )

    assert pillarmod._obfuscate_inner({1, 2}) == {"<int>"}

    assert pillarmod._obfuscate_inner((1, 2)) == ("<int>", "<int>")


def test_obfuscate(pillar_value):
    with patch("salt.modules.pillar.items", MagicMock(return_value=pillar_value)):
        assert pillarmod.obfuscate() == dict(a="<int>", b="<str>")


def test_obfuscate_with_kwargs(pillar_value):
    with patch(
        "salt.modules.pillar.items", MagicMock(return_value=pillar_value)
    ) as pillar_items_mock:
        ret = pillarmod.obfuscate(saltenv="saltenv")
        # ensure the kwargs are passed along to pillar.items
        assert call(saltenv="saltenv") in pillar_items_mock.mock_calls
        assert ret == dict(a="<int>", b="<str>")


def test_ls(pillar_value):
    with patch("salt.modules.pillar.items", MagicMock(return_value=pillar_value)):
        ls = sorted(pillarmod.ls())
        assert ls == ["a", "b"]


def test_pillar_get_default_merge():
    defaults = {
        "int": 1,
        "string": "foo",
        "list": ["foo"],
        "dict": {"foo": "bar", "subkey": {"foo": "bar"}},
    }

    pillar_mock = {
        "int": 2,
        "string": "bar",
        "list": ["bar", "baz"],
        "dict": {"baz": "qux", "subkey": {"baz": "qux"}},
    }

    # Test that we raise a KeyError when pillar_raise_on_missing is True
    with patch.dict(pillarmod.__opts__, {"pillar_raise_on_missing": True}):
        pytest.raises(KeyError, pillarmod.get, "missing")
    # Test that we return an empty string when it is not
    with patch.dict(pillarmod.__opts__, {}):
        assert pillarmod.get("missing") == ""

    with patch.dict(pillarmod.__pillar__, pillar_mock):
        # Test with no default passed (it should be KeyError) and merge=True.
        # The merge should be skipped and the value returned from __pillar__
        # should be returned.
        for item in pillarmod.__pillar__:
            assert pillarmod.get(item, merge=True) == pillarmod.__pillar__[item]

        # Test merging when the type of the default value is not the same as
        # what was returned. Merging should be skipped and the value returned
        # from __pillar__ should be returned.
        for default_type in defaults:
            for data_type in ("dict", "list"):
                if default_type == data_type:
                    continue
                assert (
                    pillarmod.get(data_type, default=defaults[default_type], merge=True)
                    == pillarmod.__pillar__[data_type]
                )

        # Test recursive dict merging
        assert pillarmod.get("dict", default=defaults["dict"], merge=True) == {
            "foo": "bar",
            "baz": "qux",
            "subkey": {"foo": "bar", "baz": "qux"},
        }

        # Test list merging
        assert pillarmod.get("list", default=defaults["list"], merge=True) == [
            "foo",
            "bar",
            "baz",
        ]


def test_pillar_get_default_merge_regression_38558():
    """Test for pillar.get(key=..., default=..., merge=True)
    Do not update the ``default`` value when using ``merge=True``.
    See: https://github.com/saltstack/salt/issues/38558
    """
    with patch.dict(pillarmod.__pillar__, {"l1": {"l2": {"l3": 42}}}):

        res = pillarmod.get(key="l1")
        assert {"l2": {"l3": 42}} == res

        default = {"l2": {"l3": 43}}

        res = pillarmod.get(key="l1", default=default)
        assert {"l2": {"l3": 42}} == res
        assert {"l2": {"l3": 43}} == default

        res = pillarmod.get(key="l1", default=default, merge=True)
        assert {"l2": {"l3": 42}} == res
        assert {"l2": {"l3": 43}} == default


def test_pillar_get_default_merge_regression_39062():
    """
    Confirm that we do not raise an exception if default is None and
    merge=True.
    See https://github.com/saltstack/salt/issues/39062 for more info.
    """
    with patch.dict(pillarmod.__pillar__, {"foo": "bar"}):

        assert pillarmod.get(key="foo", default=None, merge=True) == "bar"


def test_pillar_get_int_key():
    """
    Confirm that we can access pillar keys that are integers
    """
    with patch.dict(pillarmod.__pillar__, {12345: "luggage_code"}):

        assert pillarmod.get(key=12345, default=None, merge=True) == "luggage_code"

    with patch.dict(pillarmod.__pillar__, {12345: {"l2": {"l3": "my_luggage_code"}}}):

        res = pillarmod.get(key=12345)
        assert {"l2": {"l3": "my_luggage_code"}} == res

        default = {"l2": {"l3": "your_luggage_code"}}

        res = pillarmod.get(key=12345, default=default)
        assert {"l2": {"l3": "my_luggage_code"}} == res
        assert {"l2": {"l3": "your_luggage_code"}} == default

        res = pillarmod.get(key=12345, default=default, merge=True)
        assert {"l2": {"l3": "my_luggage_code"}} == res
        assert {"l2": {"l3": "your_luggage_code"}} == default


def test_pillar_keys():
    """
    Confirm that we can access pillar keys
    """
    with patch.dict(pillarmod.__pillar__, {"pkg": {"apache": "httpd"}}):
        test_key = "pkg"
        assert pillarmod.keys(test_key) == ["apache"]

    with patch.dict(
        pillarmod.__pillar__,
        {"12345": {"xyz": "my_luggage_code"}, "7": {"11": {"12": "13"}}},
    ):
        test_key = "7:11"
        res = pillarmod.keys(test_key)
        assert res == ["12"]
