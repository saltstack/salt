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

    ``parse_srn("vcf_host")``          → ``{"type": "vcf_host", "id": None}``
    ``parse_srn("vcf_host:esxi-01")``  → ``{"type": "vcf_host", "id": "esxi-01"}``

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

    * compactions (``os.replace`` → new inode), and
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

        Cross-process visibility is provided by :meth:`MmapCache._touch_mtime`,
        which bumps the file's mtime on every successful write — other
        workers then observe a fresh ``content_version`` and rebuild their
        derived views.

        Same-process visibility: the throttled stat cache in
        :meth:`_current_version` is invalidated locally so the *next* read
        is guaranteed to pick up this write without waiting for the
        throttle window to expire.

        :returns: ``True`` on success.
        """
        blob = _encode_by_id_value(minion_id, resource_type)
        ok = self._primary.put(srn_key, blob)
        if ok:
            self._invalidate_version_cache()
        return ok

    def delete(self, srn_key):
        """
        Mark a primary entry as DELETED (tombstone). Compaction reclaims
        the slot. O(1) amortised.
        """
        ok = self._primary.delete(srn_key)
        if ok:
            self._invalidate_version_cache()
        return ok

    def _invalidate_version_cache(self):
        """
        Force the next :meth:`_current_version` call to re-stat the file.

        Called after this process writes so it sees its own writes
        immediately; other processes rely on the throttled stat cycle.
        """
        self._last_version = None
        self._last_stat_time = 0.0

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
        Rebuild the primary into a fresh file using the sorted-placement
        algorithm (``O(N log N)``), then atomically swap via ``os.replace``.

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
        ok = self._primary.atomic_rebuild(items, strategy="sorted")
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

        ``content_version`` is ``(st_ino, st_mtime_ns)`` — sensitive to both
        atomic swaps (compactions) and in-place writes (puts/deletes from
        any process), because writers call
        :meth:`MmapCache._touch_mtime` on every successful mutation.

        ``None`` means the file doesn't exist yet (no writes happened).
        """
        now = time.monotonic()
        if (
            self._last_version is not None
            and now - self._last_stat_time < STALENESS_CHECK_INTERVAL
        ):
            return self._last_version
        try:
            version = self._primary.get_content_version()
        except OSError:
            version = None
        self._last_version = version
        self._last_stat_time = now
        return version

    def _ensure_derived_fresh(self):
        """
        Rebuild the derived ``by_type`` / ``by_minion`` views if the primary
        has changed since the last rebuild.

        Freshness is driven by a single signal: the primary's
        ``content_version`` tuple ``(st_ino, st_mtime_ns)``. It changes on:

        * :meth:`compact` — new inode via ``os.replace``; and
        * any writer's :meth:`put` / :meth:`delete` — same inode, new mtime
          (see :meth:`MmapCache._touch_mtime`).

        Uses double-checked locking so the common case is a single
        throttled stat() comparison.
        """
        current = self._current_version()
        if current is not None and current == self._derived_version:
            return
        with self._derived_lock:
            if current is not None and current == self._derived_version:
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

_REGISTRY_LOCK = threading.Lock()
_REGISTRY_SINGLETON = None
_REGISTRY_CACHEDIR = None


def get_registry(opts):
    """
    Return the process-wide :class:`ResourceRegistry` singleton for ``opts``.

    The first caller in a process instantiates the registry; subsequent
    callers get the same instance. If ``opts['cachedir']`` changes between
    calls (primarily a testing concern) the singleton is rebuilt.

    :param dict opts: Salt opts dict. Must contain ``cachedir``.
    :rtype: ResourceRegistry
    """
    global _REGISTRY_SINGLETON, _REGISTRY_CACHEDIR  # pylint: disable=global-statement
    cachedir = opts.get("cachedir")
    if _REGISTRY_SINGLETON is not None and _REGISTRY_CACHEDIR == cachedir:
        return _REGISTRY_SINGLETON
    with _REGISTRY_LOCK:
        if _REGISTRY_SINGLETON is not None and _REGISTRY_CACHEDIR == cachedir:
            return _REGISTRY_SINGLETON
        _REGISTRY_SINGLETON = ResourceRegistry(opts)
        _REGISTRY_CACHEDIR = cachedir
        return _REGISTRY_SINGLETON


def reset_registry():
    """
    Drop the process-wide singleton. Used by tests that need a fresh
    registry per ``opts['cachedir']`` without relying on tmp_path varying.
    """
    global _REGISTRY_SINGLETON, _REGISTRY_CACHEDIR  # pylint: disable=global-statement
    with _REGISTRY_LOCK:
        _REGISTRY_SINGLETON = None
        _REGISTRY_CACHEDIR = None
