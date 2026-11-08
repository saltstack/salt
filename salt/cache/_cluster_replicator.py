"""
Cross-master cache replication seams.

Free-function entry points for both sides of the delegate-cache-write
flow so each side is testable without instantiating a channel class
or a Cache object.  ``Cache.store`` and ``Cache.store_many`` emit via
:func:`fire_peer_cache_write` / :func:`fire_delegate_cache_write`;
``MasterPubServerChannel._handle_delegate_cache_write`` delegates to
:func:`_handle_delegate_cache_write`.
"""

import logging

import salt.cache

log = logging.getLogger(__name__)


def _fire_event(opts, write_kind, bank, key, data, expires):
    """
    Common implementation: fire ``cluster/runner/delegate_cache_write``
    with the given write_kind.  The master's publish daemon intercepts
    the event and either fans it out to every peer (``replicate``) or
    routes it to the HashRing owner (``ring``).
    """
    import salt.utils.event  # pylint: disable=import-outside-toplevel

    try:
        payload = {
            "bank": bank,
            "key": key,
            "data": data,
            "expires": expires,
            "write_kind": write_kind,
            "originating_master": opts.get("id"),
        }
        with salt.utils.event.get_event(
            "master",
            sock_dir=opts.get("sock_dir"),
            opts=opts,
            listen=False,
        ) as event:
            event.fire_event(payload, "cluster/runner/delegate_cache_write")
    except Exception:  # pylint: disable=broad-except
        log.exception(
            "cluster-cache-replication: failed to fire %s event for %s/%s",
            write_kind,
            bank,
            key,
        )


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


def fire_delegate_cache_write(opts, bank, key, data, expires=None):
    """
    Route a cache write to a single HashRing owner (1-of-N delegation).

    Called when the per-bank routing resolves to ``"ring"`` (e.g. the
    ``jobs`` bank by default, for backward compat with the existing
    ring-sharded job returner).
    """
    _fire_event(opts, "ring", bank, key, data, expires)


def _handle_delegate_cache_write(opts, payload):
    """
    Apply a peer-originated cache write locally.

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
                    ``bank``, ``key``, ``data``, and optional ``expires``.
    :returns:       ``True`` if the write was applied, ``False`` if
                    dropped (loop-guard or malformed payload).
    """
    if payload.get("originating_master") == opts.get("id"):
        return False
    bank = payload.get("bank")
    key = payload.get("key")
    if not bank or not key:
        log.warning(
            "cache-replicate: incoming event missing bank/key; dropping %r",
            payload,
        )
        return False
    data = payload.get("data")
    expires = payload.get("expires")
    try:
        cache = salt.cache.Cache(opts)
        cache.store(bank, key, data, expires=expires, _already_replicated=True)
        return True
    except Exception:  # pylint: disable=broad-except
        log.exception(
            "cache-replicate: failed to apply replicated write for %s/%s",
            bank,
            key,
        )
        return False
