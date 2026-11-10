"""
Persistent mmap-backed grain trie index for resource-registry
grain-target queries.

This module is the Mission 4 successor to
:mod:`salt.utils.grain_reverse_index`. Where the reverse index covers
operator-declared top-level grain keys from an in-process dict (RAM
scales with inventory size), the trie index persists an exhaustive
``(path_tuple, scalar_value) -> [sr_key, ...]`` mapping on disk using
:class:`salt.utils.mmap_cache.MmapCache`, so:

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
  resource-grain dispatch falls back to Mission 3's reverse-value
  index (and ultimately the legacy slow path).
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
    value = _pack_list([sr_key_1, sr_key_2, ...])

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

Leaf-list binary format
-----------------------
sr_key lists use a compact length-prefixed binary record instead of
msgpack because the Mission 4 live profile showed msgpack decode
dominates wide-match latency (~78 s for a 600K-element list). The
format is::

    byte 0        : 0xC1   (magic -- msgpack reserves this byte as
                            "never used", so it is unambiguous with
                            any valid msgpack message. Decoding the
                            cap sentinel still works because that
                            sentinel is a msgpack MAP whose first
                            byte is in the 0x80-0x8F or 0xDE/0xDF
                            range, never 0xC1.)
    byte 1..4     : uint32 LE  count of sr_keys
    byte 5..      : repeated for count:
                      uint16 LE  key length
                      <key bytes>  (UTF-8)

Decode is a tight ``struct.unpack_from`` loop with no per-element
Python object overhead -- 2-10x faster than msgpack on large lists.

High-cardinality cap
--------------------
If a single ``(path, value)`` would accumulate more than
``opts["grain_trie_max_list_size"]`` sr_keys, we store a cap sentinel::

    msgpack.packb({"_capped": True, "count": <total-observed>})

Queries that hit a cap return ``None`` to signal "fall through to the
slow path for this specific entry" -- the caller continues probing
other partitions and, if no other path serves the predicate, resumes
the legacy fetch loop.

Cap-vs-list unambiguous because the cap sentinel is a msgpack MAP
(leading byte 0x80-0x8F or 0xDE/0xDF) while the sr_key list leads
with 0xC1 (msgpack's reserved "never used" byte).

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
import struct
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

# Leaf-list binary format. 0xC1 is reserved by msgpack as "never used"
# so it is unambiguous with any valid msgpack message -- in particular
# the cap sentinel (a msgpack MAP, leading byte 0x80-0x8F or 0xDE/0xDF).
# See the module docstring "Leaf-list binary format" for the wire
# layout; _pack_list / _unpack_list below are the only producers /
# consumers.
_LIST_MAGIC = b"\xc1"
_U32 = struct.Struct("<I")
_U16 = struct.Struct("<H")
_MAX_KEY_LEN = 0xFFFF  # uint16 limit per sr_key encoded length

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
    """
    Serialise an sr_key list in the compact length-prefixed binary
    format documented in the module docstring.

    Raises ``ValueError`` if any key's UTF-8 encoding exceeds the
    uint16 length field (65535 bytes). SR keys in practice are tens
    of bytes; exceeding the limit indicates a programming error at
    the caller, not a data concern.
    """
    parts = [_LIST_MAGIC, _U32.pack(len(sr_keys))]
    for key in sr_keys:
        if isinstance(key, str):
            kb = key.encode("utf-8")
        elif isinstance(key, (bytes, bytearray)):
            kb = bytes(key)
        else:
            kb = str(key).encode("utf-8")
        if len(kb) > _MAX_KEY_LEN:
            raise ValueError(
                f"mmap_trie_index: sr_key length {len(kb)} exceeds uint16 "
                f"limit ({_MAX_KEY_LEN}); refusing to pack"
            )
        parts.append(_U16.pack(len(kb)))
        parts.append(kb)
    return b"".join(parts)


def _unpack_list(raw):
    """
    Decode a leaf-list from the length-prefixed binary format.

    Caller has already validated ``raw[0:1] == _LIST_MAGIC`` before
    dispatching here. Returns a ``list[str]``; an empty-list record
    (count=0) is handled cleanly with no further reads.
    """
    count = _U32.unpack_from(raw, 1)[0]
    keys = [None] * count
    offset = 5
    for i in range(count):
        length = _U16.unpack_from(raw, offset)[0]
        offset += 2
        keys[i] = raw[offset : offset + length].decode("utf-8")
        offset += length
    return keys


def _pack_cap(count):
    """Serialise the cap sentinel to msgpack bytes."""
    return msgpack.packb({"_capped": True, "count": int(count)}, use_bin_type=True)


def _unpack_entry(raw):
    """
    Decode a trie entry value.

    Dispatch is on the first byte:

    * ``0xC1`` -> our length-prefixed binary leaf-list format
      (see :func:`_unpack_list`).
    * anything else -> msgpack (currently only the cap sentinel,
      a msgpack MAP).

    Returns one of:

    * ``("list", [sr_key, ...])`` for a regular hit.
    * ``("cap", {"_capped": True, "count": N})`` for a cap sentinel.
    * ``None`` when the bytes cannot be decoded.
    """
    if raw is None:
        return None
    if isinstance(raw, str):
        raw = raw.encode("utf-8", errors="replace")
    if not isinstance(raw, (bytes, bytearray)):
        return None
    if not raw:
        return ("list", [])
    buf = bytes(raw)
    if buf[0:1] == _LIST_MAGIC:
        try:
            return ("list", _unpack_list(buf))
        except Exception:  # pylint: disable=broad-except
            log.debug(
                "mmap_trie_index: undecodable binary leaf-list (%d bytes)",
                len(buf),
                exc_info=True,
            )
            return None
    try:
        obj = msgpack.unpackb(buf, raw=False)
    except Exception:  # pylint: disable=broad-except
        log.debug("mmap_trie_index: undecodable entry (%d bytes)", len(buf))
        return None
    if isinstance(obj, dict) and obj.get("_capped"):
        return ("cap", obj)
    # Legacy msgpack-list entries from pre-0xC1 builds: still accept
    # them on read so a rolling upgrade sees no decode regressions.
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
        # ``capped_count`` is a cheap counter exposed in the meta file;
        # no per-key dict is kept in process memory. Caps are detected
        # at flush time by comparing ``len(existing_bucket) +
        # len(new_sr_keys)`` against ``max_list_size`` -- the mmap
        # entry is the source of truth, so the builder no longer needs
        # an O(unique-keys) observed-counts dict (which for a 10M-key
        # fleet would consume ~780 MB of in-process RAM).
        capped_count = 0
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
                        capped_count += self._flush(new_cache, accumulator)
                        total_entries += len(accumulator)
                        accumulator.clear()
                        pending_count = 0
            if accumulator:
                capped_count += self._flush(new_cache, accumulator)
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
            "(rows=%d, entries=%d, capped=%d)",
            bank,
            time.monotonic() - t0,
            total_rows,
            total_entries,
            capped_count,
        )

    def _flush(self, dest_cache, accumulator):
        """
        Merge every key in *accumulator* into *dest_cache* via
        ``put_many`` (one flock + batched fsync).

        **Merge semantics**: the streaming builder flushes
        periodically to stay inside its memory budget, so the same
        ``(path, value)`` key may already have a partial list stored
        from an earlier flush within the same rebuild. For each
        accumulator key we read the existing stored value first and
        extend before re-writing. Cap sentinels, once written, are
        never demoted back to a list.

        **Cap detection at flush time**: the length of the existing
        mmap bucket is already cheap to read here; checking
        ``len(existing) + len(new) > max_list_size`` lets the builder
        avoid the per-key ``observed_counts`` dict that would otherwise
        grow to O(unique-keys) in-process RAM.

        Returns the count of buckets that newly crossed the cap during
        this flush (purely for logging; not required for correctness).
        """
        if not accumulator:
            return 0
        items = []
        newly_capped = 0
        max_list = self.max_list_size
        for key, bucket in accumulator.items():
            existing_raw = None
            try:
                existing_raw = dest_cache.get(key)
            except Exception:  # pylint: disable=broad-except
                existing_raw = None
            existing_list = []
            if existing_raw is not None and existing_raw is not True:
                decoded = _unpack_entry(existing_raw)
                if decoded is not None:
                    kind, obj = decoded
                    if kind == "cap":
                        # Already capped; drop the new entries silently
                        # -- the sentinel's exact count is best-effort.
                        # Keep the existing sentinel in place (do not
                        # re-write).
                        continue
                    if kind == "list":
                        existing_list = list(obj)
            total = len(existing_list) + len(bucket)
            if total > max_list:
                items.append((key, _pack_cap(total)))
                newly_capped += 1
                continue
            # Prepend prior entries so order reflects insertion order
            # within the build.
            merged = existing_list + list(bucket)
            items.append((key, _pack_list(merged)))
        if not items:
            return newly_capped
        try:
            dest_cache.put_many(items)
        except Exception:  # pylint: disable=broad-except
            log.warning(
                "mmap_trie_index: put_many failed during flush "
                "(%d items); entries may be missing until next rebuild",
                len(items),
                exc_info=True,
            )
        return newly_capped

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
        * ``None`` -- the entry is CAPPED and the caller must fall
          back to the slow path for this partition.

        A missing key returns an empty list (``[]``) -- the trie knows
        the key does not exist, so no fall-back is required.
        """
        path_bytes = _encode_path_segments(path_segments)
        value_bytes = _encode_scalar_value(value)
        entry = self._get_entry(_build_key(path_bytes, value_bytes))
        if entry is None:
            return []
        kind, obj = entry
        if kind == "cap":
            return None
        return list(obj)

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
        idx = MmapTrieIndex(
            cachedir=cachedir,
            bank=bank,
            max_list_size=max_list,
            batch_size=batch,
            max_segment_bytes=max_seg,
        )
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
      consume this and short-circuit without the slow path.
    * ``None`` -- the trie could not serve the predicate: e.g. the
      index is unavailable, the opts switch is off, a partition hit a
      cap sentinel, or the predicate shape didn't yield any valid
      partition. Caller must fall through.

    The ``None`` return intentionally covers "cap hit" too: a correct
    operator response requires the slow path to re-scan those SRs. We
    conservatively return ``None`` as soon as ANY partition hits a
    cap, because mixing partial trie results with a slow-path scan
    would risk double-counting or missing SRs that the cap-covered
    partition did not get to record.
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

    ``served = False`` means the entry is CAPPED and the caller must
    bail. ``served = True`` with an empty ``hits`` is a definitive
    "no match" and the caller can continue to the next partition.
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
            # Individual value's bucket is capped -- bail the whole
            # partition. A correct answer would need to see those
            # excluded sr_keys too.
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
