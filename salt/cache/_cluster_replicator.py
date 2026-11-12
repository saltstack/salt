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
import hashlib
import logging
import os
import threading
import time

import salt.cache

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sender-side handshake gate
# ---------------------------------------------------------------------------
#
# A cluster_aes-encrypted ``cluster/peer/delegate-cache-write`` /
# ``delegate-resource-register-write`` event must only be fanned out to
# peers that have completed the cluster discover/join handshake.  A peer
# that is still running on its initial random ``cluster_aes`` (join-reply
# not yet installed) cannot decrypt the event; the publish daemon on
# that peer logs a loud ``Failed to decrypt`` exception and drops the
# payload.  The write is lost on that peer until the next write to the
# same (bank, key) lands, or until state-sync primitives (initiated by
# join-reply) catch the peer up.
#
# Catch-up guarantee: a peer that completes its handshake AFTER this
# gate decides to skip it still ends up consistent because
#
#   * the join-reply's ``state_sync_cache_banks`` enumerates every
#     replicate-mode bank and streams the current contents in
#     ``state-sync-chunk`` events (see
#     :mod:`salt.cluster.state_sync` and the ``send_state_sync_chunks``
#     call in the join-reply handler), AND
#   * subsequent writes on the originator will see the peer as joined
#     and fan out normally.
#
# So the gate never silently drops data on the floor -- it just defers
# the write to the peer's catch-up stream, which is the design-intended
# path for pre-handshake writes.
#
# API shape: the publish daemon holds the authoritative ``_discover_replies``
# + ``peer_keys`` sets; it passes them into :func:`filter_joined_pushers`
# which returns ``(kept, skipped)`` and emits a warning when a peer is
# skipped.  The gate can be disabled globally via
# ``opts["cluster_cache_replicate_require_joined"] = False``.
_SKIP_LOG_INTERVAL = 5.0  # seconds; coalesce skip-warnings per peer
_SKIP_LOG_LAST = {}  # (host, context) -> (last_ts, suppressed_count)
_SKIP_LOG_LOCK = threading.Lock()


def peer_is_joined(discover_replies, peer_keys, peer_host):
    """
    Return ``True`` if ``peer_host`` has completed the cluster
    discover/join handshake far enough to decrypt cluster_aes
    events.

    The handshake has two observable signals:

    * ``discover_replies`` -- this master has received a signed
      ``cluster/peer/discover-reply`` from the peer.  That reply is
      sent only after the peer has installed cluster.pub locally,
      which in turn happens after the peer processed a ``join-reply``
      (which carried ``cluster_aes``).  A peer in this set is
      therefore guaranteed to have our current ``cluster_aes``.

    * ``peer_keys`` -- this master has received the peer's session AES
      key via the ``cluster/peer/<master_id>`` AES-key broadcast.
      That broadcast is independent of the discover protocol but it
      ALSO only fires after the peer has installed cluster_aes
      (``send_aes_key_event`` is called from the ``cluster/peer``
      handler which itself runs after key installation).  So
      ``peer_keys`` membership is a slightly later-but-equivalent
      signal; we accept it to tolerate restart scenarios where
      ``discover_replies`` is empty but the peer is fully joined.

    The host match is lenient: ``cluster_peers`` entries may carry a
    ``:port`` suffix while the handshake handlers key on the bare
    host, so we match either form.

    :param discover_replies: Iterable/set of peer ids that have
                             sent us ``discover-reply``.
    :param peer_keys:        Dict of ``peer_id -> session_key`` from
                             ``MasterPubServerChannel.peer_keys``.
    :param peer_host:        The peer's ``pull_host`` (or
                             ``cluster_peers`` entry).
    :rtype:                  bool
    """
    if not peer_host:
        return False
    replies = discover_replies or set()
    keys = peer_keys or {}
    bare = peer_host.rsplit(":", 1)[0] if ":" in peer_host else peer_host
    if peer_host in replies or bare in replies:
        return True
    if peer_host in keys or bare in keys:
        return True
    return False


def _log_skip(peer_host, context, reason):
    """
    Emit a WARN for a skipped fan-out, coalesced per ``(host, context)``.

    A joiner that stays un-joined for many seconds will otherwise
    flood the log on every write on a busy master.  The first skip
    for a given ``(host, context)`` logs immediately; subsequent
    skips within ``_SKIP_LOG_INTERVAL`` increment a suppressed-count
    that is flushed on the next log past the interval.
    """
    now = time.monotonic()
    emit = False
    suppressed = 0
    with _SKIP_LOG_LOCK:
        last_ts, prev_suppressed = _SKIP_LOG_LAST.get((peer_host, context), (0.0, 0))
        if now - last_ts >= _SKIP_LOG_INTERVAL:
            emit = True
            suppressed = prev_suppressed
            _SKIP_LOG_LAST[(peer_host, context)] = (now, 0)
        else:
            _SKIP_LOG_LAST[(peer_host, context)] = (last_ts, prev_suppressed + 1)
    if emit:
        if suppressed:
            log.warning(
                "cluster-cache-replication: skipping %s fan-out to %s "
                "(%s); %d similar skips suppressed in last %ds",
                context,
                peer_host,
                reason,
                suppressed,
                int(_SKIP_LOG_INTERVAL),
            )
        else:
            log.warning(
                "cluster-cache-replication: skipping %s fan-out to %s (%s)",
                context,
                peer_host,
                reason,
            )


def filter_joined_pushers(pushers, discover_replies, peer_keys, opts, context=None):
    """
    Filter ``pushers`` down to peers that have completed the cluster
    handshake.

    This is the single seam the publish daemon consults before
    emitting a cluster_aes-encrypted replication event.  Peers that
    have not sent a ``discover-reply`` and whose session key has not
    been installed cannot decrypt the event and would log a loud
    ``Failed to decrypt`` on receive; skipping them here converts the
    silent-loss failure mode into a WARN on the sender side and lets
    the join-time state-sync stream catch them up.

    Catch-up guarantee: a peer that joined after this check executed
    but before the fan-out arrived will NOT receive this specific
    write; they catch up via the state-sync primitives streamed in
    the ``join-reply`` handler (see
    :mod:`salt.cluster.state_sync`) and via subsequent writes that
    see the peer as joined.  No write is silently dropped.

    :param pushers:          Iterable of ``Pusher`` objects (each
                             exposes ``pull_host``).
    :param discover_replies: Set of peer ids that have sent us
                             ``discover-reply``.
    :param peer_keys:        Dict of ``peer_id -> session_key``.
    :param opts:             Master opts dict.  Consulted for the
                             ``cluster_cache_replicate_require_joined``
                             master switch -- if False, the gate is
                             inactive and every pusher is kept.
    :param context:          Short human-readable label (e.g.
                             ``"delegate-cache-write"``) used only in
                             the skip-log; may be ``None``.
    :returns:                ``(kept, skipped)`` -- two lists of
                             pushers.  Callers that want pre-gate
                             semantics can ignore ``skipped``; today
                             we just warn.
    """
    pushers_list = list(pushers or ())
    if opts is not None and opts.get("cluster_cache_replicate_require_joined") is False:
        return pushers_list, []
    if not pushers_list:
        return pushers_list, []
    kept = []
    skipped = []
    for pusher in pushers_list:
        host = getattr(pusher, "pull_host", None)
        if peer_is_joined(discover_replies, peer_keys, host):
            kept.append(pusher)
        else:
            skipped.append(pusher)
            _log_skip(
                host, context or "cache-replicate", "peer has not completed handshake"
            )
    return kept, skipped


def secret_fingerprint(secret):
    """
    Return the first 8 hex chars of ``sha256(secret)`` for log
    correlation.

    Never logs the full secret; the fingerprint is useful for
    matching an operator's ``cluster_aes converge`` events against a
    ``Failed to decrypt`` entry in the log stream.  Returns
    ``"<unavailable>"`` if ``secret`` cannot be hashed (missing or
    wrong type).
    """
    if secret is None:
        return "<unavailable>"
    try:
        if isinstance(secret, str):
            secret = secret.encode()
        return hashlib.sha256(secret).hexdigest()[:8]
    except Exception:  # pylint: disable=broad-except
        return "<unavailable>"


# ---------------------------------------------------------------------------
# Decrypt-failure log rate-limiting
# ---------------------------------------------------------------------------
#
# Receivers that cannot decrypt a cluster_aes event today log a full
# stack trace via ``log.exception(...)``.  Under a bootstrap race the
# originator may keep firing writes faster than the receiver's
# handshake can complete; a naive log.exception per arrival explodes
# the log.  ``log_decrypt_failure`` keeps the stack trace on the
# FIRST failure for each ``(tag, peer)`` tuple within a window and
# coalesces subsequent failures into a counter flushed on the next
# log past the window.
_DECRYPT_LOG_INTERVAL = 5.0  # seconds
_DECRYPT_LOG_LAST = {}  # (tag, peer) -> (last_ts, suppressed_count)
_DECRYPT_LOG_LOCK = threading.Lock()


def log_decrypt_failure(tag, opts, secret, source_peer=None, extra=None):
    """
    Correlatable, rate-limited log for a cluster_aes decrypt failure.

    Called from the receiver side (``handle_pool_publish``) when
    ``Crypticle.loads()`` raises on an incoming cluster event.
    Captures the cluster identity, a short fingerprint of the local
    cluster_aes (never the key itself), the event tag, and whatever
    source-peer identifier the caller can supply (the ciphertext is
    opaque so source_peer may be ``None`` on wire arrivals).

    The first failure for a ``(tag, source_peer)`` tuple in each
    window logs with a full stack trace (``log.exception``) so the
    operator still gets the diagnostic signal.  Subsequent failures
    in the same window increment a suppressed-count flushed when the
    window expires.

    :param tag:         Event tag string (e.g.
                        ``cluster/peer/delegate-cache-write``).
    :param opts:        Master opts dict; ``cluster_id`` is logged.
    :param secret:      The local cluster_aes value that failed to
                        decrypt the event (passed in so the caller can
                        pass a bytes value fetched under
                        ``SMaster.secrets[...]`` without re-fetching
                        here).
    :param source_peer: Optional source-peer identifier.  ``None``
                        is acceptable; cluster_aes events on the
                        pool channel don't carry a sender id in
                        the ciphertext envelope.
    :param extra:       Optional dict of additional key/value pairs
                        to include in the log (e.g. write_kind,
                        bank name on decrypted failures).  Each
                        entry is formatted ``k=v``.
    """
    now = time.monotonic()
    key = (tag, source_peer)
    emit_exc = False
    suppressed = 0
    with _DECRYPT_LOG_LOCK:
        last_ts, prev_suppressed = _DECRYPT_LOG_LAST.get(key, (0.0, 0))
        if now - last_ts >= _DECRYPT_LOG_INTERVAL:
            emit_exc = True
            suppressed = prev_suppressed
            _DECRYPT_LOG_LAST[key] = (now, 0)
        else:
            _DECRYPT_LOG_LAST[key] = (last_ts, prev_suppressed + 1)
    if not emit_exc:
        return
    cluster_id = (opts or {}).get("cluster_id") if isinstance(opts, dict) else None
    fingerprint = secret_fingerprint(secret)
    parts = [
        f"tag={tag}",
        f"cluster_id={cluster_id!r}",
        f"cluster_aes_fp={fingerprint}",
        f"source_peer={source_peer!r}",
    ]
    if extra:
        for k, v in extra.items():
            parts.append(f"{k}={v!r}")
    if suppressed:
        parts.append(f"suppressed_similar={suppressed}")
    log.exception(
        "cluster-decrypt-failed: %s -- handshake incomplete or cluster_aes mismatch",
        " ".join(parts),
    )


# Per-process shared Cache for the peer-apply hot path.
#
# ``_handle_delegate_cache_write`` previously built a fresh ``Cache(opts)``
# on every incoming event. Under heavy peer-event load (hundreds/s) that
# forced every one of the publish daemon's ~32 executor threads to
# acquire the shared ``functools.cached_property`` RLock guarding
# ``Cache.modules``, which serialised them all through one critical
# section running ``salt.loader.cache(opts)``. Reusing one long-lived
# ``Cache`` moves the ``.modules`` lookup to a one-shot, after which
# the result lives in ``instance.__dict__`` and subsequent accesses
# bypass the descriptor's lock entirely.
#
# Keyed on ``id(opts)`` so a replacement opts dict triggers a rebuild.
# Driver-level writes (mmap_cache flock, localfs fcntl) remain
# thread-safe across concurrent ``store()`` calls on the shared
# instance; the only state ``Cache.store`` reads after the first
# ``.modules`` access is ``self.opts`` + ``self.kwargs`` (both
# immutable after construction).
_PEER_APPLY_CACHE_LOCK = threading.Lock()
_peer_apply_cache = (0, None)


def _get_peer_apply_cache(opts):
    """
    Return a long-lived ``Cache`` for peer-apply writes.

    First call initialises; subsequent calls return the cached instance
    without acquiring any lock (reading a Python-level reference is
    atomic under the GIL). Rebuilds if ``id(opts)`` changes.

    :param opts: Master opts dict.
    :rtype:      salt.cache.Cache
    """
    global _peer_apply_cache  # pylint: disable=global-statement
    opts_id = id(opts)
    cur = _peer_apply_cache
    if cur[0] == opts_id and cur[1] is not None:
        return cur[1]
    with _PEER_APPLY_CACHE_LOCK:
        cur = _peer_apply_cache
        if cur[0] != opts_id or cur[1] is None:
            _peer_apply_cache = (opts_id, salt.cache.Cache(opts))
    return _peer_apply_cache[1]


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
        cache = _get_peer_apply_cache(opts)
    except Exception:  # pylint: disable=broad-except
        log.exception(
            "cache-replicate: failed to obtain shared Cache for replication apply"
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
