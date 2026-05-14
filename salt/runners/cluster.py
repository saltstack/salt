"""
Salt runner for cluster ring management and inspection.

Query-only operator surface for the Raft-backed cluster.  Reads come
from the per-master persisted Raft state on disk, so the runner does
not need IPC into the publish daemon's ``RaftService`` (which is a
separate process and not reachable from a runner subprocess).

CLI Examples:

.. code-block:: bash

    # Show this master's view of the cluster voter/learner set.
    salt-run cluster.members

    # Show this master's current ring state.
    salt-run cluster.ring_info

.. versionadded:: 3009.0
"""

import logging

log = logging.getLogger(__name__)


def members():
    """
    Return this master's view of the cluster's committed Raft membership.

    Reads the persisted Raft log and snapshot from the local
    ``SaltStorage`` and replays committed CONFIG entries through a
    fresh :class:`~salt.cluster.consensus.raft.log.MembershipStateMachine`.
    The returned set is what *this master* has applied locally — in a
    healthy cluster every master converges to the same answer, but the
    response is local-only and may briefly diverge during membership
    changes.

    Output:

    .. code-block:: python

        {
            "node_id":            str,         # this master's interface
            "voters":             [str, ...],  # sorted
            "learners":           [str, ...],  # sorted
            "membership_version": int,         # log index of latest CONFIG entry
            "voter_count":        int,
            "learner_count":      int,
        }

    ``membership_version`` is ``-1`` when no CONFIG entry has been
    applied yet (e.g. a fresh master that has not finished joining).

    CLI Example:

    .. code-block:: bash

        salt-run cluster.members

    .. versionadded:: 3009.0
    """
    # Lazy imports — the consensus modules are optional when Salt is
    # installed without cluster support.
    from salt.cluster.consensus.raft.log import (  # pylint: disable=import-outside-toplevel
        Log,
        LogEntryType,
        MembershipStateMachine,
    )
    from salt.cluster.consensus.storage import (  # pylint: disable=import-outside-toplevel
        SaltStorage,
    )

    node_id = __opts__.get("id") or __opts__.get("interface") or "unknown"

    membership_sm = MembershipStateMachine()
    storage = SaltStorage(node_id, __opts__)
    # ``Log.__init__`` loads any persisted snapshot and restores the
    # registered state machines from it.  We then replay any post-
    # snapshot CONFIG entries below.
    log_ = Log(
        storage=storage,
        state_machines={"membership_sm": membership_sm},
    )

    # Replay CONFIG entries that landed after the snapshot.  Storage
    # holds entries in log order; non-CONFIG entries (COMMAND, RING_CONFIG)
    # are skipped because they don't move membership.
    for entry in log_.entries:
        if entry.type == LogEntryType.CONFIG:
            membership_sm.apply(entry.cmd, index=entry.index)

    voters = membership_sm.current_voters()
    learners = membership_sm.current_learners()

    # Term and most-recently-observed leader come from ``save_state``.
    # See ``salt/cluster/consensus/storage.py`` for the on-disk shape.
    # ``leader_id`` is observability only — Raft itself derives the
    # leader from incoming AppendEntries.  Persisted here so a
    # read-only consumer answers "who's the leader" without IPC; may
    # be stale on a partitioned follower that hasn't heard from the
    # current term's leader.
    raw_state = storage.load_state()
    term = raw_state.get("term", 0)
    leader_id = raw_state.get("leader_id")

    # Voter-health surface, if the leader's watchdog has written its
    # sentinel.  Absence of the file means either auto-replacement was
    # never armed on this node or the watchdog has not run yet — either
    # way, an empty list is the honest answer.
    health = _read_health_sentinel()
    return {
        "node_id": node_id,
        "voters": voters,
        "learners": learners,
        "membership_version": membership_sm.membership_version,
        "voter_count": len(voters),
        "learner_count": len(learners),
        "leader_id": leader_id,
        "term": term,
        "unhealthy_voters": health.get("unhealthy_voters", []),
        "recently_demoted": health.get("recently_demoted", []),
    }


def _read_health_sentinel():
    """
    Read the per-master health sentinel written by
    ``RaftService._check_voter_health``.

    Returns an empty dict if the sentinel is missing or unreadable.
    The sentinel is leader-written today (so only the current leader's
    cachedir holds a fresh copy); a non-leader's reply has empty lists
    even when the cluster has unhealthy voters.  Operators should
    invoke this runner against a known voter to get accurate signal.
    """
    import json  # pylint: disable=import-outside-toplevel
    import os  # pylint: disable=import-outside-toplevel

    import salt.utils.files  # pylint: disable=import-outside-toplevel

    cachedir = __opts__.get("cachedir")
    if not cachedir:
        return {}
    path = os.path.join(cachedir, "cluster-health.json")
    try:
        with salt.utils.files.fopen(path) as fp:
            return json.load(fp)
    except (OSError, ValueError):
        return {}


def ring_info():
    """
    Return a snapshot of this master's ring state.

    Reads the per-process ring populated by
    :class:`~salt.cluster.consensus.service.RaftService`.  Output:

    .. code-block:: python

        {
            "is_clustered": bool,
            "node_count":   int,
            "nodes":        [str, ...],   # sorted
            "vnodes":       int,
        }

    Note that runners run in their own subprocess; the ring instance
    they see is **not** the publish daemon's ring.  In the current
    design that subprocess never has a populated ring, so this
    function will always report ``is_clustered=False`` until stage 2
    introduces a process-shared ring (see ``GAPS.md``).  The signature
    is stable so the caller's contract does not change when the
    backing source does.

    CLI Example:

    .. code-block:: bash

        salt-run cluster.ring_info
    """
    # Lazy import — the cluster module is optional when Salt is
    # installed without consensus support.
    from salt.cluster import ring_membership  # pylint: disable=import-outside-toplevel

    ring = ring_membership.get_ring()
    return {
        "is_clustered": bool(ring.is_clustered),
        "node_count": ring.node_count(),
        "nodes": sorted(ring.nodes()),
        "vnodes": ring.token_count() // max(1, ring.node_count() or 1),
    }


def ring_set(members=None, replicas=None):  # pylint: disable=unused-argument
    """
    Propose a new ring policy through Raft.

    Stage 1 placeholder — actual Raft propose path requires IPC from
    this runner subprocess to the publish daemon's
    :class:`RaftService`, which is not yet wired.  Today the function
    raises :class:`NotImplementedError` so an operator who tries it
    sees the gap loudly rather than thinking their commit landed.

    Once the IPC path lands, expected semantics:

    * *members*: ``"self"`` (default ring contents — every master a
      single-node ring, broadcast everywhere) or ``"voters"`` (ring
      tracks the Raft voter set so writes shard).
    * *replicas*: integer >= 1.  ``1`` (default) means each key has
      exactly one owner; higher values request additional replica
      owners for fault tolerance.

    Until the propose path lands, operators wanting to flip the
    policy can call ``RaftService.propose_ring_config`` directly from
    a python hook running inside the master process — see the
    functional tests under
    ``tests/pytests/functional/cluster/consensus/test_raft_service.py``.

    CLI Example (will raise until stage 2):

    .. code-block:: bash

        salt-run cluster.ring_set members=voters replicas=2
    """
    raise NotImplementedError(
        "cluster.ring_set: cross-process Raft propose path is not yet wired. "
        "Track GAPS.md for the follow-up that adds runner -> RaftService IPC."
    )
