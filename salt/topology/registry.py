"""
Shared registry of topology identity + accepted-peer state.

Backed by :class:`salt.utils.mmap_cache.MmapCache` so every process
in the master (publish daemon, MWorkers, future diagnostics) sees
the same authoritative view with no bespoke IPC.

Write model
-----------
Solo master
    publish daemon writes directly to the MmapCache under the
    cache's cross-process flock.

Clustered master
    write goes through Raft.  The
    :class:`salt.cluster.consensus.raft.topology.TopologyStateMachine`
    applies committed entries into this same MmapCache.  Every peer
    in the cluster converges on the same cache contents; readers
    everywhere see a consistent view through the standard
    MmapCache ``_cache_id`` remap cycle.

Read model (identical for both modes)
-------------------------------------
``MmapCache.get`` is O(1) average and does not take an exclusive
flock on the fast path.  Readers take a per-process ``RLock`` and
may re-mmap when ``_cache_id`` changes (default throttle 0.25s via
``_staleness_check_interval``); the previously-stated "lock-free
fast path" is accurate for the slot read itself but not for the
staleness-check path.

Cache file layout (same convention as ``salt.cache.mmap_cache``)
----------------------------------------------------------------
* ``<pki_dir>/master/topology_registry.mmap``        --- index
* ``<pki_dir>/master/topology_registry.mmap.heap``   --- values
* ``<pki_dir>/master/topology_registry.mmap.roster`` --- live-slot roster
* ``<pki_dir>/master/topology_registry.mmap.lock``   --- flock target

Keys
----
* ``__identity_pub__``  --- bytes of this master's identity
  public key.
* ``<cluster_id>``      --- msgpack-encoded :class:`PeerState`
  per accepted peer.

The identity *private* key is NOT in this cache.  It lives at
``<pki_dir>/master/master_identity.pem`` with 0400 permissions,
same as every other RSA private key Salt holds.  Keeping it out
of the mmap heap avoids inheriting the heap file's default umask
permissions and keeps the private material in exactly one place
on disk.

Reserved key names use the double-underscore prefix so they
cannot collide with any ``cluster_id`` (which validates as
``[a-z0-9][a-z0-9_-]*`` --- see
:data:`salt.config.topology.CLUSTER_ID_RE`).  The same regex is
re-validated at Raft apply time on peer-supplied cluster_ids so
a hostile peer cannot overwrite reserved slots.
"""

import logging

log = logging.getLogger(__name__)


RESERVED_IDENTITY_PUB_KEY = "__identity_pub__"
# Reserved MmapCache key for the identity public-key bytes.

RESERVED_IDENTITY_VERSION_KEY = "__identity_version__"
# Reserved MmapCache key for a monotonically-increasing identity
# version counter.  Bumped by
# :meth:`salt.cluster.consensus.raft.topology.TopologyStateMachine._handle_identity_key`
# when a rotation replaces an existing identity.  Peers that have
# the old key in their ``masters/`` dir will reject handshakes
# with the new key until re-accepted by the operator; the version
# counter lets diagnostics distinguish "same identity, different
# session" from "identity was rotated."


def pre_create(opts):
    """
    Materialize empty index/heap/roster/lock files for the
    registry MmapCache in the master process BEFORE any
    MWorker or publish daemon forks.

    Called from :func:`salt.topology.link_manager.pre_fork`.
    Matches the pattern used for breadcrumbs: the files must
    exist before any reader (MWorker) opens the cache.

    Idempotent: no-op if the files already exist with a valid
    header.
    """


def open_writer(opts):
    """
    Open the registry MmapCache in writable mode.

    Called exactly once per process by the publish daemon at
    startup, after any fork.  The returned cache instance is
    kept open for the daemon's lifetime so flock state and the
    mmap fd stay valid.

    **Owner-PID guard**: stores ``os.getpid()`` at open time and
    refuses subsequent ops if called from a different PID.
    Defense against accidental writes from MWorkers that
    inherited the module globals via fork.

    :raises RuntimeError: If called from a process other than
        the publish daemon.
    """


def open_reader(opts):
    """
    Open the registry MmapCache in read-only mode.

    Safe to call from any process after fork.  Each process gets
    its own MmapCache instance pointing at the same backing
    files.

    :returns: An MmapCache opened without write mode.
    """


def get_identity_pub(cache):
    """
    Return the identity public key bytes, or ``None`` if the
    registry has not been bootstrapped yet.
    """


def set_identity_pub(cache, pub_pem):
    """
    Store the identity public key bytes in the registry
    MmapCache.

    Caller must hold the publish daemon writer handle.  The
    private key is persisted separately to
    ``<pki_dir>/master/master_identity.pem`` with 0400
    permissions; this cache holds only the public half.

    Idempotent: no-op if the stored bytes already match.
    """


def get_peer(cache, cluster_id):
    """
    Return the PeerState-shaped dict for ``cluster_id`` or
    ``None`` if the peer is not currently attached.

    The dict shape matches
    :class:`salt.cluster.consensus.raft.topology.PeerState`
    fields but is deliberately kept as a plain dict so this
    module does not have to import the Raft state machine for
    readers.
    """


def set_peer(cache, cluster_id, state):
    """
    Write a PeerState dict for ``cluster_id`` to the registry.

    Writer-only; caller must hold the publish daemon writer
    handle.  Overwrites any existing entry for the same
    ``cluster_id``.
    """


def delete_peer(cache, cluster_id):
    """
    Remove the peer entry for ``cluster_id``.  Writer-only.

    Idempotent: no-op if the peer was not present.
    """


def list_peer_ids(cache):
    """
    Return the ``cluster_id`` of every currently-attached peer.

    Backed by ``MmapCache.list_items`` which scans the roster
    file in O(occupied), independent of table size.
    """
