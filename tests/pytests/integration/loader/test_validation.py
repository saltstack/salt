"""
Integration tests for salt.loader.validation.

Unit tests at ``tests/pytests/unit/loader/test_validation.py`` cover the
validation functions in isolation. This file proves the whole pipeline
end-to-end through a real minion's ``LazyLoader`` dispatch via
``LoadedFunc.__call__`` -- the publish layer, reserved-kwarg
injection, CLI-string coercion, and ``SaltInvocationError``
propagation all wired together.
"""

import pytest

from salt.utils.versions import reqs
from tests.conftest import FIPS_TESTRUN

pytestmark = pytest.mark.skipif(not reqs.pydantic, reason="pydantic not installed")


# An exec module with annotated signatures. Dropped into the minion's
# ``_modules/`` and synced via ``saltutil.sync_modules`` so the real
# LazyLoader picks it up.
TYPED_EXEC_MODULE = '''
"""Fixture exec module for loader-validation integration tests."""


def typed(count: int, name: str = "default", flag: bool = False) -> dict:
    """Round-trip the three args back out with their observed types."""
    return {
        "count": count,
        "name": name,
        "flag": flag,
        "types": [
            type(count).__name__,
            type(name).__name__,
            type(flag).__name__,
        ],
    }


def unannotated(x, y):
    """No annotations -- should pass through validation untouched."""
    return {"x": x, "y": y}


def accepts_pub_kwargs(x: int, **kwargs):
    """Returns the count of publish-layer kwargs the function received.

    Modules that legitimately read ``__pub_schedule`` / ``__pub_user``
    from ``**kwargs`` (e.g. salt/modules/junos.py) must still receive
    those under validation. The wrapper must strip them from validation
    input but forward them to the underlying function unchanged.
    """
    pub_keys = sorted(k for k in kwargs if k.startswith("__pub_"))
    return {"x": x, "pub_keys": pub_keys}
'''


# A state module whose body internally dispatches via __salt__ to an
# annotated exec function with a bad input value. Under wire-only
# scope the inner call is uncchecked; under internal scope it fails.
INTERNAL_CALL_STATE_MODULE = '''
"""Fixture state module that composes with __salt__ internally."""


def calls_typed(name):
    """Dispatch through __salt__ with a deliberately bad int value.

    If internal_input_mode is off, the inner call succeeds and returns
    the raw string. If internal_input_mode is enforce/strict, the
    inner call raises SaltInvocationError which the state engine
    surfaces as a failed chunk.
    """
    inner = __salt__["validation_demo.typed"](count="not-a-number")
    return {
        "name": name,
        "changes": {"inner": inner},
        "result": True,
        "comment": "ok",
    }
'''


# A state module with one function satisfying StateReturn and one that
# violates it (missing the required ``comment`` field).
STATE_MODULE_SOURCE = '''
"""Fixture state module for loader-validation integration tests."""


def good_return(name):
    """Returns a dict matching the StateReturn contract."""
    return {"name": name, "changes": {}, "result": True, "comment": "ok"}


def bad_return(name):
    """Returns a dict missing the required ``comment`` field."""
    return {"name": name, "changes": {}, "result": True}
'''


FIPS_OVERRIDES = {
    "fips_mode": FIPS_TESTRUN,
    "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
    "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
}


@pytest.fixture(scope="module")
def input_enforce_minion(salt_master):
    """Minion with input validation in ``enforce`` mode."""
    minion = salt_master.salt_minion_daemon(
        "loader-validation-input-enforce",
        overrides={
            "loader_validate_wire_input_mode": "enforce",
            "loader_validate_wire_return_mode": "off",
            "loader_validate_internal_input_mode": "off",
            "loader_validate_internal_return_mode": "off",
            **FIPS_OVERRIDES,
        },
    )
    minion.after_terminate(
        pytest.helpers.remove_stale_minion_key, salt_master, minion.id
    )
    with salt_master.state_tree.base.temp_file(
        "_modules/validation_demo.py", TYPED_EXEC_MODULE
    ):
        with minion.started():
            cli = salt_master.salt_cli()
            cli.run("saltutil.sync_modules", minion_tgt=minion.id)
            yield minion


@pytest.fixture(scope="module")
def wire_only_minion(salt_master):
    """Minion where wire validation is on but internal is off.

    Proves the trust-boundary semantics: a state body dispatching
    through __salt__ with bad input is NOT re-validated because that's
    an internal loader call.
    """
    minion = salt_master.salt_minion_daemon(
        "loader-validation-wire-only",
        overrides={
            "loader_validate_wire_input_mode": "enforce",
            "loader_validate_wire_return_mode": "off",
            "loader_validate_internal_input_mode": "off",
            "loader_validate_internal_return_mode": "off",
            **FIPS_OVERRIDES,
        },
    )
    minion.after_terminate(
        pytest.helpers.remove_stale_minion_key, salt_master, minion.id
    )
    with salt_master.state_tree.base.temp_file(
        "_modules/validation_demo.py", TYPED_EXEC_MODULE
    ), salt_master.state_tree.base.temp_file(
        "_states/internal_call_demo.py", INTERNAL_CALL_STATE_MODULE
    ):
        with minion.started():
            cli = salt_master.salt_cli()
            cli.run("saltutil.sync_modules", minion_tgt=minion.id)
            cli.run("saltutil.sync_states", minion_tgt=minion.id)
            yield minion


@pytest.fixture(scope="module")
def wire_and_internal_minion(salt_master):
    """Minion with both wire AND internal enforce. Proves internal
    scope kicks in: the same state body (bad inner dispatch) now
    fails."""
    minion = salt_master.salt_minion_daemon(
        "loader-validation-wire-and-internal",
        overrides={
            "loader_validate_wire_input_mode": "enforce",
            "loader_validate_wire_return_mode": "off",
            "loader_validate_internal_input_mode": "enforce",
            "loader_validate_internal_return_mode": "off",
            **FIPS_OVERRIDES,
        },
    )
    minion.after_terminate(
        pytest.helpers.remove_stale_minion_key, salt_master, minion.id
    )
    with salt_master.state_tree.base.temp_file(
        "_modules/validation_demo.py", TYPED_EXEC_MODULE
    ), salt_master.state_tree.base.temp_file(
        "_states/internal_call_demo.py", INTERNAL_CALL_STATE_MODULE
    ):
        with minion.started():
            cli = salt_master.salt_cli()
            cli.run("saltutil.sync_modules", minion_tgt=minion.id)
            cli.run("saltutil.sync_states", minion_tgt=minion.id)
            yield minion


@pytest.fixture(scope="module")
def return_enforce_minion(salt_master):
    """Minion with return validation in ``enforce`` mode."""
    minion = salt_master.salt_minion_daemon(
        "loader-validation-return-enforce",
        overrides={
            "loader_validate_wire_input_mode": "off",
            "loader_validate_wire_return_mode": "enforce",
            "loader_validate_internal_input_mode": "off",
            "loader_validate_internal_return_mode": "off",
            **FIPS_OVERRIDES,
        },
    )
    minion.after_terminate(
        pytest.helpers.remove_stale_minion_key, salt_master, minion.id
    )
    with salt_master.state_tree.base.temp_file(
        "_states/validation_state_demo.py", STATE_MODULE_SOURCE
    ):
        with minion.started():
            cli = salt_master.salt_cli()
            cli.run("saltutil.sync_states", minion_tgt=minion.id)
            yield minion


class TestInputEnforce:
    """Exercise ``loader_validate_wire_input_mode=enforce`` through a
    real publish-layer dispatch -- the wire loader is the filtered
    ``minion_mods`` result produced by publish-dispatch."""

    def test_valid_input_passes(self, salt_cli, input_enforce_minion):
        ret = salt_cli.run(
            "validation_demo.typed",
            name="hello",
            count=5,
            minion_tgt=input_enforce_minion.id,
        )
        assert ret.data == {
            "count": 5,
            "name": "hello",
            "flag": False,
            "types": ["int", "str", "bool"],
        }

    def test_cli_string_coercion(self, salt_cli, input_enforce_minion):
        """salt-cli delivers all kwargs as strings; pydantic lax mode
        coerces them to the declared types before the function runs."""
        ret = salt_cli.run(
            "validation_demo.typed",
            count="42",
            name="hello",
            flag="true",
            minion_tgt=input_enforce_minion.id,
        )
        assert ret.data["count"] == 42
        assert ret.data["flag"] is True
        assert ret.data["types"] == ["int", "str", "bool"]

    def test_unparseable_type_raises(self, salt_cli, input_enforce_minion):
        """A string that can't be coerced to int surfaces as an error."""
        ret = salt_cli.run(
            "validation_demo.typed",
            count="not-a-number",
            minion_tgt=input_enforce_minion.id,
        )
        # The call must not have succeeded with the original garbage str.
        assert ret.data != {
            "count": "not-a-number",
            "name": "default",
            "flag": False,
            "types": ["str", "str", "bool"],
        }
        # Error text appears either in data or stdout.
        haystack = f"{ret.data!r} {ret.stdout or ''}"
        assert (
            "input validation failure" in haystack
            or "SaltInvocationError" in haystack
            or "validation" in haystack.lower()
        )

    def test_unannotated_function_unaffected(self, salt_cli, input_enforce_minion):
        """Functions without annotations pass through validation
        untouched -- the whole exec surface doesn't need migration."""
        ret = salt_cli.run(
            "validation_demo.unannotated",
            "a",
            "b",
            minion_tgt=input_enforce_minion.id,
        )
        assert ret.data == {"x": "a", "y": "b"}

    def test_core_test_ping_still_works(self, salt_cli, input_enforce_minion):
        """``test.ping`` -- unannotated, in salt core -- must still
        return True under enforce mode. Regression gate."""
        ret = salt_cli.run("test.ping", minion_tgt=input_enforce_minion.id)
        assert ret.data is True

    def test_pub_kwargs_reach_function(self, salt_cli, input_enforce_minion):
        """Publish-layer kwargs (``__pub_jid``, ``__pub_user``, ...)
        are injected by the minion before dispatch. The validation
        wrapper must strip them from validation input and still forward
        them to any function that reads them via ``**kwargs``."""
        ret = salt_cli.run(
            "validation_demo.accepts_pub_kwargs",
            x=1,
            minion_tgt=input_enforce_minion.id,
        )
        assert ret.data["x"] == 1
        # At minimum __pub_jid is always injected on publish-dispatched
        # calls; assert the function saw at least one __pub_* key.
        assert len(ret.data["pub_keys"]) > 0


class TestReturnEnforce:
    """Exercise ``loader_validate_wire_return_mode=enforce`` through
    state dispatch against the pinned StateReturn contract. The states
    loader is flagged is_wire_loader=True by its factory."""

    def test_good_state_return_passes(self, salt_cli, return_enforce_minion):
        ret = salt_cli.run(
            "state.single",
            "validation_state_demo.good_return",
            name="integration",
            minion_tgt=return_enforce_minion.id,
        )
        assert ret.data is not None
        # state.single wraps the return in a tagged dict.
        chunk = next(iter(ret.data.values()))
        assert chunk.get("result") is True

    def test_bad_state_return_surfaces_contract_violation(
        self, salt_cli, return_enforce_minion
    ):
        """A state function missing a StateReturn field triggers the
        contract check; the error propagates somewhere visible."""
        ret = salt_cli.run(
            "state.single",
            "validation_state_demo.bad_return",
            name="integration",
            minion_tgt=return_enforce_minion.id,
        )
        haystack = f"{ret.data!r} {ret.stdout or ''}"
        assert (
            "return contract violation" in haystack
            or "contract" in haystack.lower()
            or "SaltInvocationError" in haystack
        )


@pytest.fixture(scope="module")
def states_override_minion(salt_master):
    """Minion where tier defaults are 'warn' but 'states' is overridden
    to 'enforce'. Proves the per-loader override takes precedence over
    the tier default."""
    minion = salt_master.salt_minion_daemon(
        "loader-validation-states-override",
        overrides={
            # Tier defaults: warn everywhere.
            "loader_validate_wire_input_mode": "warn",
            "loader_validate_wire_return_mode": "warn",
            "loader_validate_internal_input_mode": "warn",
            "loader_validate_internal_return_mode": "warn",
            # Per-loader override: states is strict on returns.
            "loader_validate_overrides": {
                "states": {"return_mode": "enforce"},
            },
            **FIPS_OVERRIDES,
        },
    )
    minion.after_terminate(
        pytest.helpers.remove_stale_minion_key, salt_master, minion.id
    )
    with salt_master.state_tree.base.temp_file(
        "_states/validation_state_demo.py", STATE_MODULE_SOURCE
    ):
        with minion.started():
            cli = salt_master.salt_cli()
            cli.run("saltutil.sync_states", minion_tgt=minion.id)
            yield minion


class TestPerLoaderOverride:
    """Prove loader_validate_overrides[<name>][<direction>_mode] wins
    over the tier default."""

    def test_states_override_is_enforce_despite_warn_default(
        self, salt_cli, states_override_minion
    ):
        """Tier default is warn (would log + pass through); per-loader
        override for 'states' promotes return validation to enforce
        (raises), so the bad_return state fails rather than succeeding
        with a logged warning."""
        ret = salt_cli.run(
            "state.single",
            "validation_state_demo.bad_return",
            name="override-test",
            minion_tgt=states_override_minion.id,
        )
        haystack = f"{ret.data!r} {ret.stdout or ''}"
        assert (
            "return contract violation" in haystack
            or "contract" in haystack.lower()
            or "SaltInvocationError" in haystack
        )


class TestScopeDistinction:
    """Prove wire vs. internal scope dispatch semantics: the *same*
    state body with the *same* bad internal __salt__ call gets
    different treatment based on the internal scope opts.

    The state function in INTERNAL_CALL_STATE_MODULE dispatches:
        __salt__["validation_demo.typed"](count="not-a-number")

    - Under wire_only_minion (internal_input=off): the inner call is
      an internal loader dispatch, validation is skipped, the typed
      function receives the bad string, returns it as-is.
    - Under wire_and_internal_minion (internal_input=enforce): the
      inner call hits validation, pydantic can't coerce
      "not-a-number" to int, SaltInvocationError is raised, the state
      chunk fails.
    """

    def test_internal_dispatch_skipped_when_internal_off(
        self, salt_cli, wire_only_minion
    ):
        ret = salt_cli.run(
            "state.single",
            "internal_call_demo.calls_typed",
            name="scope-test",
            minion_tgt=wire_only_minion.id,
        )
        chunk = next(iter(ret.data.values()))
        # State succeeded because the inner __salt__ call wasn't
        # validated; the bad string flowed through.
        assert chunk.get("result") is True
        assert chunk["changes"]["inner"]["count"] == "not-a-number"

    def test_internal_dispatch_validated_when_internal_on(
        self, salt_cli, wire_and_internal_minion
    ):
        ret = salt_cli.run(
            "state.single",
            "internal_call_demo.calls_typed",
            name="scope-test",
            minion_tgt=wire_and_internal_minion.id,
        )
        haystack = f"{ret.data!r} {ret.stdout or ''}"
        # Inner validation raised; the state chunk failed. Error text
        # is somewhere in the return payload or output.
        assert (
            "input validation failure" in haystack
            or "SaltInvocationError" in haystack
            or "not-a-number" in haystack.lower()
            and "error" in haystack.lower()
        )
