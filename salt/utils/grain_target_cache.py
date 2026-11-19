"""
In-process sorted-key cache for ``resource_id:<prefix>*`` grain-target
predicates.

Companion to :mod:`salt.utils.minions` — specifically the
``_augment_grain_match_with_resource_grains`` grain-target expansion path
that walks the ``resource_grains`` cache bank. The literal-id fast path
(Mission 1) handles ``resource_id:<exact-id>`` via an O(T) hash probe;
this module handles the next tier -- globs with a non-empty fixed prefix
such as ``resource_id:web-*`` or ``resource_id:a-dummy-00*`` -- by
binary-searching a sorted copy of the bank's keys so we iterate only the
prefix range instead of linearly scanning ~400K entries.

Scope
-----
* Query-only. Reads from the existing cache bank; never writes.
* Per-process in-memory index. No disk file, no mmap, no persistence.
* Keyed by ``(cachedir, bank)`` so a process with multiple cache dirs
  (test harness, multi-master-in-process) keeps them separate.

Invalidation
------------
A cheap per-bank "generation" signal is sampled on every query. If the
signal matches the one recorded at build time the cached sorted list is
reused verbatim; otherwise it is rebuilt. Signals (best available for
each driver):

* ``mmap_cache``: the 8-byte ``occupied_count`` header field at offset 1
  of ``<bank>/.mmap_cache.idx``. The master bumps this on every
  ``store`` / delete, so any write to the bank advances the signal
  without us having to coordinate with the writer.
* ``localfs`` (and any other dir-backed driver): ``st_mtime_ns`` of the
  bank directory. Directory mtime advances whenever a ``.p`` file is
  added, removed, or renamed.
* Anything else / signal unavailable: fall back to an "always rebuild"
  tag so correctness is preserved at the cost of the fast path's
  speedup.

Thread safety
-------------
The module exposes a singleton :class:`GrainTargetCache` guarded by a
single ``RLock``. The hot path (same generation) takes the lock, returns
the cached list (an immutable-by-convention ``list`` reference), and
releases. Rebuilds hold the lock. A caller that holds the returned list
may keep iterating it even if another thread subsequently rebuilds --
the old list stays valid because we always replace, never mutate.
"""

import bisect
import logging
import os
import struct
import threading

import salt.utils.files

log = logging.getLogger(__name__)

# mmap_cache header: offset 1, uint64 little-endian = occupied_count.
# Mirrors the constants in salt.utils.mmap_cache but duplicated here so
# we do not force-import the mmap_cache module (and its xxhash
# dependency) in every CkMinions process just to read 8 header bytes.
_MMAP_INDEX_FILENAME = ".mmap_cache.idx"
_MMAP_HDR_OCCUPIED_OFF = 1
_MMAP_HDR_OCCUPIED_FMT = "<Q"
_MMAP_HDR_OCCUPIED_SIZE = 8

# Sentinel generation returned when we cannot derive a stable signal for
# a bank. Treating it as "always-stale" means callers rebuild each time,
# which costs the enumeration pass but preserves correctness.
_GEN_UNKNOWN = object()


def fixed_prefix_of(glob_pattern):
    """
    Return the maximal literal prefix of an ``fnmatch`` glob, or ``""``
    when the pattern starts with a wildcard or char-class.

    The prefix stops at the first unescaped ``*``, ``?`` or ``[``. We do
    **not** attempt to honour ``fnmatch``'s ``[`` escape-via-brackets
    semantics (``[[]`` to match a literal ``[``); any ``[`` terminates
    the prefix. Bank keys in practice are ``<rtype>:<rid>`` where ``rid``
    is a bare id composed of ``[A-Za-z0-9._-]`` -- bracket classes are
    extremely rare and the fall-through to the linear scan handles them.

    Returns an empty string (not ``None``) when the pattern has no fixed
    prefix. ``None`` input returns ``None``.
    """
    if not isinstance(glob_pattern, str):
        return None
    prefix_chars = []
    for ch in glob_pattern:
        if ch in ("*", "?", "["):
            break
        prefix_chars.append(ch)
    return "".join(prefix_chars)


def prefix_range_candidates(sorted_keys, id_prefix):
    """
    Yield the keys from ``sorted_keys`` that start with ``id_prefix``.

    ``sorted_keys`` must be sorted by Python's default string ordering
    (``sorted(...)`` with no key). ``id_prefix`` may be empty, in which
    case the full list is yielded (callers normally short-circuit
    without calling us in that case).

    Uses ``bisect_left`` for the lower bound and walks forward until a
    key no longer starts with the prefix -- O(log N + matches).
    """
    if not sorted_keys:
        return
    if not id_prefix:
        yield from sorted_keys
        return
    lo = bisect.bisect_left(sorted_keys, id_prefix)
    n = len(sorted_keys)
    i = lo
    while i < n:
        k = sorted_keys[i]
        if not k.startswith(id_prefix):
            break
        yield k
        i += 1


def _mmap_index_path(cachedir, bank):
    """Return the expected ``.mmap_cache.idx`` path for ``bank``."""
    # bank may contain path separators (nested banks); ``os.path.join``
    # with ``os.path.normpath`` mirrors what the mmap_cache driver does
    # internally so we look at the same file.
    return os.path.join(cachedir, os.path.normpath(bank), _MMAP_INDEX_FILENAME)


def _read_mmap_generation(cachedir, bank):
    """
    Return the current mmap_cache ``occupied_count`` for *bank*, or
    ``None`` if the index file is missing / too small / unreadable.

    Reads exactly 8 bytes at offset 1 -- O(1).
    """
    path = _mmap_index_path(cachedir, bank)
    try:
        with salt.utils.files.fopen(path, "rb") as fh:
            fh.seek(_MMAP_HDR_OCCUPIED_OFF)
            buf = fh.read(_MMAP_HDR_OCCUPIED_SIZE)
    except (FileNotFoundError, PermissionError, OSError):
        return None
    if len(buf) != _MMAP_HDR_OCCUPIED_SIZE:
        return None
    try:
        return struct.unpack(_MMAP_HDR_OCCUPIED_FMT, buf)[0]
    except struct.error:
        return None


def _read_dir_generation(cachedir, bank):
    """
    Return the bank-directory's ``st_mtime_ns``, or ``None`` if the
    directory does not exist / is not accessible.
    """
    path = os.path.join(cachedir, os.path.normpath(bank))
    try:
        st = os.stat(path)
    except (FileNotFoundError, PermissionError, OSError):
        return None
    return st.st_mtime_ns


def _bank_generation(cache, bank):
    """
    Return a cheap O(1) signal that changes when *bank* is written to.

    Tries the mmap-cache ``occupied_count`` header first (available iff
    the bank directory contains ``.mmap_cache.idx``); falls back to the
    bank directory's ``st_mtime_ns``; returns :data:`_GEN_UNKNOWN` when
    neither can be derived (correctness-preserving "always rebuild").
    """
    cachedir = getattr(cache, "cachedir", None)
    if not cachedir:
        return _GEN_UNKNOWN
    mmap_gen = _read_mmap_generation(cachedir, bank)
    if mmap_gen is not None:
        return ("mmap", mmap_gen)
    dir_gen = _read_dir_generation(cachedir, bank)
    if dir_gen is not None:
        return ("dir", dir_gen)
    return _GEN_UNKNOWN


class GrainTargetCache:
    """
    Per-process cache of ``{(cachedir, bank): (generation, sorted_keys)}``.

    Not instantiated directly by callers -- use :func:`get` for the
    module-level singleton. A dedicated instance is still useful for
    tests that need isolation from the module-level state.
    """

    def __init__(self):
        self._entries = {}
        self._lock = threading.RLock()

    def _cache_key(self, cache, bank):
        cachedir = getattr(cache, "cachedir", None) or ""
        return (cachedir, bank)

    def invalidate(self, cache=None, bank=None):
        """
        Drop cached entries. With no arguments drops everything; with
        ``cache`` and ``bank`` drops only that bank.
        """
        with self._lock:
            if cache is None and bank is None:
                self._entries.clear()
                return
            key = self._cache_key(cache, bank)
            self._entries.pop(key, None)

    def get_sorted_keys(self, cache, bank):
        """
        Return the current sorted list of keys in ``bank``, rebuilding
        if the bank-generation signal has advanced since the last build.

        Returns a list -- possibly empty. Callers must treat the list as
        immutable; the cache keeps the same object on subsequent hits
        and may hand it to concurrent readers.
        """
        key = self._cache_key(cache, bank)
        with self._lock:
            current_gen = _bank_generation(cache, bank)
            entry = self._entries.get(key)
            if entry is not None:
                cached_gen, cached_keys = entry
                # _GEN_UNKNOWN never compares equal (sentinel object) so
                # banks with no cheap signal always rebuild -- correct
                # if slow.
                if cached_gen is not _GEN_UNKNOWN and cached_gen == current_gen:
                    return cached_keys
            try:
                raw = cache.list(bank) or []
            except Exception:  # pylint: disable=broad-except
                log.debug(
                    "grain_target_cache: cache.list(%r) failed; "
                    "returning empty key list",
                    bank,
                    exc_info=True,
                )
                raw = []
            # Defensive: cache.list may return an iterable (generator),
            # tuple, set, or non-string entries. Stringify + sort.
            keys = sorted(str(k) for k in raw)
            self._entries[key] = (current_gen, keys)
            return keys


# Module-level singleton. Tests that need isolation can instantiate
# their own :class:`GrainTargetCache`; the production hot path uses this
# one so a single CkMinions process does not pay the enumeration cost
# per-instance.
_default = GrainTargetCache()


def get():
    """Return the module-level :class:`GrainTargetCache` singleton."""
    return _default


def get_sorted_keys(cache, bank):
    """Shortcut for ``get().get_sorted_keys(cache, bank)``."""
    return _default.get_sorted_keys(cache, bank)


def invalidate(cache=None, bank=None):
    """Shortcut for ``get().invalidate(cache, bank)``."""
    _default.invalidate(cache=cache, bank=bank)
