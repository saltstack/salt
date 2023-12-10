"""
Test cases for salt.modules.defaults

    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import inspect

import pytest

import salt.modules.defaults as defaults
from tests.support.mock import MagicMock, patch


@pytest.fixture()
def configure_loader_modules():
    return {defaults: {}}


def test_get_mock():
    """
    Test if it execute a defaults client run and return a dict
    """
    with patch.object(inspect, "stack", MagicMock(return_value=[])), patch(
        "salt.modules.defaults.get",
        MagicMock(return_value={"users": {"root": [0]}}),
    ):
        assert defaults.get("core:users:root") == {"users": {"root": [0]}}


def test_merge_with_list_merging():
    """
    Test deep merging of dicts with merge_lists enabled.
    """

    src_dict = {
        "string_key": "string_val_src",
        "list_key": ["list_val_src"],
        "dict_key": {"dict_key_src": "dict_val_src"},
    }

    dest_dict = {
        "string_key": "string_val_dest",
        "list_key": ["list_val_dest"],
        "dict_key": {"dict_key_dest": "dict_val_dest"},
    }

    merged_dict = {
        "string_key": "string_val_src",
        "list_key": ["list_val_dest", "list_val_src"],
        "dict_key": {
            "dict_key_dest": "dict_val_dest",
            "dict_key_src": "dict_val_src",
        },
    }

    defaults.merge(dest_dict, src_dict, merge_lists=True)
    assert dest_dict == merged_dict


def test_merge_without_list_merging():
    """
    Test deep merging of dicts with merge_lists disabled.
    """

    src = {
        "string_key": "string_val_src",
        "list_key": ["list_val_src"],
        "dict_key": {"dict_key_src": "dict_val_src"},
    }

    dest = {
        "string_key": "string_val_dest",
        "list_key": ["list_val_dest"],
        "dict_key": {"dict_key_dest": "dict_val_dest"},
    }

    merged = {
        "string_key": "string_val_src",
        "list_key": ["list_val_src"],
        "dict_key": {
            "dict_key_dest": "dict_val_dest",
            "dict_key_src": "dict_val_src",
        },
    }

    defaults.merge(dest, src, merge_lists=False)
    assert dest == merged


def test_merge_not_in_place():
    """
    Test deep merging of dicts not in place.
    """

    src = {"nested_dict": {"A": "A"}}

    dest = {"nested_dict": {"B": "B"}}

    dest_orig = {"nested_dict": {"B": "B"}}

    merged = {"nested_dict": {"A": "A", "B": "B"}}

    final = defaults.merge(dest, src, in_place=False)
    assert dest == dest_orig
    assert final == merged


def test_merge_src_is_none():
    """
    Test deep merging of dicts not in place.
    """

    dest = {"nested_dict": {"B": "B"}}

    dest_orig = {"nested_dict": {"B": "B"}}

    final = defaults.merge(dest, None, in_place=False)
    assert dest == dest_orig
    assert final == dest_orig


def test_merge_dest_is_none():
    """
    Test deep merging of dicts not in place.
    """

    src = {"nested_dict": {"B": "B"}}

    src_orig = {"nested_dict": {"B": "B"}}

    final = defaults.merge(None, src, in_place=False)
    assert src == src_orig
    assert final == src_orig


def test_merge_in_place_dest_is_none():
    """
    Test deep merging of dicts not in place.
    """

    src = {"nested_dict": {"B": "B"}}

    pytest.raises(TypeError, defaults.merge, None, src)


def test_deepcopy():
    """
    Test a deep copy of object.
    """

    src = {"A": "A", "B": "B"}

    dist = defaults.deepcopy(src)
    dist.update({"C": "C"})

    result = {"A": "A", "B": "B", "C": "C"}

    assert src != dist
    assert dist == result


def test_update_in_place():
    """
    Test update with defaults values in place.
    """

    group01 = {
        "defaults": {"enabled": True, "extra": ["test", "stage"]},
        "nodes": {"host01": {"index": "foo", "upstream": "bar"}},
    }

    host01 = {
        "enabled": True,
        "index": "foo",
        "upstream": "bar",
        "extra": ["test", "stage"],
    }

    defaults.update(group01["nodes"], group01["defaults"])
    assert group01["nodes"]["host01"] == host01


def test_update_with_defaults_none():
    group01 = {
        "defaults": {"enabled": True, "extra": ["test", "stage"]},
        "nodes": {"host01": {"index": "foo", "upstream": "bar"}},
    }

    host01 = {
        "index": "foo",
        "upstream": "bar",
    }

    defaults.update(group01["nodes"], None)
    assert group01["nodes"]["host01"] == host01


def test_update_with_dest_none():
    group01 = {
        "defaults": {"enabled": True, "extra": ["test", "stage"]},
        "nodes": {"host01": {"index": "foo", "upstream": "bar"}},
    }

    ret = defaults.update(None, group01["defaults"], in_place=False)
    assert ret == {}


def test_update_in_place_with_dest_none():
    group01 = {
        "defaults": {"enabled": True, "extra": ["test", "stage"]},
        "nodes": {"host01": {"index": "foo", "upstream": "bar"}},
    }

    pytest.raises(TypeError, defaults.update, None, group01["defaults"])
