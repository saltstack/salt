"""
Functional tests for salt.loader.validation.

Exercises the real LazyLoader + LoadedFunc dispatch pipeline in-process
by writing test modules to a temp dir and instantiating a loader
directly. Faster than integration (no daemon startup, no process
spawning, no stale-scripts footgun) while still realistic (actual
loader, actual dispatch, actual pydantic validation).

Unit tests at ``tests/pytests/unit/loader/test_validation.py`` cover
the validation functions in isolation. Integration tests at
``tests/pytests/integration/loader/test_validation.py`` cover end-to-
end minion dispatch. This file is the middle tier: real loader, no
daemon.
"""

import logging

import pytest

import salt.loader.lazy
import salt.utils.files
import tests.support.helpers
from salt.exceptions import SaltInvocationError
from salt.utils.versions import reqs

pytestmark = pytest.mark.skipif(not reqs.pydantic, reason="pydantic not installed")


TYPED_MODULE = """
def typed(count: int, name: str = "default", flag: bool = False) -> dict:
    return {
        "count": count,
        "name": name,
        "flag": flag,
        "types": [type(count).__name__, type(name).__name__, type(flag).__name__],
    }


def unannotated(x, y):
    return (x, y)


def accepts_pub_kwargs(x: int, **kwargs):
    pub = sorted(k for k in kwargs if k.startswith("__pub_"))
    return {"x": x, "pub_keys": pub}
"""


STATE_MODULE = """
def good(name):
    return {"name": name, "changes": {}, "result": True, "comment": "ok"}


def bad(name):
    # Missing required 'comment' field -- fails StateReturn.
    return {"name": name, "changes": {}, "result": True}
"""


@pytest.fixture
def typed_mod_dir(tmp_path):
    """Drop TYPED_MODULE into a tmp dir and return the path."""
    with salt.utils.files.fopen(tmp_path / "typed_mod.py", "w") as fp:
        fp.write(tests.support.helpers.dedent(TYPED_MODULE))
    return tmp_path


@pytest.fixture
def state_mod_dir(tmp_path):
    """Drop STATE_MODULE into a tmp dir and return the path."""
    with salt.utils.files.fopen(tmp_path / "state_mod.py", "w") as fp:
        fp.write(tests.support.helpers.dedent(STATE_MODULE))
    return tmp_path


def _base_opts(**extra):
    opts = {"optimization_order": [0, 1, 2]}
    opts.update(extra)
    return opts


def _wire_salt_overrides(**modes):
    """Shorthand for loader_validate_overrides targeting wire_salt."""
    return {"loader_validate_overrides": {"wire_salt": dict(modes)}}


def _states_overrides(**modes):
    """Shorthand for loader_validate_overrides targeting states."""
    return {"loader_validate_overrides": {"states": dict(modes)}}


class TestInputValidation:
    """Real LazyLoader dispatch exercises validate_inputs end-to-end."""

    def test_off_passes_bad_type_through(self, typed_mod_dir):
        loader = salt.loader.lazy.LazyLoader(
            [typed_mod_dir],
            _base_opts(**_wire_salt_overrides(input_mode="off")),
            name="wire_salt",
        )
        result = loader["typed_mod.typed"](count="not-a-number")
        # Off mode: raw string passes through.
        assert result["count"] == "not-a-number"
        assert result["types"][0] == "str"

    def test_enforce_coerces_string_to_int(self, typed_mod_dir):
        loader = salt.loader.lazy.LazyLoader(
            [typed_mod_dir],
            _base_opts(**_wire_salt_overrides(input_mode="enforce")),
            name="wire_salt",
        )
        result = loader["typed_mod.typed"](count="42", name="x", flag="true")
        assert result["count"] == 42
        assert result["flag"] is True
        assert result["types"] == ["int", "str", "bool"]

    def test_enforce_raises_on_unparseable(self, typed_mod_dir):
        loader = salt.loader.lazy.LazyLoader(
            [typed_mod_dir],
            _base_opts(**_wire_salt_overrides(input_mode="enforce")),
            name="wire_salt",
        )
        with pytest.raises(SaltInvocationError, match="input validation failure"):
            loader["typed_mod.typed"](count="not-a-number")

    def test_warn_logs_and_passes_through(self, typed_mod_dir, caplog):
        loader = salt.loader.lazy.LazyLoader(
            [typed_mod_dir],
            _base_opts(**_wire_salt_overrides(input_mode="warn")),
            name="wire_salt",
        )
        with caplog.at_level(logging.WARNING, logger="salt.loader.validation"):
            result = loader["typed_mod.typed"](count="not-a-number")
        assert result["count"] == "not-a-number"
        assert any("input validation failure" in r.message for r in caplog.records)

    def test_strict_rejects_unannotated_function(self, typed_mod_dir):
        loader = salt.loader.lazy.LazyLoader(
            [typed_mod_dir],
            _base_opts(**_wire_salt_overrides(input_mode="strict")),
            name="wire_salt",
        )
        with pytest.raises(SaltInvocationError, match="missing"):
            loader["typed_mod.unannotated"]("a", "b")

    def test_unannotated_function_unaffected_under_enforce(self, typed_mod_dir):
        loader = salt.loader.lazy.LazyLoader(
            [typed_mod_dir],
            _base_opts(**_wire_salt_overrides(input_mode="enforce")),
            name="wire_salt",
        )
        assert loader["typed_mod.unannotated"]("a", "b") == ("a", "b")

    def test_reserved_kwargs_forwarded_to_fn(self, typed_mod_dir):
        loader = salt.loader.lazy.LazyLoader(
            [typed_mod_dir],
            _base_opts(**_wire_salt_overrides(input_mode="enforce")),
            name="wire_salt",
        )
        result = loader["typed_mod.accepts_pub_kwargs"](
            x=1, __pub_jid="J123", __pub_user="alice"
        )
        assert result["x"] == 1
        assert result["pub_keys"] == ["__pub_jid", "__pub_user"]


class TestReturnValidation:
    """Real states loader dispatch exercises validate_return against the
    pinned StateReturn contract."""

    def test_good_return_passes(self, state_mod_dir):
        from salt.loader.contracts.states import StateReturn

        loader = salt.loader.lazy.LazyLoader(
            [state_mod_dir],
            _base_opts(**_states_overrides(return_mode="enforce")),
            name="states",
            output_contract=StateReturn,
        )
        result = loader["state_mod.good"]("x")
        assert result["result"] is True

    def test_bad_return_raises_in_enforce(self, state_mod_dir):
        from salt.loader.contracts.states import StateReturn

        loader = salt.loader.lazy.LazyLoader(
            [state_mod_dir],
            _base_opts(**_states_overrides(return_mode="enforce")),
            name="states",
            output_contract=StateReturn,
        )
        with pytest.raises(SaltInvocationError, match="return contract violation"):
            loader["state_mod.bad"]("x")

    def test_bad_return_warns_in_warn_mode(self, state_mod_dir, caplog):
        from salt.loader.contracts.states import StateReturn

        loader = salt.loader.lazy.LazyLoader(
            [state_mod_dir],
            _base_opts(**_states_overrides(return_mode="warn")),
            name="states",
            output_contract=StateReturn,
        )
        with caplog.at_level(logging.WARNING, logger="salt.loader.validation"):
            result = loader["state_mod.bad"]("x")
        # warn mode: raw return passes through unmodified.
        assert "comment" not in result
        assert any("return contract violation" in r.message for r in caplog.records)


class TestPerLoaderLookup:
    """Each loader reads its own override entry from the same opts dict.

    Build two loaders over the same module with different ``name=``
    kwargs and prove they resolve to different modes from a single
    overrides dict.
    """

    def test_separate_names_resolve_to_separate_entries(self, typed_mod_dir):
        opts = _base_opts(
            loader_validate_overrides={
                # wire_salt sees enforce, salt_dunder has no entry (off).
                "wire_salt": {"input_mode": "enforce"},
            }
        )
        wire = salt.loader.lazy.LazyLoader([typed_mod_dir], opts, name="wire_salt")
        internal = salt.loader.lazy.LazyLoader(
            [typed_mod_dir], opts, name="salt_dunder"
        )
        # wire_salt entry exists -> enforce, raises on bad input.
        with pytest.raises(SaltInvocationError):
            wire["typed_mod.typed"](count="not-a-number")
        # salt_dunder has no entry -> off, passes through.
        result = internal["typed_mod.typed"](count="not-a-number")
        assert result["count"] == "not-a-number"


class TestUnnamedLoaderOff:
    """Loaders without a name always resolve to off, even when an
    overrides entry targets a known loader name."""

    def test_unnamed_loader_skips_validation(self, typed_mod_dir):
        opts = _base_opts(
            loader_validate_overrides={
                "wire_salt": {"input_mode": "enforce"},
            }
        )
        loader = salt.loader.lazy.LazyLoader([typed_mod_dir], opts)
        # No name -> validation off, bad input passes through.
        result = loader["typed_mod.typed"](count="not-a-number")
        assert result["count"] == "not-a-number"


class TestValidatorAtStartup:
    """Malformed loader_validate_overrides raises at LazyLoader.__init__,
    not at first dispatch."""

    def test_bogus_mode_value_raises_at_startup(self, typed_mod_dir):
        with pytest.raises(ValueError, match="not a valid mode"):
            salt.loader.lazy.LazyLoader(
                [typed_mod_dir],
                _base_opts(**_wire_salt_overrides(input_mode="enforcee")),
                name="wire_salt",
            )

    def test_unknown_override_loader_name_raises_at_startup(self, typed_mod_dir):
        with pytest.raises(ValueError, match="unknown loader"):
            salt.loader.lazy.LazyLoader(
                [typed_mod_dir],
                _base_opts(
                    loader_validate_overrides={"nonexistent": {"input_mode": "strict"}}
                ),
                name="wire_salt",
            )

    def test_valid_opts_pass_startup_check(self, typed_mod_dir):
        # No raise -- just confirms the validator runs clean on good
        # input through the real LazyLoader constructor path.
        loader = salt.loader.lazy.LazyLoader(
            [typed_mod_dir],
            _base_opts(
                loader_validate_overrides={
                    "wire_salt": {"input_mode": "enforce"},
                    "states": {"input_mode": "strict", "return_mode": "strict"},
                },
            ),
            name="wire_salt",
        )
        assert loader.name == "wire_salt"
