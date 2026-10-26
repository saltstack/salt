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
import os

import salt.topology.registry as registry
import salt.utils.files
from salt.cluster.consensus.raft.log import LogEntryType
from salt.cluster.consensus.raft.topology import (
    _read_raft_applied_peers as _sm_read_applied_peers,
)
from salt.cluster.consensus.raft.topology import build_peer_attach_entry

log = logging.getLogger(__name__)


def _is_clustered(opts):
    """
    Return True if the master is configured as a cluster peer.

    Migration is a clustered-mode concern only; a solo master never
    needs to migrate even if its registry happens to contain peer
    rows (test fixture leftovers, operator mis-configuration, etc.).
    """
    peers = opts.get("cluster_peers")
    if not peers:
        return False
    return True


def _registry_identity_pub(cache):
    """Return the identity_pub bytes stored in the registry, or None."""
    return registry.get_identity_pub(cache)


def _raft_is_bootstrapped(cache):
    """
    Return True once the Raft path has committed a
    ``MASTER_IDENTITY_KEY`` entry.

    Distinct from "registry has identity_pub" --- a solo master
    writes identity_pub directly without ever going through Raft,
    so the two signals must stay separate for crash-resume to work.
    """
    raw = cache.get(registry.RESERVED_RAFT_BOOTSTRAPPED_KEY, default=None)
    if raw is None:
        return False
    if isinstance(raw, bytes):
        return raw == b"1"
    if isinstance(raw, str):
        return raw == "1"
    return False


def _registry_peer_ids(cache):
    """Return the set of attached-peer ``cluster_id`` strings."""
    return set(registry.list_peer_ids(cache))


def _raft_applied_peer_ids(cache):
    """Return the set of peer ``cluster_id`` strings applied via Raft."""
    return _sm_read_applied_peers(cache)


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
    non-empty superset of the applied set, OR if identity_pub
    is set in the registry but the Raft side has not yet seen
    a ``MASTER_IDENTITY_KEY`` commit.

    False otherwise, including:

    * Fresh clustered install (empty registry; nothing to
      migrate).
    * Steady-state clustered run (both sets agree, Raft state
      and registry kept in sync by apply handlers).
    * Solo master (``cluster_peers`` empty).
    """
    if not _is_clustered(opts):
        return False
    reader = registry.open_reader(opts)
    try:
        identity_present = _registry_identity_pub(reader) is not None
        raft_bootstrapped = _raft_is_bootstrapped(reader)
        if identity_present and not raft_bootstrapped:
            return True
        local_peers = _registry_peer_ids(reader)
        applied_peers = _raft_applied_peer_ids(reader)
        pending = local_peers - applied_peers
        return bool(pending)
    finally:
        reader.close()


def _read_identity_private(opts):
    """
    Return the identity private-key PEM bytes from disk, or None.

    The private half is deliberately not in the registry MmapCache
    (:mod:`salt.topology.registry` keeps only the public half).
    The solo-master publish daemon writes it to
    ``<pki_dir>/master/master_identity.pem`` with 0400 perms; the
    migration pass reads it back from there so the Raft entry can
    carry both halves and every cluster peer ends up with a
    writable private key on disk.
    """
    priv_path = os.path.join(opts["pki_dir"], "master", "master_identity.pem")
    if not os.path.isfile(priv_path):
        return None
    try:
        with salt.utils.files.fopen(priv_path, "rb") as fh:
            return fh.read()
    except OSError:
        log.exception(
            "migration: failed to read identity private key from %s",
            priv_path,
        )
        return None


def _collect_pending(opts):
    """
    Build the ordered list of Raft entries that
    :func:`promote_solo_to_clustered` must propose.

    The list ordering is deterministic:

    * ``MASTER_IDENTITY_KEY`` first, iff identity_pub is set in
      the registry but the Raft side has not yet seen a bootstrap
      commit.
    * One ``MASTER_PEER_ATTACH`` entry per peer in
      ``registry.list_peer_ids`` that is not yet in the
      Raft-applied set, in sorted ``cluster_id`` order so every
      cluster peer that drives migration produces the same log
      entry stream.

    Reserved sentinel keys never leak into the output --- they
    are filtered by :func:`registry.list_peer_ids` already, but
    the migration module re-filters defensively.
    """
    reader = registry.open_reader(opts)
    try:
        entries = []
        identity_pub = _registry_identity_pub(reader)
        raft_bootstrapped = _raft_is_bootstrapped(reader)
        if identity_pub is not None and not raft_bootstrapped:
            cmd = {
                "type": LogEntryType.MASTER_IDENTITY_KEY,
                "public_key": identity_pub,
            }
            priv_pem = _read_identity_private(opts)
            if priv_pem is not None:
                cmd["private_key"] = priv_pem
            entries.append(cmd)
        local_peers = _registry_peer_ids(reader)
        applied_peers = _raft_applied_peer_ids(reader)
        pending = sorted(local_peers - applied_peers)
        for cluster_id in pending:
            # Defensive: list_peer_ids already filters reserved
            # keys, but a corrupt roster must not escape here.
            if (
                cluster_id in registry._RESERVED_KEYS
            ):  # pylint: disable=protected-access
                continue
            peer = registry.get_peer(reader, cluster_id)
            if peer is None:
                continue
            entries.append(
                build_peer_attach_entry(
                    cluster_id=cluster_id,
                    public_key=peer.get("public_key") or b"",
                    endpoints=peer.get("endpoints") or (),
                    attached_at=peer.get("attached_at") or 0.0,
                )
            )
        return entries
    finally:
        reader.close()


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

    :param opts:          Master opts.  ``cluster_peers`` must be
                          non-empty; a solo-master caller is a
                          no-op.
    :param raft_service:  Object exposing ``propose(cmd)``.  The
                          caller owns leader-only + wait-for-commit
                          semantics; migration logic treats
                          ``propose`` as "the cmd will eventually
                          apply."
    """
    if not _is_clustered(opts):
        log.debug(
            "migration.promote_solo_to_clustered: cluster_peers empty; nothing to do"
        )
        return
    entries = _collect_pending(opts)
    if not entries:
        log.debug(
            "migration.promote_solo_to_clustered: registry already converged "
            "with Raft applied state; nothing to propose"
        )
        return
    log.info(
        "migration.promote_solo_to_clustered: proposing %d entries "
        "(identity+peers) to converge Raft on the solo pre-cluster state",
        len(entries),
    )
    for entry in entries:
        raft_service.propose(entry)
