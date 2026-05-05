"""
Tests for salt.utils.secret (SecretDict, SecretList, SecretStr wrapping, redaction).
"""

import copy

import pytest

import salt.utils.secret as secret
import salt.utils.versions


def test_secret_dict_wraps_string_and_nested_dict():
    d = secret.hide({})
    d["k"] = "secret"
    assert isinstance(d["k"], secret.SecretStr)
    assert d["k"].get_secret_value() == "secret"
    d["n"] = {"a": "x"}
    assert isinstance(d["n"], secret.SecretDict)
    assert isinstance(d["n"]["a"], secret.SecretStr)


def test_secret_dict_errors_key_values_still_wrapped():
    """_errors entries are wrapped like other string leaves (no SafeDict skip)."""
    d = secret.hide({})
    d["_errors"] = ["plain error"]
    assert isinstance(d["_errors"][0], secret.SecretStr)
    assert d["_errors"][0].get_secret_value() == "plain error"


def test_secret_list_append_and_extend():
    lst = secret.SecretList([])
    lst.append("a")
    assert isinstance(lst[0], secret.SecretStr)
    lst.extend(["b", "c"])
    assert lst[1].get_secret_value() == "b"
    lst += ["d"]
    assert lst[-1].get_secret_value() == "d"


def test_secret_list_setitem_and_insert():
    lst = secret.SecretList(["a", "b"])
    lst[0] = "z"
    assert lst[0].get_secret_value() == "z"
    lst.insert(1, "mid")
    assert lst[1].get_secret_value() == "mid"


def test_wrap_pillar_tree_idempotent():
    inner = {"x": "y"}
    w1 = secret.hide(inner)
    w2 = secret.hide(w1)
    assert w1 is w2


def test_unwrap_roundtrip():
    raw = {"a": "v", "b": [1, "s", {"c": "d"}]}
    wrapped = secret.hide(copy.deepcopy(raw))
    back = secret.expose(copy.deepcopy(wrapped))
    assert back == raw


def test_unwrap_blackout_whitelist_for_str_membership():
    wrapped = secret.hide({"minion_blackout_whitelist": ["test.ping", "test.fib"]})
    wl = wrapped["minion_blackout_whitelist"]
    assert "test.ping" in wl
    plain = secret.expose(wl)
    assert plain == ["test.ping", "test.fib"]
    assert "test.ping" in plain


def test_apply_no_log_mask_changes():
    ret = {"comment": "x", "changes": {"a": "asdf", "b": 1}, "result": True}
    secret.no_log_mask(ret)
    assert str(ret["comment"]) == secret.REDACT_PLACEHOLDER
    assert str(ret["changes"]) == str({"a": secret.REDACT_PLACEHOLDER, "b": 1})


def test_apply_no_log_mask_no_changes():
    ret = {"comment": "x", "changes": None, "result": True}
    secret.no_log_mask(ret)
    assert str(ret["comment"]) == secret.REDACT_PLACEHOLDER
    assert ret["changes"] is None


def test_secret_str_redacted_str_and_equal_to_plain_str():
    s = secret.SecretStr("xyzzy")
    assert str(s) == secret.REDACT_PLACEHOLDER
    assert secret.REDACT_PLACEHOLDER in repr(s)
    assert s.get_secret_value() == "xyzzy"
    assert s == "xyzzy"
    assert "xyzzy" in s
    assert "xyzzy" not in str(s)


def test_secret_str_equality_and_deepcopy():
    a = secret.SecretStr("same")
    b = secret.SecretStr("same")
    c = secret.SecretStr("other")
    assert a == b
    assert a != c
    d = copy.deepcopy(a)
    assert d.get_secret_value() == "same"
    assert d == a


def test_secret_bytes_equal_to_plain_bytes():
    s = secret.SecretBytes(b"secret")
    assert s == b"secret"
    assert s.get_secret_value() == b"secret"


def test_secret_dict_bytes():
    d = secret.hide({})
    d["b"] = b"bin"
    assert isinstance(d["b"], secret.SecretBytes)
    assert d["b"].get_secret_value() == b"bin"


@pytest.mark.parametrize(
    "container",
    [
        pytest.param({"type": "dict"}, id="dict"),
        pytest.param({"type": "list", "items": [1, "two"]}, id="nested_list"),
    ],
)
def test_hide_yamlish_structures(container):
    w = secret.hide(container)
    assert isinstance(w, secret.SecretDict)
