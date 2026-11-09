"""
Cross-master cache replication seams.

Free-function entry points for both sides of the delegate-cache-write
flow so each side is testable without instantiating a channel class
or a Cache object.  ``Cache.store`` and ``Cache.store_many`` emit via
:func:`fire_peer_cache_write` / :func:`fire_peer_cache_write_many` /
:func:`fire_delegate_cache_write`;
``MasterPubServerChannel._handle_delegate_cache_write`` delegates to
:func:`_handle_delegate_cache_write`.
"""

import atexit
import concurrent.futures
import logging
import os
import threading

import salt.cache

log = logging.getLogger(__name__)


# Per-(sock_dir, master-id, pid) cached MasterEvent handle.
#
# ``Cache.store`` / ``Cache.store_many`` on a clustered master fire a
# cluster-runner event on every write.  Constructing a fresh
# ``MasterEvent`` (connect + fire + close) per write was measurably
# expensive at scale (200K-resource register adds ~70s per master).
# The handle is safe to reuse for the fire-only direction
# (``listen=False``): it just pushes payloads at the master event bus.
#
# Fork-safety: when a worker process forks, the child inherits the
# dict but the underlying file descriptors in the parent's handle are
# stale.  We key on ``os.getpid()`` so each process constructs its
# own handle lazily; the dict entry for the parent's pid becomes
# unused (but harmless) in the child.
_EVENT_HANDLE_CACHE = {}
_EVENT_HANDLE_LOCK = threading.Lock()


# Per-minion single-worker executor for peer-side register apply.
#
# The publish daemon dispatches each incoming
# ``cluster/peer/delegate-resource-register-write`` event into a
# ThreadPoolExecutor via ``run_in_executor(executor, ...)``.  The
# default (shared) ``run_in_executor(None, ...)`` gives no FIFO
# ordering guarantee, so a fast ``chunk_final=True`` arriving while
# an earlier non-final chunk is still queued could run the prune
# pass against an incomplete pending window and wipe valid SRNs.
#
# Fix shape: route every event for a given ``minion_id`` through a
# dedicated ``concurrent.futures.ThreadPoolExecutor(max_workers=1)``.
# That executor has an internal FIFO work queue, so successive
# submissions for the same minion run in submission order with no
# inter-chunk lock contention.  Different minions each get their own
# executor and run in parallel.
#
# The inner ``_pending_registers_lock`` in
# :meth:`ResourceRegistry.register_minion_chunk` still guards the
# ``_pending_registers`` dict against interleaving with originator
# MWorker paths that also write through the shared registry
# singleton in the same process.
#
# Replaces the previous per-``(minion_id, chunk_scope)`` ``threading.Lock``
# registry: that design worked but produced heavy contention during
# high-volume single-minion register storms because every
# ``_handle_delegate_resource_register_write`` thread blocked on the
# same contended lock.  Executor FIFO sidesteps the contention entirely.
#
# Future refactor: the per-minion work here could be an ``asyncio.Queue``
# fed by an ``asyncio.Task`` consumer, with each individual mmap write
# wrapped in ``asyncio.to_thread`` (or ``loop.run_in_executor(None, …)``)
# since the underlying ``MmapCache`` write path is synchronous and
# cannot yield.  Benefits over the current thread-per-minion design:
#
# * lower per-minion memory (task object vs. OS thread stack) — useful
#   as deployments scale their minion fleet
# * cleaner cancellation on daemon shutdown (``task.cancel()`` instead
#   of best-effort ``ThreadPoolExecutor.shutdown`` from atexit)
# * one shared worker pool for the sync mmap calls instead of a thread
#   per minion
#
# Not pursued here because the realistic swap still ends up offloading
# the mmap calls to a thread via ``to_thread`` — it moves the thread
# cost, it does not eliminate it — and the current design is simple
# and correct.  Revisit when per-minion thread count becomes observable
# in master RSS or shutdown latency.
_PEER_APPLY_EXECUTORS = {}
_PEER_APPLY_EXECUTORS_GUARD = threading.Lock()


def _get_peer_apply_executor(minion_id):
    """
    Return the dedicated single-worker executor for peer-side register
    apply for ``minion_id``.

    Created lazily on first use.  The executor holds one thread for
    the lifetime of the publish-daemon process; per-minion overhead
    is bounded by ``N_minions`` registered within the process
    lifetime (small compared to the resource-registry itself).

    The executor's internal work queue gives natural FIFO ordering
    for every event dispatched through this function, which is the
    correctness property that preserves chunk ordering within a
    minion's registration window.
    """
    with _PEER_APPLY_EXECUTORS_GUARD:
        executor = _PEER_APPLY_EXECUTORS.get(minion_id)
        if executor is None:
            executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=1,
                thread_name_prefix=f"peer-apply-{minion_id}",
            )
            _PEER_APPLY_EXECUTORS[minion_id] = executor
    return executor


def _shutdown_peer_apply_executors():
    """Best-effort teardown of every per-minion apply executor."""
    with _PEER_APPLY_EXECUTORS_GUARD:
        execs = list(_PEER_APPLY_EXECUTORS.values())
        _PEER_APPLY_EXECUTORS.clear()
    for ex in execs:
        try:
            ex.shutdown(wait=False, cancel_futures=True)
        except Exception:  # pylint: disable=broad-except
            # Interpreter shutdown can race the shutdown path; swallow.
            pass


atexit.register(_shutdown_peer_apply_executors)


def _handle_cache_key(opts):
    """Compose a (sock_dir, master_id, pid) key for the handle cache."""
    return (opts.get("sock_dir"), opts.get("id"), os.getpid())


def _get_event_handle(opts):
    """
    Return a cached ``MasterEvent`` for firing replication events.

    The handle is created lazily on first use in each process (so
    worker forks naturally pick up their own) and reused across
    subsequent calls in the same pid.  Teardown is handled by
    ``atexit`` (best-effort -- replication events are not critical
    on shutdown).
    """
    import salt.utils.event  # pylint: disable=import-outside-toplevel

    key = _handle_cache_key(opts)
    handle = _EVENT_HANDLE_CACHE.get(key)
    if handle is not None:
        return handle
    with _EVENT_HANDLE_LOCK:
        handle = _EVENT_HANDLE_CACHE.get(key)
        if handle is not None:
            return handle
        handle = salt.utils.event.get_event(
            "master",
            sock_dir=opts.get("sock_dir"),
            opts=opts,
            listen=False,
        )
        _EVENT_HANDLE_CACHE[key] = handle
    return handle


def _close_cached_handles():
    """Best-effort teardown of every cached MasterEvent on exit."""
    with _EVENT_HANDLE_LOCK:
        handles = list(_EVENT_HANDLE_CACHE.values())
        _EVENT_HANDLE_CACHE.clear()
    for handle in handles:
        try:
            handle.destroy()
        except Exception:  # pylint: disable=broad-except
            # Interpreter shutdown can race the destroy path; swallow.
            pass


atexit.register(_close_cached_handles)


def _fire_payload(opts, payload, tag="cluster/runner/delegate_cache_write"):
    """
    Fire ``payload`` on the master event bus using a pid-cached handle.

    Used by both the per-write and batched replication paths.  The
    handle is reused across calls; see :func:`_get_event_handle`.
    """
    try:
        handle = _get_event_handle(opts)
        handle.fire_event(payload, tag)
    except Exception:  # pylint: disable=broad-except
        # Invalidate the cached handle on failure so the next call
        # re-opens the socket.  The underlying ``get_event`` socket
        # may have been closed out from under us (e.g. master
        # restart) and a stale handle will keep failing until
        # reset.
        key_cache = _handle_cache_key(opts)
        with _EVENT_HANDLE_LOCK:
            stale = _EVENT_HANDLE_CACHE.pop(key_cache, None)
        if stale is not None:
            try:
                stale.destroy()
            except Exception:  # pylint: disable=broad-except
                pass
        log.exception(
            "cluster-cache-replication: failed to fire %s event (payload keys=%s)",
            tag,
            list(payload) if isinstance(payload, dict) else type(payload).__name__,
        )


def _fire_event(opts, write_kind, bank, key, data, expires):
    """
    Common implementation: fire ``cluster/runner/delegate_cache_write``
    with the given write_kind.  The master's publish daemon intercepts
    the event and either fans it out to every peer (``replicate``) or
    routes it to the HashRing owner (``ring``).

    The underlying ``MasterEvent`` handle is cached per
    ``(sock_dir, opts["id"], pid)`` so hot-path writes
    (``cache.store("grains", ...)``) avoid the connect + close cost
    on every call.  See :func:`_get_event_handle`.
    """
    payload = {
        "bank": bank,
        "key": key,
        "data": data,
        "expires": expires,
        "write_kind": write_kind,
        "originating_master": opts.get("id"),
    }
    _fire_payload(opts, payload)


def fire_peer_cache_write(opts, bank, key, data, expires=None):
    """
    Fan a cache write out to every peer master (N-of-N replication).

    Called by :meth:`salt.cache.Cache.store` and
    :meth:`salt.cache.Cache.store_many` when the per-bank routing
    resolves to ``"replicate"`` (the default).

    This is the single seam tests patch to observe fan-out intent
    without a real event bus.
    """
    _fire_event(opts, "replicate", bank, key, data, expires)


def fire_peer_cache_write_many(opts, bank, items, expires=None, write_kind="replicate"):
    """
    Batched N-of-N replication: fan a list of ``(key, data)`` pairs
    out to every peer master in a single event.

    The gate (cluster + isolated-FS + per-bank routing) is evaluated
    once by the caller -- all items share the same bank so routing
    is uniform.  This cuts the per-write event cost on hot batched
    paths like ``cache.store_many`` for resource grains.

    :param opts: Master opts dict.
    :param bank: The shared bank name.
    :param items: Iterable of ``(key, data)`` tuples.
    :param expires: Optional seconds-from-now expiry applied to
        every entry in the batch.
    :param write_kind: ``"replicate"`` (default, N-of-N fan-out) or
        ``"ring"`` (1-of-N; see
        :func:`fire_delegate_cache_write_many`).  Used to let the
        receiver dispatch via the same ``_run_delegate_cache_write``
        path as the single-item events.
    """
    pairs = list(items)
    if not pairs:
        return
    payload = {
        "bank": bank,
        "items": [[key, data] for key, data in pairs],
        "expires": expires,
        "write_kind": write_kind,
        "batch": True,
        "originating_master": opts.get("id"),
    }
    _fire_payload(opts, payload)


def fire_delegate_cache_write(opts, bank, key, data, expires=None):
    """
    Route a cache write to a single HashRing owner (1-of-N delegation).

    Called when the per-bank routing resolves to ``"ring"`` (e.g. the
    ``jobs`` bank by default, for backward compat with the existing
    ring-sharded job returner).
    """
    _fire_event(opts, "ring", bank, key, data, expires)


def fire_delegate_cache_write_many(opts, bank, items, expires=None):
    """Batched 1-of-N ring-delegation variant of :func:`fire_peer_cache_write_many`."""
    fire_peer_cache_write_many(opts, bank, items, expires=expires, write_kind="ring")


def _partition_resources_by_ring(ring, resources):
    """
    Split a ``{resource_type: [resource_id, ...]}`` dict by ring owner.

    Returns ``{owner_node_id: {resource_type: [resource_id, ...]}}``.
    The ring is consulted per-SRN (``"<type>:<id>"``) via
    :meth:`HashRing.get_owner`; SRNs whose owner cannot be resolved
    (empty ring) are returned under the ``None`` key so the caller
    can fall back to broadcast for them.
    """
    import salt.utils.resource_registry  # pylint: disable=import-outside-toplevel

    buckets = {}
    for rtype, rids in (resources or {}).items():
        for rid in rids or ():
            srn = salt.utils.resource_registry.resource_index_srn_key(rtype, rid)
            owner = ring.get_owner(srn)
            per_owner = buckets.setdefault(owner, {})
            per_owner.setdefault(rtype, []).append(rid)
    return buckets


def fire_resource_register_write(
    opts,
    minion_id,
    resources,
    chunk_final=True,
    chunk_scope=None,
    chunk_index=None,
):
    """
    Fire a resource-registry write event for the publish daemon to
    intercept and dispatch.

    The MWorker handling ``_register_resources`` runs this to hand the
    register off to the publish daemon.  The daemon
    (:meth:`salt.channel.server.MasterPubServerChannel._run_delegate_resource_register_write`)
    is the single place that owns the ring-vs-broadcast decision, the
    local-shard mmap write, and the targeted-vs-fan-out peer publish
    -- because the ``resource_index`` ring state only lives in the
    daemon process (its per-ring Raft groups aren't visible across the
    MWorker fork boundary).

    ``chunk_final`` + ``chunk_scope`` + ``chunk_index`` carry chunked-
    register metadata through to peers and the local publish-daemon
    writer so a multi-chunk register preserves additive mid-stream
    puts and defers the stale-SRN prune to the terminal chunk.  The
    ``chunk_index`` field additionally lets peer masters detect and
    buffer out-of-order final-chunk arrivals (publish-daemon
    ``run_in_executor`` has no FIFO guarantee across chunks).  Legacy
    single-shot callers can omit all three fields and get pre-chunk
    semantics (full replace, no gap check).

    :param opts:         Master opts dict (must contain ``id``).
    :param minion_id:    The reporting minion.
    :param resources:    ``{resource_type: [resource_id, ...]}`` -- the
                         exact dict that was passed to the local
                         ``update_resource_index_chunk`` call.
    :param chunk_final:  True iff this chunk ends a register window.
    :param chunk_scope:  ``None``/``"__all__"`` for a legacy single-
                         shot register, or a type name for a scoped
                         chunked register.
    :param chunk_index:  0-based monotonic index of this chunk within
                         the register window.  ``None`` for legacy
                         single-shot callers.
    """
    payload = {
        "minion_id": minion_id,
        "resources": resources,
        "originating_master": opts.get("id"),
        "chunk_final": chunk_final,
        "chunk_scope": chunk_scope or "__all__",
    }
    if chunk_index is not None:
        payload["chunk_index"] = chunk_index
    _fire_payload(
        opts,
        payload,
        tag="cluster/runner/delegate_resource_register_write",
    )


def _get_resource_index_ring():
    """
    Return the local ``resource_index`` HashRing, or ``None`` if the
    cluster module isn't importable (standalone test fixtures).
    """
    try:
        import salt.cluster.ring_membership  # pylint: disable=import-outside-toplevel
        import salt.utils.resource_registry  # pylint: disable=import-outside-toplevel
    except Exception:  # pylint: disable=broad-except
        return None
    try:
        return salt.cluster.ring_membership.get_ring(
            salt.utils.resource_registry.RESOURCE_INDEX_RING_NAME
        )
    except Exception:  # pylint: disable=broad-except
        return None


def partition_resources_for_dispatch(opts, resources):
    """
    Split ``resources`` into ``(local_bucket, peer_buckets, ring_active)``
    for the publish-daemon dispatcher.

    Used by
    :meth:`salt.channel.server.MasterPubServerChannel._run_delegate_resource_register_write`
    inside the publish daemon process where the ``resource_index``
    ring is populated.  When the ring is empty, returns the full
    ``resources`` as the "broadcast everyone" bucket and no peer
    buckets.  When populated, splits by :meth:`HashRing.get_owner`.

    :param opts: Master opts dict.
    :param resources: ``{resource_type: [resource_id, ...]}``.
    :returns: ``(local_bucket, peer_buckets, ring_active)`` where
              ``peer_buckets`` is ``{owner_node_id: resources_dict}``
              for each remote owner, and ``ring_active`` is a
              ``bool`` indicating ring routing is in effect.
    """
    import salt.cluster  # pylint: disable=import-outside-toplevel

    ring = _get_resource_index_ring()
    if ring is None or not ring.nodes():
        return resources, {}, False
    self_node = salt.cluster.node_id(opts) if opts.get("id") else None
    buckets = _partition_resources_by_ring(ring, resources)
    local = dict(buckets.get(self_node, {}))
    # SRNs whose owner didn't resolve land locally so they're not lost
    # to a fencepost in the ring state.
    for rtype, rids in buckets.get(None, {}).items():
        local.setdefault(rtype, []).extend(rids)
    peers = {
        owner: owner_resources
        for owner, owner_resources in buckets.items()
        if owner is not None and owner != self_node
    }
    return local, peers, True


def _handle_delegate_resource_register_write(opts, payload):
    """
    Apply a peer-originated resource-registry write locally.

    Peer-side counterpart to :func:`fire_resource_register_write`.
    Same loop-safety shape as :func:`_handle_delegate_cache_write`:

    1. Drop the event if ``originating_master`` equals this master's
       ``opts["id"]`` -- bus bounce-back must not become a write.
    2. Apply via :func:`salt.utils.minions.update_resource_index_chunk`
       so the local write lands through the same chunked code path a
       minion-originated register would take.  Non-final chunks
       additively ``put_many`` without pruning; only the terminal
       chunk runs the stale-SRN delete pass scoped to ``chunk_scope``.

    Idempotency: the chunked API's per-minion accumulator keys by
    scope, so duplicate deliveries converge to the same state (the
    same SRN set is re-inserted into the pending window, and a
    duplicate terminal chunk's delete-diff is a no-op).

    :param opts:    Master opts dict (must contain ``id``).
    :param payload: Decoded event payload with keys
                    ``originating_master``, ``minion_id``, ``resources``,
                    and (chunked registers only)
                    ``chunk_final``/``chunk_scope``.  Missing chunk
                    fields default to ``True``/``"__all__"`` for
                    back-compat with legacy single-shot payloads.
    :returns:       ``True`` if the register was applied, ``False``
                    if dropped (loop-guard or malformed payload).
    """
    if payload.get("originating_master") == opts.get("id"):
        return False
    minion_id = payload.get("minion_id")
    if not minion_id:
        log.warning(
            "resource-replicate: incoming event missing minion_id; dropping %r",
            payload,
        )
        return False
    resources = payload.get("resources")
    if resources is None:
        log.warning(
            "resource-replicate: incoming event missing resources; dropping %r",
            payload,
        )
        return False
    chunk_final = payload.get("chunk_final", True)
    chunk_scope = payload.get("chunk_scope") or "__all__"
    chunk_index = payload.get("chunk_index")
    try:
        import salt.utils.minions  # pylint: disable=import-outside-toplevel

        # Ordering invariant: this call expects the publish daemon
        # to have dispatched through :func:`_get_peer_apply_executor`
        # (a per-minion, single-worker ThreadPoolExecutor) so every
        # event for ``minion_id`` runs in submission order.  The
        # inner ``_pending_registers_lock`` in
        # :meth:`ResourceRegistry.register_minion_chunk` still
        # protects the pending-window dict against the originator
        # MWorker apply path that shares the same registry singleton.
        # The ``chunk_index`` gap check handles any residual out-of-
        # order case (e.g. legacy callers bypassing the executor).
        salt.utils.minions.update_resource_index_chunk(
            opts,
            minion_id,
            resources,
            chunk_final,
            chunk_scope=chunk_scope,
            chunk_index=chunk_index,
        )
        return True
    except Exception:  # pylint: disable=broad-except
        log.exception(
            "resource-replicate: failed to apply replicated register for %s",
            minion_id,
        )
        return False


def _handle_delegate_cache_write(opts, payload):
    """
    Apply a peer-originated cache write locally.

    Handles both the per-item and batched (``batch: True``,
    ``items: [[key, data], ...]``) payload shapes.

    Two loop-safety guards:

    1. Drop the event if ``originating_master`` matches this master's
       ``opts["id"]`` -- bus bounce-back must not become a write.
    2. Pass ``_already_replicated=True`` to :meth:`salt.cache.Cache.store`
       so the peer-side write does NOT re-broadcast the replication
       event to every peer again.

    Idempotency comes from the cache driver's replace semantics --
    duplicate deliveries converge to the same final state.

    :param opts:    Master opts dict (must contain ``id``).
    :param payload: Decoded event payload with keys ``originating_master``,
                    ``bank``, ``key``, ``data``, and optional ``expires``;
                    or with ``batch: True`` and ``items: [[k,v], ...]``.
    :returns:       ``True`` if at least one write was applied, ``False``
                    if dropped (loop-guard or malformed payload).
    """
    if payload.get("originating_master") == opts.get("id"):
        return False
    bank = payload.get("bank")
    if not bank:
        log.warning(
            "cache-replicate: incoming event missing bank; dropping %r", payload
        )
        return False
    expires = payload.get("expires")
    try:
        cache = salt.cache.Cache(opts)
    except Exception:  # pylint: disable=broad-except
        log.exception(
            "cache-replicate: failed to instantiate Cache for replication apply"
        )
        return False
    if payload.get("batch"):
        items = payload.get("items") or []
        if not items:
            log.warning(
                "cache-replicate: batched event with empty items list; dropping"
            )
            return False
        applied_any = False
        for entry in items:
            try:
                key, data = entry[0], entry[1]
            except (KeyError, IndexError, TypeError):
                log.warning(
                    "cache-replicate: malformed batch entry %r; skipping", entry
                )
                continue
            try:
                cache.store(bank, key, data, expires=expires, _already_replicated=True)
                applied_any = True
            except Exception:  # pylint: disable=broad-except
                log.exception(
                    "cache-replicate: failed to apply replicated write for %s/%s",
                    bank,
                    key,
                )
        return applied_any
    key = payload.get("key")
    if not key:
        log.warning(
            "cache-replicate: incoming event missing bank/key; dropping %r",
            payload,
        )
        return False
    data = payload.get("data")
    try:
        cache.store(bank, key, data, expires=expires, _already_replicated=True)
        return True
    except Exception:  # pylint: disable=broad-except
        log.exception(
            "cache-replicate: failed to apply replicated write for %s/%s",
            bank,
            key,
        )
        return False
