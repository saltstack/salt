"""
Shared ``jid -> inbound link`` map for return routing.

Backed by :class:`salt.utils.mmap_cache.MmapCache` so MWorkers can
decide --- without IPC --- whether an incoming minion return needs
upstream forwarding on a topology link.  Writes happen only in the
publish daemon when a publish is forwarded onto a peer link.

Semantics
---------
Writer
    publish daemon's :class:`salt.topology.router.TopologyRouter`.
    One ``put`` per topology-forwarded publish.

Readers
    * Publish daemon: on inbound topology return, look up to find
      the outbound link for upstream dispatch.
    * MWorker: on inbound minion return, look up to decide
      whether the return belongs to a topology-origin publish and
      needs upstream forwarding.  On hit, MWorker fires one
      ``salt/topology/return/<origin>/<jid>`` event; publish
      daemon's event subscriber picks it up and dispatches.

Lifetime
--------
Entry inserted on forward-out of a publish.  Expires at
``put_time + min(publish.timeout + topology_breadcrumb_grace,
topology_breadcrumb_max_age)``.  Expiry is enforced by the
``expiry_at`` field embedded in the value; readers compare
against ``time.time()`` and treat expired entries as absent.
:func:`cleanup` does bulk removal periodically.

Restart survival
----------------
The mmap file persists on disk, so a publish daemon restart
re-opens the same cache.  In-flight returns from downstream
clusters remain routable --- strictly better than syndic, which
drops in-flight on syndic restart.

Transit-failover case
---------------------
Per the open design decision in ``rfcs/master-topology.md``, the
behavior when the publish-daemon-owning peer dies and failover
happens is not yet finalized.  Three candidates: (mA) batched
Raft replication, (mB) peer-shared mmap via file_sync, (mC)
document as syndic-parity limitation.  Until that decision
lands, breadcrumbs are per-process only.

Cache file layout
-----------------
* ``<pki_dir>/master/topology_breadcrumbs.mmap``        --- index
* ``<pki_dir>/master/topology_breadcrumbs.mmap.heap``   --- values
* ``<pki_dir>/master/topology_breadcrumbs.mmap.roster`` --- live-slot roster
* ``<pki_dir>/master/topology_breadcrumbs.mmap.lock``   --- flock target

Keys: ``<cluster_id>:<jid>`` (the topology-prefixed jid used
everywhere in topology-forwarded traffic).  Fits in the default
``key_size=64`` for any reasonable cluster_id length.

Values: msgpack dict ``{"link_cluster_id": str, "expiry_at":
float}``.  ``link_cluster_id`` names the peer the publish arrived
from (where the return is routed back to); the link object
itself is looked up by cluster_id in
:func:`salt.topology.link_manager.get_link`.
"""

import logging
import os
import time

import salt.utils.mmap_cache
import salt.utils.msgpack

log = logging.getLogger(__name__)

#: Fraction of tombstoned slots at which :func:`cleanup` triggers
#: :meth:`salt.utils.mmap_cache.MmapCache.atomic_rebuild` to reclaim
#: index space before linear-probing degradation sets in.
_REBUILD_TOMBSTONE_RATIO = 0.3

#: Default sizing used when ``opts`` does not carry the breadcrumb
#: cache knobs.  Matches the RFC-documented defaults so a
#: topology-enabled master that hasn't yet been reconfigured still
#: comes up with a usable cache.
_DEFAULT_CACHE_SIZE = 1_000_000
_DEFAULT_KEY_SIZE = 64
_DEFAULT_GRACE = 30
_DEFAULT_MAX_AGE = 600


def _cache_path(opts):
    """Return the breadcrumbs index path for *opts*."""
    return os.path.join(opts["pki_dir"], "master", "topology_breadcrumbs.mmap")


def _cache_kwargs(opts):
    """Return the kwargs used to instantiate :class:`MmapCache`."""
    return {
        "size": opts.get("topology_breadcrumb_cache_size", _DEFAULT_CACHE_SIZE),
        "key_size": opts.get("topology_breadcrumb_cache_key_size", _DEFAULT_KEY_SIZE),
    }


def _compute_expiry_at(publish_timeout, opts, now=None):
    """
    Return the absolute wall-clock expiry timestamp for a breadcrumb.

    Formula per RFC: ``put_time + min(publish_timeout + grace, max_age)``.
    """
    grace = opts.get("topology_breadcrumb_grace", _DEFAULT_GRACE)
    max_age = opts.get("topology_breadcrumb_max_age", _DEFAULT_MAX_AGE)
    lifetime = min(publish_timeout + grace, max_age)
    base = time.time() if now is None else now
    return base + lifetime


def _check_owner(cache):
    """
    Raise :exc:`RuntimeError` if the caller's PID is not the one that
    opened this writer.

    Writer handles stamp ``_breadcrumb_owner_pid`` at
    :func:`open_writer` time; reader handles don't carry that attribute,
    so this guard is a no-op for them.
    """
    owner = getattr(cache, "_breadcrumb_owner_pid", None)
    if owner is None:
        return
    if os.getpid() != owner:
        raise RuntimeError(
            "topology breadcrumb writer called from pid %d but was opened "
            "by pid %d" % (os.getpid(), owner)
        )


def pre_create(opts):
    """
    Materialize empty index/heap/roster/lock files for the
    breadcrumbs MmapCache in the master process BEFORE any
    MWorker or publish daemon forks.

    Called from :func:`salt.topology.link_manager.pre_fork`.
    Prevents the race where MWorkers fork and start accepting
    returns before the publish daemon has done its first
    ``put``: without pre-creation, each MWorker's
    :func:`open_reader` call would see no file, treat every
    inbound jid as "no breadcrumb" (local-only), and silently
    drop topology returns during the startup window.

    Idempotent: no-op if the files already exist with a valid
    header.
    """
    path = _cache_path(opts)
    if os.path.exists(path):
        return
    cache = salt.utils.mmap_cache.MmapCache(path, **_cache_kwargs(opts))
    try:
        # open(write=True) performs the actual on-disk layout work
        # (zero-filled index, empty heap, header magic).
        if not cache.open(write=True):
            raise RuntimeError(
                "failed to pre-create topology breadcrumbs cache at %s" % path
            )
    finally:
        cache.close()


def open_writer(opts):
    """
    Open the breadcrumbs MmapCache in writable mode.  Call once
    in the publish daemon after fork; keep the handle open for
    the daemon's lifetime.

    The cache files are expected to exist already --- they are
    materialized by :func:`pre_create` in the master pre-fork
    path.

    **Owner-PID guard**: stores ``os.getpid()`` at open time and
    refuses any subsequent op if called from a different PID.
    Defense against accidental MWorker writes.

    :raises RuntimeError: If called from a process other than
        the publish daemon.
    """
    path = _cache_path(opts)
    cache = salt.utils.mmap_cache.MmapCache(path, **_cache_kwargs(opts))
    if not cache.open(write=True):
        cache.close()
        raise RuntimeError(
            "failed to open topology breadcrumbs writer at %s "
            "(did pre_create run?)" % path
        )
    cache._breadcrumb_owner_pid = os.getpid()  # pylint: disable=protected-access
    return cache


def open_reader(opts):
    """
    Open the breadcrumbs MmapCache in read-only mode.

    MWorkers open the cache with ``staleness_check_interval=0``
    so every lookup re-stats --- the 250ms default is too long
    for the return hot path, where a breadcrumb written 50ms ago
    on the publish daemon must be visible immediately.

    Call once per MWorker after fork; keep the handle open for
    the worker's lifetime.
    """
    path = _cache_path(opts)
    kwargs = _cache_kwargs(opts)
    kwargs["staleness_check_interval"] = 0
    return salt.utils.mmap_cache.MmapCache(path, **kwargs)


def put(cache, jid, inbound_link_cluster_id, publish_timeout, opts):
    """
    Record a breadcrumb for ``jid``.

    :param cache: Writer handle from :func:`open_writer`.
    :param jid: Topology-prefixed jid (``<cluster_id>:<jid>``).
    :param inbound_link_cluster_id: The peer cluster_id this
        publish arrived from --- where returns route back.
    :param publish_timeout: Caller's declared timeout; combined
        with ``opts["topology_breadcrumb_grace"]`` and clamped by
        ``opts["topology_breadcrumb_max_age"]`` to compute
        expiry.
    :param opts: Master opts.
    """
    _check_owner(cache)
    expiry_at = _compute_expiry_at(publish_timeout, opts)
    value = salt.utils.msgpack.dumps(
        {
            "link_cluster_id": inbound_link_cluster_id,
            "expiry_at": expiry_at,
        },
        use_bin_type=True,
    )
    cache.put(jid, value)


def _decode(raw):
    """Decode a stored msgpack value into a dict, or ``None`` on failure."""
    if raw is None:
        return None
    if isinstance(raw, str):
        # ``MmapCache.get`` decodes bytes->str via utf-8/latin-1 fallback;
        # msgpack bytes aren't utf-8 so Salt's stringutils typically
        # returns the raw bytes.  Guard against both shapes.
        try:
            raw = raw.encode("latin-1")
        except UnicodeEncodeError:
            return None
    try:
        return salt.utils.msgpack.loads(raw, raw=False)
    except Exception:  # pylint: disable=broad-except
        log.warning("failed to decode breadcrumb value for lookup")
        return None


def lookup(cache, jid):
    """
    Return the ``inbound_link_cluster_id`` for ``jid``, or
    ``None`` if there is no breadcrumb or it has expired.

    Expiry check is lazy: the embedded ``expiry_at`` is compared
    against ``time.time()`` on read.  Expired entries are
    returned as absent but not immediately removed;
    :func:`cleanup` does bulk removal periodically.

    Safe to call from any process.  O(1) average; the MWorker
    read path is intentionally un-throttled on staleness so the
    hot return path sees fresh writes.
    """
    raw = cache.get(jid)
    decoded = _decode(raw)
    if decoded is None:
        return None
    if decoded.get("expiry_at", 0) <= time.time():
        return None
    return decoded.get("link_cluster_id")


def delete(cache, jid):
    """
    Remove the breadcrumb for ``jid``.  Writer-only.

    Called by the publish daemon after a return has been
    successfully forwarded upstream so the breadcrumb can be
    reclaimed before expiry.
    """
    _check_owner(cache)
    cache.delete(jid)


def cleanup(cache):
    """
    Remove expired breadcrumbs from the cache.  Writer-only.

    Scans via ``MmapCache.list_items`` (O(occupied) via roster,
    not full-table scan) and deletes entries whose ``expiry_at``
    is in the past.  When the ratio of tombstones to occupied
    slots exceeds 0.3 after a sweep, triggers
    ``MmapCache.atomic_rebuild`` to reclaim index space before
    linear-probing degradation shows up.

    Called periodically by the publish daemon's housekeeping
    loop (typically every ``topology_breadcrumb_grace`` seconds)
    and once at startup to prune entries older than
    ``opts["topology_breadcrumb_max_age"]`` left behind by a
    previous process.

    :returns: Number of entries removed.
    """
    _check_owner(cache)
    now = time.time()
    removed = 0
    for key, raw in cache.list_items():
        decoded = _decode(raw)
        if decoded is None:
            # Corrupt / undecodable entries get swept too; they can't be
            # routed on anyway.
            cache.delete(key)
            removed += 1
            continue
        if decoded.get("expiry_at", 0) <= now:
            cache.delete(key)
            removed += 1

    if removed == 0:
        return 0

    stats = cache.get_stats()
    occupied = stats.get("occupied", 0)
    deleted = stats.get("deleted", 0)
    denom = occupied + deleted
    if denom > 0 and (deleted / denom) > _REBUILD_TOMBSTONE_RATIO:
        # Rebuild from the surviving (key, raw-value) pairs.  We hand
        # ``MmapCache.list_items`` output straight back in; ``raw`` is
        # the msgpack-serialised bytes so round-tripping preserves the
        # on-disk format exactly.
        surviving = [
            (k, v if isinstance(v, bytes) else v.encode("latin-1"))
            for k, v in cache.list_items()
            if v is not True
        ]
        try:
            cache.atomic_rebuild(iter(surviving))
        except Exception:  # pylint: disable=broad-except
            log.exception("topology breadcrumbs atomic_rebuild failed")

    return removed
