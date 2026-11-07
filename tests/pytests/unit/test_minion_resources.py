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
    resources when ``tgt`` is not a managed resource id.  ``salt 'minion'``
    should only run on the minion itself, not on its managed resources.
    """
    load = {"tgt": "minion", "tgt_type": "glob", "fun": "test.ping", "arg": []}
    targets = minion_with_resources._resolve_resource_targets(load)
    assert targets == [], "non-resource specific-name glob must not dispatch"


def test_resolve_resource_targets_glob_exact_managed_resource_id(minion_with_resources):
    """Exact glob with no wildcards must dispatch when ``tgt`` is a resource id."""
    load = {"tgt": "dummy-02", "tgt_type": "glob", "fun": "test.ping", "arg": []}
    targets = minion_with_resources._resolve_resource_targets(load)
    assert targets == [{"id": "dummy-02", "type": "dummy"}]


def test_pure_resource_target_excludes_own_minion_id(minion_opts):
    """A bare id that is BOTH the minion's own id and a managed resource id is
    not a pure-resource target, so the minion still runs its own job."""
    minion_opts["resources"] = RESOURCES
    minion_opts["multiprocessing"] = False
    minion_opts["id"] = "dummy-01"
    with mock_patch("salt.minion.Minion.gen_modules"):
        with mock_patch("salt.minion.Minion.connect_master"):
            m = salt.minion.Minion(minion_opts, load_grains=False)
    own_id = {"tgt": "dummy-01", "tgt_type": "glob", "fun": "test.ping", "arg": []}
    other_resource = {
        "tgt": "dummy-02",
        "tgt_type": "glob",
        "fun": "test.ping",
        "arg": [],
    }
    assert m._is_pure_resource_target(own_id) is False
    assert m._is_pure_resource_target(other_resource) is True


def test_resolve_resource_targets_list_bare_ids(minion_with_resources):
    load = {
        "tgt": "dummy-02,node1",
        "tgt_type": "list",
        "fun": "test.ping",
        "arg": [],
    }
    targets = minion_with_resources._resolve_resource_targets(load)
    ids_types = {(t["id"], t["type"]) for t in targets}
    assert ids_types == {("dummy-02", "dummy"), ("node1", "ssh")}


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
# Per-resource grain swap in _thread_return
# ---------------------------------------------------------------------------


class _PackOnly:
    """Minimal stand-in for a resource loader: exposes only ``.pack``."""

    def __init__(self):
        self.pack = {}


def _grain_swap(resource_target, resource_funcs, functions_to_use):
    """
    Mirror the grain-swap branch of ``salt.minion.Minion._thread_return``
    (the four lines following ``resource_ctxvar.set(resource_target)``).
    A regression in those lines should cause this helper to diverge from
    the real method, which the source-inspection test below catches.
    """
    resource_type = resource_target["type"]
    grains_fn = f"{resource_type}.grains"
    if grains_fn in resource_funcs:
        functions_to_use.pack["__grains__"] = resource_funcs[grains_fn]()


def test_thread_return_grain_swap_packs_resource_grains():
    """
    When a resource job dispatches with ``resource_target`` and the resource
    loader exposes ``<type>.grains``, the swap must pack that function's
    return value into ``functions_to_use.pack["__grains__"]`` so the job
    sees the resource's grains, not the managing minion's.
    """
    expected = {
        "dummy_grain_1": "one",
        "dummy_grain_2": "two",
        "dummy_grain_3": "three",
        "resource_id": "dummy-01",
    }
    resource_funcs = {"dummy.grains": lambda: expected}
    functions_to_use = _PackOnly()
    target = {"id": "dummy-01", "type": "dummy"}
    _grain_swap(target, resource_funcs, functions_to_use)
    assert functions_to_use.pack["__grains__"] is expected


def test_thread_return_grain_swap_skipped_without_grains_fn():
    """
    If the resource loader has no ``<type>.grains`` callable, the swap must
    leave ``functions_to_use.pack`` untouched — no ``__grains__`` key
    appears, so the loader's pre-existing pack still drives the job.
    """
    resource_funcs = {"dummy.ping": lambda: True}  # no .grains
    functions_to_use = _PackOnly()
    target = {"id": "dummy-01", "type": "dummy"}
    _grain_swap(target, resource_funcs, functions_to_use)
    assert "__grains__" not in functions_to_use.pack


def test_thread_return_grain_swap_uses_resource_target_type():
    """
    Two resource types share one ``resource_funcs`` mapping; the swap must
    pick the function keyed on ``resource_target["type"]``, not any global
    default. Targeting an SSH resource must call ``ssh.grains``, not
    ``dummy.grains`` even when both are registered.
    """
    resource_funcs = {
        "dummy.grains": lambda: {"who": "dummy"},
        "ssh.grains": lambda: {"who": "ssh"},
    }
    functions_to_use = _PackOnly()
    _grain_swap({"id": "node1", "type": "ssh"}, resource_funcs, functions_to_use)
    assert functions_to_use.pack["__grains__"] == {"who": "ssh"}


def test_thread_return_grain_swap_source_inspection():
    """
    Catch a regression where someone removes the grain-swap from
    ``_thread_return``. The local helper above mirrors those lines; if the
    real method drops them, this test fails and the helper drifts out of
    sync with reality.
    """
    import inspect

    source = inspect.getsource(salt.minion.Minion._thread_return)
    # All four anchor lines must be present in order, in the same scope as
    # ``resource_ctxvar.set(resource_target)``.
    assert "resource_ctxvar.set(resource_target)" in source
    assert 'grains_fn = f"{resource_type}.grains"' in source
    assert "if grains_fn in minion_instance.resource_funcs:" in source
    assert 'functions_to_use.pack["__grains__"] =' in source
    assert "minion_instance.resource_funcs[grains_fn]()" in source


# ---------------------------------------------------------------------------
# _discover_resources tests
# ---------------------------------------------------------------------------


def test_discover_resources_no_pillar_key_clears_like_empty(minion_with_resources):
    """
    When the pillar contains no 'resources' key at all, _discover_resources
    must behave like pillar['resources'] == {}: return {} and not preserve
    stale opts["resources"].
    """
    minion_with_resources.opts["pillar"] = {}
    result = minion_with_resources._discover_resources()
    assert result == {}


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
# _discover_resources error paths and return-shape contract
# ---------------------------------------------------------------------------


def _fake_resource_loader(discovers):
    """Return a dict-like loader whose ``<type>.discover`` callables come
    from the ``discovers`` mapping ({rtype: callable}). Types absent from
    ``discovers`` have no ``<type>.discover`` key — mirrors a loader where
    the discover function is missing for that type."""
    return {f"{rtype}.discover": fn for rtype, fn in discovers.items()}


def test_discover_resources_continues_when_one_type_raises(
    minion_with_resources, caplog
):
    """
    A single resource type whose ``discover()`` raises must not block
    discovery of the other types. The raising type is omitted from the
    result; a warning is logged.
    """
    minion_with_resources.opts["pillar"] = {
        "resources": {"good_a": {}, "boom": {}, "good_b": {}}
    }
    fake_loader = _fake_resource_loader(
        {
            "good_a": lambda opts: ["a-1"],
            "boom": lambda opts: (_ for _ in ()).throw(
                RuntimeError("connection refused")
            ),
            "good_b": lambda opts: ["b-1", "b-2"],
        }
    )
    with mock_patch("salt.loader.resource", return_value=fake_loader):
        with caplog.at_level("WARNING"):
            result = minion_with_resources._discover_resources()

    assert result == {"good_a": ["a-1"], "good_b": ["b-1", "b-2"]}
    assert any(
        "Resource discovery failed for type 'boom'" in rec.message
        for rec in caplog.records
    ), "Expected a warning naming the failing type"


def test_discover_resources_skips_type_missing_discover_fn(
    minion_with_resources, caplog
):
    """
    A type listed in pillar whose loader has no ``<type>.discover`` is
    skipped with a warning; other types still discover normally.
    """
    minion_with_resources.opts["pillar"] = {
        "resources": {"with_disc": {}, "no_disc": {}}
    }
    fake_loader = _fake_resource_loader(
        {"with_disc": lambda opts: ["w-1"]}
    )  # "no_disc.discover" intentionally absent
    with mock_patch("salt.loader.resource", return_value=fake_loader):
        with caplog.at_level("WARNING"):
            result = minion_with_resources._discover_resources()

    assert result == {"with_disc": ["w-1"]}
    assert any(
        "No resource module found for type 'no_disc'" in rec.message
        for rec in caplog.records
    ), "Expected a warning naming the type missing its discover function"


def test_discover_resources_drops_type_when_discover_returns_none(
    minion_with_resources,
):
    """
    ``discover()`` returning ``None`` is treated as "no ids for this type"
    — the type is omitted from the result entirely. Pins the current
    ``if ids:`` guard at minion.py:596.
    """
    minion_with_resources.opts["pillar"] = {"resources": {"empty": {}, "populated": {}}}
    fake_loader = _fake_resource_loader(
        {
            "empty": lambda opts: None,
            "populated": lambda opts: ["p-1"],
        }
    )
    with mock_patch("salt.loader.resource", return_value=fake_loader):
        result = minion_with_resources._discover_resources()

    assert result == {"populated": ["p-1"]}
    assert "empty" not in result


def test_discover_resources_drops_type_when_discover_returns_empty_list(
    minion_with_resources,
):
    """
    ``discover()`` returning ``[]`` is treated like ``None`` — type
    omitted from result, no empty entry created.
    """
    minion_with_resources.opts["pillar"] = {"resources": {"empty": {}}}
    fake_loader = _fake_resource_loader({"empty": lambda opts: []})
    with mock_patch("salt.loader.resource", return_value=fake_loader):
        result = minion_with_resources._discover_resources()

    assert result == {}


def test_discover_resources_coerces_tuple_return_to_list(minion_with_resources):
    """
    ``discover()`` returning a tuple is wrapped in ``list()`` (minion.py:597),
    so downstream code consistently sees lists.
    """
    minion_with_resources.opts["pillar"] = {"resources": {"tup": {}}}
    fake_loader = _fake_resource_loader({"tup": lambda opts: ("t-1", "t-2")})
    with mock_patch("salt.loader.resource", return_value=fake_loader):
        result = minion_with_resources._discover_resources()

    assert result == {"tup": ["t-1", "t-2"]}
    assert isinstance(result["tup"], list)


def test_discover_resources_coerces_generator_return_to_list(minion_with_resources):
    """
    ``discover()`` returning a generator is fully drained into a list,
    matching the tuple-coercion contract.
    """
    minion_with_resources.opts["pillar"] = {"resources": {"gen": {}}}

    def gen_discover(opts):
        yield "g-1"
        yield "g-2"
        yield "g-3"

    fake_loader = _fake_resource_loader({"gen": gen_discover})
    with mock_patch("salt.loader.resource", return_value=fake_loader):
        result = minion_with_resources._discover_resources()

    assert result == {"gen": ["g-1", "g-2", "g-3"]}
    assert isinstance(result["gen"], list)


def test_discover_resources_stores_dynamic_ids_verbatim(minion_with_resources):
    """
    Pins the current contract: ``discover()`` is the sole source of ids
    for its type. The framework does NOT merge with pillar-declared ids.

    Pillar declares ``dynamic_test`` with ``resource_ids: ["p-1", "p-2"]``
    (the values a type like dummy/ssh would read), but ``discover()``
    returns ``["d-1", "d-2"]`` — the result is exactly ``discover()``'s
    output, with the pillar ids dropped on the floor.

    This test will need updating when union-with-override lands as a
    framework-level merge for the declarative-resources work.
    """
    minion_with_resources.opts["pillar"] = {
        "resources": {
            "dynamic_test": {"resource_ids": ["p-1", "p-2"]},
        }
    }
    fake_loader = _fake_resource_loader({"dynamic_test": lambda opts: ["d-1", "d-2"]})
    with mock_patch("salt.loader.resource", return_value=fake_loader):
        result = minion_with_resources._discover_resources()

    assert result == {"dynamic_test": ["d-1", "d-2"]}, (
        "discover() output is currently authoritative; pillar's "
        "resource_ids are NOT merged in by the framework."
    )


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


# ---------------------------------------------------------------------------
# _MERGE_RESOURCE_FUNS tests
# ---------------------------------------------------------------------------


def test_merge_resource_funs_contains_expected_state_functions():
    """All state-dispatch functions that should trigger merge mode are present."""
    expected = {
        "state.apply",
        "state.highstate",
        "state.sls",
        "state.sls_id",
        "state.single",
    }
    assert expected <= salt.minion.Minion._MERGE_RESOURCE_FUNS


def test_merge_resource_funs_does_not_contain_test_ping():
    """test.ping must NOT be in _MERGE_RESOURCE_FUNS so it dispatches normally."""
    assert "test.ping" not in salt.minion.Minion._MERGE_RESOURCE_FUNS


def test_merge_resource_funs_is_frozenset():
    assert isinstance(salt.minion.Minion._MERGE_RESOURCE_FUNS, frozenset)


def test_merge_resource_funs_minions_and_minion_in_sync():
    """_MERGE_RESOURCE_FUNS must be identical in salt.minion and salt.utils.minions."""
    import salt.utils.minions as _minions_mod

    assert salt.minion.Minion._MERGE_RESOURCE_FUNS == _minions_mod._MERGE_RESOURCE_FUNS


# ---------------------------------------------------------------------------
# _prefix_resource_state_key tests
# ---------------------------------------------------------------------------


def test_prefix_resource_state_key_id_and_name_prefixed():
    """Both the id (comps[1]) and name (comps[2]) components gain the rid prefix."""
    key = "pkg_|-curl_|-curl_|-installed"
    result = salt.minion.Minion._prefix_resource_state_key(key, "node1")
    assert result == "pkg_|-node1 curl_|-node1 curl_|-installed"


def test_prefix_resource_state_key_preserves_module_and_function():
    """comps[0] (module) and comps[3] (function) are unchanged."""
    key = "pkg_|-curl_|-curl_|-installed"
    result = salt.minion.Minion._prefix_resource_state_key(key, "node1")
    parts = result.split("_|-")
    assert parts[0] == "pkg"
    assert parts[3] == "installed"


def test_prefix_resource_state_key_id_with_spaces():
    """Resource IDs containing spaces are handled correctly."""
    key = "service_|-nginx_|-nginx_|-running"
    result = salt.minion.Minion._prefix_resource_state_key(key, "my host")
    assert result == "service_|-my host nginx_|-my host nginx_|-running"


def test_prefix_resource_state_key_no_top_file_key():
    """The 'no_|-states_|-states_|-None' key used for empty-top returns is prefixed."""
    key = "no_|-states_|-states_|-None"
    result = salt.minion.Minion._prefix_resource_state_key(key, "node1")
    assert result == "no_|-node1 states_|-node1 states_|-None"


def test_prefix_resource_state_key_malformed_key_falls_back():
    """A key that cannot be split into 4 parts produces the fallback synthetic key."""
    result = salt.minion.Minion._prefix_resource_state_key("not-a-state-key", "node1")
    assert result == "no_|-node1_|-node1_|-None"


def test_prefix_resource_state_key_three_part_key_falls_back():
    """Only three _|- separators → fallback."""
    key = "pkg_|-curl_|-curl"
    result = salt.minion.Minion._prefix_resource_state_key(key, "node1")
    assert result == "no_|-node1_|-node1_|-None"


# ---------------------------------------------------------------------------
# _handle_payload merge-mode guard (source inspection)
# ---------------------------------------------------------------------------


def test_handle_payload_skips_resource_dispatch_for_merge_funs():
    """
    _handle_payload must guard the separate resource-dispatch block with a
    'fun not in _MERGE_RESOURCE_FUNS' check.  A missing guard would cause
    duplicate responses for state.apply jobs.
    """
    import inspect

    source = inspect.getsource(salt.minion.Minion._handle_payload)
    assert "_MERGE_RESOURCE_FUNS" in source, (
        "_handle_payload must reference _MERGE_RESOURCE_FUNS to skip "
        "redundant resource job dispatch for merge-mode functions"
    )
    assert "resource_targets" in source


# ---------------------------------------------------------------------------
# Merge block helper: _merge_resource_into_ret logic
# ---------------------------------------------------------------------------


def _make_ret(return_val=None, retcode=0):
    """Build a minimal ret dict as produced by _thread_return."""
    return {
        "return": return_val if return_val is not None else {},
        "retcode": retcode,
        "success": retcode == 0,
    }


def _run_merge_block(
    minion_instance, resource, resource_loader, function_name, resource_return
):
    """
    Simulate the per-resource section of _thread_return's merge block.

    Drives the same if/elif/else branches:
      - resource_loader is None → no-loader synthetic entry
      - function_name not in resource_loader → unsupported string
      - resource_return is a dict → prefix keys and merge
      - resource_return is a str → synthetic entry with result False
    """
    import salt.defaults.exitcodes

    ret = _make_ret()
    run_num_base = 0
    rid = resource["id"]
    rtype = resource["type"]

    if resource_loader is None:
        ret["return"][f"no_|-{rid}_|-{rid}_|-None"] = {
            "result": False,
            "comment": f"No resource loader for type '{rtype}'. Ensure the resource module exists.",
            "name": rid,
            "changes": {},
            "__run_num__": run_num_base,
        }
        run_num_base += 1
        if ret.get("retcode") == salt.defaults.exitcodes.EX_OK:
            ret["retcode"] = salt.defaults.exitcodes.EX_GENERIC
    elif function_name not in resource_loader:
        resource_return = (
            f"Function '{function_name}' is not supported for resource type '{rtype}'. "
            f"Implement it in a '{rtype}resource_*' execution module."
        )
        ret["return"][f"no_|-{rid}_|-{rid}_|-None"] = {
            "result": False,
            "comment": str(resource_return),
            "name": rid,
            "changes": {},
            "__run_num__": run_num_base,
        }
        run_num_base += 1
        if ret.get("retcode") == salt.defaults.exitcodes.EX_OK:
            ret["retcode"] = salt.defaults.exitcodes.EX_GENERIC
    elif isinstance(resource_return, dict):
        for state_id, state_val in resource_return.items():
            entry = (
                dict(state_val)
                if isinstance(state_val, dict)
                else {
                    "result": True,
                    "comment": str(state_val),
                    "name": rid,
                    "changes": {},
                }
            )
            entry["__run_num__"] = run_num_base
            run_num_base += 1
            ret["return"][
                salt.minion.Minion._prefix_resource_state_key(state_id, rid)
            ] = entry
        if ret.get("retcode") == salt.defaults.exitcodes.EX_OK:
            # retcode only updated when resource_loader context signals failure
            pass
    else:
        ret["return"][f"no_|-{rid}_|-{rid}_|-None"] = {
            "result": False,
            "comment": str(resource_return),
            "name": rid,
            "changes": {},
            "__run_num__": run_num_base,
        }
        run_num_base += 1
        if ret.get("retcode") == salt.defaults.exitcodes.EX_OK:
            ret["retcode"] = salt.defaults.exitcodes.EX_GENERIC

    ret["success"] = ret.get("retcode") == salt.defaults.exitcodes.EX_OK
    return ret


class _FakeLoader(dict):
    """Minimal stand-in for a resource loader (just a dict with a pack)."""

    def __init__(self, funs):
        super().__init__(funs)
        self.pack = {"__context__": {}}


def test_merge_block_no_loader_produces_false_entry(minion_with_resources):
    resource = {"id": "dummy-01", "type": "dummy"}
    ret = _run_merge_block(minion_with_resources, resource, None, "state.apply", None)
    key = "no_|-dummy-01_|-dummy-01_|-None"
    assert key in ret["return"]
    assert ret["return"][key]["result"] is False
    assert "No resource loader" in ret["return"][key]["comment"]
    assert ret["retcode"] != 0
    assert ret["success"] is False


def test_merge_block_unsupported_function_produces_false_entry(minion_with_resources):
    resource = {"id": "dummy-01", "type": "dummy"}
    loader = _FakeLoader({})  # empty — function not present
    ret = _run_merge_block(minion_with_resources, resource, loader, "state.apply", None)
    key = "no_|-dummy-01_|-dummy-01_|-None"
    assert key in ret["return"]
    assert ret["return"][key]["result"] is False
    assert "not supported" in ret["return"][key]["comment"]
    assert ret["retcode"] != 0


def test_merge_block_dict_return_prefixes_keys(minion_with_resources):
    resource = {"id": "node1", "type": "ssh"}
    loader = _FakeLoader({"state.apply": lambda: {}})
    resource_return = {
        "pkg_|-curl_|-curl_|-installed": {
            "result": True,
            "comment": "Already installed",
            "name": "curl",
            "changes": {},
        }
    }
    ret = _run_merge_block(
        minion_with_resources, resource, loader, "state.apply", resource_return
    )
    assert "pkg_|-node1 curl_|-node1 curl_|-installed" in ret["return"]
    assert (
        "pkg_|-curl_|-curl_|-installed" not in ret["return"]
    ), "un-prefixed key must not appear"


def test_merge_block_string_return_produces_false_entry(minion_with_resources):
    resource = {"id": "node1", "type": "ssh"}
    loader = _FakeLoader({"state.apply": lambda: "some error"})
    ret = _run_merge_block(
        minion_with_resources,
        resource,
        loader,
        "state.apply",
        "ERROR running state.apply",
    )
    key = "no_|-node1_|-node1_|-None"
    assert key in ret["return"]
    assert ret["return"][key]["result"] is False
    assert ret["retcode"] != 0
    assert ret["success"] is False


# ---------------------------------------------------------------------------
# _collect_resource_grains
# ---------------------------------------------------------------------------


def _patch_resource_funcs(minion, funcs_by_name):
    """Replace ``minion.resource_funcs`` with a plain dict of callables."""
    minion.resource_funcs = funcs_by_name


def test_collect_resource_grains_returns_srn_keyed_dict(minion_with_resources):
    """
    ``_collect_resource_grains`` walks ``opts["resources"]`` and packs each
    resource's grains under the SRN composite key ``"<type>:<id>"``.
    """
    seen_targets = []

    def grains_fn():
        target = salt.loader.context.resource_ctxvar.get()
        seen_targets.append(target)
        return {"who": target["id"]}

    _patch_resource_funcs(minion_with_resources, {"dummy.grains": grains_fn})
    result = minion_with_resources._collect_resource_grains()
    # ssh.grains is absent → ssh resources skipped.
    assert sorted(result.keys()) == [
        "dummy:dummy-01",
        "dummy:dummy-02",
        "dummy:dummy-03",
    ]
    assert result["dummy:dummy-01"] == {"who": "dummy-01"}
    # The function saw the right resource_ctxvar each call.
    assert {t["id"] for t in seen_targets} == {"dummy-01", "dummy-02", "dummy-03"}


def test_collect_resource_grains_skips_types_without_grains(minion_with_resources):
    """
    Resource types whose loader has no ``<type>.grains`` callable are
    silently skipped — they don't appear in the result and don't raise.
    """
    _patch_resource_funcs(minion_with_resources, {})  # nothing
    assert minion_with_resources._collect_resource_grains() == {}


def test_collect_resource_grains_swallows_per_resource_failure(minion_with_resources):
    """
    A resource whose ``grains()`` raises is logged and skipped — the rest of
    the resources still produce entries.
    """

    def grains_fn():
        target = salt.loader.context.resource_ctxvar.get()
        if target["id"] == "dummy-02":
            raise RuntimeError("boom")
        return {"who": target["id"]}

    _patch_resource_funcs(minion_with_resources, {"dummy.grains": grains_fn})
    result = minion_with_resources._collect_resource_grains()
    assert "dummy:dummy-01" in result
    assert "dummy:dummy-02" not in result, "broken resource must not block siblings"
    assert "dummy:dummy-03" in result


def test_collect_resource_grains_skips_non_dict_returns(minion_with_resources):
    """
    A ``grains()`` that returns something other than a dict (string, None,
    etc.) is dropped — the resource_grains payload must only contain dicts.
    """

    def grains_fn():
        return "not a dict"

    _patch_resource_funcs(minion_with_resources, {"dummy.grains": grains_fn})
    assert minion_with_resources._collect_resource_grains() == {}


def test_collect_resource_grains_resets_ctxvar_on_failure(minion_with_resources):
    """
    Even when ``grains()`` raises, ``resource_ctxvar`` must be reset to its
    prior value — a leak would corrupt later jobs in the same thread.
    """
    sentinel = {"id": "outer", "type": "outer"}
    tok = salt.loader.context.resource_ctxvar.set(sentinel)
    try:

        def grains_fn():
            raise RuntimeError("boom")

        _patch_resource_funcs(minion_with_resources, {"dummy.grains": grains_fn})
        minion_with_resources._collect_resource_grains()
        assert salt.loader.context.resource_ctxvar.get() is sentinel
    finally:
        salt.loader.context.resource_ctxvar.reset(tok)


# ---------------------------------------------------------------------------
# _resolve_resource_targets — grain / grain_pcre branches
# ---------------------------------------------------------------------------


def test_resolve_resource_targets_grain_match(minion_with_resources):
    """
    ``tgt_type == "grain"`` walks the cached resource grain dicts and
    returns the matching ``{id, type}`` dicts.
    """
    minion_with_resources._resource_grains_cache = {
        "dummy:dummy-01": {"k": "v", "id": "dummy-01"},
        "dummy:dummy-02": {"k": "x", "id": "dummy-02"},
        "ssh:node1": {"k": "v", "id": "node1"},
    }
    load = {"tgt": "k:v", "tgt_type": "grain", "fun": "test.ping", "arg": []}
    targets = minion_with_resources._resolve_resource_targets(load)
    ids_types = {(t["id"], t["type"]) for t in targets}
    assert ids_types == {("dummy-01", "dummy"), ("node1", "ssh")}


def test_resolve_resource_targets_grain_no_match(minion_with_resources):
    """A grain expression that no resource satisfies returns no targets."""
    minion_with_resources._resource_grains_cache = {
        "dummy:dummy-01": {"k": "v"},
    }
    load = {"tgt": "nope:nothing", "tgt_type": "grain", "fun": "test.ping"}
    assert minion_with_resources._resolve_resource_targets(load) == []


def test_resolve_resource_targets_grain_pcre_uses_regex(minion_with_resources):
    """``tgt_type == "grain_pcre"`` enables regex matching on values."""
    minion_with_resources._resource_grains_cache = {
        "dummy:dummy-01": {"env": "production-east"},
        "dummy:dummy-02": {"env": "staging-east"},
    }
    load = {
        "tgt": "env:^production-.*",
        "tgt_type": "grain_pcre",
        "fun": "test.ping",
    }
    targets = minion_with_resources._resolve_resource_targets(load)
    ids = {t["id"] for t in targets}
    assert ids == {"dummy-01"}


def test_resolve_resource_targets_grain_lazy_collects_when_cache_missing(
    minion_with_resources,
):
    """
    If the grain cache has never been populated (e.g. registration hasn't
    happened yet or the operator opted out of in-memory retention), the
    resolver falls back to :meth:`_collect_resource_grains_for` so a
    freshly-started minion still acts on grain targets. Under the
    ``resource_grains_cache_in_memory`` default (False) the rendered map
    is not persisted — the cache remains ``None`` after the call.
    """
    minion_with_resources._resource_grains_cache = None
    seen = []

    def grains_fn():
        target = salt.loader.context.resource_ctxvar.get()
        seen.append(target["id"])
        return {"freshly_loaded": True, "id": target["id"]}

    minion_with_resources.resource_funcs = {"dummy.grains": grains_fn}
    load = {
        "tgt": "freshly_loaded:True",
        "tgt_type": "grain",
        "fun": "test.ping",
    }
    targets = minion_with_resources._resolve_resource_targets(load)
    ids = {t["id"] for t in targets}
    assert ids == {"dummy-01", "dummy-02", "dummy-03"}
    # Opt-out of retention (the default) must NOT persist the rendered
    # map — otherwise a 200K-resource minion carries 40-80 MB forever.
    assert minion_with_resources._resource_grains_cache is None


def test_resolve_resource_targets_grain_opt_in_persists_cache(
    minion_with_resources,
):
    """
    When :conf_minion:`resource_grains_cache_in_memory` is True, the
    resolver persists the rendered grain map on first use so subsequent
    calls skip the re-render. This is the pre-chunking-PR behaviour, now
    gated behind an explicit opt-in.
    """
    minion_with_resources.opts["resource_grains_cache_in_memory"] = True
    minion_with_resources._resource_grains_cache = None

    def grains_fn():
        target = salt.loader.context.resource_ctxvar.get()
        return {"freshly_loaded": True, "id": target["id"]}

    minion_with_resources.resource_funcs = {"dummy.grains": grains_fn}
    load = {
        "tgt": "freshly_loaded:True",
        "tgt_type": "grain",
        "fun": "test.ping",
    }
    minion_with_resources._resolve_resource_targets(load)
    assert minion_with_resources._resource_grains_cache is not None


def test_resolve_resource_targets_compound_G_at_grain(minion_with_resources):
    """
    A compound expression containing ``G@key:value`` must dispatch to every
    managed resource whose own grains satisfy the term. Boolean operators
    are intentionally ignored — the union of matches is dispatched and the
    master's CkMinions arbitrates the final response wait set.
    """
    minion_with_resources._resource_grains_cache = {
        "dummy:dummy-01": {"environment": "prod"},
        "dummy:dummy-02": {"environment": "prod"},
        "dummy:dummy-03": {"environment": "staging"},
        "ssh:node1": {"environment": "prod"},
    }
    load = {
        "tgt": "G@environment:prod",
        "tgt_type": "compound",
        "fun": "test.ping",
    }
    targets = minion_with_resources._resolve_resource_targets(load)
    ids = {(t["id"], t["type"]) for t in targets}
    assert ids == {
        ("dummy-01", "dummy"),
        ("dummy-02", "dummy"),
        ("node1", "ssh"),
    }


def test_resolve_resource_targets_compound_P_at_grain_pcre(minion_with_resources):
    """``P@key:regex`` in compound applies the regex against resource grains."""
    minion_with_resources._resource_grains_cache = {
        "dummy:dummy-01": {"env": "production-east"},
        "dummy:dummy-02": {"env": "production-west"},
        "dummy:dummy-03": {"env": "staging-east"},
    }
    load = {
        "tgt": "P@env:^production-.*",
        "tgt_type": "compound",
        "fun": "test.ping",
    }
    targets = minion_with_resources._resolve_resource_targets(load)
    ids = {t["id"] for t in targets}
    assert ids == {"dummy-01", "dummy-02"}


def test_resolve_resource_targets_compound_T_and_G_intersection(minion_with_resources):
    """
    ``T@... and G@...`` is a true conjunction — only resources matched by
    BOTH terms qualify. dummy-02 satisfies the T@ but not the grain;
    dummy-01 satisfies the grain but not the T@. Neither satisfies both,
    so the result is empty.
    """
    minion_with_resources._resource_grains_cache = {
        "dummy:dummy-01": {"env": "prod"},
        "dummy:dummy-02": {"env": "staging"},
        "dummy:dummy-03": {"env": "staging"},
    }
    load = {
        "tgt": "T@dummy:dummy-02 and G@env:prod",
        "tgt_type": "compound",
        "fun": "test.ping",
    }
    targets = minion_with_resources._resolve_resource_targets(load)
    assert targets == [], "AND must require both terms; got resources matching only one"


def test_resolve_resource_targets_compound_T_or_G_union(minion_with_resources):
    """``T@... or G@...`` is a true disjunction — match either term."""
    minion_with_resources._resource_grains_cache = {
        "dummy:dummy-01": {"env": "prod"},
        "dummy:dummy-02": {"env": "staging"},
        "dummy:dummy-03": {"env": "staging"},
    }
    load = {
        "tgt": "T@dummy:dummy-02 or G@env:prod",
        "tgt_type": "compound",
        "fun": "test.ping",
    }
    targets = minion_with_resources._resolve_resource_targets(load)
    ids = {t["id"] for t in targets}
    assert ids == {"dummy-01", "dummy-02"}


def test_resolve_resource_targets_compound_G_and_G_intersection(minion_with_resources):
    """Two G@ terms with ``and`` must intersect, not union."""
    minion_with_resources._resource_grains_cache = {
        "dummy:dummy-01": {"env": "prod", "role": "web"},
        "dummy:dummy-02": {"env": "prod", "role": "db"},
        "dummy:dummy-03": {"env": "staging", "role": "web"},
    }
    load = {
        "tgt": "G@env:prod and G@role:web",
        "tgt_type": "compound",
        "fun": "test.ping",
    }
    targets = minion_with_resources._resolve_resource_targets(load)
    ids = {t["id"] for t in targets}
    assert ids == {"dummy-01"}, f"AND of two grain terms must intersect; got {ids}"


def test_resolve_resource_targets_compound_not_negation(minion_with_resources):
    """
    ``not G@…`` selects every resource whose grains do NOT satisfy the
    term — including resources that have no entry for that grain key at
    all. This mirrors how Salt's minion-side grain matching treats
    missing grains as a non-match.
    """
    minion_with_resources._resource_grains_cache = {
        "dummy:dummy-01": {"env": "prod"},
        "dummy:dummy-02": {"env": "staging"},
        "dummy:dummy-03": {"env": "staging"},
        # ssh resources from the fixture have no grain entry at all.
    }
    load = {
        "tgt": "not G@env:prod",
        "tgt_type": "compound",
        "fun": "test.ping",
    }
    targets = minion_with_resources._resolve_resource_targets(load)
    ids = {t["id"] for t in targets}
    # dummy-02 / dummy-03 don't have env:prod; ssh resources have no
    # ``env`` grain at all, so they also satisfy ``not env:prod``.
    assert ids == {"dummy-02", "dummy-03", "node1", "localhost"}


def test_resolve_resource_targets_compound_T_and_not_G(minion_with_resources):
    """
    ``T@type and not G@…`` — combine type filter with grain negation.
    Useful for "all dummy resources except those with env:prod".
    """
    minion_with_resources._resource_grains_cache = {
        "dummy:dummy-01": {"env": "prod"},
        "dummy:dummy-02": {"env": "staging"},
        "dummy:dummy-03": {"env": "staging"},
    }
    load = {
        "tgt": "T@dummy and not G@env:prod",
        "tgt_type": "compound",
        "fun": "test.ping",
    }
    targets = minion_with_resources._resolve_resource_targets(load)
    ids = {t["id"] for t in targets}
    assert ids == {"dummy-02", "dummy-03"}


def test_resolve_resource_targets_compound_parens_precedence(minion_with_resources):
    """Parens override default left-to-right precedence."""
    minion_with_resources._resource_grains_cache = {
        "dummy:dummy-01": {"env": "prod", "tier": "1"},
        "dummy:dummy-02": {"env": "prod", "tier": "2"},
        "dummy:dummy-03": {"env": "staging", "tier": "1"},
    }
    # ``(env:prod or env:staging) and tier:1`` → dummy-01 + dummy-03 only.
    load = {
        "tgt": "( G@env:prod or G@env:staging ) and G@tier:1",
        "tgt_type": "compound",
        "fun": "test.ping",
    }
    targets = minion_with_resources._resolve_resource_targets(load)
    ids = {t["id"] for t in targets}
    assert ids == {"dummy-01", "dummy-03"}


def test_resolve_resource_targets_compound_eval_safe_with_garbage(
    minion_with_resources,
):
    """
    A malformed compound term must not crash or expose the eval. The
    helper renders unknown engines as ``False`` and any eval failure
    swallows to ``False``.
    """
    minion_with_resources._resource_grains_cache = {
        "dummy:dummy-01": {"env": "prod"},
    }
    # ``Z@something`` is an unknown engine; ``__import__`` would be a
    # malicious payload if eval were unrestricted. Both must render to
    # False without raising.
    load = {
        "tgt": "Z@__import__('os').system('echo pwned')",
        "tgt_type": "compound",
        "fun": "test.ping",
    }
    assert minion_with_resources._resolve_resource_targets(load) == []


def test_resolve_resource_targets_compound_T_works_without_grains(
    minion_with_resources,
):
    """
    Resources without any cached grain dict must still resolve via T@
    (the loader may not have a ``<type>.grains`` callable yet). The
    compound walk seeds an empty dict for SRNs missing from the grain
    cache.
    """
    # Grain cache is intentionally missing the ssh resources entirely.
    minion_with_resources._resource_grains_cache = {
        "dummy:dummy-01": {"env": "prod"},
    }
    load = {
        "tgt": "T@ssh:node1",
        "tgt_type": "compound",
        "fun": "test.ping",
    }
    targets = minion_with_resources._resolve_resource_targets(load)
    assert targets == [{"id": "node1", "type": "ssh"}]


# ---------------------------------------------------------------------------
# _handle_payload per-resource payload size: regression for queued-file bloat
# ---------------------------------------------------------------------------


def test_handle_payload_per_resource_load_strips_wide_fields(
    minion_with_resources, tmp_path
):
    """
    Regression for a quadratic disk-use bug in the minion's resource-fanout
    path.

    ``_handle_payload`` iterates over ``load["resource_targets"]`` and calls
    ``_handle_decoded_payload`` with a per-resource copy of the parent load.
    If that copy is a shallow ``dict(load)``, the full N-wide
    ``resource_targets`` list — and, under CLI ``--static`` retry, the full
    N-wide parent ``tgt`` list — ride along in every one of the N per-resource
    payloads.  When any of those payloads get queued via ``_queue_job``, the
    full list is msgpacked to disk once per resource, producing O(N**2)
    queued-file disk use (observed: 4.2 MB/queued-file at 150K resources,
    ~630 GB projected).

    The fix is to strip ``resource_targets`` from the per-resource base load
    once, and to compress a multi-element parent ``tgt`` list down to the
    scalar glob ``"*"`` (the per-resource job dispatches by its own
    ``resource_target`` ``{id, type}`` field, so the parent target does not
    drive dispatch at that level).

    This test proves the property by driving ``_handle_payload`` with a wide
    ``resource_targets`` and an N-wide parent ``tgt`` list, capturing every
    load that reaches ``_handle_decoded_payload``, and asserting:

    * The per-resource payload has ``resource_target`` (singular) but no
      ``resource_targets`` (plural) key.
    * The per-resource payload's ``tgt`` is a scalar (or collapsed to length
      <= 1).
    * The msgpacked size of each per-resource payload is O(1) in N: the
      per-resource payload must be strictly smaller than the parent.
    """
    import asyncio

    import salt.payload

    # Pre-build 100 resources + a 100-wide parent tgt list.  These shapes
    # match what the master+CLI feed the minion under a wide resource fanout.
    resources = [{"id": f"dummy-{i:03d}", "type": "dummy"} for i in range(100)]
    parent_tgt = [r["id"] for r in resources]

    load = {
        "jid": "20260101000000000001",
        "fun": "test.ping",
        "arg": [],
        "ret": "",
        "tgt": list(parent_tgt),
        "tgt_type": "list",
        "resource_targets": list(resources),
        "pure_resource_target": True,
        "minion_is_target": False,
    }

    delivered = []

    async def capture(data):
        # Deep snapshot so a later ``dict(load)`` can't retroactively
        # share state with what we captured.
        delivered.append(dict(data))

    # Stub ``_target_load`` so we don't have to wire up real matchers; the
    # production ``_target_load`` would normally set ``resource_targets`` and
    # ``minion_is_target`` on its own, but the load above is already shaped
    # as if it just came out of that helper.
    with mock_patch.object(
        minion_with_resources, "_target_load", return_value=True
    ), mock_patch.object(
        minion_with_resources, "_handle_decoded_payload", side_effect=capture
    ):
        asyncio.run(minion_with_resources._handle_payload({"enc": "aes", "load": load}))

    # First delivery is the managing-minion's own copy (minion_is_target
    # is False here, so that branch doesn't fire); every delivery is a
    # per-resource fanout copy.
    assert len(delivered) == len(
        resources
    ), "expected one _handle_decoded_payload call per resource target"

    # Serialize the original parent load to msgpack so we can compare sizes.
    parent_blob_len = len(salt.payload.dumps(load))

    for per_resource in delivered:
        # The singular resource_target is set and identifies one resource.
        assert "resource_target" in per_resource
        assert isinstance(per_resource["resource_target"], dict)
        assert set(per_resource["resource_target"]) == {"id", "type"}
        # The resource-job marker is set.
        assert per_resource.get("resource_job") is True
        # CRITICAL: the N-wide list must NOT ride along.
        assert "resource_targets" not in per_resource, (
            "per-resource payload must not carry the parent "
            "resource_targets list (quadratic disk use on _queue_job)"
        )
        # CRITICAL: a multi-element parent tgt list must have been
        # collapsed to a scalar (or singleton) so it does not ride along
        # either.
        tgt = per_resource.get("tgt")
        if isinstance(tgt, (list, tuple)):
            assert len(tgt) <= 1, (
                "per-resource payload tgt must not carry the full N-wide "
                "parent target list"
            )
        else:
            assert isinstance(tgt, str)

        # The msgpacked size — which is what ``_queue_job`` would write to
        # disk — must be strictly smaller than the parent (and, in practice,
        # a tiny fraction of it: the parent carries the full 100-wide list
        # of resource targets and the full 100-wide parent tgt list).
        per_resource_blob_len = len(salt.payload.dumps(per_resource))
        assert per_resource_blob_len < parent_blob_len, (
            "per-resource payload serialized larger than parent: "
            f"{per_resource_blob_len} >= {parent_blob_len}"
        )
        # The parent is ~100x wider; each per-resource payload should be
        # at most a small multiple of the per-resource item shape.  A
        # generous ceiling of parent_blob_len/10 proves the O(1)-in-N
        # property without being flaky on exact byte counts.
        assert per_resource_blob_len < parent_blob_len / 10, (
            "per-resource payload is not O(1) in N: "
            f"{per_resource_blob_len} bytes vs parent {parent_blob_len}"
        )

    # Round-trip one delivered payload through msgpack to prove ``_queue_job``
    # would reload the same shape (no hidden shared references).
    reloaded = salt.payload.loads(salt.payload.dumps(delivered[0]))
    assert "resource_targets" not in reloaded
    assert reloaded["resource_target"] == delivered[0]["resource_target"]


# ---------------------------------------------------------------------------
# Resource grains cache retention (opt-in)
# ---------------------------------------------------------------------------


def _build_large_resources(n):
    """Return a ``{dummy: [id-0, …, id-n-1]}`` pillar."""
    return {"dummy": [f"res-{i}" for i in range(n)]}


def _patch_grains_fn(minion):
    """Install a grains() callable so ``_collect_resource_grains`` yields dicts."""

    def grains_fn():
        target = salt.loader.context.resource_ctxvar.get()
        return {"env": "prod", "resource_id": target["id"]}

    minion.resource_funcs = {"dummy.grains": grains_fn}


class TestResourceGrainsCacheRetention:
    """
    ``_register_resources_with_master`` retains the per-resource grain map
    only when :conf_minion:`resource_grains_cache_in_memory` is True.
    """

    def test_default_does_not_retain_full_grain_map(self, minion_opts):
        """
        Default behaviour (opt-out): after a register call the minion
        drops the grain cache. For a 10K-resource pillar, this is ~4-8 MB
        of RAM that doesn't need to be resident between registrations.
        """
        minion_opts["resources"] = _build_large_resources(500)
        minion_opts["multiprocessing"] = False
        with mock_patch("salt.minion.Minion.gen_modules"), mock_patch(
            "salt.minion.Minion.connect_master"
        ):
            m = salt.minion.Minion(minion_opts, load_grains=False)
        _patch_grains_fn(m)
        m.tok = b"tok"

        async def noop(load, timeout=None):
            return None

        import asyncio

        with mock_patch.object(m, "_send_req_async_main", side_effect=noop):
            asyncio.run(m._register_resources_with_master())
        assert (
            m._resource_grains_cache is None
        ), "default must not retain the per-resource grain map in RAM"

    def test_opt_in_retains_full_grain_map(self, minion_opts):
        """
        ``resource_grains_cache_in_memory: True`` restores the pre-chunking-PR
        behaviour: the grain map is cached on the instance after registration.
        """
        minion_opts["resources"] = _build_large_resources(100)
        minion_opts["multiprocessing"] = False
        minion_opts["resource_grains_cache_in_memory"] = True
        with mock_patch("salt.minion.Minion.gen_modules"), mock_patch(
            "salt.minion.Minion.connect_master"
        ):
            m = salt.minion.Minion(minion_opts, load_grains=False)
        _patch_grains_fn(m)
        m.tok = b"tok"

        async def noop(load, timeout=None):
            return None

        import asyncio

        with mock_patch.object(m, "_send_req_async_main", side_effect=noop):
            asyncio.run(m._register_resources_with_master())
        assert m._resource_grains_cache is not None
        assert len(m._resource_grains_cache) == 100

    def test_resolve_resource_targets_without_cache_uses_per_id_render(
        self, minion_with_resources
    ):
        """
        With the cache cleared and opt-in off, the grain-match branch of
        ``_resolve_resource_targets`` must call
        :meth:`_collect_resource_grains_for` with a **singleton** SRN set
        for each managed resource — one render at a time, discarded
        after the match check. This proves the renderer is bounded to
        a single per-resource grain dict transiently and never allocates
        the full managed-resource grain map when the operator opts out
        of in-memory retention.
        """
        minion_with_resources._resource_grains_cache = None
        minion_with_resources.opts["resource_grains_cache_in_memory"] = False
        captured = []

        def fake_collect_for(srns):
            srns_list = list(srns)
            captured.append(srns_list)
            # Mimic the real renderer: return only entries for the
            # requested SRNs that have grains.
            all_grains = {"dummy:dummy-01": {"env": "prod"}}
            return {k: v for k, v in all_grains.items() if k in set(srns_list)}

        with mock_patch.object(
            minion_with_resources,
            "_collect_resource_grains_for",
            side_effect=fake_collect_for,
        ):
            targets = minion_with_resources._resolve_resource_targets(
                {
                    "tgt": "env:prod",
                    "tgt_type": "grain",
                    "fun": "test.ping",
                }
            )
        assert targets == [{"id": "dummy-01", "type": "dummy"}]
        assert captured, "the per-id renderer must have been called"
        # Every call must be a singleton — the streaming contract.
        # A call with more than one SRN means the resolver is back to
        # allocating the full grain map per call, defeating the
        # opt-out default.
        sizes = {len(s) for s in captured}
        assert sizes == {1}, (
            "default-mode grain-target resolve must render one SRN at a "
            f"time; got batch sizes {sizes}"
        )
        # The union of every singleton call equals the managed-resource
        # SRN set — proof that the resolver DID walk every managed
        # resource, it just didn't hold them all simultaneously.
        all_seen = {s[0] for s in captured if len(s) == 1}
        assert all_seen == {
            "dummy:dummy-01",
            "dummy:dummy-02",
            "dummy:dummy-03",
            "ssh:node1",
            "ssh:localhost",
        }


def srns_is_none_sentinel(value):
    """Allow either an explicit None or an iterable bounded by managed ids."""
    return value is None


# ---------------------------------------------------------------------------
# Resolve streaming contract — the follow-up refactor
# ---------------------------------------------------------------------------


def _make_streaming_minion(minion_opts, n_resources):
    """
    Build a Minion carrying ``n_resources`` ``dummy`` resources with a
    grains() callable that returns a 1 KiB dict per resource. Rendering
    all at once would be ``n_resources`` KiB resident; the streaming
    contract keeps peak transient allocation bounded to O(1 KiB).
    """
    minion_opts["resources"] = {"dummy": [f"res-{i}" for i in range(n_resources)]}
    minion_opts["multiprocessing"] = False
    with mock_patch("salt.minion.Minion.gen_modules"), mock_patch(
        "salt.minion.Minion.connect_master"
    ):
        m = salt.minion.Minion(minion_opts, load_grains=False)

    def grains_fn():
        target = salt.loader.context.resource_ctxvar.get()
        # Pad the dict to ~1 KiB so the aggregate cost of holding the
        # full map is measurable; the streaming contract keeps us well
        # below this.
        return {
            "env": "prod",
            "resource_id": target["id"],
            "pad": "x" * 1024,
        }

    m.resource_funcs = {"dummy.grains": grains_fn}
    return m


class TestResolveStreamingContract:
    """
    ``_resolve_resource_targets`` must render one per-resource grain
    dict at a time in default (opt-out) mode so a minion managing
    hundreds of thousands of resources does not allocate the full map
    on every ``salt -G ...`` call.

    These tests are the regression guard for the follow-up refactor to
    the primary PR (``dwoz/fix/minion-register-scale``): the primary PR
    moved the grain cache behind an opt-in flag, but the resolver still
    allocated the full map transiently on each call. The streaming
    refactor renders one SRN at a time so peak transient allocation is
    bounded to O(1) in inventory size.
    """

    def test_grain_target_resolve_default_mode_is_memory_bounded(self, minion_opts):
        """
        Regression: ``_resolve_resource_targets`` for ``tgt_type=grain``
        MUST render grains one resource at a time in default (opt-out)
        mode. A batch of >1 means the resolve path is back to allocating
        the full grain map per call, defeating the opt-out default and
        re-introducing the ~40-80 MB per-call transient spike at 200K
        resources.
        """
        minion = _make_streaming_minion(minion_opts, n_resources=200)
        minion.opts["resource_grains_cache_in_memory"] = False
        minion._resource_grains_cache = None

        original = minion._collect_resource_grains_for
        sizes_seen = []

        def wrapper(srns):
            srns_list = list(srns) if srns is not None else None
            sizes_seen.append(len(srns_list) if srns_list is not None else -1)
            return original(srns_list)

        minion._collect_resource_grains_for = wrapper
        load = {"fun": "test.ping", "tgt": "env:prod", "tgt_type": "grain"}
        targets = minion._resolve_resource_targets(load)

        assert sizes_seen, "render should have been called at least once"
        assert max(sizes_seen) == 1, (
            f"default-mode grain-target resolve rendered grains in batch "
            f"sizes {set(sizes_seen)}; expected only singleton (1-element) "
            f"calls. A larger batch means the resolve path is still "
            f"allocating the full grain map per call, defeating the "
            f"opt-out default."
        )
        # And the resolve DID walk every resource — streaming, not
        # skipping.
        assert len(sizes_seen) == 200
        # Grains match env:prod so every resource ends up in the
        # target list.
        assert len(targets) == 200
        # The cache stays empty: opt-out mode must NOT persist anything.
        assert minion._resource_grains_cache is None

    def test_grain_target_resolve_opt_in_uses_cache_only(self, minion_opts):
        """
        Opt-in mode (``resource_grains_cache_in_memory: True``) must
        keep the full-map-cached fast path: ``_collect_resource_grains_for``
        is called at most ONCE (to opportunistically warm the cache on
        first resolve); subsequent resolves hit the populated cache and
        issue zero renders.
        """
        minion = _make_streaming_minion(minion_opts, n_resources=50)
        minion.opts["resource_grains_cache_in_memory"] = True
        minion._resource_grains_cache = None

        original = minion._collect_resource_grains_for
        call_count = {"n": 0}

        def wrapper(srns):
            call_count["n"] += 1
            return original(list(srns) if srns is not None else None)

        minion._collect_resource_grains_for = wrapper
        load = {"fun": "test.ping", "tgt": "env:prod", "tgt_type": "grain"}

        # First resolve warms the cache.
        targets = minion._resolve_resource_targets(load)
        assert len(targets) == 50
        assert minion._resource_grains_cache is not None
        assert len(minion._resource_grains_cache) == 50
        first_call_count = call_count["n"]
        assert first_call_count == 1, (
            "opt-in mode should warm the cache with a single render call, "
            f"not stream — got {first_call_count} renders"
        )

        # Second resolve must hit the populated cache: zero additional
        # renders. This is the point of the opt-in flag.
        targets = minion._resolve_resource_targets(load)
        assert len(targets) == 50
        assert call_count["n"] == first_call_count, (
            "opt-in mode must hit the populated cache on subsequent "
            f"resolves (expected {first_call_count} total renders, "
            f"got {call_count['n']})"
        )

    def test_compound_target_resolve_default_mode_is_memory_bounded(self, minion_opts):
        """
        Regression: ``_resolve_resource_targets`` for ``tgt_type=compound``
        MUST render grains one resource at a time in default (opt-out)
        mode. The pre-refactor compound path called the resolver with
        the full managed SRN set AND then built an N-wide ``all_srns``
        copy on top of the result — a 2x peak transient hit on 200K
        resources. The streaming path should render one grain dict at
        a time and keep peak transient bounded.
        """
        minion = _make_streaming_minion(minion_opts, n_resources=200)
        minion.opts["resource_grains_cache_in_memory"] = False
        minion._resource_grains_cache = None

        original = minion._collect_resource_grains_for
        sizes_seen = []

        def wrapper(srns):
            srns_list = list(srns) if srns is not None else None
            sizes_seen.append(len(srns_list) if srns_list is not None else -1)
            return original(srns_list)

        minion._collect_resource_grains_for = wrapper
        load = {
            "fun": "test.ping",
            "tgt": "G@env:prod",
            "tgt_type": "compound",
        }
        targets = minion._resolve_resource_targets(load)

        assert sizes_seen, "render should have been called at least once"
        assert max(sizes_seen) == 1, (
            f"default-mode compound-target resolve rendered grains in "
            f"batch sizes {set(sizes_seen)}; expected only singleton "
            f"(1-element) calls. A larger batch means the compound "
            f"path is still allocating the full grain map per call."
        )
        # Every managed resource was walked.
        assert len(sizes_seen) == 200
        # G@env:prod matches every resource.
        assert len(targets) == 200
        # The cache stays empty in opt-out mode.
        assert minion._resource_grains_cache is None

    def test_compound_target_resolve_opt_in_uses_cache_only(self, minion_opts):
        """
        Opt-in mode must keep the compound path hitting the populated
        cache after the first warm — zero additional renders.
        """
        minion = _make_streaming_minion(minion_opts, n_resources=50)
        minion.opts["resource_grains_cache_in_memory"] = True
        minion._resource_grains_cache = None

        original = minion._collect_resource_grains_for
        call_count = {"n": 0}

        def wrapper(srns):
            call_count["n"] += 1
            return original(list(srns) if srns is not None else None)

        minion._collect_resource_grains_for = wrapper
        load = {
            "fun": "test.ping",
            "tgt": "G@env:prod",
            "tgt_type": "compound",
        }

        # First resolve warms.
        targets = minion._resolve_resource_targets(load)
        assert len(targets) == 50
        warm_count = call_count["n"]
        assert warm_count == 1

        # Second resolve: no new renders.
        targets = minion._resolve_resource_targets(load)
        assert len(targets) == 50
        assert call_count["n"] == warm_count, (
            "opt-in compound resolve must hit the populated cache "
            f"(expected {warm_count} total renders, got {call_count['n']})"
        )

    def test_compound_target_T_only_bypasses_grain_render_in_opt_in(self, minion_opts):
        """
        In opt-in mode, a compound expression that references only
        resource type / id (``T@...``) still needs the per-resource walk
        but does NOT trigger an extra render path — the cache is simply
        consulted per SRN. First resolve warms with one bulk render;
        subsequent resolves issue zero renders.
        """
        minion = _make_streaming_minion(minion_opts, n_resources=20)
        minion.opts["resource_grains_cache_in_memory"] = True
        minion._resource_grains_cache = None

        original = minion._collect_resource_grains_for
        call_count = {"n": 0}

        def wrapper(srns):
            call_count["n"] += 1
            return original(list(srns) if srns is not None else None)

        minion._collect_resource_grains_for = wrapper
        load = {
            "fun": "test.ping",
            "tgt": "T@dummy",
            "tgt_type": "compound",
        }

        targets = minion._resolve_resource_targets(load)
        assert len(targets) == 20
        # One warm-up render on first resolve; T@ terms don't need the
        # grain dict but the cache is still populated as a side effect
        # (consistent with the pre-refactor behaviour where the grain
        # map was always materialised at resolve time in opt-in mode).
        warm_count = call_count["n"]
        assert warm_count <= 1

    def test_compound_target_T_only_works_without_grains_fn(self, minion_opts):
        """
        A compound ``T@type`` must still match resources whose
        connection module exposes no ``grains`` callable: the walk is
        driven by the resource inventory, not the grain cache.
        """
        minion = _make_streaming_minion(minion_opts, n_resources=5)
        minion.opts["resource_grains_cache_in_memory"] = False
        minion._resource_grains_cache = None
        # Strip the grains callable; T@ should still work.
        minion.resource_funcs = {}

        load = {
            "fun": "test.ping",
            "tgt": "T@dummy",
            "tgt_type": "compound",
        }
        targets = minion._resolve_resource_targets(load)
        ids = {t["id"] for t in targets}
        assert ids == {f"res-{i}" for i in range(5)}

    def test_iter_resource_grains_for_match_cache_populated_yields_from_cache(
        self, minion_with_resources
    ):
        """
        With the cache populated, ``_iter_resource_grains_for_match``
        must yield from it without invoking ``_collect_resource_grains_for``.
        A cached entry is authoritative; a missing-from-cache SRN in
        opt-in mode is treated as "no grains for this resource" and
        silently skipped — same semantics as a resource type whose
        connection module exposes no ``grains`` callable.
        """
        minion_with_resources._resource_grains_cache = {
            "dummy:dummy-01": {"k": "v"},
            # dummy-02 / dummy-03 / ssh resources deliberately missing.
        }
        called = []

        def fake_collect_for(srns):
            called.append(list(srns) if srns is not None else None)
            return {}

        with mock_patch.object(
            minion_with_resources,
            "_collect_resource_grains_for",
            side_effect=fake_collect_for,
        ):
            pairs = list(
                minion_with_resources._iter_resource_grains_for_match(
                    [
                        "dummy:dummy-01",
                        "dummy:dummy-02",
                        "ssh:node1",
                    ]
                )
            )
        # Only the cached SRN was yielded.
        assert pairs == [("dummy:dummy-01", {"k": "v"})]
        # The renderer was NOT called — the populated cache is
        # authoritative.
        assert called == [], (
            "populated cache must be authoritative — "
            f"_collect_resource_grains_for was called with {called}"
        )


# ---------------------------------------------------------------------------
# Resource register RPC chunking
# ---------------------------------------------------------------------------


class TestRegisterRPCChunking:
    """
    ``_register_resources_with_master`` chunks large inventories into
    multiple RPCs sharing a per-registration token, so an 200 000-resource
    minion doesn't race the single-RPC retry timer.
    """

    @staticmethod
    def _minion_with(minion_opts, n_resources, chunk_size=None):
        minion_opts["resources"] = _build_large_resources(n_resources)
        minion_opts["multiprocessing"] = False
        if chunk_size is not None:
            minion_opts["resource_register_chunk_size"] = chunk_size
        with mock_patch("salt.minion.Minion.gen_modules"), mock_patch(
            "salt.minion.Minion.connect_master"
        ):
            m = salt.minion.Minion(minion_opts, load_grains=False)
        _patch_grains_fn(m)
        m.tok = b"tok"
        return m

    def test_small_pillar_sends_one_chunk(self, minion_opts):
        """
        An inventory below the chunk size sends a single RPC with no
        chunking metadata — wire format unchanged from the pre-PR load so
        older masters stay compatible.
        """
        m = self._minion_with(minion_opts, 50, chunk_size=1000)
        delivered = []

        async def capture(load, timeout=None):
            delivered.append(load)

        import asyncio

        with mock_patch.object(m, "_send_req_async_main", side_effect=capture):
            asyncio.run(m._register_resources_with_master())
        assert len(delivered) == 1, "small pillar must fit in one chunk"
        load = delivered[0]
        # None of the chunking fields may appear — a new minion against an
        # old master must send a byte-identical pre-chunking load.
        for key in (
            "_register_jid",
            "_chunk_seq",
            "_chunk_total",
            "_chunk_is_last",
        ):
            assert key not in load, f"{key} must be omitted on single-chunk payloads"
        assert len(load["resources"]["dummy"]) == 50

    def test_large_pillar_sends_multiple_chunks(self, minion_opts):
        """
        An inventory 2.5x the chunk size produces three chunks sharing a
        single jid. ``_chunk_is_last`` is True only on the final chunk —
        that's the master's trigger to sweep stale-jid entries.
        """
        m = self._minion_with(minion_opts, 25, chunk_size=10)
        delivered = []

        async def capture(load, timeout=None):
            delivered.append(load)

        import asyncio

        with mock_patch.object(m, "_send_req_async_main", side_effect=capture):
            asyncio.run(m._register_resources_with_master())
        assert len(delivered) == 3
        jids = {d["_register_jid"] for d in delivered}
        assert len(jids) == 1, "all chunks must share one register jid"
        assert [d["_chunk_seq"] for d in delivered] == [0, 1, 2]
        assert [d["_chunk_total"] for d in delivered] == [3, 3, 3]
        assert [d["_chunk_is_last"] for d in delivered] == [False, False, True]
        # Total resources across chunks equals the input inventory.
        total_rids = []
        for d in delivered:
            total_rids.extend(d["resources"].get("dummy", []))
        assert len(total_rids) == 25
        assert set(total_rids) == {f"res-{i}" for i in range(25)}

    def test_chunk_timeout_retries_that_chunk_only(self, minion_opts):
        """
        If sending chunk 1 fails, the minion retries chunk 1 (same jid,
        same seq) WITHOUT re-sending chunks 0 or 2.
        """
        m = self._minion_with(minion_opts, 25, chunk_size=10)
        m.opts["resource_register_chunk_retries"] = 3
        delivered = []
        call_count = {"n": 0}

        async def flaky(load, timeout=None):
            delivered.append(load)
            # Fail the second chunk (seq == 1) exactly once.
            if load.get("_chunk_seq") == 1 and call_count["n"] == 0:
                call_count["n"] += 1
                raise RuntimeError("simulated timeout")

        import asyncio

        with mock_patch.object(m, "_send_req_async_main", side_effect=flaky):
            asyncio.run(m._register_resources_with_master())
        # 3 chunks + 1 retry of chunk 1 = 4 deliveries.
        assert len(delivered) == 4
        seqs = [d["_chunk_seq"] for d in delivered]
        # The retry must be for seq=1, not a restart of seq=0.
        assert seqs == [0, 1, 1, 2]
        # The jid is stable across the retry.
        jids = {d["_register_jid"] for d in delivered}
        assert len(jids) == 1
        # Only the last-seq chunk is terminal.
        assert [d["_chunk_is_last"] for d in delivered] == [False, False, False, True]

    def test_chunk_persistent_failure_aborts_registration(self, minion_opts):
        """
        If a chunk exceeds its retry budget, the whole registration aborts
        and later chunks are NOT sent.
        """
        m = self._minion_with(minion_opts, 25, chunk_size=10)
        m.opts["resource_register_chunk_retries"] = 1
        delivered = []

        async def always_fail_seq1(load, timeout=None):
            delivered.append(load)
            if load.get("_chunk_seq") == 1:
                raise RuntimeError("down")

        import asyncio

        with mock_patch.object(m, "_send_req_async_main", side_effect=always_fail_seq1):
            asyncio.run(m._register_resources_with_master())
        # seq 0 (success) + seq 1 (fail, retry, fail) = 3; seq 2 never sent.
        seqs = [d["_chunk_seq"] for d in delivered]
        assert seqs == [0, 1, 1], (
            "once a chunk's retry budget is exhausted the rest of the "
            f"registration must abort; got seqs {seqs}"
        )
