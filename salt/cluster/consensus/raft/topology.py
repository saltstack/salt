"""
Raft state machine for master topology --- the write path for
clustered masters.

Registered alongside the existing cluster state machines in
:class:`salt.cluster.consensus.service.RaftService` when
``cluster_peers`` is non-empty.  On commit of a ``MASTER_*`` log
entry, the apply handler writes the resulting state into the
shared MmapCache at :mod:`salt.topology.registry`.

For solo (non-clustered) masters, this module is never imported
--- the publish daemon writes to the same MmapCache directly
without going through Raft.  The MmapCache contents are the
authoritative read source regardless of mode; this state machine
is purely the clustered write path.

Scaling
-------
State is ``O(direct_peers)``, bounded regardless of total minion
count or routing graph size.  Routing table and summary state are
NOT held here --- they are soft state in the publish daemon,
rebuilt from the gossip stream after any restart.

Interface
---------
Methods ``apply``, ``get_snapshot``, ``restore_snapshot`` match
the :class:`BaseStateMachine` interface in
:mod:`salt.cluster.consensus.raft.log` exactly.  Earlier RFC
drafts used ``on_apply`` / ``snapshot`` / ``restore``; those names
did not match what the Raft Node actually calls and would have
caused committed entries to never apply.
"""

import logging
from typing import NamedTuple

log = logging.getLogger(__name__)


class PeerState(NamedTuple):
    """
    Per-peer state carried in the Raft log and applied into the
    registry MmapCache.

    :param cluster_id: Peer's ``cluster_id``.
    :param public_key: Peer's ``master_identity.pub`` as PEM
        bytes.
    :param endpoints: Addresses learned during handshake.
        Expands as the peer cluster gossips its updated endpoint
        list via subsequent summaries.
    :param attached_at: Unix timestamp when the attach was
        accepted.

    ``last_summary`` is deliberately NOT in PeerState.  Summaries
    are soft state kept outside the Raft log and outside snapshots
    --- including them in snapshots would cause a joining peer's
    snapshot-restore view to differ from its live-replay view
    (soft-state replay comes from current gossip, not from the
    log).  Live summary state is tracked in the publish daemon's
    router.
    """

    cluster_id: str
    public_key: bytes
    endpoints: tuple
    attached_at: float


class TopologyStateMachine:
    """
    Raft-committed write path for the topology registry.

    This class is the Raft side; it does not hold its own
    authoritative state.  Instead, each ``apply`` call writes
    into the registry :class:`salt.utils.mmap_cache.MmapCache`
    that both this process and the MWorker readers see.

    Attributes:
        opts: Master opts.
        registry: Writable handle onto the registry MmapCache
            (opened once in this process, kept across applies).
    """

    def __init__(self, opts):
        """
        :param opts: Master opts.
        """

    def apply(self, cmd, client_id, sequence_num, index=-1):
        """
        Apply a committed Raft log entry.

        Matches :class:`salt.cluster.consensus.raft.log.BaseStateMachine`
        signature exactly.  Called by the Raft Node on commit;
        must be idempotent.

        Dispatches on ``cmd["type"]`` (a ``LogEntryType`` value):

        * ``MASTER_IDENTITY_KEY`` -> :meth:`_handle_identity_key`
        * ``MASTER_PEER_ATTACH`` -> :meth:`_handle_peer_attach`
        * ``MASTER_PEER_DETACH`` -> :meth:`_handle_peer_detach`

        Unknown entry types are logged at DEBUG and ignored ---
        a different state machine handles them.

        Note: ``MASTER_PEER_SUMMARY`` is NOT a replicated log
        entry type; summaries are soft state received directly
        from inbound links by the router, not committed to Raft.
        ``MASTER_PEER_ROUTE`` was in a prior design draft and was
        removed; routes are derived from the summary stream
        locally.
        """

    def get_snapshot(self):
        """
        Serialize the registry contents for Raft snapshotting.

        Matches :class:`BaseStateMachine.get_snapshot` signature.
        Format is msgpack with a schema version prefix.
        Includes the identity public key and the peer registry;
        excludes any soft state (last_summary, routes) that
        would make snapshot replay diverge from live gossip
        replay.
        """

    def restore_snapshot(self, data):
        """
        Replace in-memory state and MmapCache contents from a
        Raft snapshot.

        Matches :class:`BaseStateMachine.restore_snapshot`
        signature.  Called during joiner catch-up or follower
        restart.  Applied in one write-locked transaction on the
        registry MmapCache so readers never see a partial
        restore.
        """

    def _handle_identity_key(self, entry):
        """
        Apply ``MASTER_IDENTITY_KEY``.

        **Idempotent on repeat with identical bytes.**  Writes
        the identity public key bytes to the registry MmapCache
        under the reserved key ``__identity_pub__``.  Also
        persists the keypair to
        ``pki_dir/master/master_identity.{pub,pem}`` with strict
        permissions (0400 priv, 0444 pub) for other components
        that read the files directly (e.g. ``salt-key -F``).

        The private key is NOT stored in the MmapCache --- it
        lives only on disk at 0400 to avoid inheriting the
        MmapCache heap file's default umask permissions.

        **Rotation path:** when the entry's bytes differ from
        the stored bytes, this is an identity rotation.  Replace
        the keypair in the registry + on disk, increment the
        ``__identity_version__`` counter, and tear down any
        existing peer-master links so they re-authenticate with
        the new key on reconnect.  Peers that have the old key
        in their ``masters/`` dir will reject the new key until
        re-accepted by the operator; this is intentional (an
        operator-visible rotation).
        """

    def _handle_peer_attach(self, entry):
        """
        Apply ``MASTER_PEER_ATTACH``.

        **Hostile-peer validation at apply time**: re-validates
        the entry's ``cluster_id`` against
        :data:`salt.config.topology.CLUSTER_ID_RE`.  Local
        config validation is not enough --- a hostile or buggy
        peer could claim a reserved name like ``__identity_pub__``
        and overwrite protected slots.  Rejects invalid names
        with CRITICAL log; the entry is applied as a no-op so
        state converges across cluster peers.

        **Conflict resolution on duplicate cluster_id**: if a
        PeerState for the same ``cluster_id`` already exists
        with a different ``public_key``, the apply is rejected
        unless the entry carries an explicit ``force_replace``
        flag.  Attempting to attach a different-keyed peer
        under an existing name is logged at CRITICAL --- this
        is either an operator mistake (re-generated the peer's
        identity without first detaching) or an attack.

        On accept: writes a new :class:`PeerState` entry into
        the registry MmapCache keyed by ``cluster_id``.  Moves
        the accepted ``<cluster_id>.pub`` from
        ``pki_dir/masters_pre/`` to ``pki_dir/masters/`` if it
        was pending; writes the key from the entry if the file
        is absent (follower that joined after the attach was
        committed).

        **Propose-first ordering**: salt-key does NOT rename
        the file; this handler does.  Keeps file-system state
        in sync with Raft state across every cluster peer.
        """

    def _handle_peer_detach(self, entry):
        """
        Apply ``MASTER_PEER_DETACH``.

        Removes the peer entry from the registry MmapCache and
        moves the key file to ``masters_denied/`` or deletes it
        depending on the ``reason`` field.

        Also signals the publish daemon's
        :mod:`salt.topology.link_manager` to invalidate any
        routing-table entries whose next-hop was this peer.
        The routing table itself is not Raft-replicated, so
        this signal is a function call within the same process
        (publish daemon only).
        """

    def generate_identity_key(self):
        """
        Generate a fresh RSA keypair for the master identity.

        Caller is responsible for proposing a
        ``MASTER_IDENTITY_KEY`` Raft entry with the returned
        bytes; this method does NOT write to disk or MmapCache.
        Disk and cache persistence happen in
        :meth:`_handle_identity_key` on commit.

        :returns: ``(pub_pem, priv_pem)`` as bytes.
        """

    def is_bootstrapped(self):
        """
        Return True once the identity key is committed to Raft
        and reflected in the registry MmapCache.
        """
