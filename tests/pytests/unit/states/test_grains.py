"""
unit tests for the grains state
"""

import contextlib
import os

import pytest

import salt.modules.grains as grainsmod
import salt.states.grains as grains
import salt.utils.files
import salt.utils.stringutils
import salt.utils.yaml
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules(minion_opts):
    minion_opts["local"] = True
    minion_opts["test"] = False
    loader_globals = {
        "__opts__": minion_opts,
        "__salt__": {
            "cmd.run_all": MagicMock(
                return_value={"pid": 5, "retcode": 0, "stderr": "", "stdout": ""}
            ),
            "grains.get": grainsmod.get,
            "grains.set": grainsmod.set,
            "grains.setval": grainsmod.setval,
            "grains.delval": grainsmod.delval,
            "grains.append": grainsmod.append,
            "grains.remove": grainsmod.remove,
            "saltutil.sync_grains": MagicMock(),
        },
    }
    return {grains: loader_globals, grainsmod: loader_globals}


def assert_grain_file_content(grains_string):
    grains_file = os.path.join(grains.__opts__["conf_dir"], "grains")
    with salt.utils.files.fopen(grains_file, "r") as grf:
        grains_data = salt.utils.stringutils.to_unicode(grf.read())
    assert grains_string == grains_data


@contextlib.contextmanager
def set_grains(grains_data):
    with patch.dict(grains.__grains__, grains_data):
        with patch.dict(grainsmod.__grains__, grains_data):
            grains_file = os.path.join(grains.__opts__["conf_dir"], "grains")
            with salt.utils.files.fopen(grains_file, "w+") as grf:
                salt.utils.yaml.safe_dump(grains_data, grf, default_flow_style=False)
            yield


# 'exists' function tests: 2


def test_exists_missing():
    with set_grains({"a": "aval"}):
        ret = grains.exists(name="foo")
        assert ret["result"] is False
        assert ret["comment"] == "Grain does not exist"
        assert ret["changes"] == {}


def test_exists_found():
    with set_grains({"a": "aval", "foo": "bar"}):
        # Grain already set
        ret = grains.exists(name="foo")
        assert ret["result"] is True
        assert ret["comment"] == "Grain exists"
        assert ret["changes"] == {}

    # 'make_hashable' function tests: 1


def test_make_hashable():
    with set_grains({"cmplx_lst_grain": [{"a": "aval"}, {"foo": "bar"}]}):
        hashable_list = {"cmplx_lst_grain": [{"a": "aval"}, {"foo": "bar"}]}
        assert grains.make_hashable(grains.__grains__).issubset(
            grains.make_hashable(hashable_list)
        )

    # 'present' function tests: 12


def test_present_add():
    # Set a non existing grain
    with set_grains({"a": "aval"}):
        ret = grains.present(name="foo", value="bar")
        assert ret["result"] is True
        assert ret["changes"] == {"foo": "bar"}
        assert grains.__grains__ == {"a": "aval", "foo": "bar"}
        assert_grain_file_content("a: aval\nfoo: bar\n")

    # Set a non existing nested grain
    with set_grains({"a": "aval"}):
        ret = grains.present(name="foo:is:nested", value="bar")
        assert ret["result"] is True
        assert ret["changes"] == {"foo": {"is": {"nested": "bar"}}}
        assert grains.__grains__ == {"a": "aval", "foo": {"is": {"nested": "bar"}}}
        assert_grain_file_content("a: aval\nfoo:\n  is:\n    nested: bar\n")

    # Set a non existing nested dict grain
    with set_grains({"a": "aval"}):
        ret = grains.present(name="foo:is:nested", value={"bar": "is a dict"})
        assert ret["result"] is True
        assert ret["changes"] == {"foo": {"is": {"nested": {"bar": "is a dict"}}}}
        assert grains.__grains__ == {
            "a": "aval",
            "foo": {"is": {"nested": {"bar": "is a dict"}}},
        }
        assert_grain_file_content(
            "a: aval\nfoo:\n  is:\n    nested:\n      bar: is a dict\n"
        )


def test_present_add_key_to_existing():
    with set_grains({"a": "aval", "foo": {"k1": "v1"}}):
        # Fails setting a grain to a dict
        ret = grains.present(name="foo:k2", value="v2")
        assert ret["result"] is True
        assert ret["comment"] == "Set grain foo:k2 to v2"
        assert ret["changes"] == {"foo": {"k2": "v2", "k1": "v1"}}
        assert grains.__grains__ == {"a": "aval", "foo": {"k1": "v1", "k2": "v2"}}
        assert_grain_file_content("a: aval\nfoo:\n  k1: v1\n  k2: v2\n")


def test_present_already_set():
    with set_grains({"a": "aval", "foo": "bar"}):
        # Grain already set
        ret = grains.present(name="foo", value="bar")
        assert ret["result"] is True
        assert ret["comment"] == "Grain is already set"
        assert ret["changes"] == {}
        assert grains.__grains__ == {"a": "aval", "foo": "bar"}

    with set_grains({"a": "aval", "foo": {"is": {"nested": "bar"}}}):
        # Nested grain already set
        ret = grains.present(name="foo:is:nested", value="bar")
        assert ret["result"] is True
        assert ret["comment"] == "Grain is already set"
        assert ret["changes"] == {}
        assert grains.__grains__ == {"a": "aval", "foo": {"is": {"nested": "bar"}}}

    with set_grains({"a": "aval", "foo": {"is": {"nested": "bar"}}}):
        # Nested dict grain already set
        ret = grains.present(name="foo:is", value={"nested": "bar"})
        assert ret["result"] is True
        assert ret["comment"] == "Grain is already set"
        assert ret["changes"] == {}
        assert grains.__grains__ == {"a": "aval", "foo": {"is": {"nested": "bar"}}}


def test_present_overwrite():
    with set_grains({"a": "aval", "foo": "bar"}):
        # Overwrite an existing grain
        ret = grains.present(name="foo", value="newbar")
        assert ret["result"] is True
        assert ret["changes"] == {"foo": "newbar"}
        assert grains.__grains__ == {"a": "aval", "foo": "newbar"}
        assert_grain_file_content("a: aval\nfoo: newbar\n")

    with set_grains({"a": "aval", "foo": "bar"}):
        # Clear a grain (set to None)
        ret = grains.present(name="foo", value=None)
        assert ret["result"] is True
        assert ret["changes"] == {"foo": None}
        assert grains.__grains__ == {"a": "aval", "foo": None}
        assert_grain_file_content("a: aval\nfoo: null\n")

    with set_grains({"a": "aval", "foo": {"is": {"nested": "bar"}}}):
        # Overwrite an existing nested grain
        ret = grains.present(name="foo:is:nested", value="newbar")
        assert ret["result"] is True
        assert ret["changes"] == {"foo": {"is": {"nested": "newbar"}}}
        assert grains.__grains__ == {"a": "aval", "foo": {"is": {"nested": "newbar"}}}
        assert_grain_file_content("a: aval\nfoo:\n  is:\n    nested: newbar\n")

    with set_grains({"a": "aval", "foo": {"is": {"nested": "bar"}}}):
        # Clear a nested grain (set to None)
        ret = grains.present(name="foo:is:nested", value=None)
        assert ret["result"] is True
        assert ret["changes"] == {"foo": {"is": {"nested": None}}}
        assert grains.__grains__ == {"a": "aval", "foo": {"is": {"nested": None}}}
        assert_grain_file_content("a: aval\nfoo:\n  is:\n    nested: null\n")


def test_present_fail_overwrite():
    with set_grains({"a": "aval", "foo": {"is": {"nested": "val"}}}):
        # Overwrite an existing grain
        ret = grains.present(name="foo:is", value="newbar")
        assert ret["result"] is False
        assert ret["changes"] == {}
        assert (
            ret["comment"]
            == "The key 'foo:is' exists but is a dict or a list. Use 'force=True' to overwrite."
        )
        assert grains.__grains__ == {"a": "aval", "foo": {"is": {"nested": "val"}}}

    with set_grains({"a": "aval", "foo": {"is": {"nested": "val"}}}):
        # Clear a grain (set to None)
        ret = grains.present(name="foo:is", value=None)
        assert ret["result"] is False
        assert ret["changes"] == {}
        assert (
            ret["comment"]
            == "The key 'foo:is' exists but is a dict or a list. Use 'force=True' to overwrite."
        )
        assert grains.__grains__ == {"a": "aval", "foo": {"is": {"nested": "val"}}}


def test_present_fails_to_set_dict_or_list():
    with set_grains({"a": "aval", "foo": "bar"}):
        # Fails to overwrite a grain to a list
        ret = grains.present(name="foo", value=["l1", "l2"])
        assert ret["result"] is False
        assert (
            ret["comment"]
            == "The key 'foo' exists and the given value is a dict or a list. Use 'force=True' to overwrite."
        )
        assert ret["changes"] == {}
        assert grains.__grains__ == {"a": "aval", "foo": "bar"}

    with set_grains({"a": "aval", "foo": "bar"}):
        # Fails setting a grain to a dict
        ret = grains.present(name="foo", value={"k1": "v1"})
        assert ret["result"] is False
        assert (
            ret["comment"]
            == "The key 'foo' exists and the given value is a dict or a list. Use 'force=True' to overwrite."
        )
        assert ret["changes"] == {}
        assert grains.__grains__ == {"a": "aval", "foo": "bar"}

    with set_grains({"a": "aval", "foo": {"is": {"nested": "bar"}}}):
        # Fails to overwrite a nested grain to a list
        ret = grains.present(name="foo,is,nested", value=["l1", "l2"], delimiter=",")
        assert ret["result"] is False
        assert ret["changes"] == {}
        assert (
            ret["comment"]
            == "The key 'foo:is:nested' exists and the given value is a dict or a list. Use 'force=True' to overwrite."
        )
        assert grains.__grains__ == {"a": "aval", "foo": {"is": {"nested": "bar"}}}

    with set_grains({"a": "aval", "foo": {"is": {"nested": "bar"}}}):
        # Fails setting a nested grain to a dict
        ret = grains.present(name="foo:is:nested", value={"k1": "v1"})
        assert ret["result"] is False
        assert (
            ret["comment"]
            == "The key 'foo:is:nested' exists and the given value is a dict or a list. Use 'force=True' to overwrite."
        )
        assert ret["changes"] == {}
        assert grains.__grains__ == {"a": "aval", "foo": {"is": {"nested": "bar"}}}


def test_present_fail_merge_dict():
    with set_grains({"a": "aval", "foo": {"k1": "v1"}}):
        # Fails setting a grain to a dict
        ret = grains.present(name="foo", value={"k2": "v2"})
        assert ret["result"] is False
        assert (
            ret["comment"]
            == "The key 'foo' exists but is a dict or a list. Use 'force=True' to overwrite."
        )
        assert grains.__grains__ == {"a": "aval", "foo": {"k1": "v1"}}
        assert_grain_file_content("a: aval\nfoo:\n  k1: v1\n")


def test_present_force_to_set_dict_or_list():
    with set_grains({"a": "aval", "foo": "bar"}):
        # Force to overwrite a grain to a list
        ret = grains.present(name="foo", value=["l1", "l2"], force=True)
        assert ret["result"] is True
        assert ret["comment"] == "Set grain foo to ['l1', 'l2']"
        assert ret["changes"] == {"foo": ["l1", "l2"]}
        assert grains.__grains__ == {"a": "aval", "foo": ["l1", "l2"]}
        assert_grain_file_content("a: aval\nfoo:\n- l1\n- l2\n")

    with set_grains({"a": "aval", "foo": "bar"}):
        # Force setting a grain to a dict
        ret = grains.present(name="foo", value={"k1": "v1"}, force=True)
        assert ret["result"] is True
        assert ret["comment"] == "Set grain foo to {'k1': 'v1'}"
        assert ret["changes"] == {"foo": {"k1": "v1"}}
        assert grains.__grains__ == {"a": "aval", "foo": {"k1": "v1"}}
        assert_grain_file_content("a: aval\nfoo:\n  k1: v1\n")

    with set_grains({"a": "aval", "foo": {"is": {"nested": "bar"}}}):
        # Force to overwrite a nested grain to a list
        ret = grains.present(
            name="foo,is,nested", value=["l1", "l2"], delimiter=",", force=True
        )
        assert ret["result"] is True
        assert ret["changes"] == {"foo": {"is": {"nested": ["l1", "l2"]}}}
        assert ret["comment"] == "Set grain foo:is:nested to ['l1', 'l2']"
        assert grains.__grains__ == {
            "a": "aval",
            "foo": {"is": {"nested": ["l1", "l2"]}},
        }
        assert_grain_file_content(
            "a: aval\nfoo:\n  is:\n    nested:\n    - l1\n    - l2\n"
        )

    with set_grains({"a": "aval", "foo": {"is": {"nested": "bar"}, "and": "other"}}):
        # Force setting a nested grain to a dict
        ret = grains.present(name="foo:is:nested", value={"k1": "v1"}, force=True)
        assert ret["result"] is True
        assert ret["comment"] == "Set grain foo:is:nested to {'k1': 'v1'}"
        assert ret["changes"] == {
            "foo": {"is": {"nested": {"k1": "v1"}}, "and": "other"}
        }
        assert grains.__grains__ == {
            "a": "aval",
            "foo": {"is": {"nested": {"k1": "v1"}}, "and": "other"},
        }
        assert_grain_file_content(
            "a: aval\nfoo:\n  and: other\n  is:\n    nested:\n      k1: v1\n"
        )


def test_present_fails_to_convert_value_to_key():
    with set_grains({"a": "aval", "foo": "bar"}):
        # Fails converting a value to a nested grain key
        ret = grains.present(name="foo:is:nested", value={"k1": "v1"})
        assert ret["result"] is False
        assert (
            ret["comment"]
            == "The key 'foo' value is 'bar', which is different from the provided key 'is'. Use 'force=True' to overwrite."
        )
        assert ret["changes"] == {}


def test_present_overwrite_test():
    with patch.dict(grains.__opts__, {"test": True}):
        with set_grains({"a": "aval", "foo": "bar"}):
            # Overwrite an existing grain
            ret = grains.present(name="foo", value="newbar")
            assert ret["result"] is None
            assert ret["changes"] == {"changed": {"foo": "newbar"}}
            assert grains.__grains__ == {"a": "aval", "foo": "bar"}
            assert_grain_file_content("a: aval\nfoo: bar\n")


def test_present_convert_value_to_key():
    with set_grains({"a": "aval", "foo": "is"}):
        # Converts a value to a nested grain key
        ret = grains.present(name="foo:is:nested", value={"k1": "v1"})
        assert ret["result"] is True
        assert ret["comment"] == "Set grain foo:is:nested to {'k1': 'v1'}"
        assert ret["changes"] == {"foo": {"is": {"nested": {"k1": "v1"}}}}
        assert grains.__grains__ == {
            "a": "aval",
            "foo": {"is": {"nested": {"k1": "v1"}}},
        }
        assert_grain_file_content("a: aval\nfoo:\n  is:\n    nested:\n      k1: v1\n")

    with set_grains({"a": "aval", "foo": ["one", "is", "correct"]}):
        # Converts a list element to a nested grain key
        ret = grains.present(name="foo:is:nested", value={"k1": "v1"})
        assert ret["result"] is True
        assert ret["comment"] == "Set grain foo:is:nested to {'k1': 'v1'}"
        assert ret["changes"] == {
            "foo": ["one", {"is": {"nested": {"k1": "v1"}}}, "correct"]
        }
        assert grains.__grains__ == {
            "a": "aval",
            "foo": ["one", {"is": {"nested": {"k1": "v1"}}}, "correct"],
        }
        assert_grain_file_content(
            "a: aval\nfoo:\n- one\n- is:\n    nested:\n      k1: v1\n- correct\n"
        )


def test_present_unknown_failure():
    with patch("salt.modules.grains.setval") as mocked_setval:
        mocked_setval.return_value = "Failed to set grain foo"
        with set_grains({"a": "aval", "foo": "bar"}):
            # Unknown reason failure
            ret = grains.present(name="foo", value="baz")
            assert ret["result"] is False
            assert ret["comment"] == "Failed to set grain foo"
            assert ret["changes"] == {}
            assert grains.__grains__ == {"a": "aval", "foo": "bar"}
            assert_grain_file_content("a: aval\nfoo: bar\n")


# 'absent' function tests: 6


def test_absent_already():
    # Unset a non existent grain
    with set_grains({"a": "aval"}):
        ret = grains.absent(name="foo")
        assert ret["result"] is True
        assert ret["comment"] == "Grain foo does not exist"
        assert ret["changes"] == {}
        assert grains.__grains__ == {"a": "aval"}
        assert_grain_file_content("a: aval\n")

    # Unset a non existent nested grain
    with set_grains({"a": "aval"}):
        ret = grains.absent(name="foo:is:nested")
        assert ret["result"] is True
        assert ret["comment"] == "Grain foo:is:nested does not exist"
        assert ret["changes"] == {}
        assert grains.__grains__ == {"a": "aval"}
        assert_grain_file_content("a: aval\n")


def test_absent_unset():
    # Unset a grain
    with set_grains({"a": "aval", "foo": "bar"}):
        ret = grains.absent(name="foo")
        assert ret["result"] is True
        assert ret["comment"] == "Value for grain foo was set to None"
        assert ret["changes"] == {"grain": "foo", "value": None}
        assert grains.__grains__ == {"a": "aval", "foo": None}
        assert_grain_file_content("a: aval\nfoo: null\n")

    # Unset grain when its value is False
    with set_grains({"a": "aval", "foo": False}):
        ret = grains.absent(name="foo")
        assert ret["result"] is True
        assert ret["comment"] == "Value for grain foo was set to None"
        assert ret["changes"] == {"grain": "foo", "value": None}
        assert grains.__grains__ == {"a": "aval", "foo": None}
        assert_grain_file_content("a: aval\nfoo: null\n")

    # Unset a nested grain
    with set_grains(
        {"a": "aval", "foo": ["order", {"is": {"nested": "bar"}}, "correct"]}
    ):
        ret = grains.absent(name="foo,is,nested", delimiter=",")
        assert ret["result"] is True
        assert ret["comment"] == "Value for grain foo:is:nested was set to None"
        assert ret["changes"] == {"grain": "foo:is:nested", "value": None}
        assert grains.__grains__ == {
            "a": "aval",
            "foo": ["order", {"is": {"nested": None}}, "correct"],
        }
        assert_grain_file_content(
            "a: aval\nfoo:\n- order\n- is:\n    nested: null\n- correct\n"
        )

    # Unset a nested value don't change anything
    with set_grains({"a": "aval", "foo": ["order", {"is": "nested"}, "correct"]}):
        ret = grains.absent(name="foo:is:nested")
        assert ret["result"] is True
        assert ret["comment"] == "Grain foo:is:nested does not exist"
        assert ret["changes"] == {}
        assert grains.__grains__ == {
            "a": "aval",
            "foo": ["order", {"is": "nested"}, "correct"],
        }
        assert_grain_file_content("a: aval\nfoo:\n- order\n- is: nested\n- correct\n")


def test_absent_unset_test():
    with patch.dict(grains.__opts__, {"test": True}):
        with set_grains({"a": "aval", "foo": "bar"}):
            # Overwrite an existing grain
            ret = grains.absent(name="foo")
            assert ret["result"] is None
            assert ret["changes"] == {"grain": "foo", "value": None}
            assert grains.__grains__ == {"a": "aval", "foo": "bar"}
            assert_grain_file_content("a: aval\nfoo: bar\n")


def test_absent_fails_nested_complex_grain():
    # Unset a nested complex grain
    with set_grains(
        {"a": "aval", "foo": ["order", {"is": {"nested": "bar"}}, "correct"]}
    ):
        ret = grains.absent(name="foo:is")
        assert ret["result"] is False
        assert (
            ret["comment"]
            == "The key 'foo:is' exists but is a dict or a list. Use 'force=True' to overwrite."
        )
        assert ret["changes"] == {}
        assert grains.__grains__ == {
            "a": "aval",
            "foo": ["order", {"is": {"nested": "bar"}}, "correct"],
        }
        assert_grain_file_content(
            "a: aval\nfoo:\n- order\n- is:\n    nested: bar\n- correct\n"
        )


def test_absent_force_nested_complex_grain():
    # Unset a nested complex grain
    with set_grains(
        {"a": "aval", "foo": ["order", {"is": {"nested": "bar"}}, "correct"]}
    ):
        ret = grains.absent(name="foo:is", force=True)
        assert ret["result"] is True
        assert ret["comment"] == "Value for grain foo:is was set to None"
        assert ret["changes"] == {"grain": "foo:is", "value": None}
        assert grains.__grains__ == {
            "a": "aval",
            "foo": ["order", {"is": None}, "correct"],
        }
        assert_grain_file_content("a: aval\nfoo:\n- order\n- is: null\n- correct\n")


def test_absent_delete():
    # Delete a grain
    with set_grains({"a": "aval", "foo": "bar"}):
        ret = grains.absent(name="foo", destructive=True)
        assert ret["result"] is True
        assert ret["comment"] == "Grain foo was deleted"
        assert ret["changes"] == {"deleted": "foo"}
        assert grains.__grains__ == {"a": "aval"}
        assert_grain_file_content("a: aval\n")

    # Delete a previously unset grain
    with set_grains({"a": "aval", "foo": None}):
        ret = grains.absent(name="foo", destructive=True)
        assert ret["result"] is True
        assert ret["comment"] == "Grain foo was deleted"
        assert ret["changes"] == {"deleted": "foo"}
        assert grains.__grains__ == {"a": "aval"}
        assert_grain_file_content("a: aval\n")

    # Delete a nested grain
    with set_grains(
        {
            "a": "aval",
            "foo": [
                "order",
                {"is": {"nested": "bar", "other": "value"}},
                "correct",
            ],
        }
    ):
        ret = grains.absent(name="foo:is:nested", destructive=True)
        assert ret["result"] is True
        assert ret["comment"] == "Grain foo:is:nested was deleted"
        assert ret["changes"] == {"deleted": "foo:is:nested"}
        assert grains.__grains__ == {
            "a": "aval",
            "foo": ["order", {"is": {"other": "value"}}, "correct"],
        }
        assert_grain_file_content(
            "a: aval\nfoo:\n- order\n- is:\n    other: value\n- correct\n"
        )


# 'append' function tests: 6


def test_append():
    # Append to an existing list
    with set_grains({"a": "aval", "foo": ["bar"]}):
        ret = grains.append(name="foo", value="baz")
        assert ret["result"] is True
        assert ret["comment"] == "Value baz was added to grain foo"
        assert ret["changes"] == {"added": "baz"}
        assert grains.__grains__ == {"a": "aval", "foo": ["bar", "baz"]}
        assert_grain_file_content("a: aval\nfoo:\n- bar\n- baz\n")


def test_append_nested():
    # Append to an existing nested list
    with set_grains({"a": "aval", "foo": {"list": ["bar"]}}):
        ret = grains.append(name="foo,list", value="baz", delimiter=",")
        assert ret["result"] is True
        assert ret["comment"] == "Value baz was added to grain foo:list"
        assert ret["changes"] == {"added": "baz"}
        assert grains.__grains__ == {"a": "aval", "foo": {"list": ["bar", "baz"]}}
        assert_grain_file_content("a: aval\nfoo:\n  list:\n  - bar\n  - baz\n")


def test_append_already():
    # Append to an existing list
    with set_grains({"a": "aval", "foo": ["bar"]}):
        ret = grains.append(name="foo", value="bar")
        assert ret["result"] is True
        assert ret["comment"] == "Value bar is already in the list " + "for grain foo"
        assert ret["changes"] == {}
        assert grains.__grains__ == {"a": "aval", "foo": ["bar"]}
        assert_grain_file_content("a: aval\nfoo:\n- bar\n")


def test_append_fails_not_a_list():
    # Fail to append to an existing grain, not a list
    with set_grains({"a": "aval", "foo": {"bar": "val"}}):
        ret = grains.append(name="foo", value="baz")
        assert ret["result"] is False
        assert ret["comment"] == "Grain foo is not a valid list"
        assert ret["changes"] == {}
        assert grains.__grains__ == {"a": "aval", "foo": {"bar": "val"}}


def test_append_convert_to_list():
    # Append to an existing grain, converting to a list
    with set_grains({"a": "aval", "foo": {"bar": "val"}}):
        assert_grain_file_content("a: aval\nfoo:\n  bar: val\n")
        ret = grains.append(name="foo", value="baz", convert=True)
        assert ret["result"] is True
        assert ret["comment"] == "Value baz was added to grain foo"
        assert ret["changes"] == {"added": "baz"}
        assert grains.__grains__ == {"a": "aval", "foo": [{"bar": "val"}, "baz"]}
        assert_grain_file_content("a: aval\nfoo:\n- bar: val\n- baz\n")

    # Append to an existing grain, converting to a list a multi-value dict
    with set_grains({"a": "aval", "foo": {"bar": "val", "other": "value"}}):
        assert_grain_file_content("a: aval\nfoo:\n  bar: val\n  other: value\n")
        ret = grains.append(name="foo", value="baz", convert=True)
        assert ret["result"] is True
        assert ret["comment"] == "Value baz was added to grain foo"
        assert ret["changes"] == {"added": "baz"}
        assert grains.__grains__ == {
            "a": "aval",
            "foo": [{"bar": "val", "other": "value"}, "baz"],
        }
        assert_grain_file_content("a: aval\nfoo:\n- bar: val\n  other: value\n- baz\n")


def test_append_fails_inexistent():
    # Append to a non existing grain
    with set_grains({"a": "aval"}):
        ret = grains.append(name="foo", value="bar")
        assert ret["result"] is False
        assert ret["comment"] == "Grain foo does not exist"
        assert ret["changes"] == {}
        assert grains.__grains__ == {"a": "aval"}


def test_append_convert_to_list_empty():
    # Append to an existing list
    with set_grains({"foo": None}):
        ret = grains.append(name="foo", value="baz", convert=True)
        assert ret["result"] is True
        assert ret["comment"] == "Value baz was added to grain foo"
        assert ret["changes"] == {"added": "baz"}
        assert grains.__grains__ == {"foo": ["baz"]}
        assert_grain_file_content("foo:\n- baz\n")


# 'list_present' function tests: 7


def test_list_present():
    with set_grains({"a": "aval", "foo": ["bar"]}):
        ret = grains.list_present(name="foo", value="baz")
        assert ret["result"] is True
        assert ret["comment"] == "Append value baz to grain foo"
        assert ret["changes"] == {"new": {"foo": ["bar", "baz"]}}
        assert grains.__grains__ == {"a": "aval", "foo": ["bar", "baz"]}
        assert_grain_file_content("a: aval\nfoo:\n- bar\n- baz\n")


def test_list_present_nested():
    with set_grains({"a": "aval", "foo": {"is": {"nested": ["bar"]}}}):
        ret = grains.list_present(name="foo,is,nested", value="baz", delimiter=",")
        assert ret["result"] is True
        assert ret["comment"] == "Append value baz to grain foo:is:nested"
        assert ret["changes"] == {"new": {"foo": {"is": {"nested": ["bar", "baz"]}}}}
        assert grains.__grains__ == {
            "a": "aval",
            "foo": {"is": {"nested": ["bar", "baz"]}},
        }
        assert_grain_file_content(
            "a: aval\nfoo:\n  is:\n    nested:\n    - bar\n    - baz\n"
        )


def test_list_present_inexistent():
    with set_grains({"a": "aval"}):
        ret = grains.list_present(name="foo", value="baz")
        assert ret["result"] is True
        assert ret["comment"] == "Append value baz to grain foo"
        assert ret["changes"] == {"new": {"foo": ["baz"]}}
        assert grains.__grains__ == {"a": "aval", "foo": ["baz"]}
        assert_grain_file_content("a: aval\nfoo:\n- baz\n")


def test_list_present_inexistent_nested():
    with set_grains({"a": "aval"}):
        ret = grains.list_present(name="foo:is:nested", value="baz")
        assert ret["result"] is True
        assert ret["comment"] == "Append value baz to grain foo:is:nested"
        assert ret["changes"] == {"new": {"foo": {"is": {"nested": ["baz"]}}}}
        assert grains.__grains__ == {"a": "aval", "foo": {"is": {"nested": ["baz"]}}}
        assert_grain_file_content("a: aval\nfoo:\n  is:\n    nested:\n    - baz\n")


def test_list_present_not_a_list():
    with set_grains({"a": "aval", "foo": "bar"}):
        ret = grains.list_present(name="foo", value="baz")
        assert ret["result"] is False
        assert ret["comment"] == "Grain foo is not a valid list"
        assert ret["changes"] == {}
        assert grains.__grains__ == {"a": "aval", "foo": "bar"}
        assert_grain_file_content("a: aval\nfoo: bar\n")


def test_list_present_nested_already():
    with set_grains({"a": "aval", "b": {"foo": ["bar"]}}):
        ret = grains.list_present(name="b:foo", value="bar")
        assert ret["result"] is True
        assert ret["comment"] == "Value bar is already in grain b:foo"
        assert ret["changes"] == {}
        assert grains.__grains__ == {"a": "aval", "b": {"foo": ["bar"]}}
        assert_grain_file_content("a: aval\nb:\n  foo:\n  - bar\n")


def test_list_present_already():
    with set_grains({"a": "aval", "foo": ["bar"]}):
        ret = grains.list_present(name="foo", value="bar")
        assert ret["result"] is True
        assert ret["comment"] == "Value bar is already in grain foo"
        assert ret["changes"] == {}
        assert grains.__grains__ == {"a": "aval", "foo": ["bar"]}
        assert_grain_file_content("a: aval\nfoo:\n- bar\n")


def test_list_present_unknown_failure():
    with set_grains({"a": "aval", "foo": ["bar"]}):
        # Unknown reason failure

        with patch.dict(grainsmod.__salt__, {"grains.append": MagicMock()}):
            ret = grains.list_present(name="foo", value="baz")
            assert ret["result"] is False
            assert ret["comment"] == "Failed append value baz to grain foo"
            assert ret["changes"] == {}
            assert grains.__grains__ == {"a": "aval", "foo": ["bar"]}
            assert_grain_file_content("a: aval\nfoo:\n- bar\n")


# 'list_absent' function tests: 6


def test_list_absent():
    with set_grains({"a": "aval", "foo": ["bar"]}):
        ret = grains.list_absent(name="foo", value="bar")
        assert ret["result"] is True
        assert ret["comment"] == "Value bar was deleted from grain foo"
        assert ret["changes"] == {"deleted": ["bar"]}
        assert grains.__grains__ == {"a": "aval", "foo": []}
        assert_grain_file_content("a: aval\nfoo: []\n")


def test_list_absent_nested():
    with set_grains({"a": "aval", "foo": {"list": ["bar"]}}):
        ret = grains.list_absent(name="foo:list", value="bar")
        assert ret["result"] is True
        assert ret["comment"] == "Value bar was deleted from grain foo:list"
        assert ret["changes"] == {"deleted": ["bar"]}
        assert grains.__grains__ == {"a": "aval", "foo": {"list": []}}
        assert_grain_file_content("a: aval\nfoo:\n  list: []\n")


def test_list_absent_inexistent():
    with set_grains({"a": "aval"}):
        ret = grains.list_absent(name="foo", value="baz")
        assert ret["result"] is True
        assert ret["comment"] == "Grain foo does not exist"
        assert ret["changes"] == {}
        assert grains.__grains__ == {"a": "aval"}
        assert_grain_file_content("a: aval\n")


def test_list_absent_inexistent_nested():
    with set_grains({"a": "aval"}):
        ret = grains.list_absent(name="foo:list", value="baz")
        assert ret["result"] is True
        assert ret["comment"] == "Grain foo:list does not exist"
        assert ret["changes"] == {}
        assert grains.__grains__ == {"a": "aval"}
        assert_grain_file_content("a: aval\n")


def test_list_absent_not_a_list():
    with set_grains({"a": "aval", "foo": "bar"}):
        ret = grains.list_absent(name="foo", value="bar")
        assert ret["result"] is False
        assert ret["comment"] == "Grain foo is not a valid list"
        assert ret["changes"] == {}
        assert grains.__grains__ == {"a": "aval", "foo": "bar"}
        assert_grain_file_content("a: aval\nfoo: bar\n")


def test_list_absent_already():
    with set_grains({"a": "aval", "foo": ["bar"]}):
        ret = grains.list_absent(name="foo", value="baz")
        assert ret["result"] is True
        assert ret["comment"] == "Value baz is absent from grain foo"
        assert ret["changes"] == {}
        assert grains.__grains__ == {"a": "aval", "foo": ["bar"]}
        assert_grain_file_content("a: aval\nfoo:\n- bar\n")
