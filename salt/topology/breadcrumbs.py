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

log = logging.getLogger(__name__)


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


def delete(cache, jid):
    """
    Remove the breadcrumb for ``jid``.  Writer-only.

    Called by the publish daemon after a return has been
    successfully forwarded upstream so the breadcrumb can be
    reclaimed before expiry.
    """


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
