"""
    tests.unit.utils.test_dynamic_dict
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the dynamic dict class
"""

import copy

import pytest

from salt.utils.dynamic_dict import DynamicDict


@pytest.fixture(name="base_dict")
def fixture_base_dict():
    return {
        "a": 1,
        "b": 2,
        "c": 3,
    }


@pytest.fixture(name="ddict")
def fixture_ddict(base_dict):
    return DynamicDict(**base_dict)


@pytest.fixture(name="copied_ddict")
def fixture_copied_ddict(ddict):
    return ddict.copy()


@pytest.fixture(name="dyn_func")
def fixture_dyn_func():
    def dyn_func(data=None, dyn_dict=None, key=None):
        return range(3)

    return dyn_func


def test_constructor_items(base_dict):
    ddict = DynamicDict(base_dict.items())
    for key, val in base_dict.items():
        assert (
            key in ddict
        ), f"Missing key '{key}' in DynamicDict: Tuple __init__() failed"
        assert (
            ddict[key] == val
        ), "Value of key '{}':{} != {}: Tuple __init__() failed".format(
            key, ddict[key], val
        )


def test_constructor_expansion(base_dict):
    ddict = DynamicDict(**base_dict)
    for key, val in base_dict.items():
        assert (
            key in ddict
        ), f"Missing key '{key}' in DynamicDict: Tuple __init__() failed"
        assert (
            ddict[key] == val
        ), "Value of key '{}':{} != {}: Tuple __init__() failed".format(
            key, ddict[key], val
        )


def test_static(ddict, base_dict):
    ddict["foo"] = "FOO"
    copied_ddict = base_dict.copy()
    copied_ddict["foo"] = "FOO"
    assert "foo" in ddict, "Failed to add static key 'foo'"
    assert ddict["foo"] == "FOO", "Static key 'foo':{} != 'FOO'".format(ddict["foo"])
    assert ddict.get("foo") == "FOO", "Static key 'foo':{} != 'FOO'".format(
        ddict["foo"]
    )
    assert not ddict.is_dyn_key("foo"), "Static key 'foo' should not be a dynamic key"
    del ddict["foo"]
    del copied_ddict["foo"]
    assert "foo" not in ddict, "failed to delete static key 'foo'"


def test_dynamic(ddict, copied_ddict, dyn_func):
    ddict.add_dyn("foo", dyn_func)
    copied_ddict["foo"] = dyn_func()
    assert "foo" in ddict, "Failed to add dynamic key 'foo'"
    assert not set(copied_ddict.keys()).difference(
        ddict.keys()
    ), "Unexpected keys in DynamicDict"
    assert ddict["foo"] == copied_ddict["foo"]
    assert ddict["foo"] == copied_ddict.get("foo")
    assert ddict.get("foo") == dyn_func()
    assert ddict.get("foo") == copied_ddict["foo"]


def test_iterating(base_dict, ddict, copied_ddict, dyn_func):
    for key in ddict:
        assert key in copied_ddict, f"Found an unexpected key: {key}"
        del copied_ddict[key]
    assert (
        not copied_ddict
    ), "Failed to iterate across all keys in DynamicDict - remaining: {}".format(
        copied_ddict
    )

    ddict.add_dyn("foo", dyn_func)
    copied_ddict = base_dict.copy()
    copied_ddict["foo"] = dyn_func()
    for key in ddict.keys():
        assert key in copied_ddict, f"Found an unexpected key: {key}"
        del copied_ddict[key]
    assert (
        not copied_ddict
    ), "Failed to iterate across all keys in DynamicDict - remaining: {}".format(
        copied_ddict
    )


def test_copy(ddict, base_dict, dyn_func):
    ddict.add_dyn("foo", dyn_func)
    ddict2 = ddict.copy()
    copied_dict = base_dict.copy()
    copied_dict["foo"] = dyn_func()
    for key in ddict2.keys():
        assert key in copied_dict, f"Found an unexpected key in the copy: {key}"
        del copied_dict[key]
    assert (
        not copied_dict
    ), "Failed to iterate across all keys in DynamicDict copy - remaining: {}".format(
        copied_dict
    )
    assert hasattr(
        ddict2._func_dict.get("foo"), "__call__"
    ), "Failed to copy dynamic key"

    ddict2 = {"ddict": ddict}
    copied_dict = {"ddict": base_dict.copy()}
    copied_dict["ddict"]["foo"] = dyn_func()
    ddict3 = copy.deepcopy(ddict2)
    assert ddict3["ddict"].is_dyn_key("foo"), "Dyn key 'foo' is no longer a dynamic key"
    assert hasattr(
        ddict3["ddict"]._func_dict.get("foo"), "__call__"
    ), "Failed to copy dynamic key"

    copied_dict = base_dict.copy()
    copied_dict["foo"] = dyn_func()
    for key, val in ddict.items():
        assert key in copied_dict, f"Found an unexpected key: {key}"
        del copied_dict[key]
    assert (
        not copied_dict
    ), "Failed to iterate across all keys in DynamicDict - remaining: {}".format(
        copied_dict
    )


def test_static_dict(ddict, base_dict, dyn_func):
    ddict.add_dyn("foo", dyn_func)
    static_dict = ddict.static_dict()
    assert not isinstance(static_dict, DynamicDict)
    assert set(static_dict.keys()) == set(ddict.keys())
    for key, val in static_dict.items():
        assert val == ddict[key]


def test_copy_iterator(base_dict, ddict, dyn_func):
    ddict.add_dyn("foo", dyn_func)
    copied_dict = base_dict.copy()
    copied_dict["foo"] = dyn_func()
    xvals = [val for val in copied_dict.values()]
    for val in ddict.values():
        assert val in xvals, f"Found an unexpected value: {val}"
        xvals.remove(val)
    assert (
        not xvals
    ), "Failed to iterate across all values in DynamicDict - remaining: {}".format(
        xvals
    )


def _dyn_func(data=None, dyn_dict=None, key=None):
    return 7


def test_delete_dyn_key(ddict):
    ddict.add_dyn("foo", _dyn_func)
    val = ddict.pop("foo")
    assert val == _dyn_func(), f"Failed pop(): {val} != {_dyn_func()}"
    assert "foo" not in ddict, "Failed to remove key 'foo' when pop()ed"

    ddict.add_dyn("foo", _dyn_func)
    del ddict["foo"]
    assert "foo" not in ddict, "Failed to delete dynamic key 'foo'"
