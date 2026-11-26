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


# State-system helper functions whose returns aren't StateReturn-shaped.
# Enforce-mode return validation must skip these.
def mod_init(low):
    return True


def mod_aggregate(low, chunks, running):
    return low


def mod_run_check(low, running, test_mode):
    return True


def mod_run_check_cmd(cmd):
    return True
"""


# Exec module exercising the input-passthrough contract: unannotated
# params, **kwargs catchall, and number-to-str coercion all need to
# round-trip the full call through LoadedFunc.__call__.
PASSTHROUGH_MODULE = """
def mixed(annotated: int, unannotated):
    '''unannotated must survive validation; annotated must coerce.'''
    return {"annotated": annotated, "unannotated": unannotated}


def install(name: str, **kwargs):
    '''**kwargs contents must survive validation.'''
    return {"name": name, "kwargs": dict(kwargs)}


def versioned(name: str, version: str = "latest"):
    '''version=1.2 (float) must coerce to "1.2" (str), not raise.'''
    return {"name": name, "version": version, "version_type": type(version).__name__}
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


@pytest.fixture
def passthrough_mod_dir(tmp_path):
    """Drop PASSTHROUGH_MODULE into a tmp dir and return the path."""
    with salt.utils.files.fopen(tmp_path / "passthrough.py", "w") as fp:
        fp.write(tests.support.helpers.dedent(PASSTHROUGH_MODULE))
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


# ---------------------------------------------------------------------------
# End-to-end regression tests for charzl's PR #70943 review comments. These
# dispatch THROUGH LoadedFunc.__call__ (not directly at validate_inputs /
# validate_return), proving the real wiring -- not just that the mechanism
# works in isolation.
# ---------------------------------------------------------------------------


class TestStateHelperSkipThroughDispatch:
    """charzl: ``StateReturn`` was being applied to ``mod_init`` /
    ``mod_aggregate`` / ``mod_run_check`` / ``mod_run_check_cmd``,
    breaking under ``loader_validate_overrides.states.return_mode=enforce``
    AND under ``loader_validate_defaults.return_mode=enforce``. The skip
    must fire regardless of how the mode was resolved."""

    @pytest.fixture
    def state_loader(self, state_mod_dir):
        from salt.loader.contracts.states import StateReturn

        return state_mod_dir, StateReturn

    @pytest.mark.parametrize(
        "helper,args",
        [
            ("mod_init", ({"state": "state_mod"},)),
            ("mod_aggregate", ({"state": "state_mod"}, [], {})),
            ("mod_run_check", ({"state": "state_mod"}, {}, False)),
            ("mod_run_check_cmd", ("/bin/true",)),
        ],
    )
    def test_skip_under_overrides_enforce(self, state_loader, helper, args):
        state_mod_dir, StateReturn = state_loader
        loader = salt.loader.lazy.LazyLoader(
            [state_mod_dir],
            _base_opts(
                loader_validate_overrides={"states": {"return_mode": "enforce"}},
            ),
            name="states",
            output_contract=StateReturn,
        )
        # Without the skip, this would raise SaltInvocationError because
        # mod_init returns bool (not a StateReturn-shaped dict).
        result = loader[f"state_mod.{helper}"](*args)
        assert result in (True, args[0])

    @pytest.mark.parametrize(
        "helper,args",
        [
            ("mod_init", ({"state": "state_mod"},)),
            ("mod_aggregate", ({"state": "state_mod"}, [], {})),
        ],
    )
    def test_skip_under_defaults_enforce(self, state_loader, helper, args):
        """Same skip must work when the mode is resolved from
        ``loader_validate_defaults`` rather than per-loader overrides.
        This is the scenario charzl called out specifically."""
        state_mod_dir, StateReturn = state_loader
        loader = salt.loader.lazy.LazyLoader(
            [state_mod_dir],
            _base_opts(
                loader_validate_defaults={"return_mode": "enforce"},
            ),
            name="states",
            output_contract=StateReturn,
        )
        result = loader[f"state_mod.{helper}"](*args)
        assert result in (True, args[0])

    def test_regular_state_fn_still_validated_under_enforce(self, state_loader):
        """Sanity: with the skip in place, non-helper state functions
        still validate. ``good`` passes, ``bad`` (missing comment) raises."""
        state_mod_dir, StateReturn = state_loader
        loader = salt.loader.lazy.LazyLoader(
            [state_mod_dir],
            _base_opts(
                loader_validate_defaults={"return_mode": "enforce"},
            ),
            name="states",
            output_contract=StateReturn,
        )
        assert loader["state_mod.good"]("x")["result"] is True
        with pytest.raises(SaltInvocationError, match="contract violation"):
            loader["state_mod.bad"]("x")


class TestInputPassthroughThroughDispatch:
    """charzl: ``validate_inputs`` was rebuilding the call from
    ``validated.model_fields``, which dropped unannotated params and
    ``**kwargs`` extras. These tests dispatch THROUGH LoadedFunc so the
    function actually gets invoked with the constructed args/kwargs --
    proving the wiring, not just the shape of what validate_inputs
    returns."""

    def test_unannotated_positional_reaches_function(self, passthrough_mod_dir):
        """``def mixed(annotated: int, unannotated)`` dispatched as
        ``mixed(1, "preserve-me")`` must actually call the function
        with both args. Before the fix the unannotated slot was dropped
        and the function raised ``TypeError`` for a missing arg."""
        loader = salt.loader.lazy.LazyLoader(
            [passthrough_mod_dir],
            _base_opts(
                loader_validate_overrides={"wire_salt": {"input_mode": "enforce"}},
            ),
            name="wire_salt",
        )
        result = loader["passthrough.mixed"](1, "preserve-me")
        assert result == {"annotated": 1, "unannotated": "preserve-me"}

    def test_var_kwargs_catchall_reaches_function(self, passthrough_mod_dir):
        """``def install(name: str, **kwargs)`` dispatched as
        ``install("nginx", refresh=True, pkgs=["a", "b"])`` must call
        the function with the full ``**kwargs``. Before the fix those
        extras were dropped by the model-fields rebuild."""
        loader = salt.loader.lazy.LazyLoader(
            [passthrough_mod_dir],
            _base_opts(
                loader_validate_overrides={"wire_salt": {"input_mode": "enforce"}},
            ),
            name="wire_salt",
        )
        result = loader["passthrough.install"]("nginx", refresh=True, pkgs=["a", "b"])
        assert result == {
            "name": "nginx",
            "kwargs": {"refresh": True, "pkgs": ["a", "b"]},
        }


class TestNumberToStrCoercionThroughDispatch:
    """charzl: salt-api / SLS / YAML dispatch commonly produces
    ``version=1.2`` as a Python float. The documented behavior is that
    it coerces to ``"1.2"`` for a ``version: str`` parameter. Pydantic 2
    lax mode rejects numbers->str without ``coerce_numbers_to_str=True``;
    verify the SALT_VALIDATE_CONFIG enables it end-to-end."""

    def test_float_coerces_to_str(self, passthrough_mod_dir):
        loader = salt.loader.lazy.LazyLoader(
            [passthrough_mod_dir],
            _base_opts(
                loader_validate_overrides={"wire_salt": {"input_mode": "enforce"}},
            ),
            name="wire_salt",
        )
        result = loader["passthrough.versioned"]("nginx", version=1.2)
        assert result == {
            "name": "nginx",
            "version": "1.2",
            "version_type": "str",
        }

    def test_int_coerces_to_str(self, passthrough_mod_dir):
        loader = salt.loader.lazy.LazyLoader(
            [passthrough_mod_dir],
            _base_opts(
                loader_validate_overrides={"wire_salt": {"input_mode": "enforce"}},
            ),
            name="wire_salt",
        )
        result = loader["passthrough.versioned"]("nginx", version=42)
        assert result == {
            "name": "nginx",
            "version": "42",
            "version_type": "str",
        }
