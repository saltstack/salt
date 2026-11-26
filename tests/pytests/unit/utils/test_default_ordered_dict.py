"""
Unit tests for DefaultOrderedDict in salt.utils.datastructures
"""

import copy

from salt.utils.datastructures import DefaultOrderedDict


def test_repr_has_the_factory_and_the_items():
    value = DefaultOrderedDict(list)
    value["a"].append(1)
    text = repr(value)
    assert "DefaultOrderedDict" in text
    assert "<class 'list'>" in text
    assert "'a': [1]" in text
    assert str(value) == text


def test_repr_without_a_factory():
    assert "None" in repr(DefaultOrderedDict())


def test_missing_key_is_created_by_the_factory():
    value = DefaultOrderedDict(list)
    assert value["missing"] == []
    assert list(value) == ["missing"]


def test_deepcopy_does_not_share_the_items():
    value = DefaultOrderedDict(list)
    value["a"].append(1)
    clone = copy.deepcopy(value)
    clone["a"].append(2)
    assert value["a"] == [1]
    assert clone["a"] == [1, 2]
    assert clone.default_factory is list
