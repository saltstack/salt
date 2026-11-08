"""
Unit tests for cross-master resource-registry replication.

Companion to ``test_cluster_cache_replication.py`` but targets the
``salt.utils.resource_registry.ResourceRegistry.register_minion``
write path -- it bypasses ``salt.cache.Cache`` (hash-indexed mmap
with the SRN key shape) so the generic facade-level fan-out does
NOT cover it.  These tests enforce that

* ``AESFuncs.__register_resources_sync`` fires a replication event
  after the local register lands.
* The peer-side handler applies the register locally via
  ``update_resource_index`` with the same loop-guard shape
  (``originating_master == self.opts["id"]`` -> drop) as the cache
  fan-out.
* The event is gated on the same preconditions
  (``cluster_id`` set, ``cluster_isolated_filesystem`` True,
  ``cluster_cache_replication`` not forced False).
* Peer-side apply does NOT re-broadcast.
"""

import pytest

import salt.cache._cluster_replicator as replicator
from tests.support.mock import MagicMock, patch


@pytest.fixture
def cluster_opts(tmp_path):
    """
    Cluster + isolated-FS opts -- the "replication should fire" shape.
    """
    return {
        "id": "master-1",
        "cachedir": str(tmp_path),
        "cluster_id": "c1",
        "cluster_peers": ["master-2", "master-3"],
        "cluster_isolated_filesystem": True,
        "cluster_cache_replication": True,
        "sock_dir": str(tmp_path),
    }


@pytest.fixture
def shared_fs_opts(cluster_opts):
    """Cluster but shared-FS -- replication must NOT fire."""
    cluster_opts["cluster_isolated_filesystem"] = False
    return cluster_opts


@pytest.fixture
def replication_disabled_opts(cluster_opts):
    """Cluster + isolated-FS but operator forced replication off."""
    cluster_opts["cluster_cache_replication"] = False
    return cluster_opts


# ---------------------------------------------------------------------------
# Originator-side (fire)
# ---------------------------------------------------------------------------


def test_fire_resource_register_write_payload_shape(cluster_opts):
    """
    Invariant: ``fire_resource_register_write`` emits an event whose
    payload carries ``{minion_id, resources, originating_master}``
    with ``originating_master`` set to the local master id.
    """
    captured = {}

    def fake_fire(opts, payload, tag=None):
        captured["payload"] = payload
        captured["tag"] = tag

    resources = {"bigip_vip": ["vip-1", "vip-2"]}
    with patch.object(replicator, "_fire_payload", side_effect=fake_fire):
        replicator.fire_resource_register_write(cluster_opts, "minion-a", resources)

    assert captured["payload"]["minion_id"] == "minion-a"
    assert captured["payload"]["resources"] == resources
    assert captured["payload"]["originating_master"] == cluster_opts["id"]
    assert captured["tag"] == "cluster/runner/delegate_resource_register_write"


def test_register_resources_sync_fires_replication_event(cluster_opts, tmp_path):
    """
    Invariant: in a clustered + isolated-FS deployment,
    ``__register_resources_sync`` defers both the local write and the
    peer fan-out to the publish daemon -- so the MWorker does NOT
    call ``update_resource_index`` directly, and fires exactly one
    replication event instead.  This avoids double-writing peer-owned
    SRNs when ring routing is active (the daemon has the ring state;
    the MWorker doesn't).
    """
    import salt.master

    aes = salt.master.AESFuncs.__new__(salt.master.AESFuncs)
    aes.opts = cluster_opts
    aes._AESFuncs__verify_load = lambda load, keys: load  # noqa: SLF001
    load = {"id": "minion-a", "resources": {"bigip_vip": ["vip-1"]}}

    with patch(
        "salt.utils.minions.update_resource_index", return_value=(1, 0)
    ) as upd_mock, patch(
        "salt.cache._cluster_replicator.fire_resource_register_write"
    ) as fire_mock:
        ret, fire_event, minion_id = aes._AESFuncs__register_resources_sync(
            load
        )  # noqa: SLF001

    assert ret is True
    assert upd_mock.call_count == 0, (
        "Clustered MWorker must defer local write to the publish daemon; "
        f"got {upd_mock.call_count} direct writes"
    )
    fire_mock.assert_called_once_with(cluster_opts, "minion-a", load["resources"])


def test_register_resources_sync_standalone_writes_locally(tmp_path):
    """
    Invariant: a standalone (non-cluster) master writes to the mmap
    registry directly inside the MWorker and never fires a
    replication event.  This is today's behavior for single-master
    deployments and the defensive path when ``cluster_cache_replication``
    is forced off.
    """
    import salt.master

    opts = {
        "id": "standalone-1",
        "cachedir": str(tmp_path),
        "cluster_id": None,
        "cluster_isolated_filesystem": False,
        "sock_dir": str(tmp_path),
    }
    aes = salt.master.AESFuncs.__new__(salt.master.AESFuncs)
    aes.opts = opts
    aes._AESFuncs__verify_load = lambda load, keys: load  # noqa: SLF001
    load = {"id": "minion-a", "resources": {"bigip_vip": ["vip-1"]}}

    with patch(
        "salt.utils.minions.update_resource_index", return_value=(1, 0)
    ) as upd_mock, patch(
        "salt.cache._cluster_replicator.fire_resource_register_write"
    ) as fire_mock:
        aes._AESFuncs__register_resources_sync(load)  # noqa: SLF001

    upd_mock.assert_called_once_with(opts, "minion-a", load["resources"])
    assert fire_mock.call_count == 0


def test_register_resources_sync_no_fire_on_shared_fs(shared_fs_opts):
    """
    Invariant: when ``cluster_isolated_filesystem`` is False the
    peers already see the shared mmap; replication must NOT fire,
    and the MWorker writes locally (no daemon deferral needed).
    """
    import salt.master

    aes = salt.master.AESFuncs.__new__(salt.master.AESFuncs)
    aes.opts = shared_fs_opts
    aes._AESFuncs__verify_load = lambda load, keys: load  # noqa: SLF001
    load = {"id": "minion-a", "resources": {"bigip_vip": ["vip-1"]}}

    with patch(
        "salt.utils.minions.update_resource_index", return_value=(1, 0)
    ) as upd_mock, patch(
        "salt.cache._cluster_replicator.fire_resource_register_write"
    ) as fire_mock:
        aes._AESFuncs__register_resources_sync(load)  # noqa: SLF001

    upd_mock.assert_called_once_with(shared_fs_opts, "minion-a", load["resources"])
    assert fire_mock.call_count == 0, (
        "Shared-FS cluster must not fan-out resource-register writes; "
        f"got {fire_mock.call_count} events"
    )


def test_register_resources_sync_no_fire_when_replication_disabled(
    replication_disabled_opts,
):
    """
    Invariant: ``cluster_cache_replication: False`` forces the
    replication off even in a cluster + isolated-FS topology.
    """
    import salt.master

    aes = salt.master.AESFuncs.__new__(salt.master.AESFuncs)
    aes.opts = replication_disabled_opts
    aes._AESFuncs__verify_load = lambda load, keys: load  # noqa: SLF001
    load = {"id": "minion-a", "resources": {"bigip_vip": ["vip-1"]}}

    with patch("salt.utils.minions.update_resource_index", return_value=(1, 0)), patch(
        "salt.cache._cluster_replicator.fire_resource_register_write"
    ) as fire_mock:
        aes._AESFuncs__register_resources_sync(load)  # noqa: SLF001

    assert fire_mock.call_count == 0


def test_register_resources_sync_no_fire_on_standalone(tmp_path):
    """
    Invariant: a standalone (non-cluster) master must not fire the
    replication event -- there are no peers to send it to.
    """
    import salt.master

    opts = {
        "id": "standalone-1",
        "cachedir": str(tmp_path),
        "cluster_id": None,
        "cluster_isolated_filesystem": False,
        "sock_dir": str(tmp_path),
    }
    aes = salt.master.AESFuncs.__new__(salt.master.AESFuncs)
    aes.opts = opts
    aes._AESFuncs__verify_load = lambda load, keys: load  # noqa: SLF001
    load = {"id": "minion-a", "resources": {"bigip_vip": ["vip-1"]}}

    with patch("salt.utils.minions.update_resource_index", return_value=(1, 0)), patch(
        "salt.cache._cluster_replicator.fire_resource_register_write"
    ) as fire_mock:
        aes._AESFuncs__register_resources_sync(load)  # noqa: SLF001

    assert fire_mock.call_count == 0


# ---------------------------------------------------------------------------
# Peer-side (handle)
# ---------------------------------------------------------------------------


def test_handle_delegate_resource_register_write_loop_guard(cluster_opts):
    """
    Invariant: a peer master receiving a resource-register event whose
    ``originating_master`` equals its own ``opts["id"]`` MUST drop
    the write.  Prevents bus echo from re-applying the register (and
    re-firing the fan-out).
    """
    payload = {
        "minion_id": "minion-a",
        "resources": {"bigip_vip": ["vip-1"]},
        "originating_master": cluster_opts["id"],  # == self
    }
    upd_mock = MagicMock()
    with patch("salt.utils.minions.update_resource_index", upd_mock):
        result = replicator._handle_delegate_resource_register_write(
            cluster_opts, payload
        )
    assert result is False
    assert upd_mock.call_count == 0, (
        "Loop-guard must drop self-originated event; "
        f"update_resource_index was called {upd_mock.call_count} times"
    )


def test_handle_delegate_resource_register_write_applies_locally(cluster_opts):
    """
    Invariant: a peer master receiving a foreign-origin register must
    call ``update_resource_index(opts, minion_id, resources)`` exactly
    once.
    """
    payload = {
        "minion_id": "minion-a",
        "resources": {"bigip_vip": ["vip-1", "vip-2"]},
        "originating_master": "master-2",
    }
    upd_mock = MagicMock(return_value=(2, 0))
    with patch("salt.utils.minions.update_resource_index", upd_mock):
        result = replicator._handle_delegate_resource_register_write(
            cluster_opts, payload
        )
    assert result is True
    upd_mock.assert_called_once_with(cluster_opts, "minion-a", payload["resources"])


def test_handle_delegate_resource_register_write_missing_fields(cluster_opts):
    """
    Invariant: malformed payloads (missing ``minion_id`` or
    ``resources``) are dropped rather than crashing the receiver.
    """
    upd_mock = MagicMock()
    with patch("salt.utils.minions.update_resource_index", upd_mock):
        # Missing minion_id
        assert (
            replicator._handle_delegate_resource_register_write(
                cluster_opts,
                {"resources": {}, "originating_master": "master-2"},
            )
            is False
        )
        # Missing resources
        assert (
            replicator._handle_delegate_resource_register_write(
                cluster_opts,
                {"minion_id": "x", "originating_master": "master-2"},
            )
            is False
        )
    assert upd_mock.call_count == 0


# ---------------------------------------------------------------------------
# Ring-routed dispatch (1-of-N via ring_membership) -- publish-daemon side
# ---------------------------------------------------------------------------


@pytest.fixture
def ring_cluster_opts(cluster_opts):
    """
    Three-master cluster opts matching the ring voter set used in the
    ring-routing tests.
    """
    cluster_opts["id"] = "master-1"
    cluster_opts["cluster_peers"] = ["master-2", "master-3"]
    return cluster_opts


@pytest.fixture
def populated_ring():
    """
    Rebuild the ``resource_index`` ring with three voters for the
    duration of a test, then reset the registry.  Three voters gives
    deterministic 1-of-3 ownership for any SRN.
    """
    import salt.cluster.ring_membership as rm
    import salt.utils.resource_registry as rr

    rm.reset()
    rm.rebuild(rr.RESOURCE_INDEX_RING_NAME, ["master-1", "master-2", "master-3"])
    try:
        yield rm.get_ring(rr.RESOURCE_INDEX_RING_NAME)
    finally:
        rm.reset()


def test_partition_for_dispatch_ring_active(ring_cluster_opts, populated_ring):
    """
    Invariant: with the ``resource_index`` ring populated,
    :func:`partition_resources_for_dispatch` returns a local bucket
    containing only self-owned SRNs, peer buckets keyed by remote
    owner, and ``ring_active=True``.
    """
    import salt.cluster
    import salt.utils.resource_registry as rr

    resources = {"dummy": [f"dummy-{i:04d}" for i in range(30)]}
    local, peers, ring_active = replicator.partition_resources_for_dispatch(
        ring_cluster_opts, resources
    )

    assert ring_active is True
    self_node = salt.cluster.node_id(ring_cluster_opts)

    # Build the expected ownership map.
    expected = {}
    for rid in resources["dummy"]:
        srn = rr.resource_index_srn_key("dummy", rid)
        owner = populated_ring.get_owner(srn)
        expected.setdefault(owner, []).append(rid)

    # Local bucket == self_node's bucket from expected.
    local_rids = sorted(local.get("dummy", []))
    assert local_rids == sorted(expected.get(self_node, [])), (
        f"Local partition mismatch; expected {sorted(expected.get(self_node, []))}, "
        f"got {local_rids}"
    )

    # Peer buckets == remaining owners in expected.
    peer_rids_by_owner = {
        owner: sorted(r.get("dummy", [])) for owner, r in peers.items()
    }
    expected_peer_rids = {
        owner: sorted(rids)
        for owner, rids in expected.items()
        if owner != self_node
    }
    assert peer_rids_by_owner == expected_peer_rids


def test_partition_for_dispatch_partition_disjoint(ring_cluster_opts, populated_ring):
    """
    Invariant (partition): for any SRN, exactly one bucket owns it.
    No SRN appears in both ``local`` and any peer bucket, and no SRN
    appears in more than one peer bucket.
    """
    resources = {"dummy": [f"dummy-{i:04d}" for i in range(50)]}
    local, peers, _ = replicator.partition_resources_for_dispatch(
        ring_cluster_opts, resources
    )

    seen = set()
    for rid in local.get("dummy", []):
        assert rid not in seen, f"Duplicate SRN in local bucket: {rid}"
        seen.add(rid)
    for owner, owner_resources in peers.items():
        for rid in owner_resources.get("dummy", []):
            assert rid not in seen, (
                f"SRN {rid} appeared in a prior bucket and in peer {owner}"
            )
            seen.add(rid)
    # Every input SRN landed in exactly one bucket.
    assert seen == set(resources["dummy"])


def test_partition_for_dispatch_ring_empty_returns_broadcast(ring_cluster_opts):
    """
    Invariant: empty/absent ring returns the full resources as the
    local bucket, no peer buckets, and ``ring_active=False`` so the
    caller falls through to today's broadcast semantics.
    """
    import salt.cluster.ring_membership as rm

    rm.reset()  # Empty ring -- no voters
    resources = {"dummy": ["a", "b", "c"]}
    local, peers, ring_active = replicator.partition_resources_for_dispatch(
        ring_cluster_opts, resources
    )
    assert ring_active is False
    assert local == resources
    assert peers == {}


def test_fire_resource_register_write_always_emits_single_event(ring_cluster_opts):
    """
    Invariant: ``fire_resource_register_write`` is a thin MWorker-side
    emit that always publishes one event with the full resources
    dict.  The publish daemon's dispatcher owns the ring vs
    broadcast decision -- not this function.
    """
    import salt.cluster.ring_membership as rm

    rm.reset()
    emitted = []
    with patch.object(
        replicator,
        "_fire_payload",
        side_effect=lambda o, p, tag=None: emitted.append((p, tag)),
    ):
        resources = {"dummy": ["a", "b", "c"]}
        replicator.fire_resource_register_write(
            ring_cluster_opts, "minion-a", resources
        )
    assert len(emitted) == 1
    payload, tag = emitted[0]
    assert tag == "cluster/runner/delegate_resource_register_write"
    assert payload["resources"] == resources
    assert payload["minion_id"] == "minion-a"
    assert payload["originating_master"] == ring_cluster_opts["id"]
    assert "target_master" not in payload


def test_register_resources_sync_cluster_mode_defers_to_daemon(
    ring_cluster_opts,
):
    """
    Invariant: in a clustered + isolated-FS deployment the MWorker
    does NOT call ``update_resource_index`` directly -- it fires a
    replication event and lets the publish daemon apply the local
    write under ring-aware partitioning.  This is the structural
    guard against the MWorker's fork-time-empty ring state causing a
    double-write of peer-owned SRNs.
    """
    import salt.master

    aes = salt.master.AESFuncs.__new__(salt.master.AESFuncs)
    aes.opts = ring_cluster_opts
    aes._AESFuncs__verify_load = lambda load, keys: load  # noqa: SLF001
    resources = {"dummy": [f"dummy-{i:04d}" for i in range(10)]}
    load = {"id": "minion-a", "resources": resources}

    with patch(
        "salt.utils.minions.update_resource_index", return_value=(0, 0)
    ) as upd_mock, patch(
        "salt.cache._cluster_replicator.fire_resource_register_write"
    ) as fire_mock:
        ret, _, _ = aes._AESFuncs__register_resources_sync(load)  # noqa: SLF001

    assert ret is True
    assert upd_mock.call_count == 0, (
        "Clustered MWorker must defer the local write to the publish daemon"
    )
    fire_mock.assert_called_once_with(ring_cluster_opts, "minion-a", resources)


def test_handle_delegate_resource_register_write_no_re_broadcast(cluster_opts):
    """
    Invariant: applying a peer-originated register must NOT re-trigger
    a secondary fan-out.  ``update_resource_index`` is a direct call
    to the mmap registry (no cache facade), so there is no
    ``_already_replicated``-equivalent flag to thread through -- the
    non-broadcasting property is structural: the handler calls
    ``update_resource_index`` and nothing else, and
    ``update_resource_index`` itself has no replication seam.

    Patch the originator-side seam and assert it's never touched when
    the peer-side handler runs.
    """
    payload = {
        "minion_id": "minion-a",
        "resources": {"bigip_vip": ["vip-1"]},
        "originating_master": "master-2",
    }
    with patch("salt.utils.minions.update_resource_index", return_value=(1, 0)), patch(
        "salt.cache._cluster_replicator.fire_resource_register_write"
    ) as fire_mock:
        replicator._handle_delegate_resource_register_write(cluster_opts, payload)
    assert fire_mock.call_count == 0, (
        "Peer-side apply must not re-fire the replication event; "
        f"got {fire_mock.call_count} secondary emits"
    )
