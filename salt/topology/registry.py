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
import os

import salt.utils.msgpack
from salt.utils.mmap_cache import MmapCache

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

_RESERVED_KEYS = frozenset([RESERVED_IDENTITY_PUB_KEY, RESERVED_IDENTITY_VERSION_KEY])

# Default sizing when opts do not provide values.  The index is a
# fixed-size open-addressing table; 4096 slots at the default
# ``slot_size`` costs well under 1 MiB on disk and comfortably
# covers the practical peer-count ceiling for a single logical
# master.
_DEFAULT_CACHE_SIZE = 4096
_DEFAULT_KEY_SIZE = 64


def _cache_paths(opts):
    """
    Return the on-disk paths used by the registry MmapCache.

    All four files sit under ``<pki_dir>/master/`` next to the
    master identity keypair, keeping topology state alongside the
    master's existing PKI material.
    """
    master_dir = os.path.join(opts["pki_dir"], "master")
    index_path = os.path.join(master_dir, "topology_registry.mmap")
    return master_dir, index_path


def _cache_sizing(opts):
    """
    Resolve ``(size, key_size)`` from opts with sensible defaults.
    """
    size = opts.get("topology_registry_cache_size") or _DEFAULT_CACHE_SIZE
    key_size = opts.get("topology_registry_cache_key_size") or _DEFAULT_KEY_SIZE
    return int(size), int(key_size)


def _build_cache(opts, write):
    """
    Construct an :class:`MmapCache` wired at the registry's
    well-known paths and sizing.  Writers initialise fresh files
    on first open; readers only map existing files.
    """
    master_dir, index_path = _cache_paths(opts)
    size, key_size = _cache_sizing(opts)
    if write:
        os.makedirs(master_dir, exist_ok=True)
    cache = MmapCache(
        path=index_path,
        size=size,
        key_size=key_size,
    )
    cache.open(write=write)
    return cache


class _WriterHandle:
    """
    Thin wrapper around :class:`MmapCache` that enforces the
    owner-PID guard.

    Captures ``os.getpid()`` at open time.  Every write-side call
    in this module checks that the current PID still matches
    before touching the cache.  A fork copies this object into
    the child, but the child's ``os.getpid()`` differs so the
    guard fires and prevents accidental cache mutation from an
    MWorker that inherited the publish daemon's handle.
    """

    __slots__ = ("_cache", "_owner_pid")

    def __init__(self, cache):
        self._cache = cache
        self._owner_pid = os.getpid()

    def _check_pid(self):
        """Raise RuntimeError if called from a non-owner PID."""
        if os.getpid() != self._owner_pid:
            raise RuntimeError(
                "topology registry writer accessed from PID "
                f"{os.getpid()} but was opened by PID {self._owner_pid}; "
                "writes are permitted only from the publish daemon."
            )

    # Read ops are delegated as-is; the PID check is enforced only
    # on write-side operations (set/delete).  Readers in the same
    # process can safely use the writer handle to inspect state.
    def get(self, key, default=None):
        return self._cache.get(key, default=default)

    def list_items(self):
        return self._cache.list_items()

    def list_keys(self):
        return self._cache.list_keys()

    def put(self, key, value):
        self._check_pid()
        return self._cache.put(key, value)

    def delete(self, key):
        self._check_pid()
        return self._cache.delete(key)

    def close(self):
        """Release the underlying mmap + lock fds."""
        self._cache.close()


class _ReaderHandle:
    """
    Thin wrapper around :class:`MmapCache` for read-only use.

    Exposes only the lookup / listing surface.  No PID guard is
    needed: readers do not mutate shared state and the MmapCache
    read path is cross-process safe.
    """

    __slots__ = ("_cache",)

    def __init__(self, cache):
        self._cache = cache

    def get(self, key, default=None):
        return self._cache.get(key, default=default)

    def list_items(self):
        return self._cache.list_items()

    def list_keys(self):
        return self._cache.list_keys()

    def close(self):
        self._cache.close()


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


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
    cache = _build_cache(opts, write=True)
    # Opening in write mode already created and header-stamped
    # the files; closing the handle releases the lock fd so the
    # subsequent ``open_writer`` call can take it fresh.
    cache.close()


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

    :raises RuntimeError: If a write-side op is later called
        from a process other than the publish daemon.
    """
    cache = _build_cache(opts, write=True)
    return _WriterHandle(cache)


def open_reader(opts):
    """
    Open the registry MmapCache in read-only mode.

    Safe to call from any process after fork.  Each process gets
    its own MmapCache instance pointing at the same backing
    files.

    :returns: A read-only handle onto the registry cache.
    """
    cache = _build_cache(opts, write=False)
    return _ReaderHandle(cache)


# ---------------------------------------------------------------------------
# Identity public key
# ---------------------------------------------------------------------------


def get_identity_pub(cache):
    """
    Return the identity public key bytes, or ``None`` if the
    registry has not been bootstrapped yet.
    """
    value = cache.get(RESERVED_IDENTITY_PUB_KEY, default=None)
    if value is None:
        return None
    if isinstance(value, bytes):
        return value
    # The MmapCache transparently round-trips bytes-as-bytes when
    # the stored value was handed in as bytes; if a prior writer
    # stored a str the heap round-trip decodes to unicode.  Encode
    # back to the stable bytes contract callers rely on.
    if isinstance(value, str):
        return value.encode("utf-8")
    return bytes(value)


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
    if not isinstance(pub_pem, (bytes, bytearray)):
        raise TypeError(
            f"set_identity_pub requires bytes, got {type(pub_pem).__name__}"
        )
    existing = get_identity_pub(cache)
    pub_bytes = bytes(pub_pem)
    if existing == pub_bytes:
        return
    cache.put(RESERVED_IDENTITY_PUB_KEY, pub_bytes)


# ---------------------------------------------------------------------------
# Peer entries
# ---------------------------------------------------------------------------


def _encode_peer(state):
    """
    Serialise a PeerState-shaped dict to the bytes payload stored
    in the heap.  Uses msgpack for compactness and schema
    tolerance across minor peer-state additions.
    """
    payload = {
        "cluster_id": state["cluster_id"],
        "public_key": bytes(state["public_key"]),
        "endpoints": tuple(state.get("endpoints", ())),
        "attached_at": float(state["attached_at"]),
    }
    return salt.utils.msgpack.packb(payload, use_bin_type=True)


def _decode_peer(raw):
    """Deserialise a peer entry from on-disk bytes to a dict."""
    if raw is None:
        return None
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    data = salt.utils.msgpack.unpackb(raw, raw=False)
    # Normalise endpoints to a tuple regardless of what the
    # packer produced (lists on round-trip).
    if "endpoints" in data and data["endpoints"] is not None:
        data["endpoints"] = tuple(data["endpoints"])
    # msgpack packed bytes come back as bytes with raw=False only
    # for str; binary (bin8/bin16/bin32) stays as bytes.  Guard
    # for the pathological case where an older writer stored a
    # str.
    pub = data.get("public_key")
    if isinstance(pub, str):
        data["public_key"] = pub.encode("utf-8")
    return data


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
    raw = cache.get(cluster_id, default=None)
    if raw is None:
        return None
    return _decode_peer(raw)


def set_peer(cache, cluster_id, state):
    """
    Write a PeerState dict for ``cluster_id`` to the registry.

    Writer-only; caller must hold the publish daemon writer
    handle.  Overwrites any existing entry for the same
    ``cluster_id``.

    :raises ValueError: If ``cluster_id`` matches a reserved
        key name.  This is a local defense against hostile or
        buggy peers; the companion check at Raft apply time
        lives in
        :mod:`salt.cluster.consensus.raft.topology`.
    """
    if cluster_id in _RESERVED_KEYS:
        raise ValueError(
            f"cluster_id {cluster_id!r} is reserved and cannot be used "
            "as a peer identifier"
        )
    payload = _encode_peer(state)
    cache.put(cluster_id, payload)


def delete_peer(cache, cluster_id):
    """
    Remove the peer entry for ``cluster_id``.  Writer-only.

    Idempotent: no-op if the peer was not present.
    """
    if cluster_id in _RESERVED_KEYS:
        # Deleting a reserved slot via this API is nonsensical.
        # Treat as no-op rather than raise so a bulk-detach loop
        # that mistakenly includes a reserved id does not fail
        # the whole batch; the Raft apply path still protects
        # the reserved slot from cross-cluster writers.
        return
    cache.delete(cluster_id)


def list_peer_ids(cache):
    """
    Return the ``cluster_id`` of every currently-attached peer.

    Backed by ``MmapCache.list_items`` which scans the roster
    file in O(occupied), independent of table size.  Reserved
    sentinel keys are filtered out so this never leaks the
    identity key slot as a peer id.
    """
    out = []
    for key, _value in cache.list_items():
        if key in _RESERVED_KEYS:
            continue
        out.append(key)
    return out
