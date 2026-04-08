"""
Tests for salt.utils.safepillar (SafeDict, SafeList, SecretStr wrapping, redaction).
"""

import pytest
from pydantic import SecretBytes, SecretStr  # pylint: disable=3rd-party-module-not-gated

import salt.utils.safepillar as sp


def test_safe_dict_wraps_string_and_nested_dict():
    d = sp.SafeDict()
    d["k"] = "secret"
    assert isinstance(d["k"], SecretStr)
    assert d["k"].get_secret_value() == "secret"
    d["n"] = {"a": "x"}
    assert isinstance(d["n"], sp.SafeDict)
    assert isinstance(d["n"]["a"], SecretStr)


def test_safe_dict_skips_errors_key():
    d = sp.SafeDict()
    d["_errors"] = ["plain error"]
    assert d["_errors"] == ["plain error"]
    assert not isinstance(d["_errors"][0], SecretStr)


def test_safe_list_append_and_extend():
    lst = sp.SafeList()
    lst.append("a")
    assert isinstance(lst[0], SecretStr)
    lst.extend(["b", "c"])
    assert lst[1].get_secret_value() == "b"
    lst += ["d"]
    assert lst[-1].get_secret_value() == "d"


def test_safe_list_setitem_and_insert():
    lst = sp.SafeList(["a", "b"])
    lst[0] = "z"
    assert lst[0].get_secret_value() == "z"
    lst.insert(1, "mid")
    assert lst[1].get_secret_value() == "mid"


def test_wrap_pillar_tree_idempotent():
    inner = {"x": "y"}
    w1 = sp.wrap_pillar_tree(inner)
    w2 = sp.wrap_pillar_tree(w1)
    assert w1 is w2


def test_unwrap_roundtrip():
    raw = {"a": "v", "b": [1, "s", {"c": "d"}]}
    wrapped = sp.wrap_pillar_tree(raw)
    back = sp.unwrap_pillar_tree(wrapped)
    assert back == raw


def test_iter_pillar_secret_literals_order():
    p = sp.wrap_pillar_tree({"short": "ab", "longer": "abcd"})
    lit = sp.iter_pillar_secret_literals(p)
    assert "abcd" in lit
    assert "ab" in lit
    assert lit[0] == "abcd"  # longest first


def test_redact_known_literals():
    p = sp.wrap_pillar_tree({"pw": "hunter2"})
    lit = sp.iter_pillar_secret_literals(p)
    ret = {
        "comment": "pw is hunter2 here",
        "changes": {"out": "hunter2"},
    }
    red = sp.redact_known_literals(ret, lit)
    assert "hunter2" not in str(red)
    assert sp.REDACT_PLACEHOLDER in red["comment"]


def test_apply_no_log_mask():
    ret = {"comment": "x", "changes": {"a": 1}, "result": True}
    sp.apply_no_log_mask(ret)
    assert ret["comment"] == sp.REDACT_PLACEHOLDER
    assert ret["changes"] == {sp.REDACT_PLACEHOLDER: sp.REDACT_PLACEHOLDER}


def test_safe_dict_bytes():
    d = sp.SafeDict()
    d["b"] = b"bin"
    assert isinstance(d["b"], SecretBytes)
    assert d["b"].get_secret_value() == b"bin"


@pytest.mark.parametrize(
    "container",
    [
        pytest.param({"type": "dict"}, id="dict"),
        pytest.param({"type": "list", "items": [1, "two"]}, id="nested_list"),
    ],
)
def test_wrap_pillar_tree_yamlish(container):
    w = sp.wrap_pillar_tree(container)
    assert isinstance(w, sp.SafeDict)
