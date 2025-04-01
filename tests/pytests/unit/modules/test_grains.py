import copy
import os

import pytest
import yaml

import salt.modules.grains as grainsmod
import salt.utils.dictupdate as dictupdate
from salt.exceptions import SaltException
from salt.utils.odict import OrderedDict
from tests.support.mock import MagicMock, patch
from tests.support.runtests import RUNTIME_VARS


@pytest.fixture
def configure_loader_modules():
    conf_file = os.path.join(RUNTIME_VARS.TMP, "__salt_test_grains")
    cachedir = os.path.join(RUNTIME_VARS.TMP, "__salt_test_grains_cache_dir")
    if not os.path.isdir(cachedir):
        os.makedirs(cachedir)
    return {
        grainsmod: {
            "__opts__": {"conf_file": conf_file, "cachedir": cachedir},
            "__salt__": {"saltutil.refresh_grains": MagicMock()},
        }
    }


def test_filter_by():
    with patch.dict(
        grainsmod.__grains__,
        {"os_family": "MockedOS", "1": "1", "2": "2", "roles": ["A", "B"]},
    ):

        dict1 = {"A": "B", "C": {"D": {"E": "F", "G": "H"}}}
        dict2 = {
            "default": {"A": "B", "C": {"D": "E"}},
            "1": {"A": "X"},
            "2": {"C": {"D": "H"}},
            "MockedOS": {"A": "Z"},
        }

        mdict1 = {"D": {"E": "I"}, "J": "K"}
        mdict2 = {"A": "Z"}
        mdict3 = {"C": {"D": "J"}}

        # test None result with non existent grain and no default
        res = grainsmod.filter_by(dict1, grain="xxx")
        assert res is None

        # test None result with os_family grain and no matching result
        res = grainsmod.filter_by(dict1)
        assert res is None

        # test with non existent grain, and a given default key
        res = grainsmod.filter_by(dict1, grain="xxx", default="C")
        assert res == {"D": {"E": "F", "G": "H"}}

        # add a merge dictionary, F disappears
        res = grainsmod.filter_by(dict1, grain="xxx", merge=mdict1, default="C")
        assert res == {"D": {"E": "I", "G": "H"}, "J": "K"}
        # dict1 was altered, reestablish
        dict1 = {"A": "B", "C": {"D": {"E": "F", "G": "H"}}}

        # default is not present in dict1, check we only have merge in result
        res = grainsmod.filter_by(dict1, grain="xxx", merge=mdict1, default="Z")
        assert res == mdict1

        # default is not present in dict1, and no merge, should get None
        res = grainsmod.filter_by(dict1, grain="xxx", default="Z")
        assert res is None

        # test giving a list as merge argument raise exception
        pytest.raises(SaltException, grainsmod.filter_by, dict1, "xxx", ["foo"], "C")

        # Now, re-test with an existing grain (os_family), but with no match.
        res = grainsmod.filter_by(dict1)
        assert res is None
        res = grainsmod.filter_by(dict1, default="C")
        assert res == {"D": {"E": "F", "G": "H"}}
        res = grainsmod.filter_by(dict1, merge=mdict1, default="C")
        assert res == {"D": {"E": "I", "G": "H"}, "J": "K"}
        # dict1 was altered, reestablish
        dict1 = {"A": "B", "C": {"D": {"E": "F", "G": "H"}}}
        res = grainsmod.filter_by(dict1, merge=mdict1, default="Z")
        assert res == mdict1
        res = grainsmod.filter_by(dict1, default="Z")
        assert res is None
        # this one is in fact a traceback in updatedict, merging a string
        # with a dictionary
        pytest.raises(TypeError, grainsmod.filter_by, dict1, merge=mdict1, default="A")

        # Now, re-test with a matching grain.
        dict1 = {"A": "B", "MockedOS": {"D": {"E": "F", "G": "H"}}}
        res = grainsmod.filter_by(dict1)
        assert res == {"D": {"E": "F", "G": "H"}}
        res = grainsmod.filter_by(dict1, default="A")
        assert res == {"D": {"E": "F", "G": "H"}}
        res = grainsmod.filter_by(dict1, merge=mdict1, default="A")
        assert res == {"D": {"E": "I", "G": "H"}, "J": "K"}
        # dict1 was altered, reestablish
        dict1 = {"A": "B", "MockedOS": {"D": {"E": "F", "G": "H"}}}
        res = grainsmod.filter_by(dict1, merge=mdict1, default="Z")
        assert res == {"D": {"E": "I", "G": "H"}, "J": "K"}
        # dict1 was altered, reestablish
        dict1 = {"A": "B", "MockedOS": {"D": {"E": "F", "G": "H"}}}
        res = grainsmod.filter_by(dict1, default="Z")
        assert res == {"D": {"E": "F", "G": "H"}}

        # Test when grain value is a list
        dict1 = {"A": "B", "C": {"D": {"E": "F", "G": "H"}}}
        res = grainsmod.filter_by(dict1, grain="roles", default="C")
        assert res == "B"
        # Test default when grain value is a list
        dict1 = {"Z": "B", "C": {"D": {"E": "F", "G": "H"}}}
        res = grainsmod.filter_by(dict1, grain="roles", default="C")
        assert res == {"D": {"E": "F", "G": "H"}}

        # Test with wildcard pattern in the lookup_dict keys
        dict1 = {"*OS": "B", "C": {"D": {"E": "F", "G": "H"}}}
        res = grainsmod.filter_by(dict1)
        assert res == "B"
        # Test with non-strings in lookup_dict keys
        # Issue #38094
        dict1 = {1: 2, 3: {4: 5}, "*OS": "B"}
        res = grainsmod.filter_by(dict1)
        assert res == "B"
        # Test with sequence pattern with roles
        dict1 = {"Z": "B", "[BC]": {"D": {"E": "F", "G": "H"}}}
        res = grainsmod.filter_by(dict1, grain="roles", default="Z")
        assert res == {"D": {"E": "F", "G": "H"}}

        # Base tests
        # NOTE: these may fail to detect errors if dictupdate.update() is broken
        # but then the unit test for dictupdate.update() should fail and expose
        # that.  The purpose of these tests is it validate the logic of how
        # in filter_by() processes its arguments.

        # Test with just the base
        res = grainsmod.filter_by(dict2, grain="xxx", default="xxx", base="default")
        assert res == dict2["default"]
        # Test the base with the OS grain look-up
        res = grainsmod.filter_by(dict2, default="xxx", base="default")
        assert res == dictupdate.update(
            copy.deepcopy(dict2["default"]), dict2["MockedOS"]
        )
        # Test the base with default
        res = grainsmod.filter_by(dict2, grain="xxx", base="default")
        assert res == dict2["default"]

        res = grainsmod.filter_by(dict2, grain="1", base="default")
        assert res == dictupdate.update(copy.deepcopy(dict2["default"]), dict2["1"])

        res = grainsmod.filter_by(dict2, base="default", merge=mdict2)
        assert res == dictupdate.update(
            dictupdate.update(copy.deepcopy(dict2["default"]), dict2["MockedOS"]),
            mdict2,
        )

        res = grainsmod.filter_by(dict2, base="default", merge=mdict3)
        assert res == dictupdate.update(
            dictupdate.update(copy.deepcopy(dict2["default"]), dict2["MockedOS"]),
            mdict3,
        )


def test_append_not_a_list():
    with patch.dict(grainsmod.__grains__, {"b": "bval"}):
        res = grainsmod.append("b", "d")
        assert res == "The key b is not a valid list"
        assert grainsmod.__grains__ == {"b": "bval"}

        # Failing append to an existing dict
        with patch.dict(grainsmod.__grains__, {"b": {"b1": "bval1"}}):
            res = grainsmod.append("b", "d")
            assert res == "The key b is not a valid list"
            assert grainsmod.__grains__ == {"b": {"b1": "bval1"}}


def test_append_already_in_list():
    with patch.dict(grainsmod.__grains__, {"a_list": ["a", "b", "c"], "b": "bval"}):
        res = grainsmod.append("a_list", "b")
        assert res == "The val b was already in the list a_list"
        assert grainsmod.__grains__ == {"a_list": ["a", "b", "c"], "b": "bval"}


def test_append_ok():
    with patch.dict(grainsmod.__grains__, {"a_list": ["a", "b", "c"], "b": "bval"}):
        res = grainsmod.append("a_list", "d")
        assert res == {"a_list": ["a", "b", "c", "d"]}
        assert grainsmod.__grains__ == {"a_list": ["a", "b", "c", "d"], "b": "bval"}

    with patch.dict(grainsmod.__grains__, {"b": "bval"}):
        res = grainsmod.append("a_list", "d")
        assert res == {"a_list": ["d"]}
        assert grainsmod.__grains__ == {"a_list": ["d"], "b": "bval"}

    with patch.dict(grainsmod.__grains__, {"b": "bval"}):
        res = grainsmod.append("b", "d", convert=True)
        assert res == {"b": ["bval", "d"]}
        assert grainsmod.__grains__ == {"b": ["bval", "d"]}

    with patch.dict(grainsmod.__grains__, {"b": {"b1": "bval1"}}):
        res = grainsmod.append("b", "d", convert=True)
        assert res == {"b": [{"b1": "bval1"}, "d"]}
        assert grainsmod.__grains__ == {"b": [{"b1": "bval1"}, "d"]}


def test_append_nested_not_a_list():
    with patch.dict(grainsmod.__grains__, {"a": {"b": "bval"}}):
        res = grainsmod.append("a:b", "d")
        assert res == "The key a:b is not a valid list"
        assert grainsmod.__grains__ == {"a": {"b": "bval"}}

    with patch.dict(grainsmod.__grains__, {"a": {"b": {"b1": "bval1"}}}):
        res = grainsmod.append("a:b", "d")
        assert res == "The key a:b is not a valid list"
        assert grainsmod.__grains__ == {"a": {"b": {"b1": "bval1"}}}


def test_append_nested_already_in_list():
    with patch.dict(
        grainsmod.__grains__, {"a": {"a_list": ["a", "b", "c"], "b": "bval"}}
    ):
        res = grainsmod.append("a:a_list", "b")
        assert res == "The val b was already in the list a:a_list"
        assert grainsmod.__grains__ == {"a": {"a_list": ["a", "b", "c"], "b": "bval"}}


def test_append_nested_ok():
    with patch.dict(
        grainsmod.__grains__, {"a": {"a_list": ["a", "b", "c"], "b": "bval"}}
    ):
        res = grainsmod.append("a:a_list", "d")
        assert res == {"a": {"a_list": ["a", "b", "c", "d"], "b": "bval"}}
        assert grainsmod.__grains__ == {
            "a": {"a_list": ["a", "b", "c", "d"], "b": "bval"}
        }

    with patch.dict(grainsmod.__grains__, {"a": {"b": "bval"}}):
        res = grainsmod.append("a:a_list", "d")
        assert res == {"a": {"a_list": ["d"], "b": "bval"}}
        assert grainsmod.__grains__ == {"a": {"a_list": ["d"], "b": "bval"}}

    with patch.dict(grainsmod.__grains__, {"a": {"b": "bval"}}):
        res = grainsmod.append("a:b", "d", convert=True)
        assert res == {"a": {"b": ["bval", "d"]}}
        assert grainsmod.__grains__ == {"a": {"b": ["bval", "d"]}}

    with patch.dict(grainsmod.__grains__, {"a": {"b": {"b1": "bval1"}}}):
        res = grainsmod.append("a:b", "d", convert=True)
        assert res == {"a": {"b": [{"b1": "bval1"}, "d"]}}
        assert grainsmod.__grains__ == {"a": {"b": [{"b1": "bval1"}, "d"]}}


def test_append_to_an_element_of_a_list():
    with patch.dict(grainsmod.__grains__, {"a": ["b", "c"]}):
        res = grainsmod.append("a:b", "d")
        assert res == {"a": ["b", "c"]}
        assert grainsmod.__grains__ == {"a": ["b", "c"]}


def test_set_value_already_set():
    with patch.dict(grainsmod.__grains__, {"a": 12, "c": 8}):
        res = grainsmod.set("a", 12)
        assert res["result"]
        assert res["comment"] == "Grain is already set"
        assert grainsmod.__grains__ == {"a": 12, "c": 8}

    with patch.dict(grainsmod.__grains__, {"a": ["item", 12], "c": 8}):
        res = grainsmod.set("a", ["item", 12])
        assert res["result"]
        assert res["comment"] == "Grain is already set"
        assert grainsmod.__grains__ == {"a": ["item", 12], "c": 8}

    with patch.dict(
        grainsmod.__grains__, {"a": "aval", "b": {"nested": "val"}, "c": 8}
    ):
        res = grainsmod.set("b,nested", "val", delimiter=",")
        assert res["result"]
        assert res["comment"] == "Grain is already set"
        assert grainsmod.__grains__ == {"a": "aval", "b": {"nested": "val"}, "c": 8}


def test_set_fail_replacing_existing_complex_key():
    with patch.dict(grainsmod.__grains__, {"a": "aval", "c": 8}):
        res = grainsmod.set("a", ["item", 12])
        assert not res["result"]
        assert (
            res["comment"] == "The key 'a' exists and the given value is a "
            "dict or a list. Use 'force=True' to overwrite."
        )
        assert grainsmod.__grains__ == {"a": "aval", "c": 8}

    with patch.dict(grainsmod.__grains__, {"a": ["item", 12], "c": 8}):
        res = grainsmod.set("a", ["item", 14])
        assert not res["result"]
        assert (
            res["comment"] == "The key 'a' exists but is a dict or a list. "
            "Use 'force=True' to overwrite."
        )
        assert grainsmod.__grains__ == {"a": ["item", 12], "c": 8}

    with patch.dict(
        grainsmod.__grains__, {"a": "aval", "b": ["l1", {"l2": ["val1"]}], "c": 8}
    ):
        res = grainsmod.set("b,l2", "val2", delimiter=",")
        assert not res["result"]
        assert (
            res["comment"] == "The key 'b,l2' exists but is a dict or a "
            "list. Use 'force=True' to overwrite."
        )
        assert grainsmod.__grains__ == {
            "a": "aval",
            "b": ["l1", {"l2": ["val1"]}],
            "c": 8,
        }


def test_set_nested_fails_replace_simple_value():
    with patch.dict(grainsmod.__grains__, {"a": "aval", "b": "l1", "c": 8}):
        res = grainsmod.set("b,l3", "val3", delimiter=",")
        assert not res["result"]
        assert (
            res["comment"] == "The key 'b' value is 'l1', which is different from "
            "the provided key 'l3'. Use 'force=True' to overwrite."
        )
        assert grainsmod.__grains__ == {"a": "aval", "b": "l1", "c": 8}


def test_set_simple_value():
    with patch.dict(grainsmod.__grains__, {"a": ["b", "c"], "c": 8}):
        res = grainsmod.set("b", "bval")
        assert res["result"]
        assert res["changes"] == {"b": "bval"}
        assert grainsmod.__grains__ == {"a": ["b", "c"], "b": "bval", "c": 8}


def test_set_replace_value():
    with patch.dict(grainsmod.__grains__, {"a": "aval", "c": 8}):
        res = grainsmod.set("a", 12)
        assert res["result"]
        assert res["changes"] == {"a": 12}
        assert grainsmod.__grains__ == {"a": 12, "c": 8}


def test_set_None_ok():
    with patch.dict(grainsmod.__grains__, {"a": "aval", "c": 8}):
        res = grainsmod.set("b", None)
        assert res["result"]
        assert res["changes"] == {"b": None}
        assert grainsmod.__grains__ == {"a": "aval", "b": None, "c": 8}


def test_set_None_ok_destructive():
    with patch.dict(grainsmod.__grains__, {"a": "aval", "c": 8}):
        res = grainsmod.set("b", None, destructive=True)
        assert res["result"]
        assert res["changes"] == {"b": None}
        assert grainsmod.__grains__ == {"a": "aval", "c": 8}


def test_set_None_replace_ok():
    with patch.dict(grainsmod.__grains__, {"a": "aval", "c": 8}):
        res = grainsmod.set("a", None)
        assert res["result"]
        assert res["changes"] == {"a": None}
        assert grainsmod.__grains__ == {"a": None, "c": 8}


def test_set_None_force_destructive():
    with patch.dict(grainsmod.__grains__, {"a": "aval", "c": 8}):
        res = grainsmod.set("a", None, force=True, destructive=True)
        assert res["result"]
        assert res["changes"] == {"a": None}
        assert grainsmod.__grains__ == {"c": 8}


def test_set_replace_value_was_complex_force():
    with patch.dict(grainsmod.__grains__, {"a": ["item", 12], "c": 8}):
        res = grainsmod.set("a", "aval", force=True)
        assert res["result"]
        assert res["changes"] == {"a": "aval"}
        assert grainsmod.__grains__ == {"a": "aval", "c": 8}


def test_set_complex_value_force():
    with patch.dict(grainsmod.__grains__, {"a": "aval", "c": 8}):
        res = grainsmod.set("a", ["item", 12], force=True)
        assert res["result"]
        assert res["changes"] == {"a": ["item", 12]}
        assert grainsmod.__grains__ == {"a": ["item", 12], "c": 8}


def test_set_nested_create():
    with patch.dict(grainsmod.__grains__, {"a": "aval", "c": 8}):
        res = grainsmod.set("b,nested", "val", delimiter=",")
        assert res["result"]
        assert res["changes"] == {"b": {"nested": "val"}}
        assert grainsmod.__grains__ == {"a": "aval", "b": {"nested": "val"}, "c": 8}


def test_set_nested_update_dict():
    with patch.dict(
        grainsmod.__grains__, {"a": "aval", "b": {"nested": "val"}, "c": 8}
    ):
        res = grainsmod.set("b,nested", "val2", delimiter=",")
        assert res["result"]
        assert res["changes"] == {"b": {"nested": "val2"}}
        assert grainsmod.__grains__ == {"a": "aval", "b": {"nested": "val2"}, "c": 8}


def test_set_nested_update_dict_remove_key():
    with patch.dict(
        grainsmod.__grains__, {"a": "aval", "b": {"nested": "val"}, "c": 8}
    ):
        res = grainsmod.set("b,nested", None, delimiter=",", destructive=True)
        assert res["result"]
        assert res["changes"] == {"b": {}}
        assert grainsmod.__grains__ == {"a": "aval", "b": {}, "c": 8}


def test_set_nested_update_dict_new_key():
    with patch.dict(
        grainsmod.__grains__, {"a": "aval", "b": {"nested": "val"}, "c": 8}
    ):
        res = grainsmod.set("b,b2", "val2", delimiter=",")
        assert res["result"]
        assert res["changes"] == {"b": {"b2": "val2", "nested": "val"}}
        assert grainsmod.__grains__ == {
            "a": "aval",
            "b": {"b2": "val2", "nested": "val"},
            "c": 8,
        }


def test_set_nested_list_replace_key():
    with patch.dict(
        grainsmod.__grains__, {"a": "aval", "b": ["l1", "l2", "l3"], "c": 8}
    ):
        res = grainsmod.set("b,l2", "val2", delimiter=",")
        assert res["result"]
        assert res["changes"] == {"b": ["l1", {"l2": "val2"}, "l3"]}
        assert grainsmod.__grains__ == {
            "a": "aval",
            "b": ["l1", {"l2": "val2"}, "l3"],
            "c": 8,
        }


def test_set_nested_list_update_dict_key():
    with patch.dict(
        grainsmod.__grains__, {"a": "aval", "b": ["l1", {"l2": "val1"}], "c": 8}
    ):
        res = grainsmod.set("b,l2", "val2", delimiter=",")
        assert res["result"]
        assert res["changes"] == {"b": ["l1", {"l2": "val2"}]}
        assert grainsmod.__grains__ == {
            "a": "aval",
            "b": ["l1", {"l2": "val2"}],
            "c": 8,
        }


def test_set_nested_list_update_dict_key_overwrite():
    with patch.dict(
        grainsmod.__grains__, {"a": "aval", "b": ["l1", {"l2": ["val1"]}], "c": 8}
    ):
        res = grainsmod.set("b,l2", "val2", delimiter=",", force=True)
        assert res["result"]
        assert res["changes"] == {"b": ["l1", {"l2": "val2"}]}
        assert grainsmod.__grains__ == {
            "a": "aval",
            "b": ["l1", {"l2": "val2"}],
            "c": 8,
        }


def test_set_nested_list_append_dict_key():
    with patch.dict(
        grainsmod.__grains__, {"a": "aval", "b": ["l1", {"l2": "val2"}], "c": 8}
    ):
        res = grainsmod.set("b,l3", "val3", delimiter=",")
        assert res["result"]
        assert res["changes"] == {"b": ["l1", {"l2": "val2"}, {"l3": "val3"}]}
        assert grainsmod.__grains__ == {
            "a": "aval",
            "b": ["l1", {"l2": "val2"}, {"l3": "val3"}],
            "c": 8,
        }


def test_set_nested_existing_value_is_the_key():
    with patch.dict(grainsmod.__grains__, {"a": "aval", "b": "l3", "c": 8}):
        res = grainsmod.set("b,l3", "val3", delimiter=",")
        assert res["result"]
        assert res["changes"] == {"b": {"l3": "val3"}}
        assert grainsmod.__grains__ == {"a": "aval", "b": {"l3": "val3"}, "c": 8}


def test_set_nested_existing_value_overwrite():
    with patch.dict(grainsmod.__grains__, {"a": "aval", "b": "l1", "c": 8}):
        res = grainsmod.set("b,l3", "val3", delimiter=",", force=True)
        assert res["result"]
        assert res["changes"] == {"b": {"l3": "val3"}}
        assert grainsmod.__grains__ == {"a": "aval", "b": {"l3": "val3"}, "c": 8}


def test_set_deeply_nested_update():
    with patch.dict(
        grainsmod.__grains__,
        {"a": "aval", "b": {"l1": ["l21", "l22", {"l23": "l23val"}]}, "c": 8},
    ):
        res = grainsmod.set("b,l1,l23", "val", delimiter=",")
        assert res["result"]
        assert res["changes"] == {"b": {"l1": ["l21", "l22", {"l23": "val"}]}}
        assert grainsmod.__grains__ == {
            "a": "aval",
            "b": {"l1": ["l21", "l22", {"l23": "val"}]},
            "c": 8,
        }


def test_set_deeply_nested_create():
    with patch.dict(
        grainsmod.__grains__,
        {"a": "aval", "b": {"l1": ["l21", "l22", {"l23": "l23val"}]}, "c": 8},
    ):
        res = grainsmod.set("b,l1,l24,l241", "val", delimiter=",")
        assert res["result"]
        assert res["changes"] == {
            "b": {
                "l1": [
                    "l21",
                    "l22",
                    {"l23": "l23val"},
                    {"l24": {"l241": "val"}},
                ]
            }
        }
        assert grainsmod.__grains__ == {
            "a": "aval",
            "b": {
                "l1": [
                    "l21",
                    "l22",
                    {"l23": "l23val"},
                    {"l24": {"l241": "val"}},
                ]
            },
            "c": 8,
        }


def test_get_ordered():
    with patch.dict(
        grainsmod.__grains__,
        OrderedDict(
            [
                ("a", "aval"),
                (
                    "b",
                    OrderedDict(
                        [
                            ("z", "zval"),
                            (
                                "l1",
                                ["l21", "l22", OrderedDict([("l23", "l23val")])],
                            ),
                        ]
                    ),
                ),
                ("c", 8),
            ]
        ),
    ):
        res = grainsmod.get("b")
        assert type(res) == OrderedDict
        # Check that order really matters
        assert res == OrderedDict(
            [
                ("z", "zval"),
                ("l1", ["l21", "l22", OrderedDict([("l23", "l23val")])]),
            ]
        )
        assert not res == OrderedDict(
            [
                ("l1", ["l21", "l22", OrderedDict([("l23", "l23val")])]),
                ("z", "zval"),
            ]
        )


def test_get_unordered():
    with patch.dict(
        grainsmod.__grains__,
        OrderedDict(
            [
                ("a", "aval"),
                (
                    "b",
                    OrderedDict(
                        [
                            ("z", "zval"),
                            (
                                "l1",
                                ["l21", "l22", OrderedDict([("l23", "l23val")])],
                            ),
                        ]
                    ),
                ),
                ("c", 8),
            ]
        ),
    ):
        res = grainsmod.get("b", ordered=False)
        assert type(res) == dict
        # Check that order doesn't matter
        assert res == OrderedDict(
            [
                ("l1", ["l21", "l22", OrderedDict([("l23", "l23val")])]),
                ("z", "zval"),
            ]
        )


def test_equals():
    with patch.dict(
        grainsmod.__grains__,
        OrderedDict(
            [
                ("a", "aval"),
                (
                    "b",
                    OrderedDict(
                        [
                            ("z", "zval"),
                            (
                                "l1",
                                ["l21", "l22", OrderedDict([("l23", "l23val")])],
                            ),
                        ]
                    ),
                ),
                ("c", 8),
            ]
        ),
    ):
        res = grainsmod.equals("a", "aval")
        assert type(res) == bool
        assert res
        res = grainsmod.equals("b:z", "zval")
        assert res
        res = grainsmod.equals("b:z", "aval")
        assert not res


def test_grains_setval_refresh_pillar():
    """
    Test that refresh_pillar kwarg is being passed correctly from grains.setval to saltutil.refresh_grains
    """
    ret = grainsmod.setval("test_grains_setval_refresh_pillar", "saltopotamus")
    grainsmod.__salt__["saltutil.refresh_grains"].assert_called_with(
        refresh_pillar=True
    )
    ret = grainsmod.setval(
        "test_grains_setval_refresh_pillar", "saltopotamus", refresh_pillar=True
    )
    grainsmod.__salt__["saltutil.refresh_grains"].assert_called_with(
        refresh_pillar=True
    )
    ret = grainsmod.setval(
        "test_grains_setval_refresh_pillar", "saltopotamus", refresh_pillar=False
    )
    grainsmod.__salt__["saltutil.refresh_grains"].assert_called_with(
        refresh_pillar=False
    )


def test_setval_unicode():
    key = "塩"  # salt
    value = "塩人生です"  # salt is life

    # Note: call setvals 2 times is important
    # 1: add key to conf grains
    # 2: update and read key from conf grains
    for _ in range(2):
        ret = grainsmod.setvals({key: value})
        assert key in ret
        assert ret[key] == value


def test_setvals_conflicting_ids(tmp_path):
    """
    Test that conflicting top-level keys in static grains file does not break
    managing static grains
    """
    static_grains = tmp_path / "grains"
    with static_grains.open("w") as fh:
        fh.write('foo: bar\nfoo: baz\nno_conflict_here: "yay"\n')

    key = "hello"
    value = "world"

    with patch.dict(grainsmod.__opts__, {"conf_file": str(tmp_path / "minion")}):
        # Update the grains file in the temp dir
        grainsmod.setvals({key: value})

    # Load the contents of the file as text for the below asserts
    updated_grains = static_grains.read_text()

    top_level_keys = [
        line.split()[0].rstrip(":") for line in updated_grains.splitlines()
    ]
    # Confirm that the conflicting IDs were collapsed into a single value
    assert top_level_keys.count("foo") == 1
    # Confirm that the new static grain made it into the file
    assert yaml.safe_load(updated_grains)[key] == value


def test_delval_single():
    with patch.dict(
        grainsmod.__grains__, {"a": "aval", "b": {"nested": "val"}, "c": 8}
    ):
        res = grainsmod.delval("a")
        assert res["result"]
        assert res["changes"] == {"a": None}
        assert grainsmod.__grains__ == {"a": None, "b": {"nested": "val"}, "c": 8}


def test_delval_nested():
    with patch.dict(
        grainsmod.__grains__, {"a": "aval", "b": {"nested": "val"}, "c": 8}
    ):
        res = grainsmod.delval("b:nested")
        assert res["result"]
        assert res["changes"] == {"b": {"nested": None}}
        assert grainsmod.__grains__ == {"a": "aval", "b": {"nested": None}, "c": 8}


def test_delkey_single_key():
    with patch.dict(
        grainsmod.__grains__, {"a": "aval", "b": {"nested": "val"}, "c": 8}
    ):
        res = grainsmod.delkey("a")
        assert res["result"]
        assert res["changes"] == {"a": None}
        assert grainsmod.__grains__ == {"b": {"nested": "val"}, "c": 8}


def test_delkey_nested_key():
    with patch.dict(
        grainsmod.__grains__, {"a": "aval", "b": {"nested": "val"}, "c": 8}
    ):
        res = grainsmod.delkey("b:nested")
        assert res["result"]
        assert res["changes"] == {"b": {}}
        assert grainsmod.__grains__ == {"a": "aval", "b": {}, "c": 8}


def test_delkey_nested_key_force_needed():
    with patch.dict(
        grainsmod.__grains__, {"a": "aval", "b": {"nested": "val"}, "c": 8}
    ):
        res = grainsmod.delkey("b", force=True)
        assert res["comment"].find("Use 'force=True' to overwrite.") == -1
        assert res["result"]
        assert res["changes"] == {"b": None}
        assert grainsmod.__grains__ == {"a": "aval", "c": 8}
