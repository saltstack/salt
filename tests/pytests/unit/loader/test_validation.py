"""
Tests for salt.loader.validation -- annotation-driven input validation and
return-contract enforcement called from LoadedFunc.__call__.
"""

import logging

import pytest

import salt.loader.validation as validation
from salt.exceptions import SaltInvocationError

pytestmark = pytest.mark.skipif(
    not validation.HAS_PYDANTIC, reason="pydantic not installed"
)


class TestSplitReserved:
    def test_partitions(self):
        non_reserved, reserved = validation._split_reserved(
            {"a": 1, "__pub_jid": "J", "b": 2, "__id__": "x"}
        )
        assert non_reserved == {"a": 1, "b": 2}
        assert reserved == {"__pub_jid": "J", "__id__": "x"}

    def test_empty_reserved(self):
        non_reserved, reserved = validation._split_reserved({"a": 1, "b": 2})
        assert non_reserved == {"a": 1, "b": 2}
        assert reserved == {}

    def test_pub_prefix_caught_by_pattern(self):
        # __pub_schedule / __pub_stamp are injected by the publish layer
        # but not in STATE_RUNTIME_KEYWORDS; the prefix match catches them.
        non_reserved, reserved = validation._split_reserved(
            {"a": 1, "__pub_schedule": "s", "__pub_stamp": "t"}
        )
        assert non_reserved == {"a": 1}
        assert reserved == {"__pub_schedule": "s", "__pub_stamp": "t"}

    def test_reserved_kwargs_sourced_from_state_module(self):
        assert "__pub_jid" in validation.RESERVED_KWARGS
        assert "__id__" in validation.RESERVED_KWARGS
        assert "__sls__" in validation.RESERVED_KWARGS
        assert "__pub_minion_is_target" in validation.RESERVED_KWARGS
        assert "__prereq__" in validation.RESERVED_KWARGS
        # Plain-name runtime keywords (failhard, onlyif, retry, ...) are
        # stripped by the state compiler before dispatch and never reach
        # the loader; they should not appear in our set.
        assert all(k.startswith("__") for k in validation.RESERVED_KWARGS)


class TestValidateInputs:
    def test_off_passes_through(self):
        def f(x: int):
            return x

        args, kwargs = validation.validate_inputs(f, (), {"x": "not-a-number"}, "off")
        # Nothing coerced, nothing raised; raw args returned.
        assert kwargs == {"x": "not-a-number"}

    def test_no_annotations_passes_through(self):
        def f(x, y):
            return (x, y)

        args, kwargs = validation.validate_inputs(f, (1, 2), {}, "strict")
        assert args == (1, 2)
        assert kwargs == {}

    def test_strict_raises_on_bad_type(self):
        def f(x: int):
            return x

        with pytest.raises(SaltInvocationError):
            validation.validate_inputs(f, (), {"x": "not-an-int-or-numeric"}, "strict")

    def test_warn_logs_and_passes_through(self, caplog):
        def f(x: int):
            return x

        with caplog.at_level(logging.WARNING, logger="salt.loader.validation"):
            args, kwargs = validation.validate_inputs(
                f, (), {"x": "definitely-not-an-int"}, "warn"
            )
        assert kwargs == {"x": "definitely-not-an-int"}
        assert any("input validation failure" in r.message for r in caplog.records)

    def test_cli_string_coercion_int(self):
        def f(x: int):
            return x

        args, kwargs = validation.validate_inputs(f, (), {"x": "30"}, "strict")
        assert kwargs == {"x": 30}

    def test_cli_string_coercion_bool(self):
        def f(flag: bool):
            return flag

        _args, kwargs = validation.validate_inputs(f, (), {"flag": "true"}, "strict")
        assert kwargs == {"flag": True}
        _args, kwargs = validation.validate_inputs(f, (), {"flag": "false"}, "strict")
        assert kwargs == {"flag": False}

    def test_reserved_kwargs_pass_through_as_kwargs(self):
        def f(x: int, **_kwargs):
            return x

        args, kwargs = validation.validate_inputs(
            f,
            (),
            {"x": "1", "__pub_jid": "J", "__pub_user": "u", "__id__": "id-x"},
            "strict",
        )
        # Reserved kwargs preserved alongside coerced non-reserved.
        assert kwargs == {
            "x": 1,
            "__pub_jid": "J",
            "__pub_user": "u",
            "__id__": "id-x",
        }

    def test_positional_args_preserved(self):
        def f(a: int, b: str):
            return (a, b)

        args, kwargs = validation.validate_inputs(f, (1, "x"), {}, "strict")
        # bind_partial maps positional to kwarg names; downstream dispatch
        # works either way, so we accept kwargs-form here.
        reconstructed = dict(kwargs)
        # Pydantic coerced in lax mode.
        assert reconstructed == {"a": 1, "b": "x"}

    def test_model_cache_attached(self):
        def f(x: int):
            return x

        validation.validate_inputs(f, (), {"x": "1"}, "strict")
        cached = getattr(f, "__salt_validate_model__", None)
        assert cached is not None and cached is not validation._NO_MODEL

    def test_unannotated_cached_as_no_model(self):
        def f(x, y):
            return (x, y)

        validation.validate_inputs(f, (1, 2), {}, "strict")
        assert getattr(f, "__salt_validate_model__", None) is validation._NO_MODEL


class TestValidateReturn:
    def test_off_is_noop(self):
        def f():
            return {"malformed": True}

        ret = validation.validate_return(
            f, {"malformed": True}, validation.StateReturn, "off"
        )
        assert ret == {"malformed": True}

    def test_no_contract_is_noop(self):
        def f():
            return "anything"

        ret = validation.validate_return(f, "anything", None, "strict")
        assert ret == "anything"

    def test_strict_raises(self):
        def present():
            return {"name": "n", "changes": {}, "result": True}  # missing comment

        with pytest.raises(SaltInvocationError):
            validation.validate_return(
                present,
                {"name": "n", "changes": {}, "result": True},
                validation.StateReturn,
                "strict",
            )

    def test_warn_logs_and_returns_unmutated(self, caplog):
        def present():
            return {"name": "n", "changes": {}, "result": True}

        with caplog.at_level(logging.WARNING, logger="salt.loader.validation"):
            ret = validation.validate_return(
                present,
                {"name": "n", "changes": {}, "result": True},
                validation.StateReturn,
                "warn",
            )
        assert ret == {"name": "n", "changes": {}, "result": True}
        assert any("return contract violation" in r.message for r in caplog.records)

    def test_valid_state_return_passes(self):
        def present():
            return {
                "name": "n",
                "changes": {"a": 1},
                "result": True,
                "comment": "ok",
            }

        ret = validation.validate_return(
            present,
            {"name": "n", "changes": {"a": 1}, "result": True, "comment": "ok"},
            validation.StateReturn,
            "strict",
        )
        assert ret["result"] is True


class TestBuildInputModel:
    def test_skips_unannotated_params(self):
        def f(annotated: int, bare=None):
            return (annotated, bare)

        model, sig = validation._build_input_model(f)
        assert model is not None
        # Only the annotated param becomes a model field.
        assert set(model.model_fields) == {"annotated"}
        assert sig is not None

    def test_returns_none_when_no_fields(self):
        def f(a, b):
            return (a, b)

        model, _sig = validation._build_input_model(f)
        assert model is None

    def test_var_positional_and_keyword_skipped(self):
        def f(x: int, *args: str, **kwargs: int):
            return x

        model, _sig = validation._build_input_model(f)
        assert set(model.model_fields) == {"x"}
