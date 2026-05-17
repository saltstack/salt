"""
Paged bulk state-sync for cluster joiners.

The cluster join handshake (``cluster/peer/join`` ->
``cluster/peer/join-reply``) carries the cluster's identity material
(``cluster_aes``, ``cluster.pem``, peer pubs), but the joining master
also needs the *content* the cluster has accumulated: accepted /
denied minion keys, the file_roots tree, and the pillar_roots tree.
That content can run from a few KB on a fresh cluster to tens of MB
on a production deployment with thousands of minions and a large
SLS tree.

To keep the join-reply itself small and to give the joiner partial-
progress + per-channel failure isolation, the state-sync runs on
*four independent streams*, each chunked by its own budget:

==============  ==================  =======================
channel         chunked by          per-chunk budget
==============  ==================  =======================
``keys``        entry count         ``DEFAULT_KEY_CHUNK_COUNT``
``denied_keys`` entry count         ``DEFAULT_KEY_CHUNK_COUNT``
``file_roots``  cumulative bytes    ``DEFAULT_ROOTS_CHUNK_BYTES``
``pillar_roots`` cumulative bytes   ``DEFAULT_ROOTS_CHUNK_BYTES``
==============  ==================  =======================

Wire format
-----------
The responder allocates a session id, names it in the join-reply's
``state_sync_session`` field, then publishes a series of
``cluster/peer/state-sync-chunk`` events to the joiner.  Each event
payload is a Crypticle-encrypted dict (encrypted under the cluster
session AES key the joiner just received in the same join-reply)::

    {
        "session":  str,            # matches join-reply state_sync_session
        "channel":  str,            # one of ALL_CHANNELS
        "seq":      int,            # 0-indexed sequence within this channel
        "total":    int,            # total chunks for this channel (-1 if unknown)
        "eof":      bool,           # True on the final chunk for this channel
        "items":    list,           # channel-specific entries
    }

A channel with no data still emits one chunk with ``items=[]`` and
``eof=True``, so receivers can use the ``eof`` flag uniformly.

Receiver state machine
----------------------
:class:`StateSyncSession` is held by the joiner's
``MasterPubServerChannel`` and tracks per-channel ``eof`` flags.  The
caller provides an ``on_complete`` callback that fires when all four
channels have either eof'd or the deadline expires (whichever comes
first); the channel server uses that callback to call
``_start_raft_as_learner`` only after bulk sync is at rest.
"""

import logging
import secrets
import time

import salt.cache
import salt.exceptions

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Channel names + chunking knobs
# ---------------------------------------------------------------------------

KEYS_CHANNEL = "keys"
DENIED_CHANNEL = "denied_keys"
FILE_ROOTS_CHANNEL = "file_roots"
PILLAR_ROOTS_CHANNEL = "pillar_roots"

# Channel prefix for arbitrary cache banks (multi-ring migration).  A
# channel string ``"bank:jobs/loads"`` names the cache bank that
# carries the payload; the receiver routes by prefix to
# :func:`install_bank_chunk`.  Used by
# ``cluster.collect_from_peers`` for caches other than the four
# join-time channels above.
BANK_CHANNEL_PREFIX = "bank:"


def bank_channel(bank):
    """Return the wire channel name for *bank*."""
    return f"{BANK_CHANNEL_PREFIX}{bank}"


def bank_from_channel(channel):
    """Return the bank name a ``bank:`` channel was made from, or None."""
    if not channel or not channel.startswith(BANK_CHANNEL_PREFIX):
        return None
    return channel[len(BANK_CHANNEL_PREFIX) :]


ALL_CHANNELS = (
    KEYS_CHANNEL,
    DENIED_CHANNEL,
    FILE_ROOTS_CHANNEL,
    PILLAR_ROOTS_CHANNEL,
)

# Default count per chunk for cache-key channels.  Tuned so a 200-entry
# minion-key chunk (avg pub key ~500 bytes -> ~100 KB) fits comfortably in
# one Crypticle-encrypted message without dominating heartbeat bandwidth.
DEFAULT_KEY_CHUNK_COUNT = 200

# Default per-chunk byte budget for file-tree channels.  1 MB is a
# pragmatic compromise: small enough that a TCP retransmit is cheap, big
# enough that a typical SLS tree fits in a handful of chunks.
DEFAULT_ROOTS_CHUNK_BYTES = 1 * 1024 * 1024

# Default deadline (seconds) the joiner waits for all four channels to
# eof before falling back to event-driven replication.
DEFAULT_RECEIVE_TIMEOUT = 30


def new_session_id():
    """Return a fresh session id (URL-safe, no fixed length)."""
    return secrets.token_urlsafe(16)


# ---------------------------------------------------------------------------
# Sender-side: chunk generators
# ---------------------------------------------------------------------------


def _by_count(items, n):
    """Yield successive lists of *items* of size up to *n*."""
    chunk = []
    for item in items:
        chunk.append(item)
        if len(chunk) >= n:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def iter_keys_chunks(opts, channel, count=DEFAULT_KEY_CHUNK_COUNT, key_filter=None):
    """
    Yield ``items`` lists for the ``keys`` or ``denied_keys`` channel.

    Each item is ``{"id": minion_id, "value": cache_value}`` — a
    self-contained record the receiver hands straight to ``cache.store``.

    A bank with no entries (or whose entries are all filtered out) still
    yields one empty list so the caller can emit a single eof chunk.

    :param key_filter: Optional ``callable(minion_id) -> bool``.  When
                       present, only entries whose id passes the
                       filter are emitted.  Used by the multi-ring
                       ``cluster.collect_from_peers`` runner so a peer
                       only sends back the keys the requester asked
                       for, rather than its entire bank.
    """
    if channel not in (KEYS_CHANNEL, DENIED_CHANNEL):
        raise ValueError(f"iter_keys_chunks: unsupported channel {channel!r}")
    cache = salt.cache.Cache(opts, driver=opts["keys.cache_driver"])
    try:
        dump = cache.list_all(channel, include_data=True)
    except (AttributeError, salt.exceptions.SaltCacheError):
        dump = {}
    pairs = list((dump or {}).items())
    if key_filter is not None:
        pairs = [(mid, value) for mid, value in pairs if key_filter(mid)]
    items = [{"id": mid, "value": value} for mid, value in pairs]
    if not items:
        yield []
        return
    yield from _by_count(items, count)


def iter_root_chunks(roots_map, byte_budget=DEFAULT_ROOTS_CHUNK_BYTES):
    """
    Yield ``items`` lists for the ``file_roots`` / ``pillar_roots`` channel.

    Each item is ``{"env": str, "path": str, "mode": int, "data": bytes}``
    — flattened across envs so the receiver can apply each entry without
    needing to track env boundaries within a chunk.

    Chunks are bounded by *byte_budget*: a chunk is closed when adding
    the next entry would exceed the budget *and* the chunk already holds
    at least one entry.  A single file larger than the budget gets its
    own chunk on its own.

    An empty / missing roots map yields one empty list so the caller can
    emit a single eof chunk.
    """
    # Lazy import to avoid a circular dependency at module load.
    from salt.cluster.file_sync import (  # pylint: disable=import-outside-toplevel
        collect_root_tree,
    )

    dump = collect_root_tree(roots_map)
    if not dump:
        yield []
        return

    chunk = []
    chunk_bytes = 0
    for env, files in dump.items():
        for entry in files:
            entry_bytes = len(entry.get("data") or b"")
            if chunk and chunk_bytes + entry_bytes > byte_budget:
                yield chunk
                chunk = []
                chunk_bytes = 0
            chunk.append(
                {
                    "env": env,
                    "path": entry["path"],
                    "mode": entry.get("mode", 0o644),
                    "data": entry["data"],
                }
            )
            chunk_bytes += entry_bytes
    if chunk:
        yield chunk


def iter_bank_chunks(opts, bank, count=DEFAULT_KEY_CHUNK_COUNT, key_filter=None):
    """
    Yield ``items`` lists for an arbitrary :class:`salt.cache.Cache`
    bank.

    Each item is ``{"key": str, "value": any}`` — the bank name is
    carried separately in the wire channel
    (``BANK_CHANNEL_PREFIX + bank``) so a single channel maps to a
    single bank on the receiver.

    Used by :func:`salt.runners.cluster.collect_from_peers` to pull
    arbitrary operator-routed caches (e.g. the salt_cache returner's
    ``jobs/loads``) from peers.  Mirrors :func:`iter_keys_chunks`'s
    contract: an empty bank still yields a single empty list so the
    eof flag fires uniformly.
    """
    cache_driver = opts.get("cache") or opts.get("keys.cache_driver")
    cache = salt.cache.Cache(opts, driver=cache_driver)
    pairs = []
    try:
        # Prefer the bulk list_all interface — drivers that implement
        # it avoid the N+1 fetch.
        dump = cache.list_all(bank, include_data=True)
        pairs = list((dump or {}).items())
    except (AttributeError, salt.exceptions.SaltCacheError):
        # Fallback for drivers that don't expose list_all (e.g.
        # custom plugin caches).
        try:
            for key in cache.list(bank):
                value = cache.fetch(bank, key)
                pairs.append((key, value))
        except salt.exceptions.SaltCacheError:
            pairs = []
    if key_filter is not None:
        pairs = [(k, v) for k, v in pairs if key_filter(k)]
    items = [{"key": k, "value": v} for k, v in pairs]
    if not items:
        yield []
        return
    yield from _by_count(items, count)


# ---------------------------------------------------------------------------
# Receiver-side: install one chunk
# ---------------------------------------------------------------------------


def install_keys_chunk(opts, channel, items):
    """
    Apply a single chunk of ``keys`` / ``denied_keys`` entries.

    Returns the number of entries successfully written.
    """
    if channel not in (KEYS_CHANNEL, DENIED_CHANNEL):
        raise ValueError(f"install_keys_chunk: unsupported channel {channel!r}")
    cache = salt.cache.Cache(opts, driver=opts["keys.cache_driver"])
    written = 0
    for entry in items or []:
        if not isinstance(entry, dict):
            continue
        mid = entry.get("id")
        value = entry.get("value")
        if not mid or value is None:
            continue
        try:
            cache.store(channel, mid, value)
            written += 1
        except Exception:  # pylint: disable=broad-except
            log.exception("state-sync: failed to install %s entry for %s", channel, mid)
    return written


def install_bank_chunk(opts, bank, items):
    """
    Apply a single chunk of generic bank entries.

    Each item is ``{"key": str, "value": any}``; the receiver writes
    via ``cache.store(bank, key, value)``.  Idempotent — receiving
    the same chunk twice overwrites but doesn't break.  Returns the
    number of entries successfully written.
    """
    if not bank:
        raise ValueError("install_bank_chunk: bank is required")
    cache_driver = opts.get("cache") or opts.get("keys.cache_driver")
    cache = salt.cache.Cache(opts, driver=cache_driver)
    written = 0
    for entry in items or []:
        if not isinstance(entry, dict):
            continue
        key = entry.get("key")
        if key is None:
            continue
        try:
            cache.store(bank, key, entry.get("value"))
            written += 1
        except Exception:  # pylint: disable=broad-except
            log.exception(
                "state-sync: failed to install %s/%s",
                bank,
                key,
            )
    return written


def install_root_chunk(roots_map, items):
    """
    Apply a single chunk of ``file_roots`` / ``pillar_roots`` entries.

    Reuses :func:`salt.cluster.file_sync.apply_root_tree` by re-grouping
    the flat ``items`` list back into ``{env: [entry, ...]}`` shape.

    Returns the number of files successfully written.
    """
    from salt.cluster.file_sync import (  # pylint: disable=import-outside-toplevel
        apply_root_tree,
    )

    grouped = {}
    for entry in items or []:
        if not isinstance(entry, dict):
            continue
        env = entry.get("env")
        path = entry.get("path")
        if not env or not path:
            continue
        grouped.setdefault(env, []).append(
            {
                "path": path,
                "mode": entry.get("mode", 0o644),
                "data": entry.get("data"),
            }
        )
    return apply_root_tree(roots_map, grouped)


# ---------------------------------------------------------------------------
# Receiver-side: per-session state machine
# ---------------------------------------------------------------------------


class StateSyncSession:
    """
    Tracks per-channel completion for one bulk state-sync.

    Used by the joiner's ``MasterPubServerChannel``: a session is created
    when the join-reply arrives, each inbound
    ``cluster/peer/state-sync-chunk`` calls :meth:`record_chunk`, and the
    *on_complete* callback fires exactly once when all four channels have
    eof'd (or :meth:`force_complete` is called by a watchdog timer).

    :param session_id: opaque session identifier from the join-reply.
    :param on_complete: zero-arg callable invoked once when the session
        finishes (either all eofs received or forced).
    :param channels: iterable of channel names that must all eof for
        *on_complete* to fire.  Defaults to :data:`ALL_CHANNELS`.
    """

    def __init__(self, session_id, on_complete, channels=ALL_CHANNELS):
        self.session_id = session_id
        self._on_complete = on_complete
        self._channels = tuple(channels)
        # Per-channel state: eof flag + count of chunks installed
        self._state = {
            ch: {"eof": False, "chunks": 0, "items": 0} for ch in self._channels
        }
        self._completed = False
        self.created_at = time.monotonic()

    def record_chunk(self, channel, seq, eof, items_installed):
        """
        Record one chunk's arrival.  Fires *on_complete* if this was the
        last outstanding eof.
        """
        if channel not in self._state:
            log.warning(
                "state-sync session %s: unknown channel %r (chunks=%d, eof=%s)",
                self.session_id,
                channel,
                seq,
                eof,
            )
            return
        st = self._state[channel]
        st["chunks"] += 1
        st["items"] += int(items_installed)
        if eof:
            if st["eof"]:
                log.warning(
                    "state-sync session %s: duplicate eof on %s (seq=%d)",
                    self.session_id,
                    channel,
                    seq,
                )
            st["eof"] = True
        self._maybe_complete()

    def _maybe_complete(self):
        if self._completed:
            return
        if all(self._state[ch]["eof"] for ch in self._channels):
            self._completed = True
            log.info(
                "state-sync session %s complete: %s",
                self.session_id,
                {ch: self._state[ch] for ch in self._channels},
            )
            try:
                self._on_complete()
            except Exception:  # pylint: disable=broad-except
                log.exception(
                    "state-sync session %s: on_complete callback failed",
                    self.session_id,
                )

    def force_complete(self):
        """
        Fire *on_complete* regardless of outstanding eofs.

        The watchdog timer calls this when the per-session deadline
        elapses; the joiner then proceeds with whatever data arrived and
        relies on event-driven replication for the rest.
        """
        if self._completed:
            return
        missing = [ch for ch in self._channels if not self._state[ch]["eof"]]
        log.warning(
            "state-sync session %s deadline reached; forcing complete with "
            "channels still pending: %s",
            self.session_id,
            missing,
        )
        self._completed = True
        try:
            self._on_complete()
        except Exception:  # pylint: disable=broad-except
            log.exception(
                "state-sync session %s: on_complete callback failed (forced)",
                self.session_id,
            )

    @property
    def completed(self):
        return self._completed

    def status(self):
        """Return a serialisable snapshot of per-channel progress (for logs)."""
        return dict(self._state)
