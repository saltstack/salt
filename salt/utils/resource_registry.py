"""
Resource Registry — mmap-backed system of record for Salt Resources.

The registry is the master-side authority for which minions manage which
resources. It powers the ``T@`` and ``M@`` targeting engines, the
``salt '*'`` wildcard augmentation, and any runner/API that needs to walk
the set of resources a minion owns.

Architecture (Strategy 1 of ``mmap-compaction-design.md`` §"Secondaries"):

* **Primary index** (``by_id``) is a :class:`~salt.utils.mmap_cache.MmapCache`
  file on disk keyed by composite SRN (``"type:id"``) with a small JSON
  payload (``{"m": <minion_id>, "t": <resource_type>}``). Reads and writes
  are O(1) linear-probing hash lookups; compaction uses sorted placement
  (``pack_sorted``) and completes in ~1 s for 1M entries.

* **Secondary indexes** (``by_type`` and ``by_minion``) are derived views.
  They live in-process only and are (re)materialised on first access after
  the primary file is observed to have been atomically swapped (inode
  change). Each master worker carries its own derived snapshot.

* **Read consistency during compaction**: master worker processes that
  handle ``_register_resources`` can all write (Salt's MWorker pool).
  Cross-process visibility is provided by two signals:

  - ``st_ino`` — changes on :meth:`_ResourceIndexStore.compact`'s atomic
    ``os.replace``. Triggers readers to close stale mmap handles.
  - ``st_mtime_ns`` — bumped by every ``put``/``delete`` via
    :meth:`MmapCache._touch_mtime`. Triggers readers to rebuild derived
    views from the (updated in place) primary mmap.

  Together they form the ``content_version`` tuple watched by
  :meth:`_ResourceIndexStore._current_version`. Readers with an open
  mmap keep pointing at the pre-swap inode until the next staleness
  check, so they never see a torn file.

Cache-bank layout (complementary to this on-disk mmap index) is documented in
``resources-registry-design.md`` and consists of three ``salt.cache`` banks
(``grains``, ``pillar``, ``resources``) keyed by bare resource ID.

The ``resource_grains`` cache bank
----------------------------------

Independent of the on-disk mmap registry above, the master also maintains a
``resource_grains`` :class:`salt.cache` bank (default driver: ``localfs``)
that backs grain-based targeting of resources (``salt -G``, ``salt -P``,
``salt -C 'G@…'``).

Schema:

* **Bank name**: ``"resource_grains"``.
* **Key**: composite SRN of the form ``"<resource_type>:<resource_id>"`` —
  same shape produced by :func:`resource_index_srn_key` and used by the
  primary mmap index. Composite keying lets two resources share a bare id
  across types without colliding (e.g. ``"dummy:web-01"`` and
  ``"ssh:web-01"`` are distinct entries).
* **Value**: the per-resource grain dict returned by
  ``resource_funcs[f"{type}.grains"]()`` on the managing minion — collected
  by :meth:`salt.minion.Minion._collect_resource_grains` and shipped to the
  master as part of the ``_register_resources`` payload.

Lifecycle:

* **Write**: master ``_register_resources`` handler stores entries on every
  registration (intra-process visibility immediate, cross-process via the
  filesystem-backed cache).
* **Flush**: when a minion re-registers with a smaller resource set, SRNs
  that disappear from the payload are flushed *only if* the registry shows
  they're no longer owned by anyone. Multi-minion safe by design.
* **Match**: :meth:`salt.utils.minions.CkMinions._augment_grain_match_with_resource_grains`
  walks the bank for every grain/grain-pcre check and appends matched bare
  resource ids to the response wait set.

Freshness: the bank is refreshed only when the minion calls
``_register_resources_with_master``. Triggers for that are minion start,
the ``resource_refresh`` event, and ``saltutil.refresh_pillar``. A
per-resource ``<type>.grains_refresh()`` invocation does **not**
auto-propagate to the master; the operator-level recipe is to fire
``resource_refresh`` on the minion event bus.
"""

import json
import logging
import os
import threading
import time

import salt.cache
import salt.utils.mmap_cache

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RESOURCE_BANK = "resources"

#: Cache bank holding per-resource grain dicts indexed by composite SRN
#: ``"<type>:<id>"``. Populated by the master's ``_register_resources``
#: handler from the load shipped by
#: :meth:`salt.minion.Minion._collect_resource_grains`. Consumed by
#: :meth:`salt.utils.minions.CkMinions._augment_grain_match_with_resource_grains`
#: to make ``salt -G ...`` / ``salt -P ...`` / ``salt -C 'G@...'`` match
#: resources alongside minions. See the module docstring for the full
#: lifecycle and freshness model.
RESOURCE_GRAINS_BANK = "resource_grains"

#: Filename (relative to the cache dir) of the primary ``by_id`` mmap file.
PRIMARY_INDEX_FILENAME = "resource_index.by_id.mmap"

#: Subdirectory under ``cachedir`` that holds the primary mmap file.
PRIMARY_INDEX_SUBDIR = "resources"

#: Slot count for the primary. 2^21 gives ~2M slots / 256 MiB file at the
#: default slot size, comfortably holding 1M live entries at α ≈ 0.48.
DEFAULT_PRIMARY_CAPACITY = 1 << 21

#: Slot size in bytes. Payload budget is ``slot_size - 1`` (status byte),
#: of which the composite key ``"type:id"`` and the JSON value share the
#: space separated by a ``\0`` byte.
DEFAULT_SLOT_SIZE = 128

#: Minimum interval between ``os.stat`` staleness checks on the primary
#: mmap file. Without throttling, every ``get()`` would trigger a syscall.
STALENESS_CHECK_INTERVAL = 0.25  # seconds

#: Soft budget for a full derived-index rebuild from a primary scan.
#: Logged as a warning if exceeded (not enforced).
DERIVED_REBUILD_BUDGET_SECONDS = 2.0

#: Default thresholds for automatic compaction — see :meth:`maybe_compact`.
DEFAULT_COMPACT_LOAD_FACTOR = 0.6  # (occupied + deleted) / total
DEFAULT_COMPACT_TOMBSTONE_RATIO = 0.2  # deleted / occupied

#: Minimum seconds between two automatic compaction attempts. ``get_stats``
#: requires a full scan of the mmap (O(num_slots)), so bounding the check
#: rate is a first-order performance concern on hot write paths.
DEFAULT_COMPACT_MIN_INTERVAL = 30.0

#: Persisted schema version for the in-cache fallback dict (legacy path).
RESOURCE_INDEX_SCHEMA_VERSION = 2


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def parse_srn(expression):
    """
    Parse a ``T@`` pattern into its ``type`` and ``id`` components.

    A full Salt Resource Name (SRN) has the form ``<type>:<id>``. A bare
    expression contains only a type with no colon.

    ``parse_srn("vcf_host")``          -> ``{"type": "vcf_host", "id": None}``
    ``parse_srn("vcf_host:esxi-01")``  -> ``{"type": "vcf_host", "id": "esxi-01"}``

    :param str expression: A bare resource type or a full SRN.
    :rtype: dict
    """
    if not expression or not isinstance(expression, str):
        return {"type": None, "id": None}
    rtype, sep, rid = expression.partition(":")
    if not sep:
        return {"type": rtype or None, "id": None}
    return {"type": rtype or None, "id": rid or None}


def resource_index_srn_key(resource_type, resource_id):
    """
    Canonical composite key (``"<type>:<id>"``) for the primary ``by_id`` index.

    Composite keys are required because bare resource IDs are not unique
    across types (see commit ``b95bafd7627``).

    :param str resource_type: Resource type (e.g. ``"ssh"``).
    :param str resource_id: Bare resource ID (e.g. ``"web-01"``).
    :rtype: str
    """
    return f"{resource_type}:{resource_id}"


def _encode_by_id_value(minion_id, resource_type):
    """
    Encode a primary-index value. Kept compact so ``key + \\0 + value``
    fits within ``DEFAULT_SLOT_SIZE - 1``.

    Layout today: JSON ``{"m": minion_id, "t": resource_type}``. Short keys
    ``m`` / ``t`` reduce payload size and leave headroom for future fields.
    """
    return json.dumps({"m": minion_id, "t": resource_type}, separators=(",", ":"))


def _decode_by_id_value(raw):
    """
    Decode a primary-index value into ``{"minion": <id>, "type": <type>}``.

    Accepts the value returned by :class:`~salt.utils.mmap_cache.MmapCache`
    (``str`` for kv entries, ``True`` for set-member entries, or ``None``).
    Returns ``None`` for malformed or empty values.
    """
    if raw is None or raw is True:
        return None
    if not isinstance(raw, str):
        return None
    try:
        doc = json.loads(raw)
    except (TypeError, ValueError):
        log.warning("resource_registry: malformed primary value %r", raw)
        return None
    if not isinstance(doc, dict):
        return None
    return {"minion": doc.get("m"), "type": doc.get("t")}


# ---------------------------------------------------------------------------
# Internal store: primary mmap + derived-view cache
# ---------------------------------------------------------------------------


class _ResourceIndexStore:
    """
    Mmap-backed primary plus in-process derived indexes.

    Exists as a single collaborator for :class:`ResourceRegistry`. Not a
    public API — callers should go through ``ResourceRegistry``.

    Lifecycle::

        store = _ResourceIndexStore(path, capacity, slot_size)
        store.put_many([(srn_key, minion_id, rtype), ...])
        blob = store.get(srn_key)
        rids = store.rids_by_type("vcf_host")
        resources = store.resources_by_minion("vcenter-1")
        store.compact()

    Derived indexes (``by_type``, ``by_minion``) are recomputed from a full
    scan of the primary whenever the primary's *content version* has changed
    since the last rebuild. ``content_version`` is ``(st_ino, st_mtime_ns)``
    — writers bump the file's ``mtime`` on every ``put``/``delete`` (see
    :meth:`MmapCache._touch_mtime`), so the signal catches both:

    * compactions (``os.replace`` -> new inode), and
    * in-place mutations from other worker processes (same inode, fresh mtime).

    Rebuilds are serialised under an internal lock so concurrent readers
    share the cost.
    """

    def __init__(
        self,
        path,
        capacity=DEFAULT_PRIMARY_CAPACITY,
        slot_size=DEFAULT_SLOT_SIZE,
    ):
        """
        :param str path: Absolute path for the primary mmap file.
        :param int capacity: Slot count (must be a power of two for best
            distribution given the Adler-32 probing).
        :param int slot_size: Per-slot byte width including the status byte.
        """
        self._path = path
        self._capacity = capacity
        self._slot_size = slot_size

        self._primary = salt.utils.mmap_cache.MmapCache(
            path,
            size=capacity,
            slot_size=slot_size,
            staleness_check_interval=STALENESS_CHECK_INTERVAL,
        )

        # Derived views, keyed by the primary content_version they were
        # built from (``(st_ino, st_mtime_ns)``). On version mismatch the
        # views are discarded and rebuilt.
        self._derived_lock = threading.Lock()
        self._derived_version = None
        self._by_type: dict = {}  # {rtype: [rid, ...]}
        self._by_minion: dict = {}  # {minion_id: {rtype: [rid, ...]}}

        # Throttled staleness check: remember the last time we stat()ed the
        # file and the version we saw, so hot read paths don't syscall per
        # operation. See :meth:`_current_version`.
        self._last_stat_time: float = 0.0
        self._last_version = None
        # Local-write generation counter. ``MmapCache`` mutations don't bump
        # the backing file's mtime (writes go through ``mmap.flush()`` which
        # is not guaranteed to update file metadata), so the ``stat()``-based
        # ``content_version`` alone misses intra-process writes. Bumping a
        # local counter on every ``put``/``delete`` and folding it into the
        # version tuple guarantees the next ``_ensure_derived_fresh`` call
        # rebuilds. Cross-process detection still rides on the file stat.
        self._write_generation: int = 0

    def close(self):
        """
        Release the primary mmap handle (tests and :func:`reset_registry`).
        """
        self._primary.close()

    # ------------------------------------------------------------------
    # Primary: point ops
    # ------------------------------------------------------------------

    def get(self, srn_key):
        """
        Return the decoded value dict for ``srn_key``, or ``None`` if absent.

        :param str srn_key: Composite key (``"<type>:<id>"``).
        :rtype: dict or None
        """
        raw = self._primary.get(srn_key, default=None)
        return _decode_by_id_value(raw)

    def put(self, srn_key, minion_id, resource_type):
        """
        Insert or update a single primary entry. O(1) amortised.

        Cross-process visibility: after the underlying ``MmapCache.put``
        flushes via ``mmap.flush()`` — which on Linux does **not** advance
        the backing file's ``st_mtime``/``st_size`` — we explicitly bump the
        file's mtime via :func:`os.utime`. Other master workers stat() the
        file on their throttled staleness check and rebuild their derived
        view when they see the new mtime.

        Same-process visibility: in addition to the mtime bump, we
        increment :py:attr:`_write_generation` and invalidate the
        throttled stat cache so the next :meth:`_current_version` call
        always returns a fresh tuple.

        :returns: ``True`` on success.
        """
        blob = _encode_by_id_value(minion_id, resource_type)
        ok = self._primary.put(srn_key, blob)
        if ok:
            self._invalidate_version_cache()
            self._touch_primary_mtime()
        return ok

    def delete(self, srn_key):
        """
        Mark a primary entry as DELETED (tombstone). Compaction reclaims
        the slot. O(1) amortised.
        """
        ok = self._primary.delete(srn_key)
        if ok:
            self._invalidate_version_cache()
            self._touch_primary_mtime()
        return ok

    def _touch_primary_mtime(self):
        """
        Force ``st_mtime_ns`` on the primary index to advance so other
        master workers' throttled ``stat()`` picks up our write.

        ``mmap.flush()`` (used by :class:`MmapCache` after every mutation)
        is implemented via ``msync`` on Linux and is not guaranteed to
        update the backing file's metadata; an explicit ``utime`` is the
        cheapest reliable cross-process change signal.
        """
        try:
            os.utime(self._path, None)
        except OSError:
            # File may not exist yet on the very first put if MmapCache
            # creates it lazily; the next put will succeed.
            pass

    def _invalidate_version_cache(self):
        """
        Force the next :meth:`_current_version` call to re-stat the file
        and produce a tuple distinct from any prior cached version.

        Called after this process writes so it sees its own writes
        immediately; other processes rely on the throttled stat cycle.
        """
        self._last_version = None
        self._last_stat_time = 0.0
        # Bump the local generation so even a stat() that returns identical
        # ``(st_ino, st_mtime_ns, st_size)`` produces a different version
        # tuple — needed because ``mmap.flush()`` doesn't always advance the
        # backing file's mtime.
        self._write_generation += 1

    # ------------------------------------------------------------------
    # Primary: bulk / write-path
    # ------------------------------------------------------------------

    def put_many(self, entries):
        """
        Insert many ``(srn_key, minion_id, resource_type)`` tuples.

        Used by :meth:`ResourceRegistry.register_minion` after it has diff'd
        the incoming resource set against the previous one for this minion.
        Each put acquires its own file lock; for very large inputs prefer
        :meth:`compact` feeding :meth:`~MmapCache.atomic_rebuild`.
        """
        ok = True
        for srn_key, minion_id, rtype in entries:
            if not self.put(srn_key, minion_id, rtype):
                ok = False
        return ok

    def delete_many(self, srn_keys):
        """
        Tombstone many primary entries. Idempotent: absent keys are
        silently ignored.
        """
        for k in srn_keys:
            self.delete(k)
        return True

    # ------------------------------------------------------------------
    # Compaction
    # ------------------------------------------------------------------

    def compact(self):
        """
        Rebuild the primary into a fresh index+heap pair via
        :meth:`MmapCache.atomic_rebuild`, then atomically swap.

        Readers with an existing mmap keep their pre-swap view until they
        next call a method that triggers a staleness check. New readers
        get the post-swap file directly.

        :returns: ``(occupied_before, occupied_after)`` for caller logging.
        """
        before = self._primary.get_stats().get("occupied", 0)
        # ``list_items`` is a full scan of OCCUPIED slots. It returns
        # ``[(key, value), ...]`` where ``value`` is the JSON blob (str)
        # or ``True`` for set-member entries. ``atomic_rebuild`` handles
        # both shapes via :func:`MmapCache._normalize_iterator`.
        items = self._primary.list_items()
        ok = self._primary.atomic_rebuild(items)
        if not ok:
            log.error("resource_registry: atomic_rebuild failed for %s", self._path)
            return before, before
        # The swap invalidates any cached derived view: both inode and
        # mtime change, so the next reader's ``_current_version`` will
        # pick it up. Proactively invalidate here too, to avoid a stale
        # hit until the throttled check fires.
        with self._derived_lock:
            self._derived_version = None
            self._last_version = None
        after = self._primary.get_stats().get("occupied", 0)
        return before, after

    # ------------------------------------------------------------------
    # Derived views (rebuilt from primary scan)
    # ------------------------------------------------------------------

    def rids_by_type(self, resource_type):
        """
        Return the list of resource IDs of ``resource_type`` across all
        minions.

        :rtype: list[str]
        """
        self._ensure_derived_fresh()
        return list(self._by_type.get(resource_type, ()))

    def resource_types(self):
        """
        Resource type names present in the derived primary view.

        :rtype: tuple[str, ...]
        """
        self._ensure_derived_fresh()
        return tuple(self._by_type.keys())

    def resources_by_minion(self, minion_id):
        """
        Return ``{resource_type: [resource_id, ...]}`` for one minion.

        :rtype: dict[str, list[str]]
        """
        self._ensure_derived_fresh()
        return {
            rt: list(rids) for rt, rids in self._by_minion.get(minion_id, {}).items()
        }

    def all_minions_by_type(self, resource_type):
        """
        Return the set of minion IDs managing at least one resource of
        ``resource_type``.

        :rtype: set[str]
        """
        self._ensure_derived_fresh()
        out = set()
        for mid, by_rtype in self._by_minion.items():
            if resource_type in by_rtype:
                out.add(mid)
        return out

    # ------------------------------------------------------------------
    # Staleness / derived-rebuild plumbing
    # ------------------------------------------------------------------

    def _current_version(self):
        """
        Return the current primary content version, stat()ing the file at
        most once per ``STALENESS_CHECK_INTERVAL`` to keep hot read paths
        cheap.

        ``content_version`` is ``(stat_tuple, write_generation)`` where
        ``stat_tuple`` is ``(st_ino, st_mtime_ns, st_size)`` — sensitive
        to atomic swaps (new inode) and most cross-process writes (new
        mtime/size). ``write_generation`` is bumped on every local
        ``put``/``delete``, covering the case where ``mmap.flush()`` does
        not advance the backing file's mtime within stat() resolution.

        ``stat_tuple`` is ``None`` until the file exists.
        """
        now = time.monotonic()
        if (
            self._last_version is not None
            and now - self._last_stat_time < STALENESS_CHECK_INTERVAL
        ):
            return self._last_version
        try:
            stat_tuple = self._primary._get_cache_id()
        except OSError:
            stat_tuple = None
        version = (stat_tuple, self._write_generation)
        self._last_version = version
        self._last_stat_time = now
        return version

    def _ensure_derived_fresh(self):
        """
        Rebuild the derived ``by_type`` / ``by_minion`` views if the primary
        has changed since the last rebuild.

        Freshness is driven by :meth:`_current_version`, which combines
        the file ``stat()`` tuple (cross-process detection: new inode on
        compaction, advancing mtime/size on most external writes) with a
        local write generation counter (intra-process detection that does
        not depend on ``mmap.flush()`` advancing file mtime).

        Uses double-checked locking so the common case is a single
        throttled stat() comparison.
        """
        current = self._current_version()
        if current == self._derived_version:
            return
        with self._derived_lock:
            if current == self._derived_version:
                return
            self._rebuild_derived(current)

    def _rebuild_derived(self, version):
        """
        Walk every OCCUPIED slot in the primary, decode the value, and
        rebuild the in-process derived dicts from scratch. O(N_slots).

        Callers must hold ``self._derived_lock``.
        """
        t0 = time.perf_counter()
        by_type: dict = {}
        by_minion: dict = {}

        # list_items() tolerates a missing file (returns []); perfect for
        # first use before any writes have happened.
        for srn_key, raw in self._primary.list_items():
            decoded = _decode_by_id_value(raw)
            if not decoded:
                continue
            mid = decoded.get("minion")
            rtype = decoded.get("type")
            if not mid or not rtype:
                continue
            # Trust the value's ``type`` field over the key split, but use
            # the key to recover ``rid`` (so a stale value with a mutated
            # ``t`` can't misplace entries in by_type).
            _rtype_from_key, _, rid = srn_key.partition(":")
            if not rid:
                continue
            by_type.setdefault(rtype, []).append(rid)
            by_minion.setdefault(mid, {}).setdefault(rtype, []).append(rid)

        self._by_type = by_type
        self._by_minion = by_minion
        self._derived_version = version
        elapsed = time.perf_counter() - t0
        if elapsed > DERIVED_REBUILD_BUDGET_SECONDS:
            log.warning(
                "resource_registry: derived-index rebuild took %.2fs "
                "(budget %.2fs, %d types, %d minions)",
                elapsed,
                DERIVED_REBUILD_BUDGET_SECONDS,
                len(by_type),
                len(by_minion),
            )
        else:
            log.debug(
                "resource_registry: derived-index rebuild %.3fs "
                "(%d types, %d minions, version=%s)",
                elapsed,
                len(by_type),
                len(by_minion),
                version,
            )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class ResourceRegistry:
    """
    Master-side interface to the Salt Resource Registry.

    Instantiate with the Salt opts dict; the class opens its own
    :class:`_ResourceIndexStore` on the master's cache directory. The
    backing mmap file is created on first write.

    All read methods are O(1) or O(k) where *k* is the size of the answer
    (e.g. number of rids of a type). Writes are O(r) where *r* is the
    resource delta for one minion. Compaction is O(N log N) and runs in
    the background; readers are not blocked.
    """

    def __init__(self, opts, store=None, cache=None):
        """
        :param dict opts: The Salt opts dict.
        :param _ResourceIndexStore store: Override the default store
            (primarily for testing).
        :param cache: Override the default ``salt.cache`` factory result
            (primarily for testing).
        """
        self._opts = opts
        cache_dir = opts.get("cachedir")
        if not cache_dir:
            raise ValueError("ResourceRegistry requires opts['cachedir'] to be set")
        index_path = os.path.join(
            cache_dir, PRIMARY_INDEX_SUBDIR, PRIMARY_INDEX_FILENAME
        )
        self._store = store or _ResourceIndexStore(
            index_path,
            capacity=opts.get(
                "resource_index_primary_capacity", DEFAULT_PRIMARY_CAPACITY
            ),
            slot_size=opts.get("resource_index_primary_slot_size", DEFAULT_SLOT_SIZE),
        )
        # ``salt.cache`` is the bank abstraction used for the topology blob
        # (``resources`` bank) plus ``grains``/``pillar``. The registry
        # only owns ``resources`` reads; the other banks are populated by
        # the existing refresh paths.
        self._cache = cache or salt.cache.factory(opts)

        # Automatic compaction policy (see :meth:`maybe_compact`).
        self._compact_load_factor = float(
            opts.get(
                "resource_registry_compact_load_factor",
                DEFAULT_COMPACT_LOAD_FACTOR,
            )
        )
        self._compact_tombstone_ratio = float(
            opts.get(
                "resource_registry_compact_tombstone_ratio",
                DEFAULT_COMPACT_TOMBSTONE_RATIO,
            )
        )
        self._compact_min_interval = float(
            opts.get(
                "resource_registry_compact_min_interval",
                DEFAULT_COMPACT_MIN_INTERVAL,
            )
        )
        self._last_compact_check = 0.0

    def close(self):
        """
        Close the backing mmap so temp dirs can be removed and FDs are not
        held until CPython GC (important for unit tests and registry resets).
        """
        self._store.close()

    # ------------------------------------------------------------------
    # Read interface — used by the targeting layer
    # ------------------------------------------------------------------

    def get_resource(self, resource_id):
        """
        Return the topology blob for a single resource from the ``resources``
        bank, or ``None`` if absent.

        :param str resource_id: Bare resource ID (e.g. ``"esxi-01"``).
        :rtype: dict or None
        """
        try:
            return self._cache.fetch(RESOURCE_BANK, resource_id)
        except Exception as exc:  # pylint: disable=broad-except
            log.warning(
                "resource_registry: cache.fetch(%s, %s) failed: %s",
                RESOURCE_BANK,
                resource_id,
                exc,
            )
            return None

    def get_managing_minions_by_type(self, resource_type):
        """
        Return the minion IDs managing at least one resource of
        ``resource_type``.

        :rtype: dict   (shape: ``{"minions": [...], "missing": []}``)
        """
        minions = sorted(self._store.all_minions_by_type(resource_type))
        return {"minions": minions, "missing": []}

    def get_managing_minions_for_srn(self, resource_type, resource_id):
        """
        Return the list of minion IDs that manage the resource identified
        by the SRN ``(resource_type, resource_id)``, or an empty list.

        Preferred over :meth:`get_managing_minions_for_id` — composite
        keys avoid cross-type collisions.

        :rtype: list[str]
        """
        srn = resource_index_srn_key(resource_type, resource_id)
        row = self._store.get(srn)
        if not row:
            return []
        mid = row.get("minion")
        return [mid] if mid else []

    def get_managing_minions_for_id(self, resource_id):
        """
        Legacy: return managing minions for a bare resource ID by consulting
        the topology blob in the ``resources`` cache bank. Ambiguous across
        types — two resources of different types with the same bare id will
        collide.

        Callers should migrate to :meth:`get_managing_minions_for_srn`.

        :rtype: list[str]
        """
        blob = self.get_resource(resource_id)
        if not blob:
            return []
        managing = blob.get("managing_minions")
        if not managing:
            return []
        return list(managing)

    def get_resources_for_minion(self, minion_id):
        """
        Return ``{resource_type: [resource_id, ...]}`` for ``minion_id``.

        :rtype: dict[str, list[str]]
        """
        return self._store.resources_by_minion(minion_id)

    def has_resource_type(self, minion_id, resource_type):
        """
        Return ``True`` if ``minion_id`` manages any resource of
        ``resource_type``.
        """
        return resource_type in self._store.resources_by_minion(minion_id)

    def has_resource(self, minion_id, resource_type, resource_id):
        """
        Return ``True`` if ``minion_id`` manages the resource identified by
        ``(resource_type, resource_id)``.
        """
        srn = resource_index_srn_key(resource_type, resource_id)
        row = self._store.get(srn)
        return bool(row) and row.get("minion") == minion_id

    def has_srn(self, resource_type, resource_id):
        """
        Return ``True`` if any minion currently manages this SRN.

        :rtype: bool
        """
        srn = resource_index_srn_key(resource_type, resource_id)
        return self._store.get(srn) is not None

    def resolve_bare_resource_id(self, resource_id):
        """
        Return every ``(resource_type, resource_id)`` pair registered under the
        bare id ``resource_id``.

        Used for list / exact-glob targeting (``salt -L web-01``) without a
        ``T@type:`` prefix. Collisions across types return multiple pairs.

        :rtype: list[tuple[str, str]]
        """
        if not resource_id or not isinstance(resource_id, str):
            return []
        out = []
        try:
            for rtype in self._store.resource_types():
                if resource_id in self._store.rids_by_type(rtype):
                    out.append((rtype, resource_id))
        except Exception as exc:  # pylint: disable=broad-except
            log.warning(
                "resource_registry: resolve_bare_resource_id(%r) failed: %s",
                resource_id,
                exc,
            )
        return out

    def get_resource_ids_by_type(self, resource_type):
        """
        Return all resource IDs of ``resource_type`` across all managing
        minions.

        :rtype: list[str]
        """
        return self._store.rids_by_type(resource_type)

    # ------------------------------------------------------------------
    # Write interface — used by AESFuncs._register_resources and refresh
    # ------------------------------------------------------------------

    def register_minion(self, minion_id, resources):
        """
        Register the full set of resources managed by ``minion_id``,
        replacing any prior set. Per-minion delta is computed internally so
        only changed SRN keys are written to the primary.

        :param str minion_id: The reporting minion.
        :param dict resources: ``{resource_type: [resource_id, ...]}``
            representing the minion's current resource inventory.
        :returns: ``(n_put, n_deleted)``.
        """
        previous = self._store.resources_by_minion(minion_id)

        new_keys = set()
        to_put = []
        for rtype, rids in (resources or {}).items():
            for rid in rids or ():
                srn = resource_index_srn_key(rtype, rid)
                new_keys.add(srn)
                to_put.append((srn, minion_id, rtype))

        to_delete = []
        for rtype, rids in previous.items():
            for rid in rids:
                srn = resource_index_srn_key(rtype, rid)
                if srn not in new_keys:
                    to_delete.append(srn)

        # Order matters only for correctness under concurrent reads: puts
        # first so that a resource moving from one type to another (rare)
        # is never transiently missing.
        self._store.put_many(to_put)
        self._store.delete_many(to_delete)

        # Opportunistic compaction on the write path. Time-throttled so
        # the O(num_slots) ``get_stats`` call doesn't run more than once
        # per :data:`DEFAULT_COMPACT_MIN_INTERVAL` seconds.
        self.maybe_compact()

        return len(to_put), len(to_delete)

    def unregister_minion(self, minion_id):
        """
        Tombstone every primary entry that maps to ``minion_id``. Used when
        a minion is forcibly removed / decommissioned.

        :returns: Number of entries tombstoned.
        """
        previous = self._store.resources_by_minion(minion_id)
        to_delete = [
            resource_index_srn_key(rtype, rid)
            for rtype, rids in previous.items()
            for rid in rids
        ]
        self._store.delete_many(to_delete)
        return len(to_delete)

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def compact(self):
        """
        Force an out-of-band compaction of the primary mmap index.

        Safe to call concurrently with reads: readers continue to see the
        pre-swap file until they next check staleness (which is rate
        limited by :data:`STALENESS_CHECK_INTERVAL`).

        For automatic policy-driven compaction, prefer :meth:`maybe_compact`.

        :returns: ``(occupied_before, occupied_after)``.
        """
        self._last_compact_check = time.monotonic()
        return self._store.compact()

    def maybe_compact(self, force_check=False):
        """
        Compact the primary if policy thresholds are exceeded.

        Thresholds (all configurable via opts, defaults in constants):

        * Load factor = ``(occupied + deleted) / total > compact_load_factor``
          (default 0.6). Prevents linear probing from degrading.
        * Tombstone ratio = ``deleted / occupied > compact_tombstone_ratio``
          (default 0.2). Reclaims dead slots.

        Time-throttled to at most one stats read per
        :data:`DEFAULT_COMPACT_MIN_INTERVAL` seconds, because
        :meth:`MmapCache.get_stats` is O(num_slots). Pass
        ``force_check=True`` to bypass the throttle (used by operator-
        initiated runners).

        :returns: ``(compacted, stats_dict)``. ``compacted`` is ``True`` if
            a compaction was triggered, ``False`` if thresholds were not
            exceeded or the throttle deferred the check.
        """
        now = time.monotonic()
        if (
            not force_check
            and (now - self._last_compact_check) < self._compact_min_interval
        ):
            return False, None

        self._last_compact_check = now
        try:
            stats = self._store._primary.get_stats()
        except Exception:  # pylint: disable=broad-except
            log.error(
                "resource_registry: maybe_compact stats read failed",
                exc_info=True,
            )
            return False, None

        occupied = stats.get("occupied", 0)
        deleted = stats.get("deleted", 0)
        total = stats.get("total", 0) or 1
        load_factor = stats.get("load_factor", (occupied + deleted) / total)
        tombstone_ratio = (deleted / occupied) if occupied else 0.0

        need = (
            load_factor > self._compact_load_factor
            or tombstone_ratio > self._compact_tombstone_ratio
        )
        if not need:
            return False, stats

        log.info(
            "resource_registry: auto-compact triggered "
            "(load_factor=%.3f, tombstone_ratio=%.3f, occupied=%d, deleted=%d)",
            load_factor,
            tombstone_ratio,
            occupied,
            deleted,
        )
        before, after = self._store.compact()
        log.info(
            "resource_registry: auto-compact finished (occupied %d -> %d)",
            before,
            after,
        )
        return True, stats

    def stats(self):
        """
        Return diagnostic counters for the primary mmap and the derived
        views. Useful for the runner and for deciding when to compact.

        :rtype: dict
        """
        primary = self._store._primary.get_stats()
        return {
            "primary": primary,
            "derived_version": self._store._derived_version,
            "derived_by_type_count": len(self._store._by_type),
            "derived_by_minion_count": len(self._store._by_minion),
            "path": self._store._path,
        }


# ---------------------------------------------------------------------------
# Process-wide singleton
# ---------------------------------------------------------------------------
#
# All code paths on the master that touch the resource registry must share a
# single :class:`ResourceRegistry` instance so the derived-view cache, the
# throttled-staleness plumbing, and the mmap file handle are reused. The
# registry is inexpensive to construct but each fresh instance pays a derived
# rebuild on first read — re-instantiating per request would defeat the O(1)
# read path.


class _NullResourceRegistry:
    """
    Read-only stand-in when ``opts['cachedir']`` is unset (minimal master
    contexts, some unit tests). :class:`CkMinions` always wires the registry;
    resource targeting then behaves as if no resources were registered.
    """

    def has_srn(self, resource_type, resource_id):
        return False

    def resolve_bare_resource_id(self, resource_id):
        return []

    def get_resource_ids_by_type(self, resource_type):
        return []

    def get_resources_for_minion(self, minion_id):
        return {}

    def register_minion(self, minion_id, resources):
        return (0, 0)

    def stats(self):
        return {
            "primary": {
                "occupied": 0,
                "deleted": 0,
                "total": 0,
                "load_factor": 0.0,
            },
            "derived_version": (0, 0),
            "derived_by_type_count": 0,
            "derived_by_minion_count": 0,
            "path": None,
        }

    def compact(self):
        return (0, 0)

    def maybe_compact(self, force_check=False):
        return False, None

    def close(self):
        """No-op: null registry holds no mmap or cache handles."""


_REGISTRY_LOCK = threading.Lock()
_REGISTRY_SINGLETON = None
_REGISTRY_CACHEDIR = None
_NULL_REGISTRY_SINGLETON = None


def get_registry(opts):
    """
    Return the process-wide :class:`ResourceRegistry` singleton for ``opts``.

    The first caller in a process instantiates the registry; subsequent
    callers get the same instance. If ``opts['cachedir']`` changes between
    calls (primarily a testing concern) the singleton is rebuilt.

    When ``cachedir`` is missing, returns a shared :class:`_NullResourceRegistry`
    so callers like :class:`~salt.utils.minions.CkMinions` can construct
    without a master cache directory (e.g. pillar unit tests).

    :param dict opts: Salt opts dict. Normally includes ``cachedir``.
    :rtype: ResourceRegistry or _NullResourceRegistry
    """
    global _REGISTRY_SINGLETON, _REGISTRY_CACHEDIR, _NULL_REGISTRY_SINGLETON  # pylint: disable=global-statement
    cachedir = opts.get("cachedir")
    if not cachedir:
        if _NULL_REGISTRY_SINGLETON is None:
            with _REGISTRY_LOCK:
                if _NULL_REGISTRY_SINGLETON is None:
                    _NULL_REGISTRY_SINGLETON = _NullResourceRegistry()
        return _NULL_REGISTRY_SINGLETON
    if _REGISTRY_SINGLETON is not None and _REGISTRY_CACHEDIR == cachedir:
        return _REGISTRY_SINGLETON
    with _REGISTRY_LOCK:
        if _REGISTRY_SINGLETON is not None and _REGISTRY_CACHEDIR == cachedir:
            return _REGISTRY_SINGLETON
        old = _REGISTRY_SINGLETON
        if old is not None:
            try:
                old.close()
            except Exception:  # pylint: disable=broad-except
                log.debug(
                    "resource_registry: error closing previous singleton",
                    exc_info=True,
                )
        _REGISTRY_SINGLETON = ResourceRegistry(opts)
        _REGISTRY_CACHEDIR = cachedir
        return _REGISTRY_SINGLETON


def reset_registry():
    """
    Drop the process-wide singleton. Used by tests that need a fresh
    registry per ``opts['cachedir']`` without relying on tmp_path varying.

    Always closes the previous registry's mmap so handles and disk space
    are released promptly.
    """
    global _REGISTRY_SINGLETON, _REGISTRY_CACHEDIR  # pylint: disable=global-statement
    with _REGISTRY_LOCK:
        old = _REGISTRY_SINGLETON
        _REGISTRY_SINGLETON = None
        _REGISTRY_CACHEDIR = None
    if old is not None:
        try:
            old.close()
        except Exception:  # pylint: disable=broad-except
            log.debug(
                "resource_registry: error closing singleton on reset",
                exc_info=True,
            )
