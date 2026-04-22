"""
Tests for salt.utils.secret (SafeDict, SafeList, SecretStr wrapping, redaction).
"""

import copy

import pytest

import salt.utils.secret as secret
import salt.utils.versions


def test_safe_dict_wraps_string_and_nested_dict():
    d = secret.SafeDict()
    d["k"] = "secret"
    assert isinstance(d["k"], secret.SecretStr)
    assert d["k"].get_secret_value() == "secret"
    d["n"] = {"a": "x"}
    assert isinstance(d["n"], secret.SafeDict)
    assert isinstance(d["n"]["a"], secret.SecretStr)


def test_safe_dict_skips_errors_key():
    d = secret.SafeDict()
    d["_errors"] = ["plain error"]
    assert d["_errors"] == ["plain error"]
    assert not isinstance(d["_errors"][0], secret.SecretStr)


def test_safe_list_append_and_extend():
    lst = secret.SafeList()
    lst.append("a")
    assert isinstance(lst[0], secret.SecretStr)
    lst.extend(["b", "c"])
    assert lst[1].get_secret_value() == "b"
    lst += ["d"]
    assert lst[-1].get_secret_value() == "d"


def test_safe_list_setitem_and_insert():
    lst = secret.SafeList(["a", "b"])
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
    wrapped = secret.hide(raw)
    back = secret.expose(wrapped)
    assert back == raw


def test_unwrap_blackout_whitelist_for_str_membership():
    wrapped = secret.hide({"minion_blackout_whitelist": ["test.ping", "test.fib"]})
    wl = wrapped["minion_blackout_whitelist"]
    assert "test.ping" not in wl
    plain = secret.expose(wl)
    assert plain == ["test.ping", "test.fib"]
    assert "test.ping" in plain


def test_iter_pillar_secret_literals_order():
    p = secret.hide({"secrets": {"short": "ab", "longer": "abcd"}})
    lit = secret.expose(p)
    assert "abcd" in lit
    assert "ab" in lit
    assert lit[0] == "abcd"  # longest first


def test_iter_pillar_secret_literals_public_keys_excluded():
    p = secret.hide({"target-path": "/tmp/pytest-of-root/x", "db_password": "hunter2"})
    lit = secret.expose(p)
    assert "hunter2" in lit
    assert "/tmp/pytest-of-root/x" not in lit


def test_redact_known_literals():
    pillar = secret.hide({"pw": "hunter2"})
    lit = secret.expose(pillar)
    ret = {
        "comment": "pw is hunter2 here",
        "changes": {"out": "hunter2"},
    }
    red = secret.redact(ret, pillar)
    assert "hunter2" not in str(red)
    assert secret.REDACT_PLACEHOLDER in red["comment"]


def test_apply_no_log_mask():
    ret = {"comment": "x", "changes": {"a": 1}, "result": True}
    secret.no_log_mask(ret)
    assert ret["comment"] == secret.REDACT_PLACEHOLDER
    assert ret["changes"] == {secret.REDACT_PLACEHOLDER: secret.REDACT_PLACEHOLDER}


def test_secret_str_redacted_str_and_not_equal_to_plain_str():
    s = secret.SecretStr("xyzzy")
    assert str(s) == secret.REDACT_PLACEHOLDER
    assert secret.REDACT_PLACEHOLDER in repr(s)
    assert s.get_secret_value() == "xyzzy"
    assert s != "xyzzy"
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


def test_secret_bytes_not_equal_to_plain_bytes():
    s = secret.SecretBytes(b"secret")
    assert s != b"secret"
    assert s.get_secret_value() == b"secret"


def test_safe_dict_bytes():
    d = secret.SafeDict()
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
def test_wrap_pillar_tree_yamlish(container):
    w = secret.wrap_pillar_tree(container)
    assert isinstance(w, secret.SafeDict)


@pytest.mark.skipif(
    not salt.utils.versions.reqs.msgpack,
    reason="msgpack not installed",
)
def test_msgpack_serialize_unwraps_secret_types():
    from salt.serializers import msgpack as msgpack_ser

    wrapped = secret.hide({"k": "secret"})
    packed = msgpack_ser.serialize(wrapped)
    assert msgpack_ser.deserialize(packed) == {"k": "secret"}

    packed2 = msgpack_ser.serialize({"x": secret.SecretStr("y")})
    assert msgpack_ser.deserialize(packed2) == {"x": "y"}
