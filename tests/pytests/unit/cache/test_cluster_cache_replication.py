"""
Unit tests for the default cross-master cache replication feature on
cluster masters.

These tests enforce the behavioural spec for ``cluster_cache_replication``
and ``cluster_cache_routing`` as written up by the design team; they are
deliberately authored *against the spec*, not against any specific
implementation, by an independent agent.  The file is expected to:

- FAIL on vanilla ``resources-2`` because the feature does not exist
  yet (no fan-out code path, no routing config knob, no
  ``store_many`` / ``_handle_delegate_cache_write`` hooks).
- PASS once the primary's ``wip/cache-cluster-replicate`` branch lands
  the feature.

Each test carries an invariant comment pointing back at the spec item
it enforces, so regressions surface with a specific failure reason.

Spec summary (3008.x, ``cluster_id`` set + ``cluster_isolated_filesystem:
True``):

* Default: every ``cache.store(bank, key, data)`` /
  ``cache.store_many(bank, items)`` on a cluster master fans out to
  every peer master via an encrypted cluster event.
* Opt-in: per-bank HashRing routing (1-of-N) via
  ``cluster_cache_routing: {bank_name: "ring"|"replicate"}``.  Default
  for unspecified banks is ``"replicate"``; ``jobs`` bank defaults to
  ``"ring"`` to preserve the existing per-bank sharding.
* Master switch: ``cluster_cache_replication: bool`` — default True
  when the cluster+isolated-FS conditions are met, else False.
* No fan-out in shared-FS mode (``cluster_isolated_filesystem: False``)
  since peers already see the mmap.
* Loop-guard: if a peer receives a delegate-cache-write whose
  ``originating_master`` equals its own ``opts["id"]``, drop.
* Replay-idempotent: applying the same (bank, key, data) twice
  produces the same final state.
"""

import pytest

import salt.cache
from tests.support.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cluster_opts(tmp_path):
    """
    Minimal opts that satisfy the "cluster + isolated-FS" precondition
    under which replication is supposed to be enabled by default.
    """
    return {
        "id": "master-1",
        "cache": "localfs",
        "memcache_expire_seconds": 0,
        "memcache_max_items": 0,
        "memcache_full_cleanup": False,
        "memcache_debug": False,
        "cachedir": str(tmp_path),
        "cluster_id": "c1",
        "cluster_peers": ["master-2", "master-3"],
        "cluster_isolated_filesystem": True,
        # cluster_cache_replication deliberately NOT set — spec says
        # it should default to True in this topology.
        "sock_dir": str(tmp_path),
    }


@pytest.fixture
def shared_fs_cluster_opts(cluster_opts):
    """Cluster opts with ``cluster_isolated_filesystem: False``."""
    cluster_opts["cluster_isolated_filesystem"] = False
    return cluster_opts


@pytest.fixture
def non_cluster_opts(tmp_path):
    """Opts with no ``cluster_id`` — standalone master."""
    return {
        "id": "standalone-1",
        "cache": "localfs",
        "memcache_expire_seconds": 0,
        "memcache_max_items": 0,
        "memcache_full_cleanup": False,
        "memcache_debug": False,
        "cachedir": str(tmp_path),
        "cluster_id": None,
        "cluster_peers": [],
        "cluster_isolated_filesystem": False,
        "sock_dir": str(tmp_path),
    }


@pytest.fixture
def fanout_recorder():
    """
    Mock the cluster-bus pusher used by ``Cache.store`` to broadcast to
    peer masters.  Returns a MagicMock standing in for the
    fire-event pusher.

    The primary's implementation is expected to go through a single
    well-known seam (e.g. ``salt.cache._cluster_replicator.fire_event``
    or a method on the Cache object) so this mock can be patched in a
    single place.  The attribute path below is the one the spec names
    as the integration point — the test will FAIL today because the
    attribute does not exist.
    """
    return MagicMock(name="cluster_cache_pusher")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _patch_cluster_fanout(recorder):
    """
    Patch the single seam the primary's branch exposes for peer fan-out.

    The spec names ``salt.cache._cluster_replicator.fire_peer_cache_write``
    as the intended seam.  The context manager yields the mock, and
    will fail loudly if the attribute is missing — that failure is the
    "not implemented yet" signal on vanilla ``resources-2``.
    """
    return patch(
        "salt.cache._cluster_replicator.fire_peer_cache_write",
        recorder,
        create=False,
    )


def _patch_delegate_fanout(recorder):
    """Patch the delegate-write (ring-routing) seam."""
    return patch(
        "salt.cache._cluster_replicator.fire_delegate_cache_write",
        recorder,
        create=False,
    )


def _build_cache_with_mocked_driver(opts):
    """
    Build a ``salt.cache.Cache`` whose underlying driver ``store`` is a
    no-op MagicMock, so tests only observe the replication layer.
    """
    cache = salt.cache.Cache(opts)
    driver_mock = MagicMock()
    # ``Cache.store`` dispatches via ``self.modules[fun](...)`` where
    # ``fun`` = ``f"{self.driver}.store"``.
    cache._modules = {
        f"{cache.driver}.store": driver_mock,
        f"{cache.driver}.store_many": driver_mock,
        f"{cache.driver}.fetch": MagicMock(return_value={}),
        f"{cache.driver}.updated": MagicMock(return_value=None),
        f"{cache.driver}.flush": MagicMock(),
        f"{cache.driver}.list": MagicMock(return_value=[]),
    }
    return cache, driver_mock


# ---------------------------------------------------------------------------
# Default fan-out behaviour
# ---------------------------------------------------------------------------


def test_cache_store_fans_out_to_peers_by_default(cluster_opts, fanout_recorder):
    """
    Invariant: on a cluster master with ``cluster_isolated_filesystem:
    True`` and no ``cluster_cache_routing`` entry for ``grains``, a
    ``cache.store("grains", ...)`` call MUST broadcast one encrypted
    event per peer master (N-1 events for an N-master cluster).

    Fails today: ``salt.cache._cluster_replicator`` doesn't exist and
    ``Cache.store`` never emits a cluster event.
    """
    cache, _driver = _build_cache_with_mocked_driver(cluster_opts)
    with _patch_cluster_fanout(fanout_recorder):
        cache.store("grains", "minion-1", {"env": "prod"})

    # Spec-conformant implementations may call the seam once (a single
    # event that the publish daemon fans out to every peer at the bus
    # layer) or N-1 times (an explicit loop over peers in Python).
    # Either is valid as long as the seam is exercised; the invariant
    # is "every peer sees the write" which the bus-layer fan-out and
    # the loop both satisfy.
    assert 1 <= fanout_recorder.call_count <= 2, (
        f"Expected 1 (bus-layer fan-out) or 2 (per-peer loop) calls, "
        f"got {fanout_recorder.call_count}"
    )
    # Payload shape: each call carries (bank, key, data,
    # originating_master, expires-or-None).  The spec allows either
    # positional or keyword — assert the fields are present rather
    # than pinning the exact kwargs ordering.
    for call in fanout_recorder.call_args_list:
        args, kwargs = call
        payload = kwargs or (args[0] if args and isinstance(args[0], dict) else {})
        # Accept either call(payload_dict) or call(bank=..., key=..., ...).
        if "bank" not in payload and args:
            # Positional shape: (peer, bank, key, data, originating_master, ...)
            # Assert basics appear somewhere in the call.
            flat = list(args) + list(kwargs.values())
            assert "grains" in flat, f"bank missing from call: {call}"
            assert "minion-1" in flat, f"key missing from call: {call}"
            assert {"env": "prod"} in flat, f"data missing from call: {call}"
        else:
            assert payload.get("bank") == "grains"
            assert payload.get("key") == "minion-1"
            assert payload.get("data") == {"env": "prod"}
            assert payload.get("originating_master") == cluster_opts["id"]


def test_cache_store_many_fans_out(cluster_opts, fanout_recorder):
    """
    Invariant: ``cache.store_many(bank, items)`` must fan out the
    whole batch to every peer master (one batched event per peer, or
    N-1 individual events per item per peer — either is spec-conformant;
    the assertion counts total write-visibility).

    Fails today: ``Cache.store_many`` does not exist yet.
    """
    cache, _driver = _build_cache_with_mocked_driver(cluster_opts)
    items = {
        "minion-a": {"env": "prod"},
        "minion-b": {"env": "staging"},
        "minion-c": {"env": "dev"},
    }
    with _patch_cluster_fanout(fanout_recorder):
        # ``store_many`` is spec-level API; absence today is the
        # failure signal.
        cache.store_many("grains", items)

    # A conformant implementation sends at minimum one event per peer
    # (batched) and at most one per item per peer (unbatched).
    # 2 peers, 3 items => 2 .. 6 events.
    assert 2 <= fanout_recorder.call_count <= 6, (
        f"Expected 2..6 peer events for store_many (2 peers x 3 items), "
        f"got {fanout_recorder.call_count}"
    )


def test_cache_store_routes_ring_when_configured(cluster_opts, fanout_recorder):
    """
    Invariant: when ``cluster_cache_routing: {"grains": "ring"}`` is
    set, a ``cache.store("grains", ...)`` must NOT fan out to every
    peer — it must instead delegate-write to the HashRing owner of
    ``(bank, key)``.  The recorder from the broadcast seam must stay
    at 0 calls; the delegate seam must receive exactly one call.
    """
    cluster_opts["cluster_cache_routing"] = {"grains": "ring"}
    cache, _driver = _build_cache_with_mocked_driver(cluster_opts)

    delegate_recorder = MagicMock(name="delegate_pusher")
    with _patch_cluster_fanout(fanout_recorder), _patch_delegate_fanout(
        delegate_recorder
    ):
        cache.store("grains", "minion-1", {"env": "prod"})

    # Spec: ring-mode is 1-of-N, not N-1 broadcast.
    assert fanout_recorder.call_count == 0, (
        f"Expected 0 broadcast events for a ring-routed bank, got "
        f"{fanout_recorder.call_count}"
    )
    assert delegate_recorder.call_count == 1, (
        f"Expected exactly 1 delegate-write for a ring-routed bank, got "
        f"{delegate_recorder.call_count}"
    )


def test_cache_store_no_fanout_when_cluster_isolated_filesystem_false(
    shared_fs_cluster_opts, fanout_recorder
):
    """
    Invariant: shared-FS mode (``cluster_isolated_filesystem: False``)
    is the only case where peers can observe writes via the on-disk
    mmap without IPC — fan-out must be a no-op.
    """
    cache, _driver = _build_cache_with_mocked_driver(shared_fs_cluster_opts)
    with _patch_cluster_fanout(fanout_recorder):
        cache.store("grains", "minion-1", {"env": "prod"})

    assert fanout_recorder.call_count == 0, (
        f"Expected 0 peer events in shared-FS mode, got "
        f"{fanout_recorder.call_count}"
    )


def test_cache_store_no_fanout_when_cluster_cache_replication_false(
    cluster_opts, fanout_recorder
):
    """
    Invariant: ``cluster_cache_replication: False`` disables the entire
    fan-out code path, even on an isolated-FS cluster.  This is the
    operator kill-switch.
    """
    cluster_opts["cluster_cache_replication"] = False
    cache, _driver = _build_cache_with_mocked_driver(cluster_opts)
    with _patch_cluster_fanout(fanout_recorder):
        cache.store("grains", "minion-1", {"env": "prod"})

    assert fanout_recorder.call_count == 0, (
        f"Master switch cluster_cache_replication=False must suppress "
        f"fan-out; got {fanout_recorder.call_count} events"
    )


def test_cache_store_no_fanout_when_not_clustered(non_cluster_opts, fanout_recorder):
    """
    Invariant: a standalone (non-cluster) master must never emit a
    replication event — no ``cluster_id`` means there are no peers.
    """
    cache, _driver = _build_cache_with_mocked_driver(non_cluster_opts)
    with _patch_cluster_fanout(fanout_recorder):
        cache.store("grains", "minion-1", {"env": "prod"})

    assert fanout_recorder.call_count == 0, (
        f"A master without cluster_id must not replicate; got "
        f"{fanout_recorder.call_count} events"
    )


# ---------------------------------------------------------------------------
# Peer-side (delegate-write receiver) handler behaviour
# ---------------------------------------------------------------------------


def _import_handler():
    """
    Import ``_handle_delegate_cache_write``.  The spec names
    ``salt.cache._cluster_replicator._handle_delegate_cache_write`` as
    the receiver.  Import failure is the "not implemented" signal.
    """
    import salt.cache._cluster_replicator as replicator  # noqa: F401  # pylint: disable=no-name-in-module,import-error

    return replicator._handle_delegate_cache_write


def test_delegate_cache_write_loop_guard(cluster_opts):
    """
    Invariant: a peer master receiving a ``cluster/peer/delegate-cache-
    write`` event whose ``originating_master`` equals its own
    ``opts["id"]`` must DROP the write.  This is the loop-guard that
    prevents the fan-out of a store from being reflected back and
    re-applied locally (which would then re-fire the fan-out again).
    """
    handler = _import_handler()
    cache_store_mock = MagicMock(name="cache.store")

    payload = {
        "bank": "grains",
        "key": "minion-1",
        "data": {"env": "prod"},
        "originating_master": cluster_opts["id"],  # == self
        "expires": None,
    }
    with patch("salt.cache.Cache.store", cache_store_mock):
        handler(cluster_opts, payload)

    # Invariant: loop-guard dropped the write.
    assert cache_store_mock.call_count == 0, (
        f"Loop-guard must drop self-originated delegate-cache-write; "
        f"cache.store was called {cache_store_mock.call_count} times"
    )


def test_delegate_cache_write_applies_locally(cluster_opts):
    """
    Invariant: a peer master receiving a delegate-cache-write from a
    *foreign* originating master must call ``cache.store(bank, key,
    data, expires=expires)`` exactly once locally.
    """
    handler = _import_handler()
    cache_store_mock = MagicMock(name="cache.store")

    payload = {
        "bank": "grains",
        "key": "minion-1",
        "data": {"env": "prod"},
        "originating_master": "master-2",  # not self
        "expires": 3600,
    }
    with patch("salt.cache.Cache.store", cache_store_mock):
        handler(cluster_opts, payload)

    assert cache_store_mock.call_count == 1, (
        f"Foreign delegate-cache-write must trigger exactly one local "
        f"cache.store; got {cache_store_mock.call_count}"
    )
    args, kwargs = cache_store_mock.call_args
    # Accept positional or keyword per primary's choice.
    flat_args = list(args) + list(kwargs.values())
    assert "grains" in flat_args
    assert "minion-1" in flat_args
    assert {"env": "prod"} in flat_args
    assert 3600 in flat_args


def test_delegate_cache_write_no_re_broadcast(cluster_opts, fanout_recorder):
    """
    Invariant: applying a delegate-cache-write on the peer side must
    NOT re-trigger another fan-out.  Otherwise 3 peers x N stores
    becomes an exponential event storm.

    The handler should either (a) call a bypass path on the cache
    backend, or (b) set a thread-local flag that suppresses the
    replication seam during the recursive store.  Either way the
    broadcast seam must stay at 0 calls after the handler runs.
    """
    handler = _import_handler()

    # Build a real Cache-with-mocked-driver so the handler's local
    # store path hits the mocked driver and the broadcast seam patch
    # is live.
    cache, _driver = _build_cache_with_mocked_driver(cluster_opts)

    payload = {
        "bank": "grains",
        "key": "minion-1",
        "data": {"env": "prod"},
        "originating_master": "master-2",
        "expires": None,
    }
    with _patch_cluster_fanout(fanout_recorder), patch(
        "salt.cache.Cache", return_value=cache
    ):
        handler(cluster_opts, payload)

    assert fanout_recorder.call_count == 0, (
        f"Peer-side delegate-cache-write must not re-broadcast; got "
        f"{fanout_recorder.call_count} secondary events"
    )


# ---------------------------------------------------------------------------
# Config defaults
# ---------------------------------------------------------------------------


def test_cluster_cache_routing_config_defaults():
    """
    Invariant: the effective ``cluster_cache_routing`` for a cluster
    master must be the merge of operator-supplied entries with the
    built-in ``{"jobs": "ring"}`` default so the existing per-bank
    job sharding is preserved on upgrade (backward compat).

    The spec names ``salt.config.get_cluster_cache_routing(opts)`` (or
    an equivalent resolver — if the primary uses a different module
    path the assertion should still hit via attribute search).  Import
    failure is the "not implemented" signal.
    """
    import salt.config  # noqa: F401

    resolver = getattr(salt.config, "get_cluster_cache_routing", None)
    if resolver is None:
        # Fallback: look in salt.cache
        resolver = getattr(salt.cache, "get_cluster_cache_routing", None)
    assert resolver is not None, (
        "Neither salt.config.get_cluster_cache_routing nor "
        "salt.cache.get_cluster_cache_routing exists — the resolver "
        "function the spec requires is missing."
    )

    # 1) Empty operator config: jobs defaults to ring, everything else
    #    defaults to replicate.
    opts_empty = {}
    routing = resolver(opts_empty)  # pylint: disable=not-callable
    assert routing.get("jobs") == "ring", (
        f"Default routing for 'jobs' must be 'ring' (backward compat), "
        f"got {routing.get('jobs')!r}"
    )
    # Any unspecified bank must resolve to "replicate" — the
    # resolver may expose this via a helper or via an explicit
    # ``__default__`` entry.  Assert at least one of these shapes
    # holds.
    assert (
        routing.get("__default__") == "replicate"
        or routing.get("grains", "replicate") == "replicate"
    ), f"Unspecified banks must default to 'replicate'; routing={routing!r}"

    # 2) Operator-supplied override must survive the merge, including
    #    an explicit override of the jobs default.
    opts_override = {"cluster_cache_routing": {"jobs": "replicate", "grains": "ring"}}
    routing2 = resolver(opts_override)  # pylint: disable=not-callable
    assert routing2.get("jobs") == "replicate", (
        "Operator override of jobs=replicate must win over the built-in "
        f"'ring' default; got {routing2.get('jobs')!r}"
    )
    assert routing2.get("grains") == "ring", (
        f"Operator-supplied grains=ring must survive the merge; got "
        f"{routing2.get('grains')!r}"
    )


def test_cluster_cache_routing_defaults_include_none_entries():
    """
    Invariant: the merged routing dict MUST include the ``"none"``
    opt-outs for ``cluster/consensus`` and ``cluster/state_sync``.  These
    are the Raft-log and state-sync banks whose contents already
    replicate via a dedicated transport; fanning them out through the
    cache facade would overwrite each master's authoritative copy.

    Additionally, operator-supplied ``"none"`` entries must survive the
    merge intact (not be coerced away or rewritten).
    """
    import salt.config

    # 1) With no operator overrides, the defaults must inject "none"
    #    for the internal cluster banks.
    routing = salt.config.get_cluster_cache_routing({})
    assert routing.get("cluster/consensus") == "none", (
        "Built-in default cluster/consensus=none must be present; got "
        f"{routing.get('cluster/consensus')!r}"
    )
    assert routing.get("cluster/state_sync") == "none", (
        "Built-in default cluster/state_sync=none must be present; got "
        f"{routing.get('cluster/state_sync')!r}"
    )

    # 2) Operator-supplied "none" entry must survive the merge.
    opts = {"cluster_cache_routing": {"custom_bank": "none"}}
    routing = salt.config.get_cluster_cache_routing(opts)
    assert routing.get("custom_bank") == "none", (
        f"Operator-supplied custom_bank=none must survive the merge; "
        f"got {routing.get('custom_bank')!r}"
    )
    # Built-in defaults must still be present alongside the operator entry.
    assert routing.get("cluster/consensus") == "none"
    assert routing.get("jobs") == "ring"


# ---------------------------------------------------------------------------
# Longest-prefix bank routing (compound-bank support + opt-out)
# ---------------------------------------------------------------------------


def test_cluster_consensus_banks_skipped(cluster_opts):
    """
    Regression for cluster-bootstrap replication loop: Raft-persistence
    writes to ``cluster/consensus/<node>/cluster`` and
    ``cluster/consensus/<node>/cluster/log`` MUST NOT fan out through
    the cache facade.  If they did, peer masters would overwrite each
    other's Raft logs on every heartbeat and the cluster would never
    stabilise.

    This test exercises the longest-prefix match: the exact bank name
    is not in ``_CLUSTER_CACHE_ROUTING_DEFAULTS``, only the
    ``cluster/consensus`` prefix is.
    """
    cache, _driver = _build_cache_with_mocked_driver(cluster_opts)
    fanout = MagicMock(name="fanout")
    delegate = MagicMock(name="delegate")
    with _patch_cluster_fanout(fanout), _patch_delegate_fanout(delegate):
        cache.store("cluster/consensus/nodeA/cluster", "term", {"term": 3})
        cache.store("cluster/consensus/nodeA/cluster/log", "17", {"index": 17})
        cache.store("cluster/state_sync/session-abc", "chunk-0", b"opaque")

    assert fanout.call_count == 0, (
        f"cluster/consensus and cluster/state_sync writes must NOT "
        f"replicate; got {fanout.call_count} fanout events"
    )
    assert delegate.call_count == 0, (
        f"cluster/consensus and cluster/state_sync writes must NOT "
        f"ring-delegate; got {delegate.call_count} delegate events"
    )


def test_jobs_compound_bank_ring_routed(cluster_opts):
    """
    Regression for the exact-match-vs-compound-bank latent bug: the
    built-in ``{"jobs": "ring"}`` default used to miss compound banks
    (``jobs/loads``, ``jobs/returns/<jid>``, ...) because the lookup
    was ``routing.get(bank, "replicate")``.  Longest-prefix match
    fixes this: ``jobs/loads`` resolves to ``"ring"``.
    """
    cache, _driver = _build_cache_with_mocked_driver(cluster_opts)
    fanout = MagicMock(name="fanout")
    delegate = MagicMock(name="delegate")
    with _patch_cluster_fanout(fanout), _patch_delegate_fanout(delegate):
        cache.store("jobs/loads", "jid123", {"jid": "jid123"})
        cache.store("jobs/returns/jid123", "minion-1", {"ret": "ok"})

    # Two stores, both ring-routed, zero broadcast.
    assert fanout.call_count == 0, (
        f"Compound jobs/* banks must ring-route (not broadcast); got "
        f"{fanout.call_count} fanout events"
    )
    assert delegate.call_count == 2, (
        f"Both jobs/* stores must fire the ring delegate; got "
        f"{delegate.call_count} delegate events"
    )


def test_resolve_bank_routing_helper():
    """
    Direct unit coverage for the longest-prefix matcher so future
    changes to the dispatch path don't silently regress the lookup.
    """
    from salt.cache import _resolve_bank_routing

    routing = {
        "jobs": "ring",
        "cluster/consensus": "none",
        "cluster/state_sync": "none",
    }
    # Exact match.
    assert _resolve_bank_routing(routing, "jobs") == "ring"
    # Single-segment prefix.
    assert _resolve_bank_routing(routing, "jobs/loads") == "ring"
    assert _resolve_bank_routing(routing, "jobs/returns/jid-9") == "ring"
    # Multi-segment prefix.
    assert _resolve_bank_routing(routing, "cluster/consensus/nodeA/cluster") == "none"
    assert (
        _resolve_bank_routing(routing, "cluster/consensus/nodeA/cluster/log") == "none"
    )
    assert _resolve_bank_routing(routing, "cluster/state_sync/session-1") == "none"
    # No prefix match falls through to "replicate".
    assert _resolve_bank_routing(routing, "grains") == "replicate"
    assert _resolve_bank_routing(routing, "cluster/other/thing") == "replicate"
    assert _resolve_bank_routing({}, "anything/at/all") == "replicate"
