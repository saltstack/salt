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
from tests.support.paths import SALT_CODE_DIR


@pytest.fixture
def configure_loader_modules():
    grains_test_dir = "__salt_test_state_grains"
    if not os.path.exists(os.path.join(SALT_CODE_DIR, grains_test_dir)):
        os.makedirs(os.path.join(SALT_CODE_DIR, grains_test_dir))
    loader_globals = {
        "__opts__": {
            "test": False,
            "conf_file": os.path.join(SALT_CODE_DIR, grains_test_dir, "minion"),
            "cachedir": os.path.join(SALT_CODE_DIR, grains_test_dir),
            "local": True,
        },
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


def assertGrainFileContent(grains_string):
    if os.path.isdir(grains.__opts__["conf_file"]):
        grains_file = os.path.join(grains.__opts__["conf_file"], "grains")
    else:
        grains_file = os.path.join(
            os.path.dirname(grains.__opts__["conf_file"]), "grains"
        )
    with salt.utils.files.fopen(grains_file, "r") as grf:
        grains_data = salt.utils.stringutils.to_unicode(grf.read())
    assert grains_string == grains_data


@contextlib.contextmanager
def setGrains(grains_data):
    with patch.dict(grains.__grains__, grains_data):
        with patch.dict(grainsmod.__grains__, grains_data):
            if os.path.isdir(grains.__opts__["conf_file"]):
                grains_file = os.path.join(grains.__opts__["conf_file"], "grains")
            else:
                grains_file = os.path.join(
                    os.path.dirname(grains.__opts__["conf_file"]), "grains"
                )
            with salt.utils.files.fopen(grains_file, "w+") as grf:
                salt.utils.yaml.safe_dump(grains_data, grf, default_flow_style=False)
            yield


# 'exists' function tests: 2


def test_exists_missing():
    with setGrains({"a": "aval"}):
        ret = grains.exists(name="foo")
        assert ret["result"] is False
        assert ret["comment"] == "Grain does not exist"
        assert ret["changes"] == {}


def test_exists_found():
    with setGrains({"a": "aval", "foo": "bar"}):
        # Grain already set
        ret = grains.exists(name="foo")
        assert ret["result"] is True
        assert ret["comment"] == "Grain exists"
        assert ret["changes"] == {}

    # 'make_hashable' function tests: 1


def test_make_hashable():
    with setGrains({"cmplx_lst_grain": [{"a": "aval"}, {"foo": "bar"}]}):
        hashable_list = {"cmplx_lst_grain": [{"a": "aval"}, {"foo": "bar"}]}
        assert (
            grains.make_hashable(grains.__grains__).issubset(
                grains.make_hashable(hashable_list)
            )
            is True
        )

    # 'present' function tests: 12


def test_present_add():
    # Set a non existing grain
    with setGrains({"a": "aval"}):
        ret = grains.present(name="foo", value="bar")
        assert ret["result"] is True
        assert ret["changes"] == {"foo": "bar"}
        assert grains.__grains__ == {"a": "aval", "foo": "bar"}
        assertGrainFileContent("a: aval\nfoo: bar\n")

    # Set a non existing nested grain
    with setGrains({"a": "aval"}):
        ret = grains.present(name="foo:is:nested", value="bar")
        assert ret["result"] is True
        assert ret["changes"] == {"foo": {"is": {"nested": "bar"}}}
        assert grains.__grains__ == {"a": "aval", "foo": {"is": {"nested": "bar"}}}
        assertGrainFileContent("a: aval\nfoo:\n  is:\n    nested: bar\n")

    # Set a non existing nested dict grain
    with setGrains({"a": "aval"}):
        ret = grains.present(name="foo:is:nested", value={"bar": "is a dict"})
        assert ret["result"] is True
        assert ret["changes"] == {"foo": {"is": {"nested": {"bar": "is a dict"}}}}
        assert grains.__grains__ == {
            "a": "aval",
            "foo": {"is": {"nested": {"bar": "is a dict"}}},
        }
        assertGrainFileContent(
            "a: aval\n"
            + "foo:\n"
            + "  is:\n"
            + "    nested:\n"
            + "      bar: is a dict\n"
        )


def test_present_add_key_to_existing():
    with setGrains({"a": "aval", "foo": {"k1": "v1"}}):
        # Fails setting a grain to a dict
        ret = grains.present(name="foo:k2", value="v2")
        assert ret["result"] is True
        assert ret["comment"] == "Set grain foo:k2 to v2"
        assert ret["changes"] == {"foo": {"k2": "v2", "k1": "v1"}}
        assert grains.__grains__ == {"a": "aval", "foo": {"k1": "v1", "k2": "v2"}}
        assertGrainFileContent("a: aval\n" + "foo:\n" + "  k1: v1\n" + "  k2: v2\n")


def test_present_already_set():
    with setGrains({"a": "aval", "foo": "bar"}):
        # Grain already set
        ret = grains.present(name="foo", value="bar")
        assert ret["result"] is True
        assert ret["comment"] == "Grain is already set"
        assert ret["changes"] == {}
        assert grains.__grains__ == {"a": "aval", "foo": "bar"}

    with setGrains({"a": "aval", "foo": {"is": {"nested": "bar"}}}):
        # Nested grain already set
        ret = grains.present(name="foo:is:nested", value="bar")
        assert ret["result"] is True
        assert ret["comment"] == "Grain is already set"
        assert ret["changes"] == {}
        assert grains.__grains__ == {"a": "aval", "foo": {"is": {"nested": "bar"}}}

    with setGrains({"a": "aval", "foo": {"is": {"nested": "bar"}}}):
        # Nested dict grain already set
        ret = grains.present(name="foo:is", value={"nested": "bar"})
        assert ret["result"] is True
        assert ret["comment"] == "Grain is already set"
        assert ret["changes"] == {}
        assert grains.__grains__ == {"a": "aval", "foo": {"is": {"nested": "bar"}}}


def test_present_overwrite():
    with setGrains({"a": "aval", "foo": "bar"}):
        # Overwrite an existing grain
        ret = grains.present(name="foo", value="newbar")
        assert ret["result"] is True
        assert ret["changes"] == {"foo": "newbar"}
        assert grains.__grains__ == {"a": "aval", "foo": "newbar"}
        assertGrainFileContent("a: aval\n" + "foo: newbar\n")

    with setGrains({"a": "aval", "foo": "bar"}):
        # Clear a grain (set to None)
        ret = grains.present(name="foo", value=None)
        assert ret["result"] is True
        assert ret["changes"] == {"foo": None}
        assert grains.__grains__ == {"a": "aval", "foo": None}
        assertGrainFileContent("a: aval\n" + "foo: null\n")

    with setGrains({"a": "aval", "foo": {"is": {"nested": "bar"}}}):
        # Overwrite an existing nested grain
        ret = grains.present(name="foo:is:nested", value="newbar")
        assert ret["result"] is True
        assert ret["changes"] == {"foo": {"is": {"nested": "newbar"}}}
        assert grains.__grains__ == {"a": "aval", "foo": {"is": {"nested": "newbar"}}}
        assertGrainFileContent(
            "a: aval\n" + "foo:\n" + "  is:\n" + "    nested: newbar\n"
        )

    with setGrains({"a": "aval", "foo": {"is": {"nested": "bar"}}}):
        # Clear a nested grain (set to None)
        ret = grains.present(name="foo:is:nested", value=None)
        assert ret["result"] is True
        assert ret["changes"] == {"foo": {"is": {"nested": None}}}
        assert grains.__grains__ == {"a": "aval", "foo": {"is": {"nested": None}}}
        assertGrainFileContent(
            "a: aval\n" + "foo:\n" + "  is:\n" + "    nested: null\n"
        )


def test_present_fail_overwrite():
    with setGrains({"a": "aval", "foo": {"is": {"nested": "val"}}}):
        # Overwrite an existing grain
        ret = grains.present(name="foo:is", value="newbar")
        assert ret["result"] is False
        assert ret["changes"] == {}
        assert (
            ret["comment"]
            == "The key 'foo:is' exists but is a dict or a list. Use 'force=True' to overwrite."
        )
        assert grains.__grains__ == {"a": "aval", "foo": {"is": {"nested": "val"}}}

    with setGrains({"a": "aval", "foo": {"is": {"nested": "val"}}}):
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
    with setGrains({"a": "aval", "foo": "bar"}):
        # Fails to overwrite a grain to a list
        ret = grains.present(name="foo", value=["l1", "l2"])
        assert ret["result"] is False
        assert (
            ret["comment"]
            == "The key 'foo' exists and the given value is a dict or a list. Use 'force=True' to overwrite."
        )
        assert ret["changes"] == {}
        assert grains.__grains__ == {"a": "aval", "foo": "bar"}

    with setGrains({"a": "aval", "foo": "bar"}):
        # Fails setting a grain to a dict
        ret = grains.present(name="foo", value={"k1": "v1"})
        assert ret["result"] is False
        assert (
            ret["comment"]
            == "The key 'foo' exists and the given value is a dict or a list. Use 'force=True' to overwrite."
        )
        assert ret["changes"] == {}
        assert grains.__grains__ == {"a": "aval", "foo": "bar"}

    with setGrains({"a": "aval", "foo": {"is": {"nested": "bar"}}}):
        # Fails to overwrite a nested grain to a list
        ret = grains.present(name="foo,is,nested", value=["l1", "l2"], delimiter=",")
        assert ret["result"] is False
        assert ret["changes"] == {}
        assert (
            ret["comment"]
            == "The key 'foo:is:nested' exists and the given value is a dict or a list. Use 'force=True' to overwrite."
        )
        assert grains.__grains__ == {"a": "aval", "foo": {"is": {"nested": "bar"}}}

    with setGrains({"a": "aval", "foo": {"is": {"nested": "bar"}}}):
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
    with setGrains({"a": "aval", "foo": {"k1": "v1"}}):
        # Fails setting a grain to a dict
        ret = grains.present(name="foo", value={"k2": "v2"})
        assert ret["result"] is False
        assert (
            ret["comment"]
            == "The key 'foo' exists but is a dict or a list. Use 'force=True' to overwrite."
        )
        assert grains.__grains__ == {"a": "aval", "foo": {"k1": "v1"}}
        assertGrainFileContent("a: aval\n" + "foo:\n" + "  k1: v1\n")


def test_present_force_to_set_dict_or_list():
    with setGrains({"a": "aval", "foo": "bar"}):
        # Force to overwrite a grain to a list
        ret = grains.present(name="foo", value=["l1", "l2"], force=True)
        assert ret["result"] is True
        assert ret["comment"] == "Set grain foo to ['l1', 'l2']"
        assert ret["changes"] == {"foo": ["l1", "l2"]}
        assert grains.__grains__ == {"a": "aval", "foo": ["l1", "l2"]}
        assertGrainFileContent("a: aval\n" + "foo:\n" + "- l1\n" + "- l2\n")

    with setGrains({"a": "aval", "foo": "bar"}):
        # Force setting a grain to a dict
        ret = grains.present(name="foo", value={"k1": "v1"}, force=True)
        assert ret["result"] is True
        assert ret["comment"] == "Set grain foo to {'k1': 'v1'}"
        assert ret["changes"] == {"foo": {"k1": "v1"}}
        assert grains.__grains__ == {"a": "aval", "foo": {"k1": "v1"}}
        assertGrainFileContent("a: aval\n" + "foo:\n" + "  k1: v1\n")

    with setGrains({"a": "aval", "foo": {"is": {"nested": "bar"}}}):
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
        assertGrainFileContent(
            "a: aval\n"
            + "foo:\n"
            + "  is:\n"
            + "    nested:\n"
            + "    - l1\n"
            + "    - l2\n"
        )

    with setGrains({"a": "aval", "foo": {"is": {"nested": "bar"}, "and": "other"}}):
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
        assertGrainFileContent(
            "a: aval\n"
            + "foo:\n"
            + "  and: other\n"
            + "  is:\n"
            + "    nested:\n"
            + "      k1: v1\n"
        )


def test_present_fails_to_convert_value_to_key():
    with setGrains({"a": "aval", "foo": "bar"}):
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
        with setGrains({"a": "aval", "foo": "bar"}):
            # Overwrite an existing grain
            ret = grains.present(name="foo", value="newbar")
            assert ret["result"] is None
            assert ret["changes"] == {"changed": {"foo": "newbar"}}
            assert grains.__grains__ == {"a": "aval", "foo": "bar"}
            assertGrainFileContent("a: aval\n" + "foo: bar\n")


def test_present_convert_value_to_key():
    with setGrains({"a": "aval", "foo": "is"}):
        # Converts a value to a nested grain key
        ret = grains.present(name="foo:is:nested", value={"k1": "v1"})
        assert ret["result"] is True
        assert ret["comment"] == "Set grain foo:is:nested to {'k1': 'v1'}"
        assert ret["changes"] == {"foo": {"is": {"nested": {"k1": "v1"}}}}
        assert grains.__grains__ == {
            "a": "aval",
            "foo": {"is": {"nested": {"k1": "v1"}}},
        }
        assertGrainFileContent(
            "a: aval\n" + "foo:\n" + "  is:\n" + "    nested:\n" + "      k1: v1\n"
        )

    with setGrains({"a": "aval", "foo": ["one", "is", "correct"]}):
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
        assertGrainFileContent(
            "a: aval\n"
            + "foo:\n"
            + "- one\n"
            + "- is:\n"
            + "    nested:\n"
            + "      k1: v1\n"
            + "- correct\n"
        )


def test_present_unknown_failure():
    with patch("salt.modules.grains.setval") as mocked_setval:
        mocked_setval.return_value = "Failed to set grain foo"
        with setGrains({"a": "aval", "foo": "bar"}):
            # Unknown reason failure
            ret = grains.present(name="foo", value="baz")
            assert ret["result"] is False
            assert ret["comment"] == "Failed to set grain foo"
            assert ret["changes"] == {}
            assert grains.__grains__ == {"a": "aval", "foo": "bar"}
            assertGrainFileContent("a: aval\n" + "foo: bar\n")


# 'absent' function tests: 6


def test_absent_already():
    # Unset a non existent grain
    with setGrains({"a": "aval"}):
        ret = grains.absent(name="foo")
        assert ret["result"] is True
        assert ret["comment"] == "Grain foo does not exist"
        assert ret["changes"] == {}
        assert grains.__grains__ == {"a": "aval"}
        assertGrainFileContent("a: aval\n")

    # Unset a non existent nested grain
    with setGrains({"a": "aval"}):
        ret = grains.absent(name="foo:is:nested")
        assert ret["result"] is True
        assert ret["comment"] == "Grain foo:is:nested does not exist"
        assert ret["changes"] == {}
        assert grains.__grains__ == {"a": "aval"}
        assertGrainFileContent("a: aval\n")


def test_absent_unset():
    # Unset a grain
    with setGrains({"a": "aval", "foo": "bar"}):
        ret = grains.absent(name="foo")
        assert ret["result"] is True
        assert ret["comment"] == "Value for grain foo was set to None"
        assert ret["changes"] == {"grain": "foo", "value": None}
        assert grains.__grains__ == {"a": "aval", "foo": None}
        assertGrainFileContent("a: aval\n" + "foo: null\n")

    # Unset grain when its value is False
    with setGrains({"a": "aval", "foo": False}):
        ret = grains.absent(name="foo")
        assert ret["result"] is True
        assert ret["comment"] == "Value for grain foo was set to None"
        assert ret["changes"] == {"grain": "foo", "value": None}
        assert grains.__grains__ == {"a": "aval", "foo": None}
        assertGrainFileContent("a: aval\n" + "foo: null\n")

    # Unset a nested grain
    with setGrains(
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
        assertGrainFileContent(
            "a: aval\n"
            + "foo:\n"
            + "- order\n"
            + "- is:\n"
            + "    nested: null\n"
            + "- correct\n"
        )

    # Unset a nested value don't change anything
    with setGrains({"a": "aval", "foo": ["order", {"is": "nested"}, "correct"]}):
        ret = grains.absent(name="foo:is:nested")
        assert ret["result"] is True
        assert ret["comment"] == "Grain foo:is:nested does not exist"
        assert ret["changes"] == {}
        assert grains.__grains__ == {
            "a": "aval",
            "foo": ["order", {"is": "nested"}, "correct"],
        }
        assertGrainFileContent(
            "a: aval\n" + "foo:\n" + "- order\n" + "- is: nested\n" + "- correct\n"
        )


def test_absent_unset_test():
    with patch.dict(grains.__opts__, {"test": True}):
        with setGrains({"a": "aval", "foo": "bar"}):
            # Overwrite an existing grain
            ret = grains.absent(name="foo")
            assert ret["result"] is None
            assert ret["changes"] == {"grain": "foo", "value": None}
            assert grains.__grains__ == {"a": "aval", "foo": "bar"}
            assertGrainFileContent("a: aval\n" + "foo: bar\n")


def test_absent_fails_nested_complex_grain():
    # Unset a nested complex grain
    with setGrains(
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
        assertGrainFileContent(
            "a: aval\n"
            + "foo:\n"
            + "- order\n"
            + "- is:\n"
            + "    nested: bar\n"
            + "- correct\n"
        )


def test_absent_force_nested_complex_grain():
    # Unset a nested complex grain
    with setGrains(
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
        assertGrainFileContent(
            "a: aval\n" + "foo:\n" + "- order\n" + "- is: null\n" + "- correct\n"
        )


def test_absent_delete():
    # Delete a grain
    with setGrains({"a": "aval", "foo": "bar"}):
        ret = grains.absent(name="foo", destructive=True)
        assert ret["result"] is True
        assert ret["comment"] == "Grain foo was deleted"
        assert ret["changes"] == {"deleted": "foo"}
        assert grains.__grains__ == {"a": "aval"}
        assertGrainFileContent("a: aval\n")

    # Delete a previously unset grain
    with setGrains({"a": "aval", "foo": None}):
        ret = grains.absent(name="foo", destructive=True)
        assert ret["result"] is True
        assert ret["comment"] == "Grain foo was deleted"
        assert ret["changes"] == {"deleted": "foo"}
        assert grains.__grains__ == {"a": "aval"}
        assertGrainFileContent("a: aval\n")

    # Delete a nested grain
    with setGrains(
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
        assertGrainFileContent(
            "a: aval\n"
            + "foo:\n"
            + "- order\n"
            + "- is:\n"
            + "    other: value\n"
            + "- correct\n"
        )


# 'append' function tests: 6


def test_append():
    # Append to an existing list
    with setGrains({"a": "aval", "foo": ["bar"]}):
        ret = grains.append(name="foo", value="baz")
        assert ret["result"] is True
        assert ret["comment"] == "Value baz was added to grain foo"
        assert ret["changes"] == {"added": "baz"}
        assert grains.__grains__ == {"a": "aval", "foo": ["bar", "baz"]}
        assertGrainFileContent("a: aval\n" + "foo:\n" + "- bar\n" + "- baz\n")


def test_append_nested():
    # Append to an existing nested list
    with setGrains({"a": "aval", "foo": {"list": ["bar"]}}):
        ret = grains.append(name="foo,list", value="baz", delimiter=",")
        assert ret["result"] is True
        assert ret["comment"] == "Value baz was added to grain foo:list"
        assert ret["changes"] == {"added": "baz"}
        assert grains.__grains__ == {"a": "aval", "foo": {"list": ["bar", "baz"]}}
        assertGrainFileContent(
            "a: aval\n" + "foo:\n" + "  list:\n" + "  - bar\n" + "  - baz\n"
        )


def test_append_already():
    # Append to an existing list
    with setGrains({"a": "aval", "foo": ["bar"]}):
        ret = grains.append(name="foo", value="bar")
        assert ret["result"] is True
        assert ret["comment"] == "Value bar is already in the list " + "for grain foo"
        assert ret["changes"] == {}
        assert grains.__grains__ == {"a": "aval", "foo": ["bar"]}
        assertGrainFileContent("a: aval\n" + "foo:\n" + "- bar\n")


def test_append_fails_not_a_list():
    # Fail to append to an existing grain, not a list
    with setGrains({"a": "aval", "foo": {"bar": "val"}}):
        ret = grains.append(name="foo", value="baz")
        assert ret["result"] is False
        assert ret["comment"] == "Grain foo is not a valid list"
        assert ret["changes"] == {}
        assert grains.__grains__ == {"a": "aval", "foo": {"bar": "val"}}


def test_append_convert_to_list():
    # Append to an existing grain, converting to a list
    with setGrains({"a": "aval", "foo": {"bar": "val"}}):
        assertGrainFileContent("a: aval\n" + "foo:\n" + "  bar: val\n")
        ret = grains.append(name="foo", value="baz", convert=True)
        assert ret["result"] is True
        assert ret["comment"] == "Value baz was added to grain foo"
        assert ret["changes"] == {"added": "baz"}
        assert grains.__grains__ == {"a": "aval", "foo": [{"bar": "val"}, "baz"]}
        assertGrainFileContent("a: aval\n" + "foo:\n" + "- bar: val\n" + "- baz\n")

    # Append to an existing grain, converting to a list a multi-value dict
    with setGrains({"a": "aval", "foo": {"bar": "val", "other": "value"}}):
        assertGrainFileContent(
            "a: aval\n" + "foo:\n" + "  bar: val\n" + "  other: value\n"
        )
        ret = grains.append(name="foo", value="baz", convert=True)
        assert ret["result"] is True
        assert ret["comment"] == "Value baz was added to grain foo"
        assert ret["changes"] == {"added": "baz"}
        assert grains.__grains__ == {
            "a": "aval",
            "foo": [{"bar": "val", "other": "value"}, "baz"],
        }
        assertGrainFileContent(
            "a: aval\n" + "foo:\n" + "- bar: val\n" + "  other: value\n" + "- baz\n"
        )


def test_append_fails_inexistent():
    # Append to a non existing grain
    with setGrains({"a": "aval"}):
        ret = grains.append(name="foo", value="bar")
        assert ret["result"] is False
        assert ret["comment"] == "Grain foo does not exist"
        assert ret["changes"] == {}
        assert grains.__grains__ == {"a": "aval"}


def test_append_convert_to_list_empty():
    # Append to an existing list
    with setGrains({"foo": None}):
        ret = grains.append(name="foo", value="baz", convert=True)
        assert ret["result"] is True
        assert ret["comment"] == "Value baz was added to grain foo"
        assert ret["changes"] == {"added": "baz"}
        assert grains.__grains__ == {"foo": ["baz"]}
        assertGrainFileContent("foo:\n" + "- baz\n")


# 'list_present' function tests: 7


def test_list_present():
    with setGrains({"a": "aval", "foo": ["bar"]}):
        ret = grains.list_present(name="foo", value="baz")
        assert ret["result"] is True
        assert ret["comment"] == "Append value baz to grain foo"
        assert ret["changes"] == {"new": {"foo": ["bar", "baz"]}}
        assert grains.__grains__ == {"a": "aval", "foo": ["bar", "baz"]}
        assertGrainFileContent("a: aval\n" + "foo:\n" + "- bar\n" + "- baz\n")


def test_list_present_nested():
    with setGrains({"a": "aval", "foo": {"is": {"nested": ["bar"]}}}):
        ret = grains.list_present(name="foo,is,nested", value="baz", delimiter=",")
        assert ret["result"] is True
        assert ret["comment"] == "Append value baz to grain foo:is:nested"
        assert ret["changes"] == {"new": {"foo": {"is": {"nested": ["bar", "baz"]}}}}
        assert grains.__grains__ == {
            "a": "aval",
            "foo": {"is": {"nested": ["bar", "baz"]}},
        }
        assertGrainFileContent(
            "a: aval\n"
            + "foo:\n"
            + "  is:\n"
            + "    nested:\n"
            + "    - bar\n"
            + "    - baz\n"
        )


def test_list_present_inexistent():
    with setGrains({"a": "aval"}):
        ret = grains.list_present(name="foo", value="baz")
        assert ret["result"] is True
        assert ret["comment"] == "Append value baz to grain foo"
        assert ret["changes"] == {"new": {"foo": ["baz"]}}
        assert grains.__grains__ == {"a": "aval", "foo": ["baz"]}
        assertGrainFileContent("a: aval\n" + "foo:\n" + "- baz\n")


def test_list_present_inexistent_nested():
    with setGrains({"a": "aval"}):
        ret = grains.list_present(name="foo:is:nested", value="baz")
        assert ret["result"] is True
        assert ret["comment"] == "Append value baz to grain foo:is:nested"
        assert ret["changes"] == {"new": {"foo": {"is": {"nested": ["baz"]}}}}
        assert grains.__grains__ == {"a": "aval", "foo": {"is": {"nested": ["baz"]}}}
        assertGrainFileContent(
            "a: aval\n" + "foo:\n" + "  is:\n" + "    nested:\n" + "    - baz\n"
        )


def test_list_present_not_a_list():
    with setGrains({"a": "aval", "foo": "bar"}):
        ret = grains.list_present(name="foo", value="baz")
        assert ret["result"] is False
        assert ret["comment"] == "Grain foo is not a valid list"
        assert ret["changes"] == {}
        assert grains.__grains__ == {"a": "aval", "foo": "bar"}
        assertGrainFileContent("a: aval\n" + "foo: bar\n")


def test_list_present_nested_already():
    with setGrains({"a": "aval", "b": {"foo": ["bar"]}}):
        ret = grains.list_present(name="b:foo", value="bar")
        assert ret["result"] is True
        assert ret["comment"] == "Value bar is already in grain b:foo"
        assert ret["changes"] == {}
        assert grains.__grains__ == {"a": "aval", "b": {"foo": ["bar"]}}
        assertGrainFileContent("a: aval\n" + "b:\n" + "  foo:\n" + "  - bar\n")


def test_list_present_already():
    with setGrains({"a": "aval", "foo": ["bar"]}):
        ret = grains.list_present(name="foo", value="bar")
        assert ret["result"] is True
        assert ret["comment"] == "Value bar is already in grain foo"
        assert ret["changes"] == {}
        assert grains.__grains__ == {"a": "aval", "foo": ["bar"]}
        assertGrainFileContent("a: aval\n" + "foo:\n" + "- bar\n")


def test_list_present_unknown_failure():
    with setGrains({"a": "aval", "foo": ["bar"]}):
        # Unknown reason failure

        with patch.dict(grainsmod.__salt__, {"grains.append": MagicMock()}):
            ret = grains.list_present(name="foo", value="baz")
            assert ret["result"] is False
            assert ret["comment"] == "Failed append value baz to grain foo"
            assert ret["changes"] == {}
            assert grains.__grains__ == {"a": "aval", "foo": ["bar"]}
            assertGrainFileContent("a: aval\n" + "foo:\n" + "- bar\n")


# 'list_absent' function tests: 6


def test_list_absent():
    with setGrains({"a": "aval", "foo": ["bar"]}):
        ret = grains.list_absent(name="foo", value="bar")
        assert ret["result"] is True
        assert ret["comment"] == "Value bar was deleted from grain foo"
        assert ret["changes"] == {"deleted": ["bar"]}
        assert grains.__grains__ == {"a": "aval", "foo": []}
        assertGrainFileContent("a: aval\n" + "foo: []\n")


def test_list_absent_nested():
    with setGrains({"a": "aval", "foo": {"list": ["bar"]}}):
        ret = grains.list_absent(name="foo:list", value="bar")
        assert ret["result"] is True
        assert ret["comment"] == "Value bar was deleted from grain foo:list"
        assert ret["changes"] == {"deleted": ["bar"]}
        assert grains.__grains__ == {"a": "aval", "foo": {"list": []}}
        assertGrainFileContent("a: aval\n" + "foo:\n" + "  list: []\n")


def test_list_absent_inexistent():
    with setGrains({"a": "aval"}):
        ret = grains.list_absent(name="foo", value="baz")
        assert ret["result"] is True
        assert ret["comment"] == "Grain foo does not exist"
        assert ret["changes"] == {}
        assert grains.__grains__ == {"a": "aval"}
        assertGrainFileContent("a: aval\n")


def test_list_absent_inexistent_nested():
    with setGrains({"a": "aval"}):
        ret = grains.list_absent(name="foo:list", value="baz")
        assert ret["result"] is True
        assert ret["comment"] == "Grain foo:list does not exist"
        assert ret["changes"] == {}
        assert grains.__grains__ == {"a": "aval"}
        assertGrainFileContent("a: aval\n")


def test_list_absent_not_a_list():
    with setGrains({"a": "aval", "foo": "bar"}):
        ret = grains.list_absent(name="foo", value="bar")
        assert ret["result"] is False
        assert ret["comment"] == "Grain foo is not a valid list"
        assert ret["changes"] == {}
        assert grains.__grains__ == {"a": "aval", "foo": "bar"}
        assertGrainFileContent("a: aval\n" + "foo: bar\n")


def test_list_absent_already():
    with setGrains({"a": "aval", "foo": ["bar"]}):
        ret = grains.list_absent(name="foo", value="baz")
        assert ret["result"] is True
        assert ret["comment"] == "Value baz is absent from grain foo"
        assert ret["changes"] == {}
        assert grains.__grains__ == {"a": "aval", "foo": ["bar"]}
        assertGrainFileContent("a: aval\n" + "foo:\n" + "- bar\n")
