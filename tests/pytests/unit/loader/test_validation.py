"""
Tests for salt.loader.validation -- annotation-driven input validation and
StateReturn contract enforcement installed at loader-wrap time.
"""

import logging
import types

import pytest

import salt.loader.validation as validation
from salt.exceptions import SaltInvocationError

pytestmark = pytest.mark.skipif(
    not validation.HAS_PYDANTIC, reason="pydantic not installed"
)


def _make_module(**attrs):
    """Build a throwaway module with the given attrs. Functions declared in
    the caller's frame carry their original __module__, which wrap_module
    uses to filter re-exports -- we rewrite __module__ to match."""
    mod = types.ModuleType("salt_test_validation_mod")
    for k, v in attrs.items():
        if callable(v) and hasattr(v, "__module__"):
            v.__module__ = mod.__name__
        setattr(mod, k, v)
    return mod


class TestWrapCallable:
    def test_off_returns_fn_unchanged(self):
        def f(x: int) -> int:
            return x

        assert validation.wrap_callable(f, mode="off") is f

    def test_unannotated_fn_returns_fn_unchanged(self):
        def f(x, y):
            return (x, y)

        assert validation.wrap_callable(f, mode="strict") is f

    def test_annotated_fn_is_wrapped(self):
        def f(x: int) -> int:
            return x

        wrapped = validation.wrap_callable(f, mode="warn")
        assert wrapped is not f
        assert getattr(wrapped, "__salt_validated__", False)
        assert wrapped.__wrapped__ is f

    def test_strict_mode_raises_on_bad_type(self):
        def f(x: int) -> int:
            return x

        wrapped = validation.wrap_callable(f, mode="strict")
        with pytest.raises(SaltInvocationError):
            wrapped(x="not-an-int-or-numeric")

    def test_warn_mode_logs_and_passes_through(self, caplog):
        def f(x: int):
            return x

        wrapped = validation.wrap_callable(f, mode="warn")
        with caplog.at_level(logging.WARNING, logger="salt.loader.validation"):
            got = wrapped(x="definitely-not-an-int")
        assert got == "definitely-not-an-int"
        assert any("input validation failure" in r.message for r in caplog.records)

    def test_cli_string_coercion_int(self):
        def f(x: int):
            return x

        wrapped = validation.wrap_callable(f, mode="strict")
        # "30" coerces to 30 in lax mode.
        assert wrapped(x="30") == 30

    def test_cli_string_coercion_bool(self):
        def f(flag: bool):
            return flag

        wrapped = validation.wrap_callable(f, mode="strict")
        assert wrapped(flag="true") is True
        assert wrapped(flag="false") is False

    def test_reserved_kwargs_pass_through_untouched(self):
        captured = {}

        def f(x: int, **kwargs):
            captured.update(kwargs)
            return x

        wrapped = validation.wrap_callable(f, mode="strict")
        ret = wrapped(x=1, __pub_jid="J", __pub_user="u", __id__="id-x")
        assert ret == 1
        # Reserved kwargs arrived at fn in kwargs, not filtered or coerced.
        assert captured == {"__pub_jid": "J", "__pub_user": "u", "__id__": "id-x"}

    def test_positional_args_preserved(self):
        def f(a: int, b: str):
            return (a, b)

        wrapped = validation.wrap_callable(f, mode="strict")
        assert wrapped(1, "x") == (1, "x")

    def test_double_wrap_is_noop(self):
        def f(x: int):
            return x

        once = validation.wrap_callable(f, mode="strict")
        twice = validation.wrap_callable(once, mode="strict")
        assert twice is once

    def test_state_return_strict_raises(self):
        def f():
            return {"name": "n", "changes": {}, "result": True}  # missing comment

        wrapped = validation.wrap_callable(f, mode="strict", validate_state_return=True)
        with pytest.raises(SaltInvocationError):
            wrapped()

    def test_state_return_warn_passes_through(self, caplog):
        def f():
            return {"name": "n", "changes": {}, "result": True}

        wrapped = validation.wrap_callable(f, mode="warn", validate_state_return=True)
        with caplog.at_level(logging.WARNING, logger="salt.loader.validation"):
            got = wrapped()
        assert got == {"name": "n", "changes": {}, "result": True}
        assert any(
            "state return contract violation" in r.message for r in caplog.records
        )

    def test_state_return_valid_passes(self):
        def f():
            return {
                "name": "n",
                "changes": {"a": 1},
                "result": True,
                "comment": "ok",
            }

        wrapped = validation.wrap_callable(f, mode="strict", validate_state_return=True)
        # Should not raise.
        assert wrapped()["result"] is True


class TestWrapModule:
    def test_wrap_module_off_is_noop(self):
        def f(x: int):
            return x

        mod = _make_module(f=f)
        original = mod.f
        validation.wrap_module(mod, {"loader_validate_mode": "off"}, "modules")
        assert mod.f is original

    def test_wrap_module_wraps_annotated_only(self):
        def annotated(x: int):
            return x

        def plain(x, y):
            return (x, y)

        mod = _make_module(annotated=annotated, plain=plain)
        validation.wrap_module(mod, {"loader_validate_mode": "warn"}, "modules")
        assert getattr(mod.annotated, "__salt_validated__", False)
        # Plain functions (no annotations) are untouched.
        assert not getattr(mod.plain, "__salt_validated__", False)

    def test_wrap_module_skips_private(self):
        def _private(x: int):
            return x

        def public(x: int):
            return x

        mod = _make_module(_private=_private, public=public)
        validation.wrap_module(mod, {"loader_validate_mode": "warn"}, "modules")
        assert mod._private is _private
        assert getattr(mod.public, "__salt_validated__", False)

    def test_wrap_module_skips_reexports(self):
        """Functions whose __module__ doesn't match the loaded module's
        name are imports and should not be wrapped."""

        def f(x: int):
            return x

        mod = _make_module()
        # Attach without rewriting __module__ (simulating an import).
        setattr(mod, "imported", f)
        validation.wrap_module(mod, {"loader_validate_mode": "warn"}, "modules")
        assert mod.imported is f

    def test_wrap_module_states_tag_wraps_returns(self):
        def present(name: str):
            return {"name": name, "changes": {}, "result": "not-a-bool", "comment": ""}

        mod = _make_module(present=present)
        validation.wrap_module(mod, {"loader_validate_mode": "strict"}, "states")
        # The wrapped call should fail because result is a string.
        with pytest.raises(SaltInvocationError):
            mod.present(name="foo")

    def test_wrap_module_modules_tag_does_not_wrap_returns(self):
        def f() -> dict:
            # A return that would fail StateReturn (no 'name' key) but we're
            # under the 'modules' tag -- no return validation applies.
            return {"anything": "goes"}

        mod = _make_module(f=f)
        validation.wrap_module(mod, {"loader_validate_mode": "strict"}, "modules")
        assert mod.f() == {"anything": "goes"}

    def test_wrap_module_invalid_mode_is_noop(self, caplog):
        def f(x: int):
            return x

        mod = _make_module(f=f)
        original = mod.f
        with caplog.at_level(logging.WARNING, logger="salt.loader.validation"):
            validation.wrap_module(mod, {"loader_validate_mode": "bogus"}, "modules")
        assert mod.f is original
        assert any("Invalid loader_validate_mode" in r.message for r in caplog.records)


class TestReservedKwargs:
    def test_split_reserved_partitions(self):
        non_reserved, reserved = validation._split_reserved(
            {"a": 1, "__pub_jid": "J", "b": 2, "__id__": "x"}
        )
        assert non_reserved == {"a": 1, "b": 2}
        assert reserved == {"__pub_jid": "J", "__id__": "x"}

    def test_split_reserved_empty_reserved(self):
        non_reserved, reserved = validation._split_reserved({"a": 1, "b": 2})
        assert non_reserved == {"a": 1, "b": 2}
        assert reserved == {}

    def test_reserved_kwargs_includes_pub_and_state_keys(self):
        assert "__pub_jid" in validation.RESERVED_KWARGS
        assert "__id__" in validation.RESERVED_KWARGS
        assert "__sls__" in validation.RESERVED_KWARGS
        # Guard against accidental additions of plain names.
        assert all(k.startswith("__") for k in validation.RESERVED_KWARGS)
