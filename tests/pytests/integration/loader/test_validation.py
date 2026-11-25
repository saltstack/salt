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
    """Minion with wire_salt input validation in ``enforce`` mode."""
    minion = salt_master.salt_minion_daemon(
        "loader-validation-input-enforce",
        overrides={
            "loader_validate_overrides": {
                "wire_salt": {"input_mode": "enforce"},
            },
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
def return_enforce_minion(salt_master):
    """Minion with states return validation in ``enforce`` mode."""
    minion = salt_master.salt_minion_daemon(
        "loader-validation-return-enforce",
        overrides={
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


class TestInputEnforce:
    """Exercise the wire_salt loader with ``input_mode=enforce`` through
    a real publish-layer dispatch -- the filtered ``minion_mods`` loader
    is named ``wire_salt`` by its factory."""

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
    """Exercise the states loader with ``return_mode=enforce`` through
    state dispatch against the pinned StateReturn contract. The states
    loader is named ``states`` by its factory."""

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
    """Minion where the states loader is overridden to ``enforce`` on
    returns. Proves per-loader override lookup works end-to-end."""
    minion = salt_master.salt_minion_daemon(
        "loader-validation-states-override",
        overrides={
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
    """Prove loader_validate_overrides[<name>][<direction>_mode] is
    plumbed through to the right loader via its ``name=`` kwarg."""

    def test_states_override_enforces_on_bad_return(
        self, salt_cli, states_override_minion
    ):
        """The states loader override promotes return validation to
        enforce, so the bad_return state fails rather than succeeding."""
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
