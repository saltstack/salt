"""
Tests for salt.utils.secret (MaskedDict, MaskedList, hide/expose/serial/mask_output).
"""

import copy

import salt.utils.secret as secret

# ---------------------------------------------------------------------------
# MaskedDict behaviour
# ---------------------------------------------------------------------------


def test_masked_dict_stores_plain_scalars():
    d = secret.MaskedDict({"k": "value", "n": 42})
    # __getitem__ returns the plain stored value
    assert d["k"] == "value"
    assert d["n"] == 42


def test_masked_dict_repr_redacts_strings():
    d = secret.MaskedDict({"password": "hunter2", "count": 3})
    r = repr(d)
    assert secret.REDACT_PLACEHOLDER in r
    assert "hunter2" not in r
    assert "3" not in r


def test_masked_dict_str_redacts_strings():
    d = secret.MaskedDict({"k": "secret"})
    assert secret.REDACT_PLACEHOLDER in str(d)
    assert "secret" not in str(d)


def test_masked_dict_wraps_nested_dict():
    d = secret.MaskedDict({"outer": {"inner": "val"}})
    assert isinstance(d["outer"], secret.MaskedDict)
    assert d["outer"]["inner"] == "val"


def test_masked_dict_wraps_nested_list():
    d = secret.MaskedDict({"items": [1, "x"]})
    assert isinstance(d["items"], secret.MaskedList)
    assert d["items"][0] == 1
    assert d["items"][1] == "x"


def test_masked_dict_is_a_dict():
    d = secret.MaskedDict({"k": "v"})
    assert isinstance(d, dict)


def test_masked_dict_setitem_wraps():
    d = secret.MaskedDict()
    d["sub"] = {"a": "b"}
    assert isinstance(d["sub"], secret.MaskedDict)
    d["lst"] = ["x"]
    assert isinstance(d["lst"], secret.MaskedList)
    d["s"] = "plain"
    assert d["s"] == "plain"  # scalars stored as-is


def test_masked_dict_update_wraps():
    d = secret.MaskedDict()
    d.update({"x": {"y": 1}})
    assert isinstance(d["x"], secret.MaskedDict)


def test_masked_dict_copy_is_masked():
    d = secret.MaskedDict({"k": "v"})
    d2 = d.copy()
    assert isinstance(d2, secret.MaskedDict)
    assert d2["k"] == "v"


def test_masked_dict_deepcopy_is_masked():
    d = secret.MaskedDict({"k": "v", "sub": {"a": 1}})
    d2 = copy.deepcopy(d)
    assert isinstance(d2, secret.MaskedDict)
    assert isinstance(d2["sub"], secret.MaskedDict)
    assert d2["k"] == "v"


def test_masked_dict_isinstance_dict_subclass():
    d = secret.MaskedDict({"k": "v"})
    assert isinstance(d, dict)
    assert issubclass(secret.MaskedDict, dict)


# ---------------------------------------------------------------------------
# MaskedList behaviour
# ---------------------------------------------------------------------------


def test_masked_list_stores_plain_scalars():
    lst = secret.MaskedList([1, "hello", True])
    assert lst[0] == 1
    assert lst[1] == "hello"
    assert lst[2] is True


def test_masked_list_repr_redacts_strings():
    lst = secret.MaskedList(["secret", 42])
    r = repr(lst)
    assert secret.REDACT_PLACEHOLDER in r
    assert "secret" not in r
    assert "42" not in r


def test_masked_list_wraps_nested_dict():
    lst = secret.MaskedList([{"k": "v"}])
    assert isinstance(lst[0], secret.MaskedDict)
    assert lst[0]["k"] == "v"


def test_masked_list_is_a_list():
    lst = secret.MaskedList([1, 2])
    assert isinstance(lst, list)


def test_masked_list_append_wraps():
    lst = secret.MaskedList([])
    lst.append({"a": "b"})
    assert isinstance(lst[0], secret.MaskedDict)
    lst.append("plain")
    assert lst[1] == "plain"


def test_masked_list_extend_wraps():
    lst = secret.MaskedList([])
    lst.extend([{"x": 1}, "y"])
    assert isinstance(lst[0], secret.MaskedDict)
    assert lst[1] == "y"


def test_masked_list_insert_wraps():
    lst = secret.MaskedList(["a"])
    lst.insert(0, {"k": "v"})
    assert isinstance(lst[0], secret.MaskedDict)


def test_masked_list_setitem_wraps():
    lst = secret.MaskedList(["a", "b"])
    lst[0] = {"k": "v"}
    assert isinstance(lst[0], secret.MaskedDict)


def test_masked_list_iadd_wraps():
    lst = secret.MaskedList(["a"])
    lst += [{"k": "v"}, "b"]
    assert isinstance(lst[1], secret.MaskedDict)
    assert lst[2] == "b"


def test_masked_list_in_operator():
    lst = secret.MaskedList(["test.ping", "test.fib"])
    assert "test.ping" in lst
    assert "missing" not in lst


def test_masked_list_isinstance_list_subclass():
    lst = secret.MaskedList([])
    assert isinstance(lst, list)
    assert issubclass(secret.MaskedList, list)


# ---------------------------------------------------------------------------
# hide()
# ---------------------------------------------------------------------------


def test_hide_dict_returns_masked_dict():
    d = secret.hide({"k": "v"})
    assert isinstance(d, secret.MaskedDict)


def test_hide_list_returns_masked_list():
    lst = secret.hide(["a", "b"])
    assert isinstance(lst, secret.MaskedList)


def test_hide_scalar_is_noop():
    assert secret.hide("string") == "string"
    assert secret.hide(42) == 42
    assert secret.hide(None) is None


def test_hide_already_masked_dict_is_idempotent():
    d = secret.MaskedDict({"k": "v"})
    d2 = secret.hide(d)
    assert d2 is d


def test_hide_already_masked_list_is_idempotent():
    lst = secret.MaskedList(["a"])
    lst2 = secret.hide(lst)
    assert lst2 is lst


# ---------------------------------------------------------------------------
# expose()
# ---------------------------------------------------------------------------


def test_expose_masked_dict_returns_plain_dict():
    d = secret.MaskedDict({"k": "v", "n": 1})
    result = secret.expose(d)
    assert type(result) is dict
    assert result == {"k": "v", "n": 1}


def test_expose_masked_list_returns_plain_list():
    lst = secret.MaskedList(["a", 1])
    result = secret.expose(lst)
    assert type(result) is list
    assert result == ["a", 1]


def test_expose_nested():
    d = secret.MaskedDict({"sub": {"a": "b"}, "lst": ["x"]})
    result = secret.expose(d)
    assert type(result) is dict
    assert type(result["sub"]) is dict
    assert type(result["lst"]) is list
    assert result["sub"]["a"] == "b"
    assert result["lst"][0] == "x"


def test_expose_plain_scalar_passthrough():
    assert secret.expose("abc") == "abc"
    assert secret.expose(99) == 99
    assert secret.expose(None) is None


def test_expose_roundtrip():
    raw = {"a": "v", "b": [1, "s", {"c": "d"}], "n": 42}
    masked = secret.hide(copy.deepcopy(raw))
    back = secret.expose(masked)
    assert back == raw


# ---------------------------------------------------------------------------
# serial()  — aggressive redaction
# ---------------------------------------------------------------------------


def test_serial_redacts_plain_string():
    assert secret.serial("hunter2") == secret.REDACT_PLACEHOLDER


def test_serial_leaves_empty_string():
    assert secret.serial("") == ""


def test_serial_leaves_non_string_scalars():
    assert secret.serial(42) == 42
    assert secret.serial(True) is True
    assert secret.serial(None) is None


def test_serial_redacts_masked_dict_strings():
    d = secret.MaskedDict({"password": "hunter2", "count": 3})
    result = secret.serial(d)
    assert result == {"password": secret.REDACT_PLACEHOLDER, "count": 3}


def test_serial_redacts_plain_dict_strings():
    # serial is aggressive — also redacts strings in plain dicts
    d = {"k": "v", "n": 1}
    result = secret.serial(d)
    assert result == {"k": secret.REDACT_PLACEHOLDER, "n": 1}


def test_serial_redacts_nested():
    d = secret.MaskedDict({"sub": {"s": "secret"}, "lst": ["a", 1]})
    result = secret.serial(d)
    assert result["sub"]["s"] == secret.REDACT_PLACEHOLDER
    assert result["lst"][0] == secret.REDACT_PLACEHOLDER
    assert result["lst"][1] == 1


# ---------------------------------------------------------------------------
# mask_output()  — gentle redaction (safety net)
# ---------------------------------------------------------------------------


def test_mask_output_plain_dict_is_noop():
    d = {"comment": "State worked fine", "result": True}
    assert secret.mask_output(d) == d


def test_mask_output_plain_string_is_noop():
    assert secret.mask_output("normal output") == "normal output"


def test_mask_output_redacts_masked_dict():
    d = {"pillar_data": secret.MaskedDict({"password": "secret"})}
    result = secret.mask_output(d)
    assert result["pillar_data"]["password"] == secret.REDACT_PLACEHOLDER


def test_mask_output_redacts_masked_list():
    d = {"items": secret.MaskedList(["sensitive", 1])}
    result = secret.mask_output(d)
    assert result["items"][0] == secret.REDACT_PLACEHOLDER
    assert result["items"][1] == 1


def test_mask_output_nested_plain_dicts_not_redacted():
    d = {"result": {"changes": {"before": "old", "after": "new"}}}
    result = secret.mask_output(d)
    # plain nested dicts should not be redacted
    assert result["result"]["changes"]["before"] == "old"


# ---------------------------------------------------------------------------
# no_log_mask()
# ---------------------------------------------------------------------------


def test_no_log_mask_redacts_comment():
    ret = {"comment": "Executed command", "changes": {}, "result": True}
    secret.no_log_mask(ret)
    assert ret["comment"] == secret.REDACT_PLACEHOLDER
    assert ret["result"] is True  # result is not touched


def test_no_log_mask_redacts_changes():
    ret = {
        "comment": "ok",
        "changes": {"before": "plaintext_password", "after": "new_pass"},
        "result": True,
    }
    secret.no_log_mask(ret)
    assert ret["changes"]["before"] == secret.REDACT_PLACEHOLDER
    assert ret["changes"]["after"] == secret.REDACT_PLACEHOLDER


def test_no_log_mask_empty_comment():
    ret = {"comment": "", "changes": {}, "result": True}
    secret.no_log_mask(ret)
    assert ret["comment"] == ""  # empty string not redacted


# ---------------------------------------------------------------------------
# mask_pillar ContextVar gates container repr
# ---------------------------------------------------------------------------


def test_masked_dict_repr_respects_context_var():
    """When mask_pillar.get() is False, MaskedDict repr is plain.

    Without this, a state SLS that does ``{{ pillar['dict_value'] }}`` on the
    minion sees a redacted string because Jinja calls __str__ on the
    MaskedDict and __str__ ignored the ContextVar.
    """
    d = secret.MaskedDict({"k": "v"})
    assert secret.REDACT_PLACEHOLDER in repr(d)
    assert secret.REDACT_PLACEHOLDER in str(d)
    token = secret.mask_pillar.set(False)
    try:
        assert "v" in repr(d)
        assert secret.REDACT_PLACEHOLDER not in repr(d)
        assert "v" in str(d)
        assert secret.REDACT_PLACEHOLDER not in str(d)
    finally:
        secret.mask_pillar.reset(token)


def test_masked_list_repr_respects_context_var():
    """When mask_pillar.get() is False, MaskedList repr is plain.

    Reproducer for the issue 69160 shape: ``{{ pillar['list_value'] }}``
    must interpolate plain values when the renderer brackets the call with
    mask_pillar=False.
    """
    lst = secret.MaskedList(["a", "b", "c"])
    assert secret.REDACT_PLACEHOLDER in repr(lst)
    assert secret.REDACT_PLACEHOLDER in str(lst)
    token = secret.mask_pillar.set(False)
    try:
        plain = str(lst)
        assert "a" in plain and "b" in plain and "c" in plain
        assert secret.REDACT_PLACEHOLDER not in plain
    finally:
        secret.mask_pillar.reset(token)


def test_masked_nested_repr_respects_context_var():
    """Nested MaskedDict/MaskedList repr is plain end-to-end under unmask."""
    d = secret.MaskedDict({"hosts": ["host1", "host2"], "creds": {"user": "bob"}})
    token = secret.mask_pillar.set(False)
    try:
        r = repr(d)
        assert "host1" in r and "host2" in r
        assert "bob" in r
        assert secret.REDACT_PLACEHOLDER not in r
    finally:
        secret.mask_pillar.reset(token)
    # Back to default — masked again
    r = repr(d)
    assert secret.REDACT_PLACEHOLDER in r
    assert "host1" not in r
