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
