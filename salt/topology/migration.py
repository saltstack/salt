"""
One-shot migration of topology state when a master transitions
from solo to clustered.

The on-disk registry layout is identical in both modes --- the
only thing that changes is the writer.  A solo master writes
directly; a clustered master routes writes through Raft so
every peer in the cluster converges on the same cache contents.

This module handles the transition: when a formerly-solo master
starts up with ``cluster_peers`` set for the first time, the
publish daemon proposes Raft entries from the current registry
contents so the new cluster peers get the same state via
commit.

The reverse direction (clustered -> solo) is not supported in
v1.  Collapsing a cluster to a single master requires manual
migration.
"""

import logging

log = logging.getLogger(__name__)


def needs_migration(opts):
    """
    Return True if the master is now clustered but the Raft
    topology state machine's view does not match the local
    registry contents.

    **Peer-set comparison, not bootstrap-flag check.**  The
    naive implementation would return False as soon as
    ``is_bootstrapped()`` is True (identity committed), but a
    crash between proposing ``MASTER_IDENTITY_KEY`` and
    proposing the first ``MASTER_PEER_ATTACH`` would leave the
    identity committed and the peer set partially migrated ---
    the next startup must detect this and resume.

    Implementation: compute set-difference between the local
    registry's attached-peer ids and the Raft state machine's
    applied-peer ids.  Return True if the local set is a
    non-empty superset of the applied set.

    False otherwise, including:

    * Fresh clustered install (empty registry; nothing to
      migrate).
    * Steady-state clustered run (both sets agree, Raft state
      and registry kept in sync by apply handlers).
    * Solo master (``cluster_peers`` empty).
    """


def promote_solo_to_clustered(opts, raft_service):
    """
    Propose Raft entries from the current registry so the
    clustered state machine converges on the solo master's
    pre-cluster state.

    Steps, in order:

    1. If the Raft state is not bootstrapped, propose
       ``MASTER_IDENTITY_KEY`` with the stored identity
       keypair.
    2. For each attached peer in the registry that is NOT
       already in the Raft applied set, propose
       ``MASTER_PEER_ATTACH`` with the stored PeerState.
       (Only the un-proposed subset; see :func:`needs_migration`
       for how this set is computed on resume.)

    Routes are rebuilt by the state machine from the summary
    stream after startup; no explicit routing migration.
    Summaries are not Raft-replicated.

    **Idempotent across crash resume.**  Each ``_handle_*`` on
    the state machine is a no-op when the apply would not
    change state, AND this function iterates only the
    un-proposed subset, so a replay after crash picks up
    exactly where it stopped without double-applying.

    After all entries commit, the migration is complete; the
    registry remains the authoritative read source, and future
    writes flow through Raft.
    """
