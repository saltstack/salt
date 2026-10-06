"""
Unit tests for :class:`salt.cluster.consensus.storage.SaltStorage`.

Most of SaltStorage's behaviour is exercised transitively through
``test_raft_log.py``; this file covers the multi-ring constructor
parameter and the on-disk path layout that makes per-ring Raft groups
coexist on a single master.
"""

import pytest

import salt.config
from salt.cluster.consensus.raft.log import LogEntry, LogEntryType
from salt.cluster.consensus.storage import SaltStorage


@pytest.fixture
def opts(tmp_path):
    """Master opts with a per-test cachedir so storage writes are isolated."""
    opts = salt.config.master_config("/dev/null")
    opts["cachedir"] = str(tmp_path)
    return opts


def test_default_ring_id_is_cluster(opts):
    """
    Pre-multi-ring callers that omit ``ring_id`` are routed to the
    main cluster Raft log.  This is the source of backward compat
    for every existing site that builds a ``SaltStorage``.
    """
    storage = SaltStorage("node-a", opts)
    assert storage._ring_id == "cluster"
    assert storage._meta_bank == "cluster/consensus/node-a/cluster"
    assert storage._log_bank == "cluster/consensus/node-a/cluster/log"


def test_explicit_ring_id_isolates_paths(opts):
    """
    Two storages on the same node but different rings persist into
    disjoint cache banks.  This is the invariant that lets one
    master process host the cluster Raft group plus N per-ring
    Raft groups without their logs colliding on disk.
    """
    cluster_storage = SaltStorage("node-a", opts, ring_id="cluster")
    jobs_storage = SaltStorage("node-a", opts, ring_id="jobs")

    assert cluster_storage._meta_bank != jobs_storage._meta_bank
    assert cluster_storage._log_bank != jobs_storage._log_bank
    assert "/jobs" in jobs_storage._meta_bank
    assert "/cluster" in cluster_storage._meta_bank


def test_per_ring_state_does_not_collide(opts):
    """
    Writing state through one ring's storage must not appear in
    another ring's storage.  Concrete check that the path keying
    actually keeps committed Raft state separated, not just that
    the strings differ.
    """
    cluster_storage = SaltStorage("node-a", opts, ring_id="cluster")
    jobs_storage = SaltStorage("node-a", opts, ring_id="jobs")

    cluster_storage.save_state(term=7, voted_for="node-a", leader_id="node-a")
    jobs_storage.save_state(term=2, voted_for="node-b", leader_id="node-b")

    # Each ring sees its own state, unaffected by the other.
    cluster = cluster_storage.load_state()
    jobs = jobs_storage.load_state()
    assert cluster["term"] == 7
    assert jobs["term"] == 2
    assert cluster["leader_id"] == "node-a"
    assert jobs["leader_id"] == "node-b"


def test_per_ring_log_does_not_collide(opts):
    """
    A log entry committed in one ring's storage is invisible from
    another ring.  The ring_id segment is the only thing keeping
    these apart; without it both Raft groups would corrupt each
    other's commit stream.
    """
    cluster_storage = SaltStorage("node-a", opts, ring_id="cluster")
    jobs_storage = SaltStorage("node-a", opts, ring_id="jobs")

    cluster_storage.append_log(
        LogEntry(term=1, index=0, cmd={"x": 1}, type=LogEntryType.COMMAND)
    )
    jobs_storage.append_log(
        LogEntry(term=1, index=0, cmd={"y": 2}, type=LogEntryType.COMMAND)
    )

    cluster_entries = cluster_storage.load_log()
    jobs_entries = jobs_storage.load_log()
    assert len(cluster_entries) == 1
    assert len(jobs_entries) == 1
    assert cluster_entries[0].cmd == {"x": 1}
    assert jobs_entries[0].cmd == {"y": 2}
