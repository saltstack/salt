"""
Unit tests for the deprecated salt.utils.odict
"""

import copy

import pytest

odict = pytest.importorskip("salt.utils.odict")

pytestmark = [
    pytest.mark.filterwarnings("ignore::DeprecationWarning"),
]


def test_default_ordered_dict_can_be_deep_copied():
    value = odict.DefaultOrderedDict(list)
    value["a"].append(1)
    clone = copy.deepcopy(value)
    clone["a"].append(2)
    assert value["a"] == [1]
    assert clone["a"] == [1, 2]
    assert clone.default_factory is list


def test_default_ordered_dict_deep_copy_keeps_the_order_and_the_type():
    value = odict.DefaultOrderedDict(dict)
    for key in ("z", "a", "m"):
        value[key]["k"] = key
    clone = copy.deepcopy(value)
    assert type(clone) is odict.DefaultOrderedDict
    assert list(clone) == ["z", "a", "m"]


def test_default_ordered_dict_shallow_copy_shares_the_items():
    value = odict.DefaultOrderedDict(list)
    value["a"].append(1)
    clone = copy.copy(value)
    clone["a"].append(2)
    assert value["a"] == [1, 2]
