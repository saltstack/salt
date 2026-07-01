"""
Unit tests for the ``cluster`` runner.

Covers:

* ``ring_info`` (read-only ring snapshot).
* ``members`` (read-only membership replay from local Raft storage).
* ``ring_set`` raising :class:`NotImplementedError` until the
  runner-to-master IPC slice ships.
"""

import pytest

import salt.config
from salt.cluster import ring_membership
from salt.cluster.consensus.raft.log import LogEntry, LogEntryType
from salt.cluster.consensus.storage import SaltStorage
from salt.runners import cluster as cluster_runner


@pytest.fixture(autouse=True)
def _isolate_ring():
    """Each test gets a fresh empty ring; cleanup also resets it."""
    ring_membership.reset()
    yield
    ring_membership.reset()


def test_ring_info_default_state():
    """
    A runner subprocess has never received a rebuild — the ring is
    empty.  ``is_clustered`` is False, ``node_count`` is 0, the nodes
    list is empty.  Stable shape so the docs / runbook never lie.
    """
    info = cluster_runner.ring_info()
    assert info["is_clustered"] is False
    assert info["node_count"] == 0
    assert info["nodes"] == []
    # ``vnodes`` is computed from the token table; an empty ring has 0
    # tokens so the answer is 0 rather than the default-150 constant.
    assert info["vnodes"] == 0


def test_ring_info_after_rebuild():
    """
    A populated ring round-trips through ``ring_info`` cleanly.  This
    is the shape stage 2 will see once the runner's ring is sourced
    from the same SM the publish daemon's ring is.
    """
    ring_membership.rebuild(["m1", "m2", "m3"])
    info = cluster_runner.ring_info()
    assert info["is_clustered"] is True
    assert info["node_count"] == 3
    assert info["nodes"] == ["m1", "m2", "m3"]
    assert info["vnodes"] >= 1


def test_ring_set_validates_required_name():
    """
    ``cluster.ring_set`` requires a ring name — every per-ring
    propose is scoped to a named ring, never to "the ring".  Pre-
    multi-ring callers that pass no name see a clear error.
    """
    with pytest.raises(ValueError, match="non-empty 'name'"):
        cluster_runner.ring_set()
    with pytest.raises(ValueError, match="non-empty 'name'"):
        cluster_runner.ring_set(members="voters", replicas=2)


# ---------------------------------------------------------------------------
# cluster.members — read-only membership replay from local Raft storage
# ---------------------------------------------------------------------------


@pytest.fixture
def _runner_opts(tmp_path, monkeypatch):
    """
    Inject a master-config-like ``__opts__`` into the runner module so
    ``cluster.members`` can resolve the storage path and node id.

    Storage writes go under ``tmp_path``; tests can then seed CONFIG
    entries via a SaltStorage built with the same opts and assert what
    the runner reads back.
    """
    opts = salt.config.master_config("/dev/null")
    opts["cachedir"] = str(tmp_path)
    opts["id"] = "127.0.0.1"
    opts["interface"] = "127.0.0.1"
    monkeypatch.setattr(cluster_runner, "__opts__", opts, raising=False)
    return opts


def test_members_empty_storage_returns_empty_set(_runner_opts):
    """
    A master that has not yet applied any CONFIG entry reports an empty
    voter and learner set with ``membership_version == -1``.  This is
    the stable contract for a fresh joiner before it has caught up.
    """
    result = cluster_runner.members()
    assert result == {
        "node_id": "127.0.0.1",
        "voters": [],
        "learners": [],
        "membership_version": -1,
        "voter_count": 0,
        "learner_count": 0,
        # Leader visibility — None when no leader has been observed yet.
        "leader_id": None,
        "term": 0,
        # Voter-health fields default to empty when no sentinel exists
        # on disk (e.g. a fresh master before the leader's watchdog has
        # had a chance to write).
        "unhealthy_voters": [],
        "recently_demoted": [],
    }


def test_members_replays_committed_config_entries(_runner_opts):
    """
    A storage with two persisted CONFIG entries (the second supersedes
    the first) round-trips through the runner: only the latest voter /
    learner set is returned, version stamped to the latest entry's
    index.
    """
    storage = SaltStorage(_runner_opts["id"], _runner_opts)
    storage.append_log(
        LogEntry(
            term=1,
            index=0,
            cmd={"voters": ["m1"], "learners": []},
            type=LogEntryType.CONFIG,
        )
    )
    storage.append_log(
        LogEntry(
            term=1,
            index=1,
            cmd={"voters": ["m1", "m2", "m3"], "learners": ["m4"]},
            type=LogEntryType.CONFIG,
        )
    )

    result = cluster_runner.members()
    assert result["voters"] == ["m1", "m2", "m3"]
    assert result["learners"] == ["m4"]
    assert result["membership_version"] == 1
    assert result["voter_count"] == 3
    assert result["learner_count"] == 1


def test_members_surfaces_persisted_leader(_runner_opts):
    """
    When the local Node has previously observed a leader and persisted
    that observation via ``save_state``, ``cluster.members`` surfaces
    the leader_id and term.  Operators get "who's the leader" without
    daemon IPC.

    Note: ``leader_id`` is observability only and may be stale on a
    follower that has been partitioned away from the current-term
    leader; the field reflects what *this* master last saw.
    """
    storage = SaltStorage(_runner_opts["id"], _runner_opts)
    storage.save_state(term=7, voted_for="127.0.0.2", leader_id="127.0.0.2")

    result = cluster_runner.members()
    assert result["leader_id"] == "127.0.0.2"
    assert result["term"] == 7


def test_members_surfaces_health_sentinel_when_present(_runner_opts, tmp_path):
    """
    When the daemon's voter-health watchdog has written
    ``cachedir/cluster-health.json``, ``cluster.members`` surfaces the
    unhealthy_voters / recently_demoted lists from it.  An operator
    invoking the runner on the current leader gets accurate liveness
    signal without any IPC into the daemon.
    """
    import json

    sentinel = tmp_path / "cluster-health.json"
    sentinel.write_text(
        json.dumps(
            {
                "unhealthy_voters": ["m4"],
                "recently_demoted": ["m4"],
                "updated_at": 1.0,
            }
        )
    )

    result = cluster_runner.members()
    assert result["unhealthy_voters"] == ["m4"]
    assert result["recently_demoted"] == ["m4"]


def test_members_skips_non_config_entries(_runner_opts):
    """
    COMMAND / RING_CONFIG entries interleaved with CONFIG entries must
    not perturb the membership reply.  Pins the contract that only
    CONFIG entries move the voter set.
    """
    storage = SaltStorage(_runner_opts["id"], _runner_opts)
    storage.append_log(
        LogEntry(
            term=1,
            index=0,
            cmd={"voters": ["m1", "m2"], "learners": []},
            type=LogEntryType.CONFIG,
        )
    )
    storage.append_log(
        LogEntry(term=1, index=1, cmd=b"work", type=LogEntryType.COMMAND)
    )
    storage.append_log(
        LogEntry(
            term=1,
            index=2,
            cmd={"members": "voters", "replicas": 2},
            type=LogEntryType.RING_CONFIG,
        )
    )

    result = cluster_runner.members()
    assert result["voters"] == ["m1", "m2"]
    assert result["learners"] == []
    # version stamp is from the CONFIG entry, not the trailing
    # non-membership entries.
    assert result["membership_version"] == 0


# ---------------------------------------------------------------------------
# cluster.sync_roots — operator-driven content fan-out
# ---------------------------------------------------------------------------


def test_sync_roots_rejects_invalid_roots(_runner_opts):
    """
    ``roots`` is constrained to ``{"file", "pillar", "both"}``.  Anything
    else is rejected up-front so the operator doesn't silently fire a
    no-op event.
    """
    _runner_opts["cluster_id"] = "test_cluster"
    with pytest.raises(ValueError, match="roots must be"):
        cluster_runner.sync_roots(roots="everything")


def test_sync_roots_no_cluster_id_is_skip(_runner_opts):
    """
    A non-cluster master returns a structured skip rather than
    firing a meaningless event.  Lets ops automation call this runner
    unconditionally without breaking standalone masters.
    """
    _runner_opts["cluster_id"] = None
    result = cluster_runner.sync_roots()
    assert result["status"] == "skipped"
    assert "no cluster_id" in result["reason"]


def test_sync_roots_fires_local_event(_runner_opts, monkeypatch):
    """
    The happy path: the runner fires a ``cluster/runner/sync_roots``
    event with the resolved channel list.  The master daemon (not the
    runner subprocess) is responsible for the actual fan-out — the
    runner's job is just to make the request loudly enough that the
    daemon picks it up.
    """
    _runner_opts["cluster_id"] = "test_cluster"
    fired = []

    class _FakeEvent:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def fire_event(self, data, tag):
            fired.append((tag, data))

    import salt.utils.event

    monkeypatch.setattr(salt.utils.event, "get_event", lambda *a, **kw: _FakeEvent())

    result = cluster_runner.sync_roots(roots="both")
    assert result["status"] == "fan-out initiated"
    assert result["channels"] == ["file_roots", "pillar_roots"]
    assert len(fired) == 1
    tag, data = fired[0]
    assert tag == "cluster/runner/sync_roots"
    assert data == {"channels": ["file_roots", "pillar_roots"]}


def test_sync_roots_file_only_filters_channels(_runner_opts, monkeypatch):
    """
    ``roots="file"`` requests only the file_roots channel; pillar_roots
    is excluded from the runner's event payload so the daemon doesn't
    push pillars when the operator only wanted SLS.
    """
    _runner_opts["cluster_id"] = "test_cluster"
    fired = []

    class _FakeEvent:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def fire_event(self, data, tag):
            fired.append((tag, data))

    import salt.utils.event

    monkeypatch.setattr(salt.utils.event, "get_event", lambda *a, **kw: _FakeEvent())

    result = cluster_runner.sync_roots(roots="file")
    assert result["channels"] == ["file_roots"]
    assert fired[0][1] == {"channels": ["file_roots"]}


# ---------------------------------------------------------------------------
# Multi-ring operator runners (slice 6)
# ---------------------------------------------------------------------------


class _FakeEvent:
    """Minimal context-manager fake used by the runner tests."""

    fired = None

    def __init__(self, *a, **kw):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def fire_event(self, data, tag):
        _FakeEvent.fired.append((tag, data))


def _intercept_event_bus(monkeypatch):
    """
    Replace ``salt.utils.event.get_event`` with a fake that records
    every fired event, returning a list the test can assert on.
    """
    import salt.utils.event

    _FakeEvent.fired = []
    monkeypatch.setattr(salt.utils.event, "get_event", lambda *a, **kw: _FakeEvent())
    return _FakeEvent.fired


def test_ring_create_fires_event(_runner_opts, monkeypatch):
    _runner_opts["cluster_id"] = "test_cluster"
    fired = _intercept_event_bus(monkeypatch)
    result = cluster_runner.ring_create(name="jobs", voters=["m1", "m2", "m3"])
    assert result["status"] == "fan-out initiated"
    assert fired == [
        (
            "cluster/runner/ring_create",
            {"ring_id": "jobs", "founding_voters": ["m1", "m2", "m3"]},
        )
    ]


def test_ring_create_validates_inputs(_runner_opts):
    _runner_opts["cluster_id"] = "test_cluster"
    with pytest.raises(ValueError, match="non-empty 'name'"):
        cluster_runner.ring_create(name="", voters=["m1"])
    with pytest.raises(ValueError, match="non-empty 'voters'"):
        cluster_runner.ring_create(name="jobs", voters=[])


def test_ring_create_skips_outside_cluster(_runner_opts):
    """A non-cluster master returns a structured skip rather than firing."""
    _runner_opts["cluster_id"] = None
    result = cluster_runner.ring_create(name="jobs", voters=["m1"])
    assert result["status"] == "skipped"


def test_ring_destroy_fires_event(_runner_opts, monkeypatch):
    _runner_opts["cluster_id"] = "test_cluster"
    fired = _intercept_event_bus(monkeypatch)
    cluster_runner.ring_destroy(name="jobs")
    assert fired == [("cluster/runner/ring_destroy", {"ring_id": "jobs"})]


def test_route_set_fires_event(_runner_opts, monkeypatch):
    _runner_opts["cluster_id"] = "test_cluster"
    fired = _intercept_event_bus(monkeypatch)
    cluster_runner.route_set(data_type="jobs", ring="jobs_ring")
    assert fired == [
        (
            "cluster/runner/route_set",
            {"data_type": "jobs", "ring_id": "jobs_ring"},
        )
    ]


def test_route_clear_fires_event(_runner_opts, monkeypatch):
    _runner_opts["cluster_id"] = "test_cluster"
    fired = _intercept_event_bus(monkeypatch)
    cluster_runner.route_clear(data_type="jobs")
    assert fired == [("cluster/runner/route_clear", {"data_type": "jobs"})]


def test_route_set_validates_inputs(_runner_opts):
    _runner_opts["cluster_id"] = "test_cluster"
    with pytest.raises(ValueError, match="non-empty 'data_type'"):
        cluster_runner.route_set(data_type="", ring="r")
    with pytest.raises(ValueError, match="non-empty 'ring'"):
        cluster_runner.route_set(data_type="jobs", ring="")


def test_ring_set_fires_event_with_partial_update(_runner_opts, monkeypatch):
    _runner_opts["cluster_id"] = "test_cluster"
    fired = _intercept_event_bus(monkeypatch)
    cluster_runner.ring_set(name="jobs", members="voters")
    assert fired == [
        (
            "cluster/runner/ring_set",
            {"ring_id": "jobs", "members": "voters"},
        )
    ]


def test_ring_set_fires_event_with_replicas(_runner_opts, monkeypatch):
    _runner_opts["cluster_id"] = "test_cluster"
    fired = _intercept_event_bus(monkeypatch)
    cluster_runner.ring_set(name="jobs", replicas=2)
    assert fired == [("cluster/runner/ring_set", {"ring_id": "jobs", "replicas": 2})]


# ---------------------------------------------------------------------------
# cluster.shed_unowned — migration "going in" runner (slice 7)
# ---------------------------------------------------------------------------


def _seed_registry_and_ring_membership(opts, ring, voters):
    """
    Helper: write a RING_REGISTRY entry into the cluster log and a
    matching CONFIG entry into the ring's own log so the runner has
    something to replay.
    """
    from salt.cluster.consensus.raft.log import LogEntry, LogEntryType
    from salt.cluster.consensus.storage import SaltStorage

    node_id = opts["interface"]
    cluster_storage = SaltStorage(node_id, opts, ring_id="cluster")
    cluster_storage.append_log(
        LogEntry(
            term=1,
            index=0,
            cmd={
                "ring_id": ring,
                "founding_voters": voters,
                "status": "active",
            },
            type=LogEntryType.RING_REGISTRY,
        )
    )
    ring_storage = SaltStorage(node_id, opts, ring_id=ring)
    ring_storage.append_log(
        LogEntry(
            term=1,
            index=0,
            cmd={"voters": voters, "learners": []},
            type=LogEntryType.CONFIG,
        )
    )


def test_shed_unowned_validates_inputs(_runner_opts):
    with pytest.raises(ValueError, match="non-empty 'ring'"):
        cluster_runner.shed_unowned(ring="")
    with pytest.raises(ValueError, match="at least one bank"):
        cluster_runner.shed_unowned(ring="jobs", banks=[])


def test_shed_unowned_skips_when_ring_not_registered(_runner_opts):
    """
    Without a RING_REGISTRY entry for the ring, the runner refuses
    to drop anything — protects against typos like running with the
    wrong ring name and quietly nuking data.
    """
    result = cluster_runner.shed_unowned(ring="never-created")
    assert result["status"] == "skipped"
    assert "not active" in result["reason"]


def test_shed_unowned_skips_when_not_a_founder(_runner_opts):
    """
    Master is not in the ring's founding voter set: nothing to shed
    because nothing on this master is governed by the ring.  The
    runner skips rather than producing a confusing "kept=0,
    dropped=0" result with no explanation.
    """
    _seed_registry_and_ring_membership(
        _runner_opts, "jobs", voters=["other-1", "other-2"]
    )
    result = cluster_runner.shed_unowned(ring="jobs")
    assert result["status"] == "skipped"
    assert "not a founding voter" in result["reason"]


def test_shed_unowned_drops_only_unowned_entries(_runner_opts):
    """
    With this master as a founder and a populated generic cache
    bank, the runner keeps the entries this master owns and flushes
    the rest.  Uses the standard ``salt.cache.Cache`` (localfs
    driver) so the test exercises the real flush path on opaque
    payloads — the same shape any future per-ring cache routes will
    take.
    """
    import salt.cache

    node_id = _runner_opts["interface"]
    _seed_registry_and_ring_membership(
        _runner_opts, "jobs", voters=[node_id, "m2", "m3"]
    )

    cache = salt.cache.Cache(_runner_opts, driver="localfs")
    # Seed enough entries that the hash distributes some on this
    # master and some elsewhere.  Verify by checking owns() ourselves.
    from salt.cluster.ring import HashRing

    hash_ring = HashRing()
    hash_ring.rebuild([node_id, "m2", "m3"])
    seeded = [f"jid-{i:04d}" for i in range(50)]
    for jid in seeded:
        cache.store("jobs/jid", jid, {"minions": ["m"]})

    owned_before = [k for k in seeded if hash_ring.owns(k, node_id)]
    unowned_before = [k for k in seeded if not hash_ring.owns(k, node_id)]
    # Sanity: hash distributes at least one to each side; otherwise
    # the test would be vacuous.
    assert owned_before and unowned_before

    result = cluster_runner.shed_unowned(
        ring="jobs",
        banks=["jobs/jid"],
        driver="localfs",
        subbank_template=None,
    )
    assert result["status"] == "ok"
    assert result["dropped"] == len(unowned_before)
    assert result["kept"] == len(owned_before)
    assert result["subbanks_dropped"] == 0

    # The cache reflects the partition: every owned key is still
    # there, every unowned key is gone.
    after = set(cache.list("jobs/jid"))
    assert set(owned_before).issubset(after)
    assert not set(unowned_before) & after


def test_shed_unowned_cascades_subbanks_for_unowned_keys(_runner_opts):
    """
    The salt_cache returner stores per-JID returns in their own
    bank ``jobs/returns/<jid>``.  When the parent JID is shed, the
    runner must also flush that per-JID sub-bank wholesale —
    otherwise the returns leak forever.  Pins the cascade-flush
    contract that makes the salt_cache returner usable end-to-end.
    """
    import salt.cache

    node_id = _runner_opts["interface"]
    _seed_registry_and_ring_membership(
        _runner_opts, "jobs", voters=[node_id, "m2", "m3"]
    )

    cache = salt.cache.Cache(_runner_opts, driver="localfs")
    from salt.cluster.ring import HashRing

    hash_ring = HashRing()
    hash_ring.rebuild([node_id, "m2", "m3"])
    seeded = [f"jid-{i:04d}" for i in range(30)]
    for jid in seeded:
        cache.store("jobs/loads", jid, {"fun": "test.ping"})
        cache.store(f"jobs/returns/{jid}", "minion-x", {"return": True})
        cache.store(f"jobs/returns/{jid}", "minion-y", {"return": False})

    owned = [k for k in seeded if hash_ring.owns(k, node_id)]
    unowned = [k for k in seeded if not hash_ring.owns(k, node_id)]
    assert owned and unowned

    result = cluster_runner.shed_unowned(
        ring="jobs",
        banks=["jobs/loads"],
        driver="localfs",
        subbank_template="jobs/returns/{key}",
    )
    assert result["status"] == "ok"
    assert result["dropped"] == len(unowned)
    assert result["kept"] == len(owned)
    assert result["subbanks_dropped"] == len(unowned)

    # Primary bank partitioned correctly.
    after = set(cache.list("jobs/loads"))
    assert set(owned).issubset(after)
    assert not set(unowned) & after

    # Returns sub-banks: gone for unowned JIDs, intact for owned ones.
    for jid in unowned:
        assert list(cache.list(f"jobs/returns/{jid}")) == []
    for jid in owned:
        assert set(cache.list(f"jobs/returns/{jid}")) == {"minion-x", "minion-y"}


def test_shed_unowned_default_banks_match_salt_cache_layout(_runner_opts):
    """
    Calling ``shed_unowned ring=jobs`` with no other arguments must
    target the four ``jobs/*`` banks that
    :mod:`salt.returners.salt_cache` writes through.  Operators
    using the recommended ``master_job_cache: salt_cache`` shouldn't
    need to spell the layout out by hand.
    """
    import salt.cache

    node_id = _runner_opts["interface"]
    _seed_registry_and_ring_membership(
        _runner_opts, "jobs", voters=[node_id, "m2", "m3"]
    )

    cache = salt.cache.Cache(_runner_opts, driver="localfs")
    # Seed each default bank with the same JID so we can prove every
    # bank gets visited.
    seeded = [f"jid-{i:04d}" for i in range(40)]
    for jid in seeded:
        cache.store("jobs/loads", jid, {"fun": "test.ping"})
        cache.store("jobs/minions", jid, ["m"])
        cache.store("jobs/endtimes", jid, 0.0)
        cache.store("jobs/nocache", jid, True)
        cache.store(f"jobs/returns/{jid}", "minion-x", {"return": True})

    result = cluster_runner.shed_unowned(ring="jobs", driver="localfs")
    assert result["status"] == "ok"
    # Each of the four banks contributes the same unowned-JID set;
    # dropped counts them all.  Cascade counts the unowned set once
    # (from the primary bank, ``jobs/loads``).
    assert result["dropped"] % 4 == 0
    assert result["subbanks_dropped"] * 4 == result["dropped"]

    from salt.cluster.ring import HashRing

    hash_ring = HashRing()
    hash_ring.rebuild([node_id, "m2", "m3"])
    unowned = [k for k in seeded if not hash_ring.owns(k, node_id)]
    owned = [k for k in seeded if hash_ring.owns(k, node_id)]

    for bank in ("jobs/loads", "jobs/minions", "jobs/endtimes", "jobs/nocache"):
        remaining = set(cache.list(bank))
        assert set(owned).issubset(remaining)
        assert not set(unowned) & remaining


def test_collect_from_peers_default_targets_jobs_banks(_runner_opts, monkeypatch):
    """
    ``cluster.collect_from_peers`` with no arguments collects the
    four ``jobs/*`` banks the salt_cache returner writes through.
    Pins the operator default that lines up with the going-out
    migration flow documented in ``MULTI_RING_DESIGN.md``.
    """
    _runner_opts["cluster_id"] = "test_cluster"
    fired = _intercept_event_bus(monkeypatch)
    result = cluster_runner.collect_from_peers()
    assert result["status"] == "fan-out initiated"
    assert fired == [
        (
            "cluster/runner/collect_from_peers",
            {
                "channels": [
                    "bank:jobs/loads",
                    "bank:jobs/minions",
                    "bank:jobs/endtimes",
                    "bank:jobs/nocache",
                ]
            },
        )
    ]


def test_collect_from_peers_mixes_channels_and_banks(_runner_opts, monkeypatch):
    _runner_opts["cluster_id"] = "test_cluster"
    fired = _intercept_event_bus(monkeypatch)
    cluster_runner.collect_from_peers(
        channels=["keys"], banks=["jobs/loads", "jobs/minions"]
    )
    assert fired == [
        (
            "cluster/runner/collect_from_peers",
            {"channels": ["keys", "bank:jobs/loads", "bank:jobs/minions"]},
        )
    ]


def test_collect_from_peers_rejects_unknown_fixed_channels(_runner_opts):
    _runner_opts["cluster_id"] = "test_cluster"
    with pytest.raises(ValueError, match="unsupported fixed channels"):
        cluster_runner.collect_from_peers(channels=["bogus"])


def test_collect_from_peers_rejects_no_request(_runner_opts):
    _runner_opts["cluster_id"] = "test_cluster"
    with pytest.raises(ValueError, match="at least one channel or bank"):
        cluster_runner.collect_from_peers(channels=[], banks=[])


# ---------------------------------------------------------------------------
# cluster.rings — read-only registry replay
# ---------------------------------------------------------------------------


def test_rings_empty_storage(_runner_opts):
    """
    Fresh cluster with no committed RING_REGISTRY entries returns
    empty registry + active_rings == [] and version -1.  Stable
    shape so the operator runbook doesn't have to special-case
    "no rings yet."
    """
    result = cluster_runner.rings()
    assert result == {
        "node_id": _runner_opts["id"],
        "rings": {},
        "active_rings": [],
        "registry_version": -1,
    }


def test_rings_surfaces_active_and_destroyed_entries(_runner_opts):
    """
    The runner replays every committed RING_REGISTRY entry; the
    response carries the latest state per ring + a convenience
    ``active_rings`` list excluding destroyed entries.
    """
    storage = SaltStorage(_runner_opts["id"], _runner_opts)
    storage.append_log(
        LogEntry(
            term=1,
            index=0,
            cmd={
                "ring_id": "jobs",
                "founding_voters": ["m1", "m2", "m3"],
                "status": "active",
            },
            type=LogEntryType.RING_REGISTRY,
        )
    )
    storage.append_log(
        LogEntry(
            term=1,
            index=1,
            cmd={
                "ring_id": "events",
                "founding_voters": ["m1", "m2"],
                "status": "active",
            },
            type=LogEntryType.RING_REGISTRY,
        )
    )
    storage.append_log(
        LogEntry(
            term=1,
            index=2,
            cmd={"ring_id": "events", "status": "destroyed"},
            type=LogEntryType.RING_REGISTRY,
        )
    )

    result = cluster_runner.rings()
    assert result["rings"] == {
        "jobs": {"founding_voters": ["m1", "m2", "m3"], "status": "active"},
        "events": {"founding_voters": ["m1", "m2"], "status": "destroyed"},
    }
    assert result["active_rings"] == ["jobs"]
    assert result["registry_version"] == 2


# ---------------------------------------------------------------------------
# cluster.routes — read-only routing table replay
# ---------------------------------------------------------------------------


def test_routes_empty_storage(_runner_opts):
    result = cluster_runner.routes()
    assert result["node_id"] == _runner_opts["id"]
    assert result["routes"] == {}
    assert result["routing_version"] == -1
    assert result["drop_stats"] == {}


def test_routes_surfaces_route_entries_and_clears(_runner_opts):
    """
    A route to a ring followed by a clear (route to ``None``) ends
    up in the table as ``None`` — the registry preserves the
    lifecycle and the runner surfaces it directly.
    """
    storage = SaltStorage(_runner_opts["id"], _runner_opts)
    storage.append_log(
        LogEntry(
            term=1,
            index=0,
            cmd={"data_type": "jobs", "ring_id": "jobs_ring"},
            type=LogEntryType.ROUTE,
        )
    )
    storage.append_log(
        LogEntry(
            term=1,
            index=1,
            cmd={"data_type": "events", "ring_id": "events_ring"},
            type=LogEntryType.ROUTE,
        )
    )
    storage.append_log(
        LogEntry(
            term=1,
            index=2,
            cmd={"data_type": "events", "ring_id": None},
            type=LogEntryType.ROUTE,
        )
    )

    result = cluster_runner.routes()
    assert result["routes"] == {"jobs": "jobs_ring", "events": None}
    assert result["routing_version"] == 2


def test_routes_surfaces_drop_stats(_runner_opts):
    """
    The runner folds the per-process drop_stats snapshot into its
    response so an operator can run a single command and see both
    the routing table and any drop signal.
    """
    ring_membership.set_route("jobs", "jobs_ring")
    # Trigger one not_a_member drop on this process.
    ring_membership.owns_for({"interface": _runner_opts["id"]}, "jobs", "k")

    result = cluster_runner.routes()
    assert result["drop_stats"]["jobs"]["ring_id"] == "jobs_ring"
    assert result["drop_stats"]["jobs"]["not_a_member"] == 1


# ---------------------------------------------------------------------------
# cluster.shed_unowned_all — fan-out runner
# ---------------------------------------------------------------------------


def test_shed_unowned_all_validates_inputs(_runner_opts):
    _runner_opts["cluster_id"] = "test_cluster"
    with pytest.raises(ValueError, match="non-empty 'ring'"):
        cluster_runner.shed_unowned_all(ring="")


def test_shed_unowned_all_fires_event_and_runs_local(_runner_opts, monkeypatch):
    """
    The runner fires ``cluster/runner/shed_unowned_all`` carrying
    the operator's parameters, then runs the local shed inline so
    the caller gets back an immediately useful result.  The fan-out
    half is what the daemon's intercept consumes; the local half
    pins the same exit shape the single-master runner returns.
    """
    import salt.cache

    _runner_opts["cluster_id"] = "test_cluster"
    _seed_registry_and_ring_membership(
        _runner_opts, "jobs", voters=[_runner_opts["interface"], "m2", "m3"]
    )
    # Seed something to shed so the local result is non-trivial.
    cache = salt.cache.Cache(_runner_opts, driver="localfs")
    seeded = [f"jid-{i:04d}" for i in range(30)]
    for jid in seeded:
        cache.store("jobs/loads", jid, {"fun": "test.ping"})

    fired = _intercept_event_bus(monkeypatch)
    result = cluster_runner.shed_unowned_all(
        ring="jobs",
        banks=("jobs/loads",),
        subbank_template=None,
        driver="localfs",
    )

    # Event fanned out with the operator's parameters intact.
    assert len(fired) == 1
    tag, payload = fired[0]
    assert tag == "cluster/runner/shed_unowned_all"
    assert payload["ring_id"] == "jobs"
    assert payload["banks"] == ["jobs/loads"]
    assert payload["subbank_template"] is None
    assert payload["driver"] == "localfs"
    assert payload["dry_run"] is False

    # Local pass committed and surfaces the standard shed shape.
    assert result["local"]["status"] == "ok"
    assert result["local"]["dropped"] + result["local"]["kept"] == 30


# ---------------------------------------------------------------------------
# cluster.shed_status — read-back of the per-master sentinel
# ---------------------------------------------------------------------------


def test_shed_status_missing_returns_structured_skip(_runner_opts):
    """
    No sentinel on disk → operator sees a ``"missing"`` status with
    the inspected path so they can correlate cluster-wide.
    """
    result = cluster_runner.shed_status()
    assert result["status"] == "missing"


def test_shed_status_round_trips_through_sentinel(_runner_opts):
    """
    ``cluster.shed_unowned`` writes ``cluster-shed-status.json`` via
    :func:`salt.cluster.migration.write_shed_status`; the read-only
    runner surfaces the latest record so an operator polling every
    master can confirm shed completed.
    """
    import json
    import pathlib

    _seed_registry_and_ring_membership(
        _runner_opts, "jobs", voters=[_runner_opts["interface"], "m2", "m3"]
    )
    cluster_runner.shed_unowned(
        ring="jobs", banks=("jobs/loads",), subbank_template=None, driver="localfs"
    )

    sentinel = pathlib.Path(_runner_opts["cachedir"]) / "cluster-shed-status.json"
    assert sentinel.exists()
    on_disk = json.loads(sentinel.read_text())

    result = cluster_runner.shed_status()
    assert result == on_disk
    assert result["ring"] == "jobs"
    assert result["source"] == "runner"


# ---------------------------------------------------------------------------
# cluster.migrate_jobs_to_cache — local_cache → salt_cache one-shot
# ---------------------------------------------------------------------------


def _seed_local_cache_jid(
    jobs_root,
    jid,
    load,
    minions,
    returns,
    *,
    endtime=None,
    nocache=False,
    syndic_minions=None,
):
    """
    Write one JID's worth of state into the on-disk ``local_cache``
    layout so the migration runner has something to walk.

    ``jobs_root/<2>/<28>/`` is the canonical shape ``local_cache``
    uses; we reuse :func:`salt.utils.jid.jid_dir` to keep the
    hashing identical to production.
    """
    import os

    import salt.payload
    import salt.utils.files
    import salt.utils.jid

    jid_dir = salt.utils.jid.jid_dir(jid, str(jobs_root), "sha256")
    os.makedirs(jid_dir, exist_ok=True)
    with salt.utils.files.fopen(os.path.join(jid_dir, ".load.p"), "w+b") as fp:
        salt.payload.dump(load, fp)
    if minions is not None:
        with salt.utils.files.fopen(os.path.join(jid_dir, ".minions.p"), "w+b") as fp:
            salt.payload.dump(list(minions), fp)
    for syndic_id, syndic_minion_list in (syndic_minions or {}).items():
        with salt.utils.files.fopen(
            os.path.join(jid_dir, f".minions.{syndic_id}.p"), "w+b"
        ) as fp:
            salt.payload.dump(list(syndic_minion_list), fp)
    if endtime is not None:
        with salt.utils.files.fopen(os.path.join(jid_dir, "endtime"), "w") as fp:
            fp.write(str(endtime))
    if nocache:
        with salt.utils.files.fopen(os.path.join(jid_dir, "nocache"), "w") as fp:
            fp.write("1")
    for minion_id, record in (returns or {}).items():
        minion_dir = os.path.join(jid_dir, minion_id)
        os.makedirs(minion_dir, exist_ok=True)
        with salt.utils.files.fopen(os.path.join(minion_dir, "return.p"), "w+b") as fp:
            salt.payload.dump(record, fp)


def test_migrate_jobs_to_cache_skip_when_no_cachedir(monkeypatch):
    """
    Without a ``cachedir`` opt the runner has nothing to walk.
    Returns a structured skip rather than raising — operators
    running cleanup playbooks shouldn't be surprised.
    """
    monkeypatch.setattr(cluster_runner, "__opts__", {}, raising=False)
    result = cluster_runner.migrate_jobs_to_cache()
    assert result["status"] == "skipped"
    assert "cachedir" in result["reason"]


def test_migrate_jobs_to_cache_skip_when_no_jobs_dir(_runner_opts):
    """No existing jobs root → skip with a clear message."""
    result = cluster_runner.migrate_jobs_to_cache()
    assert result["status"] == "skipped"
    assert "no local_cache jobs root" in result["reason"]


def test_migrate_jobs_to_cache_round_trip(_runner_opts):
    """
    Seed the on-disk local_cache layout for two JIDs and confirm the
    runner copies every field into the salt_cache bank layout.
    Includes a JID with returns + endtime + nocache marker so each
    code path is exercised.
    """
    import pathlib

    import salt.cache

    jobs_root = pathlib.Path(_runner_opts["cachedir"]) / "jobs"

    _seed_local_cache_jid(
        jobs_root,
        "20260516-A",
        load={"jid": "20260516-A", "fun": "test.ping", "tgt": "*"},
        minions=["m1", "m2"],
        returns={
            "m1": {"return": True, "retcode": 0, "success": True},
            "m2": {"return": False, "retcode": 1, "success": False},
        },
        endtime=1234567890.0,
    )
    _seed_local_cache_jid(
        jobs_root,
        "20260516-B",
        load={"jid": "20260516-B", "fun": "state.apply"},
        minions=["m1"],
        returns={},
        nocache=True,
    )

    result = cluster_runner.migrate_jobs_to_cache()
    assert result["status"] == "ok"
    assert result["scanned"] == 2
    assert result["migrated"] == 2
    assert result["skipped"] == 0
    assert result["returns_migrated"] == 2  # 2 returns from JID A, 0 from B

    cache = salt.cache.Cache(_runner_opts, driver="localfs")
    # Loads landed under jobs/loads keyed by JID.
    assert cache.fetch("jobs/loads", "20260516-A")["fun"] == "test.ping"
    assert cache.fetch("jobs/loads", "20260516-B")["fun"] == "state.apply"
    # Minions list merged + sorted.
    assert cache.fetch("jobs/minions", "20260516-A") == ["m1", "m2"]
    # Endtime preserved.
    assert cache.fetch("jobs/endtimes", "20260516-A") == 1234567890.0
    # Nocache marker preserved on the right JID only.  localfs
    # returns ``{}`` for a missing key (not ``None``) — we just want
    # to assert the marker isn't a truthy ``True``.
    assert cache.fetch("jobs/nocache", "20260516-B") is True
    assert not cache.fetch("jobs/nocache", "20260516-A")
    # Returns landed in per-JID sub-banks.
    assert set(cache.list("jobs/returns/20260516-A")) == {"m1", "m2"}
    assert cache.fetch("jobs/returns/20260516-A", "m1")["return"] is True
    assert cache.fetch("jobs/returns/20260516-A", "m1")["retcode"] == 0


def test_migrate_jobs_to_cache_merges_syndic_minions(_runner_opts):
    """
    A JID that has both a main ``.minions.p`` and a syndic-supplied
    ``.minions.<syndic>.p`` ends up with the union as a single sorted
    list in ``jobs/minions``.  Matches what
    :func:`salt.returners.local_cache.get_load` would compute.
    """
    import pathlib

    import salt.cache

    jobs_root = pathlib.Path(_runner_opts["cachedir"]) / "jobs"
    _seed_local_cache_jid(
        jobs_root,
        "20260516-S",
        load={"jid": "20260516-S", "fun": "test.ping"},
        minions=["main-1"],
        returns={},
        syndic_minions={"syndic-a": ["syndic-m1", "main-1"]},
    )

    cluster_runner.migrate_jobs_to_cache()
    cache = salt.cache.Cache(_runner_opts, driver="localfs")
    assert cache.fetch("jobs/minions", "20260516-S") == [
        "main-1",
        "syndic-m1",
    ]


def test_migrate_jobs_to_cache_dry_run_writes_nothing(_runner_opts):
    """
    Dry-run counts JIDs but does not call ``cache.store`` for any of
    them.  Pin the operator preview contract — ``salt-run
    cluster.migrate_jobs_to_cache dry_run=True`` must be a pure read.
    """
    import pathlib

    import salt.cache

    jobs_root = pathlib.Path(_runner_opts["cachedir"]) / "jobs"
    _seed_local_cache_jid(
        jobs_root,
        "20260516-D",
        load={"jid": "20260516-D", "fun": "test.ping"},
        minions=["m1"],
        returns={"m1": {"return": "x"}},
    )

    result = cluster_runner.migrate_jobs_to_cache(dry_run=True)
    assert result["status"] == "ok"
    assert result["scanned"] == 1
    assert result["migrated"] == 1
    assert result["returns_migrated"] == 1
    assert result["dry_run"] is True

    cache = salt.cache.Cache(_runner_opts, driver="localfs")
    # No bank populated despite the runner claiming success.
    assert not cache.fetch("jobs/loads", "20260516-D")
    assert cache.list("jobs/returns/20260516-D") == []


def test_migrate_jobs_to_cache_skips_stub_jid_dirs(_runner_opts):
    """
    A JID directory with no ``.load.p`` (typically left over from a
    crash mid-prep_jid) is counted as skipped rather than failing
    the whole migration.
    """
    import os
    import pathlib

    import salt.utils.jid

    jobs_root = pathlib.Path(_runner_opts["cachedir"]) / "jobs"
    # Build the dir directly without dropping a .load.p.
    jid_dir = salt.utils.jid.jid_dir("20260516-stub", str(jobs_root), "sha256")
    os.makedirs(jid_dir, exist_ok=True)

    result = cluster_runner.migrate_jobs_to_cache()
    assert result["status"] == "ok"
    assert result["scanned"] == 1
    assert result["migrated"] == 0
    assert result["skipped"] == 1


def test_shed_unowned_dry_run_flushes_nothing(_runner_opts):
    """
    ``dry_run=True`` returns the same counts but leaves the cache
    untouched — operator can preview the partition before committing.
    """
    import salt.cache

    node_id = _runner_opts["interface"]
    _seed_registry_and_ring_membership(
        _runner_opts, "jobs", voters=[node_id, "m2", "m3"]
    )
    cache = salt.cache.Cache(_runner_opts, driver="localfs")
    seeded = [f"jid-{i:04d}" for i in range(50)]
    for jid in seeded:
        cache.store("jobs/jid", jid, {"minions": ["m"]})

    result = cluster_runner.shed_unowned(
        ring="jobs",
        banks=["jobs/jid"],
        driver="localfs",
        subbank_template=None,
        dry_run=True,
    )
    assert result["status"] == "ok"
    assert result["dry_run"] is True
    assert result["dropped"] > 0
    # All keys are still there.
    assert set(cache.list("jobs/jid")) == set(seeded)
