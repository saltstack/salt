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


def test_ring_set_raises_until_propose_path_lands():
    """
    Operators who try to commit a new policy through the runner today
    must see a loud failure rather than a silent no-op.  ``ring_set``
    raises :class:`NotImplementedError` until the runner-to-master
    IPC arrives.
    """
    with pytest.raises(NotImplementedError):
        cluster_runner.ring_set(members="voters", replicas=2)


def test_ring_set_raises_with_no_args_too():
    """``ring_set`` raises before validating arguments."""
    with pytest.raises(NotImplementedError):
        cluster_runner.ring_set()


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
