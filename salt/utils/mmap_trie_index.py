"""
Persistent mmap-backed grain trie index for resource-registry
grain-target queries.

Persists an exhaustive ``(path_tuple, scalar_value) -> [sr_key, ...]``
mapping on disk using :class:`salt.utils.mmap_cache.MmapCache`, so:

* **Nested paths are auto-covered.** ``dns:nameservers:127.0.0.11`` or
  any other arbitrarily-deep ``<a>:<b>:<c>:<value>`` predicate is served
  by splitting the expression on the delimiter and probing every valid
  (path, value) partition.
* **Process RAM is bounded.** The builder reads one grain dict at a
  time and flushes a bounded accumulator (default 1024 entries) to the
  mmap trie; the live query only materialises the specific sr_key list
  for a hit.

Scope
-----
* Opt-in via ``opts["enable_grain_trie_index"]``. When off, the
  resource-grain dispatch falls back to the legacy per-key
  fetch loop.
* Per-bank. Each bank gets its own trie-cache files under
  ``<cachedir>/<bank>/.trie/`` -- never mixed with the primary bank's
  mmap files.
* Build is scheduled lazily: queries rebuild when the bank-generation
  signal (see :mod:`salt.utils.grain_target_cache`) advances past the
  version persisted in ``trie.meta``.

Key / value schema
------------------
Every scalar leaf under a grain dict yields exactly one trie entry::

    key   = b"<path_segments-joined-by-\\x1e>\\x1f<str(value)>"
    value = msgpack.packb([sr_key_1, sr_key_2, ...])

Separator choice: ``\\x1e`` (ASCII RS) and ``\\x1f`` (ASCII US) are
ASCII control bytes that cannot appear in grain key identifiers
(Python-ish names) nor in the stringified scalar values our callers
emit. **Critically**, neither is NUL: the backing
:class:`MmapCache` uses ``\\x00`` as its key-field padding sentinel
and truncates reads at the first null. Embedding ``\\x00`` in a trie
key would cause silent slot-identity collisions during probing. The
separators are also both below ``0x20`` so they cannot be valid
UTF-8 continuation bytes, keeping the encoding injective across
every grain-value encoding we might encounter.

High-cardinality buckets (chunked storage)
------------------------------------------
When a single ``(path, value)`` would accumulate more than
``opts["grain_trie_max_list_size"]`` sr_keys we switch the bucket
layout from "one msgpack list under the natural key" to a **chunked**
layout:

* The natural trie key now stores a *chunk marker*::

      msgpack.packb({"_chunks": N, "_total": T})

  where ``N`` is the number of chunks on disk and ``T`` is the total
  sr_key count across those chunks.

* Chunk ``i`` lives under a derived key::

      <natural_key_bytes> + b"\\x1d" + f"{i:08X}".encode("ascii")

  i.e. a fixed 8-character uppercase-hex rendering of ``i``. Hex
  (rather than a raw ``to_bytes`` of the integer) keeps the key free
  of NUL bytes, which is necessary because :class:`MmapCache` uses
  NUL as the key-field padding sentinel and truncates reads at the
  first null. A little-endian uint32 of ``0`` is four NUL bytes --
  that would collapse chunk-0 and all subsequent chunks onto the
  same slot. 8 hex characters give 32 bits of index space (``2**32``
  chunks), well beyond any plausible fleet.

  Each chunk's value is a plain msgpack list of sr_keys -- exactly the
  same shape as a small non-chunked bucket.

Separator rationale: ``\\x1d`` (ASCII GS, Group Separator) is reserved
for the chunk-key suffix. It is distinct from the path separators
``\\x1e`` / ``\\x1f`` chosen in Mission 4, is not NUL (so MmapCache's
NUL-pad truncation does not bite), and is not a UTF-8 continuation
byte. A grain scalar value containing ``\\x1d`` would collide with a
chunk-key suffix of a shorter natural key -- extremely unlikely in
practice given the grain-value shapes we encounter, but called out
here as a documented limitation.

Amortised merge cost: once a bucket is chunked, flushes within a
single rebuild only mutate the LAST chunk until it fills, so cumulative
merge work for a bucket growing to size ``M`` is ``O(M)`` linear, not
``O(M^2 / batch_size)`` as it was under the "re-read the full list every
flush" approach.

Dict-vs-list unambiguity: a real sr_key leaf is always a msgpack ARRAY
while the chunk marker is a msgpack MAP, so the entry decoder can
dispatch on the leading byte.

Legacy ``_capped`` sentinel
---------------------------
Mission 4 (and the first iteration of this module) used a different
sentinel::

    msgpack.packb({"_capped": True, "count": <total-observed>})

to indicate a bucket whose sr_keys had been thrown away past
``max_list_size``. That sentinel is no longer written. For back-compat
with on-disk tries built by an older version we still *recognise* it
in :func:`_unpack_entry`: callers receiving a ``("cap", ...)`` decode
treat it as "data lost, trigger slow path once", and the next rebuild
re-materialises the bucket in chunked form.

Atomic rebuild
--------------
``rebuild()`` builds into a fresh :class:`MmapCache` at
``<trie_dir>/trie.idx.new`` (plus ``.new.heap`` / ``.new.roster``),
then ``os.replace()`` swaps each file into its live name. The meta
file is swapped last. Concurrent readers see either the pre-rebuild
state or the post-rebuild state -- never a torn intermediate.

Invalidation
------------
Reuses :func:`salt.utils.grain_target_cache._bank_generation`. The
builder reads the generation BEFORE it starts the pass, writes it to
``trie.meta`` after the swap. A subsequent reader whose observed
generation matches the meta skips the rebuild.
"""

import contextlib
import fnmatch
import logging
import os
import re
import tempfile
import threading
import time

import msgpack

import salt.utils.files
import salt.utils.grain_target_cache
import salt.utils.mmap_cache

log = logging.getLogger(__name__)

# Byte sentinels used inside the mmap key. Chosen because:
#   * They never appear in grain path segments (ascii-identifier keys)
#     or typical stringified scalar values.
#   * Neither is NUL (``\x00``). ``MmapCache`` uses NUL as the
#     key-field padding sentinel and truncates reads at the first
#     ``\x00``; embedding NUL in trie keys would cause slot
#     comparison to never match on read-back.
_PATH_SEP = b"\x1e"  # ASCII RS, separates nested path segments
_PATH_VALUE_SEP = b"\x1f"  # ASCII US, separates path from value
# ASCII GS, separates the natural bucket key from a chunk index when a
# bucket's sr_key list exceeds ``max_list_size`` and we spill it across
# multiple chunk entries. Reserved: a grain value containing ``\x1d``
# would collide with a chunk-key suffix of a shorter natural key. The
# collision is theoretical given the scalar shapes grain-flatten emits
# but is called out for forward-compat.
_CHUNK_SEP = b"\x1d"

# Default knobs mirrored from salt.config so a caller can instantiate
# an index without pulling the full opts dict through.
DEFAULT_MAX_LIST_SIZE = 100000
DEFAULT_BATCH_SIZE = 1024
# Trie files sit in a hidden sibling directory of the bank so a bank
# ``flush`` never accidentally stomps the trie (the primary bank only
# scans its own key hash-table).
_TRIE_DIRNAME = ".trie"
_TRIE_INDEX_FILENAME = "trie.idx"
_TRIE_META_FILENAME = "trie.meta"

# MmapCache sizing for the trie. The trie stores up to
# ``num_scalar_leaves(all_grain_dicts)`` entries. A fleet of 1M SRs x
# 10 grain leaves = 10M distinct keys worst case. We size for ~2x
# headroom (20M slots) by default, which the operator can override
# with ``grain_trie_mmap_size``.
_DEFAULT_MMAP_SIZE = 2_000_000
# Key size: path_segments-joined + \x1f + value. Grain keys are
# typically short (``dns``, ``nameservers``, etc.) so 128 bytes comfortably
# covers 3-level nesting + reasonable scalar values. Longer keys get
# truncated by MmapCache's slot_size enforcement -- documented in the
# class docstring.
_DEFAULT_KEY_SIZE = 128
# slot_size must be >= _FIXED_OVERHEAD + key_size = 21 + 128 = 149.
# Round up to a cache-line multiple for struct alignment.
_DEFAULT_SLOT_SIZE = 160

# Generation sentinel reused from grain_target_cache: when the bank
# signal is unknown we treat every open as potentially stale and
# rebuild eagerly. Mirrors the semantics used elsewhere.
_GEN_UNKNOWN = salt.utils.grain_target_cache._GEN_UNKNOWN  # noqa: SLF001


def _encode_path_segments(segments):
    """
    Return the ``\\x1e``-joined byte encoding of ``segments``.

    Segments are coerced to ``str`` then UTF-8 encoded. Empty-string
    segments are preserved so colon-in-value predicates (like
    ``ipv6:fe80::1``) can still be partitioned faithfully by the
    query-time splitter.
    """
    encoded = []
    for seg in segments:
        if isinstance(seg, bytes):
            encoded.append(seg)
        else:
            encoded.append(str(seg).encode("utf-8", errors="replace"))
    return _PATH_SEP.join(encoded)


def _encode_scalar_value(value):
    """
    Return the byte encoding used for a scalar leaf value.

    ``str`` passes through as UTF-8. ``bool``, ``int``, ``float`` use
    Python's default ``str()`` so we round-trip the human-readable form
    that a grain-target predicate also uses.
    """
    if isinstance(value, bytes):
        return value
    if isinstance(value, bool):
        # ``bool`` is a subclass of ``int`` in Python; check first so
        # ``True`` -> ``"True"`` matches what a grain predicate carries.
        return str(value).encode("utf-8")
    return str(value).encode("utf-8", errors="replace")


def _build_key(path_bytes, value_bytes):
    """Return the raw mmap key for a ``(path, value)`` pair."""
    return path_bytes + _PATH_VALUE_SEP + value_bytes


def _split_predicate(expr, delimiter):
    """
    Enumerate every valid ``(path_segments, value_string)`` partition of
    ``expr`` against ``delimiter``.

    For ``expr = "a:b:c"``, ``delimiter = ":"`` this yields::

        (["a"], "b:c")
        (["a", "b"], "c")

    Note: empty trailing segments are NOT emitted because a predicate
    ``"a:b:"`` with no value cannot match any leaf. Empty MIDDLE
    segments ARE preserved so that ``ipv6:fe80::1`` is partitioned as
    ``(["ipv6"], "fe80::1")``, ``(["ipv6", "fe80"], ":1")``,
    ``(["ipv6", "fe80", ""], "1")`` -- the exact set of lookups
    described in the mission edge-case table.
    """
    if not isinstance(expr, str) or not expr:
        return
    segments = expr.split(delimiter)
    if len(segments) < 2:
        return
    for i in range(1, len(segments)):
        path = segments[:i]
        value = delimiter.join(segments[i:])
        if not value:
            # Last segment partition with empty value is not useful --
            # a trie leaf is always a non-empty string value.
            continue
        yield path, value


def _flatten_leaves(gdict):
    """
    Yield ``(path_bytes, value_bytes)`` pairs for every indexable
    scalar leaf under ``gdict``.

    Walk rules (mirrors the mission spec):

    * ``dict``       -> recurse, path extended with the key.
    * ``list`` /
      ``tuple``      -> recurse into each element at the SAME path
                        so e.g. ``nameservers = ["1.1.1.1", "8.8.8.8"]``
                        produces two leaves both under
                        ``("dns", "nameservers")``.
    * ``None``       -> skip.
    * ``str`` / ``int`` /
      ``float`` /
      ``bool``       -> yield one leaf.
    * ``bytes``      -> yield one leaf (passed through verbatim).
    * anything else  -> skip with a DEBUG log.

    Does NOT emit for the top-level call when ``gdict`` is not a dict.
    """
    if not isinstance(gdict, dict):
        return
    stack = [((), gdict)]
    while stack:
        path, node = stack.pop()
        if isinstance(node, dict):
            for k, v in node.items():
                stack.append((path + (k,), v))
        elif isinstance(node, (list, tuple)):
            for element in node:
                stack.append((path, element))
        elif node is None:
            continue
        elif isinstance(node, (str, int, float, bool, bytes)):
            try:
                path_bytes = _encode_path_segments(path)
                value_bytes = _encode_scalar_value(node)
            except Exception:  # pylint: disable=broad-except
                log.debug(
                    "mmap_trie_index: skipping unencodable leaf path=%r value=%r",
                    path,
                    node,
                    exc_info=True,
                )
                continue
            yield path_bytes, value_bytes
        else:
            log.debug(
                "mmap_trie_index: skipping unsupported leaf type %s at path=%r",
                type(node).__name__,
                path,
            )


def _pack_list(sr_keys):
    """Serialise an sr_key list to msgpack bytes."""
    return msgpack.packb(list(sr_keys), use_bin_type=True)


def _pack_cap(count):
    """
    Serialise the legacy cap sentinel to msgpack bytes.

    Retained only so :mod:`tests` and the back-compat decode path can
    construct an old-format sentinel; no production call site writes
    these any more (Mission 6 chunks over-cap buckets instead).
    """
    return msgpack.packb({"_capped": True, "count": int(count)}, use_bin_type=True)


def _pack_chunk_marker(n_chunks, total):
    """
    Serialise a chunk-marker entry to msgpack bytes.

    ``n_chunks`` is the number of chunk entries stored under derived
    keys, ``total`` is the sr_key count across every chunk.
    """
    return msgpack.packb(
        {"_chunks": int(n_chunks), "_total": int(total)}, use_bin_type=True
    )


def _chunk_write_fresh(key_bytes, sr_keys, max_list):
    """
    Return the ``(items, n_chunks, total, promoted)`` tuple describing
    the write-set for a bucket whose current on-disk state is empty /
    a legacy sentinel.

    ``items`` is a list of ``(key, packed_value)`` pairs ready to feed
    into :meth:`MmapCache.put_many`. ``promoted`` is ``True`` when the
    resulting layout is chunked (i.e. the input exceeded ``max_list``).

    The function never reads the backing cache; it is purely a layout
    decision.
    """
    total = len(sr_keys)
    if total <= max_list:
        return (
            [(bytes(key_bytes), _pack_list(sr_keys))],
            0,
            total,
            False,
        )
    items = []
    n_chunks = 0
    for start in range(0, total, max_list):
        chunk = sr_keys[start : start + max_list]
        items.append((_chunk_key(key_bytes, n_chunks), _pack_list(chunk)))
        n_chunks += 1
    items.append((bytes(key_bytes), _pack_chunk_marker(n_chunks, total)))
    return items, n_chunks, total, True


def _chunk_key(key_bytes, chunk_index):
    """
    Return the storage key for a specific chunk of a wide bucket.

    The key is the natural bucket key with ``\\x1d`` + an 8-character
    uppercase hex rendering of the chunk index appended. Hex encoding
    (as opposed to a binary ``to_bytes``) avoids embedding ``\\x00``
    into the key -- :class:`MmapCache` uses NUL as the key-field
    padding sentinel and truncates reads at the first null, which
    would silently collapse ``chunk_index=0`` and all subsequent
    chunks onto the same slot. 8 hex chars encode up to ``2**32``
    chunks (far beyond any realistic fleet's ``2**32 * max_list_size``
    sr_keys per bucket).
    """
    if not isinstance(key_bytes, (bytes, bytearray)):
        raise TypeError("key_bytes must be bytes")
    idx = int(chunk_index)
    if idx < 0 or idx > 0xFFFFFFFF:
        raise ValueError(f"chunk_index out of range: {idx!r}")
    return bytes(key_bytes) + _CHUNK_SEP + f"{idx:08X}".encode("ascii")


def _unpack_entry(raw):
    """
    Decode a trie entry value.

    Returns one of:

    * ``("list", [sr_key, ...])`` for a regular hit.
    * ``("chunks", {"_chunks": N, "_total": T})`` for a chunk marker;
      the caller must then fetch each chunk and union them.
    * ``("cap", {"_capped": True, "count": N})`` for the legacy cap
      sentinel (on-disk back-compat only; no new writes produce this).
    * ``None`` when the bytes cannot be decoded or carry an unknown
      shape.
    """
    if raw is None:
        return None
    if isinstance(raw, str):
        raw = raw.encode("utf-8", errors="replace")
    if not isinstance(raw, (bytes, bytearray)):
        return None
    if not raw:
        return ("list", [])
    try:
        obj = msgpack.unpackb(bytes(raw), raw=False)
    except Exception:  # pylint: disable=broad-except
        log.debug("mmap_trie_index: undecodable entry (%d bytes)", len(raw))
        return None
    if isinstance(obj, dict):
        if "_chunks" in obj:
            return ("chunks", obj)
        if obj.get("_capped"):
            return ("cap", obj)
        # Unknown dict shape -- corrupt entry.
        log.warning(
            "mmap_trie_index: unknown dict-shaped entry keys=%r; treating as missing",
            sorted(obj.keys()),
        )
        return None
    if isinstance(obj, list):
        return ("list", obj)
    # Unknown shape -- treat as missing so the caller falls back.
    return None


class MmapTrieIndex:
    """
    Persistent trie-style scalar-leaf index backed by
    :class:`salt.utils.mmap_cache.MmapCache`.

    One instance per ``(cachedir, bank)`` pair; callers normally
    acquire instances through :func:`for_bank`, which maintains a
    module-level registry so opening the same bank twice returns the
    same object (and the same ``MmapCache`` fds).

    The class only *reads* the primary bank; it never mutates it. It
    writes its own three mmap-cache files under ``<bank>/.trie/``.
    """

    def __init__(
        self,
        cachedir,
        bank,
        max_list_size=DEFAULT_MAX_LIST_SIZE,
        batch_size=DEFAULT_BATCH_SIZE,
        mmap_size=_DEFAULT_MMAP_SIZE,
        slot_size=_DEFAULT_SLOT_SIZE,
        key_size=_DEFAULT_KEY_SIZE,
        max_segment_bytes=None,
    ):
        self.cachedir = cachedir
        self.bank = bank
        self.max_list_size = max_list_size
        self.batch_size = batch_size
        self.mmap_size = mmap_size
        self.slot_size = slot_size
        self.key_size = key_size
        # ``None`` means "inherit MmapCache's default" (1 GiB). Tests
        # exercising the segment-roll code path override this to force
        # quick rolls on tiny data.
        self.max_segment_bytes = max_segment_bytes

        self._trie_dir = os.path.join(cachedir, os.path.normpath(bank), _TRIE_DIRNAME)
        self._index_path = os.path.join(self._trie_dir, _TRIE_INDEX_FILENAME)
        self._meta_path = os.path.join(self._trie_dir, _TRIE_META_FILENAME)
        # MmapCache reused across queries; opened lazily and reopened
        # after a rebuild swaps the underlying files out (the inode
        # changes, MmapCache's staleness check will tear down the stale
        # mmap on next ``open()``).
        self._mmap_cache = None
        self._meta_cache = None  # dict from msgpack.unpackb of meta file
        self._lock = threading.RLock()
        # Guards concurrent rebuild attempts from racing on the
        # ``.new`` temp files.
        self._build_lock = threading.Lock()

    # ------------------------------------------------------------------
    # File-level helpers
    # ------------------------------------------------------------------

    def _ensure_dir(self):
        """Create the ``<bank>/.trie/`` directory if missing."""
        os.makedirs(self._trie_dir, exist_ok=True)

    def _mmap_cache_kwargs(self):
        """
        Return extra kwargs to forward to :class:`MmapCache` from
        either the live reader (:meth:`_get_mmap`) or the rebuild's
        temp cache. Optional tunables that the operator didn't set are
        omitted so the ``MmapCache`` defaults apply.
        """
        kwargs = {}
        if self.max_segment_bytes is not None:
            kwargs["max_segment_bytes"] = self.max_segment_bytes
        return kwargs

    def _get_mmap(self):
        """
        Return an open :class:`MmapCache` for the trie index, creating
        and opening it on first use.

        Returns ``None`` if the index file does not exist yet AND we
        cannot create one (e.g. read-only filesystem). Callers treat
        ``None`` as "no trie available, fall through".
        """
        if self._mmap_cache is not None:
            return self._mmap_cache
        self._ensure_dir()
        try:
            cache = salt.utils.mmap_cache.MmapCache(
                path=self._index_path,
                size=self.mmap_size,
                slot_size=self.slot_size,
                key_size=self.key_size,
                **self._mmap_cache_kwargs(),
            )
        except Exception:  # pylint: disable=broad-except
            log.warning(
                "mmap_trie_index: cannot construct MmapCache at %s",
                self._index_path,
                exc_info=True,
            )
            return None
        self._mmap_cache = cache
        return cache

    def _reset_mmap(self):
        """Close and forget the current MmapCache (post-rebuild swap)."""
        if self._mmap_cache is not None:
            try:
                self._mmap_cache.close()
            except Exception:  # pylint: disable=broad-except
                pass
            self._mmap_cache = None

    def _list_new_heap_segments(self, base_new_heap_path, include_base=False):
        """
        Return the rolled-over scratch heap segments on disk for the
        in-progress rebuild.

        The result is sorted by segment ID ascending. When
        ``include_base`` is True the segment-0 file (``base_new_heap_path``
        itself) is included at the head of the list if it exists, so the
        caller can iterate the full segment set in one pass.

        Result shape:

        * ``include_base=False`` -> ``[str, str, ...]`` -- just the paths
          of ``.new.heap.1``, ``.new.heap.2``, ... that exist.
        * ``include_base=True``  -> ``[(seg_id, path), ...]`` sorted by
          ``seg_id`` ascending.
        """
        directory = os.path.dirname(base_new_heap_path) or "."
        base_name = os.path.basename(base_new_heap_path)
        prefix = base_name + "."
        found = []
        try:
            entries = os.listdir(directory)
        except OSError:
            entries = []
        for name in entries:
            if not name.startswith(prefix):
                continue
            suffix = name[len(prefix) :]
            if not suffix.isdigit():
                continue
            seg_id = int(suffix)
            found.append((seg_id, os.path.join(directory, name)))
        found.sort(key=lambda item: item[0])
        if include_base:
            if os.path.exists(base_new_heap_path):
                return [(0, base_new_heap_path)] + found
            return found
        return [p for _seg_id, p in found]

    def _list_live_heap_segment_ids(self, base_heap_path):
        """
        Return the segment IDs (sorted ascending) currently backing the
        live trie heap: 0 for the base file, plus any rolled-over
        ``.heap.N`` siblings. Missing files are omitted (an aborted
        prior rebuild may leave gaps).
        """
        ids = []
        if os.path.exists(base_heap_path):
            ids.append(0)
        directory = os.path.dirname(base_heap_path) or "."
        base_name = os.path.basename(base_heap_path)
        prefix = base_name + "."
        try:
            entries = os.listdir(directory)
        except OSError:
            entries = []
        for name in entries:
            if not name.startswith(prefix):
                continue
            suffix = name[len(prefix) :]
            if not suffix.isdigit():
                continue
            ids.append(int(suffix))
        ids.sort()
        return ids

    def _read_meta(self):
        """
        Return the persisted meta dict for the current trie, or ``None``
        when the meta file is missing / unreadable / corrupt.
        """
        try:
            with salt.utils.files.fopen(self._meta_path, "rb") as fh:
                raw = fh.read()
        except (FileNotFoundError, PermissionError, OSError):
            return None
        if not raw:
            return None
        try:
            obj = msgpack.unpackb(raw, raw=False)
        except Exception:  # pylint: disable=broad-except
            log.warning(
                "mmap_trie_index: meta file %s is corrupt -- forcing rebuild",
                self._meta_path,
            )
            return None
        if not isinstance(obj, dict):
            return None
        return obj

    def _write_meta_atomic(self, meta):
        """
        Write ``meta`` (a dict) to the meta file via a temp file +
        ``os.replace`` so observers never see a half-written header.
        """
        self._ensure_dir()
        raw = msgpack.packb(meta, use_bin_type=True)
        fd, tmp = tempfile.mkstemp(dir=self._trie_dir, prefix=".trie_meta_")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(raw)
                fh.flush()
                os.fsync(fh.fileno())
            fd = -1
            os.replace(tmp, self._meta_path)
        finally:
            if fd != -1:
                try:
                    os.close(fd)
                except OSError:
                    pass
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except OSError:
                pass

    def _generation_tag(self, current_gen):
        """
        Return a JSON-friendly serialisation of a ``_bank_generation``
        tuple so it survives msgpack round-trips in the meta file.

        ``_bank_generation`` returns one of ``("mmap", int)``,
        ``("dir", int)``, or the ``_GEN_UNKNOWN`` sentinel.
        """
        if current_gen is _GEN_UNKNOWN:
            return None
        if isinstance(current_gen, tuple) and len(current_gen) == 2:
            return [current_gen[0], current_gen[1]]
        return None

    def _meta_matches(self, meta, current_gen):
        """Return True if ``meta`` recorded the same generation we see now."""
        if meta is None:
            return False
        if current_gen is _GEN_UNKNOWN:
            return False
        stored = meta.get("generation")
        wanted = self._generation_tag(current_gen)
        if stored is None or wanted is None:
            return False
        return list(stored) == wanted

    @property
    def generation(self):
        """
        Return a monotonic generation tag for the current trie.

        Returns the ``built_at_ns`` nanosecond timestamp from the meta
        file: strictly monotonic across successive rebuilds and always
        an ``int`` when the trie has been built. Callers use this to
        detect "did the trie change since I last looked?" with a cheap
        ``>=`` comparison.

        Returns ``None`` only when the trie has never been built (no
        meta file on disk) or the meta file is unreadable / corrupt.

        O(1): reads a cached dict already loaded by
        :meth:`ensure_current`; falls back to a single meta-file read
        when accessed before ``ensure_current``.
        """
        meta = self._meta_cache
        if meta is None:
            meta = self._read_meta()
            if meta is not None:
                self._meta_cache = meta
        if not meta:
            return None
        built_at_ns = meta.get("built_at_ns")
        if built_at_ns is None:
            return None
        return int(built_at_ns)

    # ------------------------------------------------------------------
    # Build pipeline
    # ------------------------------------------------------------------

    def ensure_current(self, cache, bank):
        """
        Rebuild the on-disk trie if the bank's generation has advanced.

        Called at the top of :meth:`lookup_literal` and
        :meth:`values_for_path`. Returns ``True`` if a current trie is
        available, ``False`` if we could not produce one (e.g. the
        primary bank has no mmap or the rebuild failed).
        """
        try:
            current_gen = (
                salt.utils.grain_target_cache._bank_generation(  # noqa: SLF001
                    cache, bank
                )
            )
        except Exception:  # pylint: disable=broad-except
            current_gen = _GEN_UNKNOWN

        if self._meta_cache is None:
            self._meta_cache = self._read_meta()

        if self._meta_matches(self._meta_cache, current_gen):
            return self._get_mmap() is not None

        # Serialise concurrent build attempts; the second arrival will
        # find the meta current when it re-checks.
        with self._build_lock:
            self._meta_cache = self._read_meta()
            if self._meta_matches(self._meta_cache, current_gen):
                return self._get_mmap() is not None
            try:
                self._rebuild(cache, bank, current_gen)
            except Exception:  # pylint: disable=broad-except
                log.warning(
                    "mmap_trie_index: rebuild of bank=%r failed; "
                    "retaining stale/absent trie",
                    bank,
                    exc_info=True,
                )
                return self._get_mmap() is not None
        return self._get_mmap() is not None

    def _iter_bank_rows(self, cache, bank):
        """
        Yield ``(sr_key, grain_dict)`` pairs from *cache* / *bank* in a
        streaming fashion.

        Prefers per-key fetch over ``list_all``: ``list_all`` builds the
        full mapping in memory (defeats the memory-discipline goal).
        If the driver does not expose ``list`` we return an empty
        iterator and log at DEBUG.
        """
        try:
            keys = cache.list(bank) or []
        except Exception:  # pylint: disable=broad-except
            log.debug(
                "mmap_trie_index: cache.list(%r) failed; "
                "no trie entries will be built",
                bank,
                exc_info=True,
            )
            return
        for sr_key in keys:
            try:
                gdict = cache.fetch(bank, sr_key)
            except Exception:  # pylint: disable=broad-except
                continue
            yield sr_key, gdict

    def _rebuild(self, cache, bank, current_gen):
        """
        Produce a fresh trie by streaming the primary bank through the
        flattener, batching into a bounded accumulator, and atomically
        swapping the built files into place.

        Memory ceiling: one grain dict + the accumulator (bounded by
        ``self.batch_size``). The accumulator is a dict mapping encoded
        keys to lists of sr_keys; its size is bounded by ``batch_size``
        TOTAL sr_keys across all buckets.

        Exceptions mid-build leave the temp files behind; the finally
        clause cleans them up. The live trie is only mutated once the
        whole pass succeeds.
        """
        self._ensure_dir()
        new_index_path = self._index_path + ".new"
        # MmapCache-adjacent files follow the ``.heap`` / ``.roster``
        # naming scheme the class uses internally.
        new_heap_path = new_index_path + ".heap"
        new_roster_path = new_index_path + ".roster"
        # Remove any stale .new files from a previously-aborted build.
        # This includes rolled-over heap segments ``.new.heap.1``,
        # ``.new.heap.2``, ...  -- MmapCache rolls to a new segment
        # after each 1 GiB of heap data by default.
        stale_new_files = [new_index_path, new_heap_path, new_roster_path]
        stale_new_files.extend(self._list_new_heap_segments(new_heap_path))
        for p in stale_new_files:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass

        try:
            new_cache = salt.utils.mmap_cache.MmapCache(
                path=new_index_path,
                size=self.mmap_size,
                slot_size=self.slot_size,
                key_size=self.key_size,
                **self._mmap_cache_kwargs(),
            )
        except Exception:  # pylint: disable=broad-except
            log.warning(
                "mmap_trie_index: cannot create temp MmapCache at %s; aborting rebuild",
                new_index_path,
                exc_info=True,
            )
            return

        # Force creation of the backing files even if the bank is
        # empty. Without this, an empty-bank rebuild would skip the
        # atomic swap and leave stale .idx / .heap / .roster in place
        # from a previous non-empty generation.
        if not new_cache.open(write=True):
            log.warning(
                "mmap_trie_index: cannot initialise temp MmapCache files at %s",
                new_index_path,
            )
            try:
                new_cache.close()
            except Exception:  # pylint: disable=broad-except
                pass
            return

        accumulator = {}
        pending_count = 0
        # ``chunked_count`` is a cheap counter exposed in the log line;
        # no per-key dict is kept in process memory. Promotion to
        # chunked layout is decided at flush time by comparing
        # ``len(existing_bucket) + len(new_sr_keys)`` against
        # ``max_list_size`` -- the mmap entry is the source of truth,
        # so the builder needs no O(unique-keys) observed-counts dict.
        chunked_count = 0
        total_entries = 0
        total_rows = 0
        t0 = time.monotonic()

        try:
            for sr_key, gdict in self._iter_bank_rows(cache, bank):
                total_rows += 1
                if not isinstance(gdict, dict):
                    continue
                sr_key_str = str(sr_key)
                for path_bytes, value_bytes in _flatten_leaves(gdict):
                    key = _build_key(path_bytes, value_bytes)
                    bucket = accumulator.get(key)
                    if bucket is None:
                        bucket = []
                        accumulator[key] = bucket
                    bucket.append(sr_key_str)
                    pending_count += 1
                    if pending_count >= self.batch_size:
                        chunked_count += self._flush(new_cache, accumulator)
                        total_entries += len(accumulator)
                        accumulator.clear()
                        pending_count = 0
            if accumulator:
                chunked_count += self._flush(new_cache, accumulator)
                total_entries += len(accumulator)
                accumulator.clear()
        except Exception:  # pylint: disable=broad-except
            log.warning(
                "mmap_trie_index: rebuild loop failed mid-stream for bank=%r",
                bank,
                exc_info=True,
            )
            # Abort: close and delete temp files; leave live state alone.
            try:
                new_cache.close()
            except Exception:  # pylint: disable=broad-except
                pass
            abort_cleanup = [new_index_path, new_roster_path, new_heap_path]
            abort_cleanup.extend(self._list_new_heap_segments(new_heap_path))
            for p in abort_cleanup:
                try:
                    if os.path.exists(p):
                        os.remove(p)
                except OSError:
                    pass
            return

        try:
            new_cache.close()
        except Exception:  # pylint: disable=broad-except
            pass

        # Atomic swap: heap segments (all of them!) -> roster -> index.
        # ``os.replace`` is atomic on POSIX; the index file is swapped
        # last so an observer that races in during the swap sees the
        # pre-rebuild index + its matching pre-rebuild heap, never a
        # new index pointing into a deleted heap. The generation tag
        # in the meta file is updated last of all, so partial swaps
        # don't look "current" to the next reader -- they trigger a
        # full rebuild.
        #
        # Heap segments: ``MmapCache`` rolls heap data to additional
        # files once segment 0 exceeds ``max_segment_bytes`` (1 GiB by
        # default). The swap MUST cover every rolled segment: an
        # operator with >1 GiB of trie-heap data would otherwise find
        # the index's segment-N offsets pointing at a freshly renamed
        # segment 0 that doesn't contain them.
        live_heap_path = self._index_path + ".heap"
        new_segments = self._list_new_heap_segments(new_heap_path, include_base=True)
        # Validate the segment numbering: segments must be contiguous
        # starting at 0 (seg 0 == new_heap_path, seg N == .new.heap.N).
        # A gap indicates a torn build; refuse to swap.
        expected_ids = list(range(len(new_segments)))
        if [seg_id for seg_id, _ in new_segments] != expected_ids:
            observed = [seg_id for seg_id, _ in new_segments]
            log.error(
                "mmap_trie_index: rebuild for bank=%r produced non-contiguous "
                "heap segments %r; refusing swap to avoid a torn trie",
                bank,
                observed,
            )
            for _seg_id, p in new_segments:
                try:
                    if os.path.exists(p):
                        os.remove(p)
                except OSError:
                    pass
            for p in (new_roster_path, new_index_path):
                try:
                    if os.path.exists(p):
                        os.remove(p)
                except OSError:
                    pass
            return

        # Discover the full set of live segments too, so we can prune
        # any that the new build no longer uses (e.g. cardinality cap
        # shrank the data to fit in segment 0).
        old_segment_ids = self._list_live_heap_segment_ids(live_heap_path)

        swap_pairs = []
        for seg_id, src in new_segments:
            if seg_id == 0:
                dst = live_heap_path
            else:
                dst = f"{live_heap_path}.{seg_id}"
            swap_pairs.append((src, dst))
        if os.path.exists(new_roster_path):
            swap_pairs.append((new_roster_path, self._index_path + ".roster"))
        if os.path.exists(new_index_path):
            swap_pairs.append((new_index_path, self._index_path))

        # Close any live reader we hold so the inode swap is visible.
        self._reset_mmap()
        try:
            for src, dst in swap_pairs:
                os.replace(src, dst)
        except OSError as exc:
            log.warning(
                "mmap_trie_index: failed atomic swap for bank=%r (%s); "
                "trie may be inconsistent until next successful rebuild",
                bank,
                exc,
            )
            # Clean up any left-over temp files.
            for src, _dst in swap_pairs:
                try:
                    if os.path.exists(src):
                        os.remove(src)
                except OSError:
                    pass
            return

        # Prune stale live heap segments whose offset range is no
        # longer referenced by the swapped-in index. This handles the
        # rare case where a cardinality cap shrank the heap enough that
        # the new build emitted fewer segments than the previous one;
        # leaving them in place would waste disk and -- worse -- let a
        # future ``MmapCache._discover_segments`` reattach them if the
        # inode numbering lined up suspiciously.
        max_new_seg_id = new_segments[-1][0] if new_segments else -1
        for seg_id in old_segment_ids:
            if seg_id <= max_new_seg_id:
                continue
            stale = f"{live_heap_path}.{seg_id}"
            try:
                if os.path.exists(stale):
                    os.remove(stale)
            except OSError:
                log.debug(
                    "mmap_trie_index: could not remove stale segment %s",
                    stale,
                    exc_info=True,
                )

        meta = {
            "generation": self._generation_tag(current_gen),
            "built_at_ns": time.time_ns(),
            "max_list_size": int(self.max_list_size),
            "batch_size": int(self.batch_size),
            "entries": int(total_entries),
            "rows": int(total_rows),
        }
        try:
            self._write_meta_atomic(meta)
            self._meta_cache = meta
        except OSError as exc:
            log.warning(
                "mmap_trie_index: failed to write meta for bank=%r: %s",
                bank,
                exc,
            )
            self._meta_cache = None

        log.info(
            "mmap_trie_index: rebuilt trie for bank=%r in %.3fs "
            "(rows=%d, entries=%d, chunked=%d)",
            bank,
            time.monotonic() - t0,
            total_rows,
            total_entries,
            chunked_count,
        )

    def _flush(self, dest_cache, accumulator):
        """
        Merge every key in *accumulator* into *dest_cache* via
        ``put_many`` (one flock + batched fsync).

        **Merge semantics**: the streaming builder flushes periodically
        to stay inside its memory budget, so the same ``(path, value)``
        key may already have a partial list stored from an earlier
        flush within the same rebuild. Per-key behaviour:

        * No existing entry: write a plain msgpack list if the new
          bucket fits in ``max_list_size``; otherwise write it as a
          chunked bucket (``N`` chunk entries + one chunk-marker on
          the natural key).
        * Existing ``list``: extend in-memory, then write back as a
          plain list -- unless the merged size exceeds
          ``max_list_size``, in which case the bucket is *promoted* to
          chunked storage (all existing + new entries redistributed
          into chunks and the marker written over the natural key).
        * Existing ``chunks``: we only touch the LAST chunk. If it has
          free space, append until full; roll over to a new chunk once
          full; repeat until all new entries land. Earlier chunks are
          immutable across the rebuild, which is what makes cumulative
          merge cost O(M) linear instead of O(M^2 / batch_size).
        * Existing ``cap`` (legacy sentinel): treated as "needs
          rebuild", replaced in-place by the new bucket. We land the
          new entries as if the slot were empty; a follow-up flush in
          the same rebuild will see the new list / chunks naturally.

        Returns the count of buckets that newly became chunked during
        this flush (purely for logging; not required for correctness).
        """
        if not accumulator:
            return 0
        items = []
        newly_chunked = 0
        max_list = self.max_list_size
        for key, bucket in accumulator.items():
            existing_raw = None
            try:
                existing_raw = dest_cache.get(key)
            except Exception:  # pylint: disable=broad-except
                existing_raw = None
            kind = "none"
            obj = None
            if existing_raw is not None and existing_raw is not True:
                decoded = _unpack_entry(existing_raw)
                if decoded is not None:
                    kind, obj = decoded
                else:
                    kind = "none"

            new_list = list(bucket)

            if kind == "chunks":
                # Append to an existing chunked bucket by mutating only
                # the last chunk. Collect per-key writes; the final
                # ``put_many`` below batches them with everything else.
                n_chunks = int(obj.get("_chunks", 0) or 0)
                total = int(obj.get("_total", 0) or 0)
                if n_chunks <= 0:
                    # Marker claimed no chunks -- treat as fresh.
                    chunk_items, n_chunks, total, promoted = _chunk_write_fresh(
                        key, new_list, max_list
                    )
                    items.extend(chunk_items)
                    if promoted:
                        newly_chunked += 1
                    continue
                # Read the last chunk (the only one we might mutate).
                last_idx = n_chunks - 1
                last_chunk_key = _chunk_key(key, last_idx)
                last_chunk = []
                try:
                    raw_chunk = dest_cache.get(last_chunk_key)
                except Exception:  # pylint: disable=broad-except
                    raw_chunk = None
                if raw_chunk is not None and raw_chunk is not True:
                    decoded_chunk = _unpack_entry(raw_chunk)
                    if decoded_chunk is not None and decoded_chunk[0] == "list":
                        last_chunk = list(decoded_chunk[1])
                # Drain the new entries into the last chunk, rolling
                # over as it fills.
                for sr_key in new_list:
                    if len(last_chunk) < max_list:
                        last_chunk.append(sr_key)
                    else:
                        # Seal the current last chunk, start a new one.
                        items.append((last_chunk_key, _pack_list(last_chunk)))
                        n_chunks += 1
                        last_idx = n_chunks - 1
                        last_chunk_key = _chunk_key(key, last_idx)
                        last_chunk = [sr_key]
                    total += 1
                # Always write the final last chunk and an updated marker.
                items.append((last_chunk_key, _pack_list(last_chunk)))
                items.append((key, _pack_chunk_marker(n_chunks, total)))
                continue

            if kind == "list":
                merged = list(obj) + new_list
                if len(merged) > max_list:
                    chunk_items, _n, _t, _promoted = _chunk_write_fresh(
                        key, merged, max_list
                    )
                    items.extend(chunk_items)
                    newly_chunked += 1
                else:
                    items.append((key, _pack_list(merged)))
                continue

            # kind in ("none", "cap") -- treat the slot as empty. For
            # the legacy ``cap`` case this discards the sentinel and
            # replaces it with freshly-written data (the stored sr_keys
            # were already lost; we rebuild from scratch).
            chunk_items, _n, _t, promoted = _chunk_write_fresh(key, new_list, max_list)
            items.extend(chunk_items)
            if promoted:
                newly_chunked += 1

        if not items:
            return newly_chunked
        try:
            dest_cache.put_many(items)
        except Exception:  # pylint: disable=broad-except
            log.warning(
                "mmap_trie_index: put_many failed during flush "
                "(%d items); entries may be missing until next rebuild",
                len(items),
                exc_info=True,
            )
        return newly_chunked

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------

    def _get_entry(self, key_bytes):
        """
        Fetch a raw trie entry and decode it.

        Returns the decoded ``(kind, obj)`` tuple (see
        :func:`_unpack_entry`), or ``None`` if the key is absent or
        unreadable.
        """
        mm = self._get_mmap()
        if mm is None:
            return None
        try:
            raw = mm.get(key_bytes)
        except Exception:  # pylint: disable=broad-except
            log.debug("mmap_trie_index: get(%r) failed", key_bytes, exc_info=True)
            return None
        if raw is None or raw is True:
            # ``raw is True`` means a presence-only entry; we never
            # write those, so treat as missing.
            return None
        return _unpack_entry(raw)

    def lookup_literal(self, path_segments, value):
        """
        Return the sr_key list for an exact ``(path, value)`` match.

        Return value semantics mirror the mission spec:

        * ``list`` (possibly empty) -- the trie served the predicate.
        * ``None`` -- the entry is a legacy cap sentinel (stored data
          was lost) or references orphaned chunks, and the caller must
          fall back to the slow path for this partition.

        A missing key returns an empty list (``[]``) -- the trie knows
        the key does not exist, so no fall-back is required.

        For a chunked bucket the sr_key lists from each chunk are
        concatenated in insertion order (chunk 0 first). Duplicate
        suppression is NOT performed here: within a single rebuild the
        builder guarantees no cross-chunk duplicates, and callers of
        :func:`dispatch_predicate` already deduplicate across partitions.
        """
        path_bytes = _encode_path_segments(path_segments)
        value_bytes = _encode_scalar_value(value)
        key_bytes = _build_key(path_bytes, value_bytes)
        entry = self._get_entry(key_bytes)
        if entry is None:
            return []
        kind, obj = entry
        if kind == "cap":
            # Legacy sentinel left over from an older build: data was
            # thrown away. Signal fall-back; next rebuild will chunk it.
            log.debug(
                "mmap_trie_index: legacy cap sentinel at key=%r; "
                "triggering slow-path fallback until next rebuild",
                key_bytes,
            )
            return None
        if kind == "chunks":
            return self._read_chunks(key_bytes, obj)
        return list(obj)

    def _read_chunks(self, key_bytes, marker):
        """
        Materialise a chunked bucket by reading every chunk entry and
        concatenating their sr_key lists.

        Returns ``None`` when a chunk entry is missing or carries an
        unexpected shape (an orphaned marker / corrupt chunk). Logs a
        WARNING so operators can catch chronic issues; the caller then
        falls through to the slow path.
        """
        mm = self._get_mmap()
        if mm is None:
            return None
        try:
            n_chunks = int(marker.get("_chunks", 0) or 0)
        except (TypeError, ValueError):
            n_chunks = 0
        if n_chunks <= 0:
            # Marker with zero chunks -- treat as an empty bucket.
            return []
        out = []
        for i in range(n_chunks):
            chunk_key = _chunk_key(key_bytes, i)
            try:
                raw = mm.get(chunk_key)
            except Exception:  # pylint: disable=broad-except
                log.warning(
                    "mmap_trie_index: get of chunk %d for key=%r raised; "
                    "treating bucket as unavailable",
                    i,
                    key_bytes,
                    exc_info=True,
                )
                return None
            if raw is None or raw is True:
                log.warning(
                    "mmap_trie_index: orphaned chunk marker at key=%r "
                    "(chunk %d/%d missing); falling back to slow path",
                    key_bytes,
                    i,
                    n_chunks,
                )
                return None
            decoded = _unpack_entry(raw)
            if decoded is None or decoded[0] != "list":
                log.warning(
                    "mmap_trie_index: chunk %d of key=%r has unexpected "
                    "shape (kind=%r); falling back to slow path",
                    i,
                    key_bytes,
                    None if decoded is None else decoded[0],
                )
                return None
            out.extend(decoded[1])
        return out

    def values_for_path(self, path_segments):
        """
        Return every scalar value observed under *path_segments* across
        all SRs.

        Walks the mmap roster and filters by the exact path prefix
        (``<path>\\x00``). Yields decoded ``value_bytes`` as UTF-8
        strings. Non-UTF-8 values pass through as the raw bytes; the
        caller is expected to accept either.

        This is the glob / regex support path -- the caller walks the
        returned set and applies ``fnmatch`` / ``re.search`` per value,
        then calls :meth:`lookup_literal` per match.
        """
        mm = self._get_mmap()
        if mm is None:
            return []
        path_bytes = _encode_path_segments(path_segments)
        wanted_prefix = path_bytes + _PATH_VALUE_SEP
        prefix_len = len(wanted_prefix)
        out = []
        seen = set()
        try:
            keys = mm.list_keys() or []
        except Exception:  # pylint: disable=broad-except
            log.debug(
                "mmap_trie_index: list_keys failed in values_for_path", exc_info=True
            )
            return []
        for k in keys:
            if isinstance(k, str):
                kb = k.encode("utf-8", errors="replace")
            else:
                kb = bytes(k)
            if not kb.startswith(wanted_prefix):
                continue
            value_bytes = kb[prefix_len:]
            # Skip chunk sub-keys: a chunked bucket stores entries
            # under ``<natural_key>\x1d<uint32-le>``. The natural key
            # (which is also present on disk, carrying the chunk
            # marker) will still be emitted by the plain prefix match
            # below, so there is no information loss from skipping the
            # chunk-key sub-entries here.
            if _CHUNK_SEP in value_bytes:
                continue
            try:
                value_str = value_bytes.decode("utf-8")
            except UnicodeDecodeError:
                value_str = value_bytes
            if value_str in seen:
                continue
            seen.add(value_str)
            out.append(value_str)
        return out

    def close(self):
        """Release resources. Safe to call repeatedly."""
        self._reset_mmap()


# --------------------------------------------------------------------
# Module-level registry
# --------------------------------------------------------------------

_registry_lock = threading.RLock()
_registry: dict = {}


def for_bank(cache, bank, opts):
    """
    Return the :class:`MmapTrieIndex` for ``(cache.cachedir, bank)``,
    creating it on first use.

    ``opts`` supplies the tuning knobs:

    * ``grain_trie_max_list_size`` -- default 100000
    * ``grain_trie_build_batch_size`` -- default 1024
    * ``grain_trie_mmap_size`` -- MmapCache slot count, default 2000000
    * ``grain_trie_mmap_max_segment_bytes`` -- per-segment heap cap
      forwarded to :class:`MmapCache`; ``None`` / absent inherits the
      1 GiB default.

    When the cache driver does not expose ``cachedir`` (some test
    fakes) the function returns ``None`` -- the caller falls back to
    the slow path.
    """
    cachedir = getattr(cache, "cachedir", None)
    if not cachedir:
        return None
    max_list = int(opts.get("grain_trie_max_list_size", DEFAULT_MAX_LIST_SIZE) or 0)
    if max_list <= 0:
        max_list = DEFAULT_MAX_LIST_SIZE
    batch = int(opts.get("grain_trie_build_batch_size", DEFAULT_BATCH_SIZE) or 0)
    if batch <= 0:
        batch = DEFAULT_BATCH_SIZE
    # ``grain_trie_mmap_size`` sets the MmapCache slot count. Each slot
    # is ``slot_size`` bytes (default 160) so the sparse index file is
    # ``mmap_size * slot_size`` bytes. Tests shrink this to avoid
    # allocating a 320 MiB sparse file per tmp bank -- a fleet of them
    # on tmpfs-backed CI runners fills ``/tmp`` and silently drops
    # writes.
    mmap_size_raw = opts.get("grain_trie_mmap_size")
    try:
        mmap_size = int(mmap_size_raw) if mmap_size_raw else None
    except (TypeError, ValueError):
        mmap_size = None
    if mmap_size is not None and mmap_size <= 0:
        mmap_size = None
    # ``grain_trie_mmap_max_segment_bytes`` lets the operator tune (or,
    # in tests, shrink) the per-segment heap cap passed to
    # :class:`MmapCache`. ``None`` / absent means "inherit the mmap
    # default" (1 GiB).
    max_seg_raw = opts.get("grain_trie_mmap_max_segment_bytes")
    try:
        max_seg = int(max_seg_raw) if max_seg_raw else None
    except (TypeError, ValueError):
        max_seg = None
    if max_seg is not None and max_seg <= 0:
        max_seg = None
    reg_key = (cachedir, bank)
    with _registry_lock:
        entry = _registry.get(reg_key)
        if entry is not None:
            # If the operator tuned the knobs, honour the new values
            # on an existing instance (max_list_size + batch_size only
            # affect future rebuilds).
            entry.max_list_size = max_list
            entry.batch_size = batch
            entry.max_segment_bytes = max_seg
            return entry
        kwargs = {
            "cachedir": cachedir,
            "bank": bank,
            "max_list_size": max_list,
            "batch_size": batch,
            "max_segment_bytes": max_seg,
        }
        if mmap_size is not None:
            kwargs["mmap_size"] = mmap_size
        idx = MmapTrieIndex(**kwargs)
        _registry[reg_key] = idx
        return idx


def invalidate(cachedir=None, bank=None):
    """
    Drop registry entries. With no arguments drops every tracked bank.
    """
    with _registry_lock:
        if cachedir is None and bank is None:
            for idx in list(_registry.values()):
                with contextlib.suppress(Exception):
                    idx.close()
            _registry.clear()
            return
        reg_key = (cachedir or "", bank)
        entry = _registry.pop(reg_key, None)
        if entry is not None:
            with contextlib.suppress(Exception):
                entry.close()


# --------------------------------------------------------------------
# Dispatch helper used by salt.utils.minions
# --------------------------------------------------------------------


def dispatch_predicate(cache, bank, opts, expr, delimiter, regex_match):
    """
    Attempt to answer a grain-target predicate from the mmap trie.

    Returns one of:

    * ``list`` (possibly empty) -- UNION of sr_keys that match every
      valid ``(path, value)`` partition of ``expr``. Caller should
      consume this and short-circuit without the slow path. Wide
      buckets (``> max_list_size``) are transparently reconstituted by
      reading chunk entries off disk, so a single trie partition can
      now return millions of sr_keys without triggering fall-back.
    * ``None`` -- the trie could not serve the predicate: e.g. the
      index is unavailable, the opts switch is off, a partition hit a
      *legacy* cap sentinel (data was lost in an older build and the
      trie is out-of-date), the chunk marker was orphaned, or the
      predicate shape didn't yield any valid partition. Caller must
      fall through.

    Legacy cap sentinel back-compat: a Mission-4-era on-disk trie may
    still contain ``{"_capped": True, ...}`` entries. Hitting one
    returns ``None`` -- the next successful rebuild will re-materialise
    the bucket as chunked and the slow-path fallback will not fire
    again for that key.
    """
    if not opts.get("enable_grain_trie_index"):
        return None
    if not isinstance(expr, str) or delimiter not in expr:
        return None
    idx = for_bank(cache, bank, opts)
    if idx is None:
        return None
    if not idx.ensure_current(cache, bank):
        return None

    out = []
    seen = set()
    any_partition_served = False

    for path_segments, value_str in _split_predicate(expr, delimiter):
        if regex_match:
            served, hits = _serve_regex_partition(idx, path_segments, value_str)
        elif _is_literal_pattern(value_str):
            served, hits = _serve_literal_partition(idx, path_segments, value_str)
        else:
            served, hits = _serve_glob_partition(idx, path_segments, value_str)
        if not served:
            # Cap or lookup failure -- fall back entirely.
            log.debug(
                "mmap_trie_index: partition path=%r value=%r could not be "
                "served (cap hit); falling back to slow path",
                path_segments,
                value_str,
            )
            return None
        any_partition_served = True
        for sr_key in hits:
            if sr_key not in seen:
                out.append(sr_key)
                seen.add(sr_key)

    # No valid partition at all -> predicate wasn't shaped like
    # ``<key>:<value>``; caller must use the slow path.
    if not any_partition_served:
        return None
    return out


def _is_literal_pattern(value):
    """``True`` iff value has no fnmatch wildcards."""
    if not isinstance(value, str) or not value:
        return False
    return not any(c in value for c in ("*", "?", "["))


def _serve_literal_partition(idx, path_segments, value_str):
    """
    Return ``(served, hits)`` for a literal-value partition.

    ``served = False`` means the trie could not materialise the
    bucket (legacy cap sentinel or orphaned chunk marker) and the
    caller must bail. ``served = True`` with an empty ``hits`` is a
    definitive "no match" and the caller can continue to the next
    partition.
    """
    hits = idx.lookup_literal(path_segments, value_str)
    if hits is None:
        return False, []
    return True, hits


def _serve_glob_partition(idx, path_segments, pattern):
    """Return ``(served, hits)`` for a glob (fnmatch) value partition."""
    try:
        values = idx.values_for_path(path_segments)
    except Exception:  # pylint: disable=broad-except
        log.debug(
            "mmap_trie_index: values_for_path failed for glob partition",
            exc_info=True,
        )
        return False, []
    hits = []
    seen = set()
    for value in values:
        if not isinstance(value, str):
            continue
        if not fnmatch.fnmatchcase(value, pattern):
            continue
        sr_keys = idx.lookup_literal(path_segments, value)
        if sr_keys is None:
            # Individual value's bucket is unavailable (legacy cap
            # sentinel or orphaned chunks) -- bail the whole partition.
            # A correct answer would need to see those excluded sr_keys
            # too.
            return False, []
        for sr_key in sr_keys:
            if sr_key not in seen:
                hits.append(sr_key)
                seen.add(sr_key)
    return True, hits


def _serve_regex_partition(idx, path_segments, pattern):
    """Return ``(served, hits)`` for a PCRE value partition."""
    try:
        rx = re.compile(pattern)
    except re.error:
        # Unparseable regex -- caller's slow path will hit the same
        # error, but returning (False, []) keeps our behaviour
        # consistent with "could not serve, fall back".
        return False, []
    try:
        values = idx.values_for_path(path_segments)
    except Exception:  # pylint: disable=broad-except
        log.debug(
            "mmap_trie_index: values_for_path failed for regex partition",
            exc_info=True,
        )
        return False, []
    hits = []
    seen = set()
    for value in values:
        if not isinstance(value, str):
            continue
        if not rx.search(value):
            continue
        sr_keys = idx.lookup_literal(path_segments, value)
        if sr_keys is None:
            return False, []
        for sr_key in sr_keys:
            if sr_key not in seen:
                hits.append(sr_key)
                seen.add(sr_key)
    return True, hits
