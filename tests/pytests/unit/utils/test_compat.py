"""
Unit tests for salt.utils.compat.py
"""

import pytest

import salt.utils.compat


def test_cmp_int_x_equals_y():
    # int x == int y
    ret = salt.utils.compat.cmp(1, 1)
    assert ret == 0


def test_cmp_int_x_less_than_y():
    # int x < int y
    ret = salt.utils.compat.cmp(1, 2)
    assert ret == -1


def test_cmp_int_x_greater_than_y():
    # int x > int y
    ret = salt.utils.compat.cmp(2, 1)
    assert ret == 1


def test_cmp_dict_x_equals_y():
    # dict x == dict y
    dict1 = {"foo": "bar", "baz": "qux"}
    dict2 = {"baz": "qux", "foo": "bar"}
    ret = salt.utils.compat.cmp(dict1, dict2)
    assert ret == 0


def test_cmp_dict_x_not_equals_y():
    # dict x != dict y
    dict1 = {"foo": "bar", "baz": "qux"}
    dict2 = {"foobar": "bar", "baz": "qux"}
    ret = salt.utils.compat.cmp(dict1, dict2)
    assert ret == -1


def test_cmp_dict_x_not_equals_int_y():
    # dict x != int y
    dict1 = {"foo": "bar", "baz": "qux"}
    pytest.raises(TypeError, salt.utils.compat.cmp, dict1, 1)
