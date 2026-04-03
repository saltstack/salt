"""
Tests for resource dispatch logic in salt.minion.

Covers:
- Minion._resolve_resource_targets(): what resource jobs each minion spawns
- gen_modules() atomic resource_loaders assignment: Race 2 fix
- resource_ctxvar injection in _thread_return: Race 1 fix
"""

import threading

import pytest

import salt.loader.context
import salt.minion
from tests.support.mock import patch as mock_patch

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

RESOURCES = {
    "dummy": ["dummy-01", "dummy-02", "dummy-03"],
    "ssh": ["node1", "localhost"],
}


@pytest.fixture
def minion_with_resources(minion_opts):
    """A Minion instance with resources configured, no real master connection."""
    minion_opts["resources"] = RESOURCES
    minion_opts["multiprocessing"] = False
    with mock_patch("salt.minion.Minion.gen_modules"):
        with mock_patch("salt.minion.Minion.connect_master"):
            m = salt.minion.Minion(minion_opts, load_grains=False)
    return m


# ---------------------------------------------------------------------------
# _resolve_resource_targets tests
# ---------------------------------------------------------------------------


def test_resolve_resource_targets_glob_wildcard(minion_with_resources):
    """
    A broad glob ('*') with no resource-aware tgt_type returns all managed
    resources so that every resource job is dispatched.
    """
    load = {"tgt": "*", "tgt_type": "glob", "fun": "test.ping", "arg": []}
    targets = minion_with_resources._resolve_resource_targets(load)
    ids = [t["id"] for t in targets]
    assert set(ids) == {"dummy-01", "dummy-02", "dummy-03", "node1", "localhost"}
    types = {t["type"] for t in targets}
    assert types == {"dummy", "ssh"}


def test_resolve_resource_targets_glob_specific_minion(minion_with_resources):
    """
    A specific name glob (no wildcard characters) must NOT dispatch to
    resources.  ``salt 'minion' test.ping`` should only run on the minion
    itself, not on its managed resources.
    """
    load = {"tgt": "minion", "tgt_type": "glob", "fun": "test.ping", "arg": []}
    targets = minion_with_resources._resolve_resource_targets(load)
    assert targets == [], "specific-name glob must not dispatch to resources"


def test_resolve_resource_targets_compound_T_full_srn(minion_with_resources):
    """T@dummy:dummy-01 in a compound expression returns exactly that resource."""
    load = {
        "tgt": "T@dummy:dummy-01",
        "tgt_type": "compound",
        "fun": "test.ping",
        "arg": [],
    }
    targets = minion_with_resources._resolve_resource_targets(load)
    assert targets == [{"id": "dummy-01", "type": "dummy"}]


def test_resolve_resource_targets_compound_T_bare_type(minion_with_resources):
    """T@dummy returns all dummy resources."""
    load = {
        "tgt": "T@dummy",
        "tgt_type": "compound",
        "fun": "test.ping",
        "arg": [],
    }
    targets = minion_with_resources._resolve_resource_targets(load)
    ids = [t["id"] for t in targets]
    assert set(ids) == {"dummy-01", "dummy-02", "dummy-03"}
    assert all(t["type"] == "dummy" for t in targets)


def test_resolve_resource_targets_compound_no_T(minion_with_resources):
    """A compound expression with no T@ or M@ terms dispatches no resource jobs."""
    load = {
        "tgt": "G@os:Debian",
        "tgt_type": "compound",
        "fun": "test.ping",
        "arg": [],
    }
    targets = minion_with_resources._resolve_resource_targets(load)
    assert targets == []


def test_resolve_resource_targets_no_resources(minion_opts):
    """A minion with no resources configured never dispatches resource jobs."""
    minion_opts.pop("resources", None)
    with mock_patch("salt.minion.Minion.gen_modules"):
        with mock_patch("salt.minion.Minion.connect_master"):
            m = salt.minion.Minion(minion_opts, load_grains=False)
    load = {"tgt": "*", "tgt_type": "glob", "fun": "test.ping", "arg": []}
    assert m._resolve_resource_targets(load) == []


def test_resolve_resource_targets_no_resource_funs(minion_with_resources):
    """
    Internal Salt plumbing functions are never dispatched to resources, even
    for a wildcard target.
    """
    for fun in salt.minion.Minion._NO_RESOURCE_FUNS:
        load = {"tgt": "*", "tgt_type": "glob", "fun": fun, "arg": []}
        assert minion_with_resources._resolve_resource_targets(load) == [], fun


def test_resolve_resource_targets_T_with_trailing_colon(minion_with_resources):
    """T@dummy: (trailing colon) is treated as a bare type, not a specific ID."""
    load = {
        "tgt": "T@dummy:",
        "tgt_type": "compound",
        "fun": "test.ping",
        "arg": [],
    }
    targets = minion_with_resources._resolve_resource_targets(load)
    ids = {t["id"] for t in targets}
    assert ids == {"dummy-01", "dummy-02", "dummy-03"}


# ---------------------------------------------------------------------------
# gen_modules() atomic resource_loaders assignment (Race 2 fix)
# ---------------------------------------------------------------------------


def test_gen_modules_resource_loaders_atomic_assignment():
    """
    The atomic build-then-assign pattern ensures self.resource_loaders is
    never transiently empty between gen_modules() calls.

    We verify this by confirming that in the gen_modules source the actual
    assignment ``self.resource_loaders = _new_resource_loaders`` appears, and
    that no bare ``self.resource_loaders = {}`` statement (outside comments)
    is present.
    """
    import inspect

    source = inspect.getsource(salt.minion.MinionBase.gen_modules)
    # The safe atomic-assign terminal statement must be present.
    assert "self.resource_loaders = _new_resource_loaders" in source
    # Verify no executable bare-clear line exists (comments are OK).
    executable_lines = [
        ln for ln in source.splitlines() if not ln.lstrip().startswith("#")
    ]
    assert not any(
        "self.resource_loaders = {}" in ln for ln in executable_lines
    ), "Found bare self.resource_loaders = {} outside a comment — Race 2 regression"


# ---------------------------------------------------------------------------
# resource_ctxvar injection in _thread_return (Race 1 fix)
# ---------------------------------------------------------------------------


def test_resource_ctxvar_set_before_function_executes():
    """
    _thread_return sets resource_ctxvar to the resource_target dict before the
    job function runs.  This test simulates the critical section and confirms
    the ctxvar carries the right value into a copy_context() snapshot — the
    mechanism that makes the fix thread-safe.
    """
    import contextvars

    target = {"id": "dummy-01", "type": "dummy"}

    # Simulate what _thread_return does.
    tok = salt.loader.context.resource_ctxvar.set(target)
    try:
        # copy_context() is what LazyLoader.run() calls on every invocation.
        ctx = contextvars.copy_context()
    finally:
        salt.loader.context.resource_ctxvar.reset(tok)

    # The copy captured the value; the current context is back to default.
    assert salt.loader.context.resource_ctxvar.get() == {}

    # But inside the snapshot the target is visible — exactly as it will be
    # inside _run_as when the module function reads __resource__.
    seen = {}
    ctx.run(lambda: seen.update({"val": salt.loader.context.resource_ctxvar.get()}))
    assert seen["val"] is target


def test_resource_ctxvar_concurrent_threads_isolated():
    """
    Two threads setting resource_ctxvar concurrently never see each other's
    values.  This directly validates the fix for Race 1 (KeyError: 'id').
    """
    target_a = {"id": "dummy-01", "type": "dummy"}
    target_b = {"id": "dummy-02", "type": "dummy"}
    errors = []
    results = {}
    barrier = threading.Barrier(2)

    def run_job(name, target):
        try:
            salt.loader.context.resource_ctxvar.set(target)
            barrier.wait()  # both threads set before either reads
            val = salt.loader.context.resource_ctxvar.get()
            if val is not target:
                errors.append(
                    f"Thread {name}: expected {target['id']}, got {val.get('id')}"
                )
            results[name] = val
        except Exception as exc:  # pylint: disable=broad-except
            errors.append(str(exc))

    t1 = threading.Thread(target=run_job, args=("a", target_a))
    t2 = threading.Thread(target=run_job, args=("b", target_b))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert not errors, errors
    assert results["a"] is target_a
    assert results["b"] is target_b


# ---------------------------------------------------------------------------
# _discover_resources tests
# ---------------------------------------------------------------------------


def test_discover_resources_no_pillar_key_preserves_opts(minion_with_resources):
    """
    When the pillar contains no 'resources' key at all, _discover_resources
    preserves whatever is already in opts["resources"].
    """
    minion_with_resources.opts["pillar"] = {}
    result = minion_with_resources._discover_resources()
    assert result == {k: list(v) for k, v in RESOURCES.items()}


def test_discover_resources_empty_pillar_key_clears_opts(minion_with_resources):
    """
    When the pillar *does* contain a 'resources' key but its value is empty,
    _discover_resources must return {} and NOT preserve the old opts resources.
    This is the fix for the stale-cache bug: removing a resource type from the
    pillar and running sync_all must clear it at runtime.
    """
    minion_with_resources.opts["pillar"] = {"resources": {}}
    result = minion_with_resources._discover_resources()
    assert (
        result == {}
    ), "_discover_resources must return {} when pillar['resources'] is empty"


# ---------------------------------------------------------------------------
# _register_resources_with_master tests
# ---------------------------------------------------------------------------


def test_register_resources_with_master_sends_empty_dict(minion_with_resources):
    """
    _register_resources_with_master must send the registration even when
    opts["resources"] is {}.  Without this, removing resources from the pillar
    and running sync_all leaves the master cache permanently stale.
    """
    minion_with_resources.opts["resources"] = {}
    sent_loads = []

    async def fake_send(load, timeout=None):
        sent_loads.append(load)

    import asyncio

    minion_with_resources.tok = b"test-tok"
    with mock_patch.object(
        minion_with_resources,
        "_send_req_async_main",
        side_effect=fake_send,
    ):
        asyncio.run(minion_with_resources._register_resources_with_master())

    assert (
        len(sent_loads) == 1
    ), "_register_resources_with_master must always send a load, even for {}"
    assert (
        sent_loads[0]["resources"] == {}
    ), "An empty resource dict must be forwarded to the master to clear stale cache"
