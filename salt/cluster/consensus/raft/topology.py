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
import os
import re
import shutil
from typing import NamedTuple

import salt.crypt
import salt.topology.registry as registry
import salt.utils.files
import salt.utils.msgpack
from salt.cluster.consensus.raft.log import BaseStateMachine, LogEntryType
from salt.config.topology import CLUSTER_ID_RE

log = logging.getLogger(__name__)


# Snapshot envelope version prefix.  Bumping is a breaking change
# for on-disk snapshot compatibility; the restore path checks the
# first field and refuses to restore unknown versions so a joiner
# with an older binary cannot silently misread a newer snapshot.
TOPOLOGY_SNAPSHOT_VERSION = "topology.snapshot.v1"

# Compiled regex for the hostile-peer re-validation at apply time.
_CLUSTER_ID_RE = re.compile(CLUSTER_ID_RE)

# Reserved MmapCache sentinel keys that must never be used as a
# peer ``cluster_id``.  Imported from the registry for a single
# source of truth; mirrored here so the SM can reject at apply
# time before touching the writer handle.
_RESERVED_IDS = frozenset(
    {
        registry.RESERVED_IDENTITY_PUB_KEY,
        registry.RESERVED_IDENTITY_VERSION_KEY,
    }
)


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


class TopologyStateMachine(BaseStateMachine):
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
        self.opts = opts
        # Materialize the mmap files on first construction so the
        # writer open below finds a valid header.  ``pre_create``
        # is idempotent --- a no-op if the files already exist.
        registry.pre_create(opts)
        self.registry = registry.open_writer(opts)
        # Dispatch table keyed by LogEntryType value.
        self._handlers = {
            LogEntryType.MASTER_IDENTITY_KEY: self._handle_identity_key,
            LogEntryType.MASTER_PEER_ATTACH: self._handle_peer_attach,
            LogEntryType.MASTER_PEER_DETACH: self._handle_peer_detach,
        }

    # ------------------------------------------------------------------
    # BaseStateMachine interface
    # ------------------------------------------------------------------

    def apply(self, cmd, client_id=None, sequence_num=None, index=-1):
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
        if not isinstance(cmd, dict):
            log.debug(
                "TopologyStateMachine: ignoring non-dict cmd (type=%s)",
                type(cmd).__name__,
            )
            return
        entry_type = cmd.get("type")
        handler = self._handlers.get(entry_type)
        if handler is None:
            log.debug(
                "TopologyStateMachine: no handler for entry type %r; ignoring",
                entry_type,
            )
            return
        handler(cmd)

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
        peers = {}
        # Use list_keys + get rather than list_items because
        # list_items rstrips trailing NUL bytes from values, which
        # can corrupt a msgpack blob whose last byte is 0x00.  get()
        # reads exactly ``length`` bytes from the heap.
        for cluster_id in self.registry.list_keys():
            if cluster_id in _RESERVED_IDS:
                continue
            decoded = registry.get_peer(self.registry, cluster_id)
            if decoded is None:
                continue
            peers[cluster_id] = decoded
        identity_pub = registry.get_identity_pub(self.registry) or b""
        identity_version = _read_identity_version(self.registry)
        payload = {
            "version": TOPOLOGY_SNAPSHOT_VERSION,
            "identity_pub": identity_pub,
            "identity_version": identity_version,
            "peers": peers,
        }
        return salt.utils.msgpack.packb(payload, use_bin_type=True)

    def restore_snapshot(self, data):
        """
        Replace in-memory state and MmapCache contents from a
        Raft snapshot.

        Matches :class:`BaseStateMachine.restore_snapshot`
        signature.  Called during joiner catch-up or follower
        restart.  The restore replaces the entire registry
        contents (identity + peers) so a joiner's post-restore
        view matches a leader that produced the snapshot.
        """
        if data is None:
            return
        try:
            payload = salt.utils.msgpack.unpackb(bytes(data), raw=False)
        except (ValueError, TypeError) as exc:
            log.error(
                "TopologyStateMachine: snapshot payload failed to decode: %s",
                exc,
            )
            return
        if not isinstance(payload, dict):
            log.error(
                "TopologyStateMachine: snapshot payload must be a dict, got %s",
                type(payload).__name__,
            )
            return
        version = payload.get("version")
        if version != TOPOLOGY_SNAPSHOT_VERSION:
            log.error(
                "TopologyStateMachine: snapshot version %r not understood "
                "(expected %r); refusing to restore",
                version,
                TOPOLOGY_SNAPSHOT_VERSION,
            )
            return
        # Wipe the current peer set so the restore truly replaces
        # state rather than merging into whatever was there.
        for existing in list(registry.list_peer_ids(self.registry)):
            registry.delete_peer(self.registry, existing)
        # Identity half.
        identity_pub = payload.get("identity_pub") or b""
        if identity_pub:
            if isinstance(identity_pub, str):
                identity_pub = identity_pub.encode("utf-8")
            registry.set_identity_pub(self.registry, identity_pub)
        else:
            # Explicit clear so a snapshot that pre-dates identity
            # bootstrap wipes any locally-stashed key.
            self.registry.delete(registry.RESERVED_IDENTITY_PUB_KEY)
        identity_version = payload.get("identity_version") or 0
        try:
            version_int = int(identity_version)
        except (TypeError, ValueError):
            version_int = 0
        self.registry.put(
            registry.RESERVED_IDENTITY_VERSION_KEY,
            str(version_int).encode("ascii"),
        )
        # Peer half.
        peers = payload.get("peers") or {}
        if isinstance(peers, dict):
            for cluster_id, state in peers.items():
                if cluster_id in _RESERVED_IDS:
                    continue
                if not isinstance(state, dict):
                    continue
                registry.set_peer(
                    self.registry,
                    cluster_id,
                    _normalise_peer_state(cluster_id, state),
                )

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

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

        **Rotation path:** when the entry's bytes differ from
        the stored bytes, this is an identity rotation.  Replace
        the keypair in the registry + on disk and increment the
        ``__identity_version__`` counter.  Peers that have the
        old key in their ``masters/`` dir will reject the new
        key until re-accepted by the operator; this is
        intentional (an operator-visible rotation).
        """
        pub_pem = entry.get("public_key")
        if not pub_pem:
            log.error(
                "TopologyStateMachine: MASTER_IDENTITY_KEY entry missing public_key"
            )
            return
        if isinstance(pub_pem, str):
            pub_pem = pub_pem.encode("utf-8")
        existing = registry.get_identity_pub(self.registry)
        if existing == pub_pem:
            # Idempotent re-apply: no state change, no version bump.
            self._persist_identity_disk(pub_pem, entry.get("private_key"))
            return
        # First commit or rotation: write pub + bump version.
        registry.set_identity_pub(self.registry, pub_pem)
        prior_version = _read_identity_version(self.registry)
        new_version = prior_version + 1
        self.registry.put(
            registry.RESERVED_IDENTITY_VERSION_KEY,
            str(new_version).encode("ascii"),
        )
        self._persist_identity_disk(pub_pem, entry.get("private_key"))
        if existing is not None:
            log.warning(
                "TopologyStateMachine: identity key rotated (version=%d); "
                "peers must re-accept the new key",
                new_version,
            )

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
        flag.
        """
        cluster_id = entry.get("cluster_id")
        if not isinstance(cluster_id, str) or not cluster_id:
            log.critical(
                "TopologyStateMachine: MASTER_PEER_ATTACH missing cluster_id; "
                "rejecting entry"
            )
            return
        if cluster_id in _RESERVED_IDS or not _CLUSTER_ID_RE.match(cluster_id):
            log.critical(
                "TopologyStateMachine: MASTER_PEER_ATTACH cluster_id %r is "
                "invalid or reserved; rejecting entry (hostile-peer defense)",
                cluster_id,
            )
            return
        public_key = entry.get("public_key")
        if public_key is None:
            log.critical(
                "TopologyStateMachine: MASTER_PEER_ATTACH for %r missing "
                "public_key; rejecting entry",
                cluster_id,
            )
            return
        if isinstance(public_key, str):
            public_key = public_key.encode("utf-8")
        else:
            public_key = bytes(public_key)
        existing = registry.get_peer(self.registry, cluster_id)
        if existing is not None:
            if existing.get("public_key") == public_key:
                # Idempotent re-apply.
                return
            if not entry.get("force_replace"):
                log.critical(
                    "TopologyStateMachine: MASTER_PEER_ATTACH for %r would "
                    "overwrite an existing peer with a different public_key "
                    "and force_replace is not set; rejecting entry",
                    cluster_id,
                )
                return
            log.warning(
                "TopologyStateMachine: MASTER_PEER_ATTACH for %r replacing "
                "an existing public_key (force_replace=True)",
                cluster_id,
            )
        state = _normalise_peer_state(
            cluster_id,
            {
                "cluster_id": cluster_id,
                "public_key": public_key,
                "endpoints": entry.get("endpoints") or (),
                "attached_at": entry.get("attached_at") or 0.0,
            },
        )
        registry.set_peer(self.registry, cluster_id, state)
        self._finalise_accepted_key_file(cluster_id, public_key)

    def _handle_peer_detach(self, entry):
        """
        Apply ``MASTER_PEER_DETACH``.

        Removes the peer entry from the registry MmapCache and
        moves the key file to ``masters_denied/`` for
        ``reason="rejected"`` or deletes it for other reasons.
        Idempotent on an already-detached peer.
        """
        cluster_id = entry.get("cluster_id")
        if not isinstance(cluster_id, str) or not cluster_id:
            log.error(
                "TopologyStateMachine: MASTER_PEER_DETACH missing cluster_id; "
                "ignoring"
            )
            return
        if cluster_id in _RESERVED_IDS:
            log.critical(
                "TopologyStateMachine: MASTER_PEER_DETACH for reserved key %r "
                "ignored",
                cluster_id,
            )
            return
        reason = entry.get("reason") or "revoked"
        registry.delete_peer(self.registry, cluster_id)
        self._move_detached_key_file(cluster_id, reason)

    # ------------------------------------------------------------------
    # Identity helpers
    # ------------------------------------------------------------------

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
        keysize = int(self.opts.get("keysize") or 2048)
        priv_str, pub_str = salt.crypt.gen_keys(keysize)
        if isinstance(priv_str, str):
            priv_pem = priv_str.encode("utf-8")
        else:
            priv_pem = bytes(priv_str)
        if isinstance(pub_str, str):
            pub_pem = pub_str.encode("utf-8")
        else:
            pub_pem = bytes(pub_str)
        return pub_pem, priv_pem

    def is_bootstrapped(self):
        """
        Return True once the identity key is committed to Raft
        and reflected in the registry MmapCache.
        """
        return registry.get_identity_pub(self.registry) is not None

    # ------------------------------------------------------------------
    # Internal: on-disk file hand-offs
    # ------------------------------------------------------------------

    def _master_pki_subdir(self, name):
        """Return (and ensure) ``pki_dir/<name>/``."""
        path = os.path.join(self.opts["pki_dir"], name)
        try:
            os.makedirs(path, exist_ok=True)
        except OSError:  # pragma: no cover - best-effort
            pass
        return path

    def _persist_identity_disk(self, pub_pem, priv_pem):
        """
        Write master_identity.{pub,pem} with strict perms.

        Idempotent on identical bytes.  The private half is
        optional: a snapshot restore on a follower will carry only
        the public key (private material never crosses the wire),
        so this method accepts ``priv_pem=None``.
        """
        master_dir = os.path.join(self.opts["pki_dir"], "master")
        try:
            os.makedirs(master_dir, exist_ok=True)
        except OSError:
            log.exception("TopologyStateMachine: could not create %s", master_dir)
            return
        pub_path = os.path.join(master_dir, "master_identity.pub")
        _write_file_atomic(pub_path, pub_pem, mode=0o444)
        if priv_pem is not None:
            if isinstance(priv_pem, str):
                priv_pem = priv_pem.encode("utf-8")
            else:
                priv_pem = bytes(priv_pem)
            priv_path = os.path.join(master_dir, "master_identity.pem")
            _write_file_atomic(priv_path, priv_pem, mode=0o400)

    def _finalise_accepted_key_file(self, cluster_id, public_key):
        """
        Move or create ``masters/<cluster_id>.pub`` for an accepted peer.

        If the file is already in ``masters_pre/``, rename it into
        ``masters/`` (operator-visible move) so file-system state
        tracks Raft state across every cluster peer.  Otherwise
        (follower that joined after the attach was committed), the
        public key bytes from the Raft entry are written out.
        """
        masters_dir = self._master_pki_subdir("masters")
        pre_dir = self._master_pki_subdir("masters_pre")
        accepted_path = os.path.join(masters_dir, f"{cluster_id}.pub")
        pre_path = os.path.join(pre_dir, f"{cluster_id}.pub")
        try:
            if os.path.exists(pre_path):
                # Move; the ``masters_pre`` convention is operator-
                # visible so we don't duplicate the bytes --- rename.
                os.replace(pre_path, accepted_path)
            else:
                _write_file_atomic(accepted_path, public_key, mode=0o644)
        except OSError:
            log.exception(
                "TopologyStateMachine: failed to finalise accepted key file "
                "for peer %r",
                cluster_id,
            )

    def _move_detached_key_file(self, cluster_id, reason):
        """
        Move or delete the on-disk key file for a detached peer.

        * ``reason="rejected"`` -> move to ``masters_denied/``
        * any other reason (default ``"revoked"``) -> delete
        """
        masters_dir = self._master_pki_subdir("masters")
        accepted_path = os.path.join(masters_dir, f"{cluster_id}.pub")
        if not os.path.exists(accepted_path):
            return
        try:
            if reason == "rejected":
                denied_dir = self._master_pki_subdir("masters_denied")
                denied_path = os.path.join(denied_dir, f"{cluster_id}.pub")
                shutil.move(accepted_path, denied_path)
            else:
                os.remove(accepted_path)
        except OSError:
            log.exception(
                "TopologyStateMachine: failed to move/delete key file for "
                "detached peer %r (reason=%s)",
                cluster_id,
                reason,
            )


# ---------------------------------------------------------------------------
# Module-local helpers
# ---------------------------------------------------------------------------


def _normalise_peer_state(cluster_id, raw):
    """Coerce a peer-state dict into the shape ``registry.set_peer`` expects."""
    public_key = raw.get("public_key") or b""
    if isinstance(public_key, str):
        public_key = public_key.encode("utf-8")
    else:
        public_key = bytes(public_key)
    endpoints = raw.get("endpoints") or ()
    try:
        endpoints = tuple(endpoints)
    except TypeError:
        endpoints = ()
    try:
        attached_at = float(raw.get("attached_at") or 0.0)
    except (TypeError, ValueError):
        attached_at = 0.0
    return {
        "cluster_id": cluster_id,
        "public_key": public_key,
        "endpoints": endpoints,
        "attached_at": attached_at,
    }


def _decode_peer_payload(raw):
    """Decode a peer value from the raw bytes stored in the MmapCache."""
    if raw is None:
        return None
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    try:
        data = salt.utils.msgpack.unpackb(bytes(raw), raw=False)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    public_key = data.get("public_key")
    if isinstance(public_key, str):
        data["public_key"] = public_key.encode("utf-8")
    endpoints = data.get("endpoints")
    if endpoints is not None:
        data["endpoints"] = tuple(endpoints)
    return data


def _read_identity_version(cache):
    """
    Return the identity version counter as an int, defaulting to 0.

    The counter is stored as ASCII-encoded bytes in the MmapCache
    (``put`` can only take bytes/str) so the SM owns the string ->
    int coercion.
    """
    raw = cache.get(registry.RESERVED_IDENTITY_VERSION_KEY, default=None)
    if raw is None:
        return 0
    if isinstance(raw, int):
        return raw
    if isinstance(raw, bytes):
        try:
            return int(raw.decode("ascii"))
        except (UnicodeDecodeError, ValueError):
            return 0
    if isinstance(raw, str):
        try:
            return int(raw)
        except ValueError:
            return 0
    return 0


def _write_file_atomic(path, data, mode):
    """Write ``data`` to ``path`` and chmod ``mode``.  Overwrites in place."""
    tmp = f"{path}.tmp"
    with salt.utils.files.fopen(tmp, "wb") as fh:
        fh.write(data)
    os.chmod(tmp, mode)
    os.replace(tmp, path)
