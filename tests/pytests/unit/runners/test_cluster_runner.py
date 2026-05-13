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
