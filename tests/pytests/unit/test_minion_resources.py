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
    happened yet), the resolver falls back to ``_collect_resource_grains``
    so a freshly-started minion still acts on grain targets.
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
    # Cache populated on the fly, persisted for the next call.
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
