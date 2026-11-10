"""
In-process reverse-value index for operator-declared grain keys in the
``resource_grains`` bank.

Companion to :mod:`salt.utils.minions` -- specifically the
``_augment_grain_match_with_resource_grains`` grain-target expansion
path. Mission 1 added a literal ``resource_id:<id>`` hash probe;
Mission 2 added a sorted-key prefix cache for ``resource_id:<prefix>*``.
This module handles the common operator case where the predicate is on
a non-``resource_id`` grain key (``role:web``, ``env:prod``,
``os:Ubuntu``), by building a reverse map
``{(grain_key, value): [sr_key, ...]}`` for a configurable set of
"indexed" grain keys.

Without this index, grain-target queries on 400K-key banks walked every
bank entry (``cache.list`` + per-key ``cache.fetch`` + ``subdict_match``)
in ~19s regardless of match count. With the index, exact-value lookups
are O(matches) list reads.

Scope
-----
* Query-only. Never writes to the primary cache; rebuilds from it.
* Per-process in-memory map. No disk / mmap / persistence.
* Keyed by ``(cachedir, bank, frozenset(declared_keys))`` so changes to
  the operator's ``index_grain_keys`` setting trigger a rebuild rather
  than silently returning stale results.
* Only covers the top-level ``<key>:<value>`` predicate shape. Nested
  (``a:b:c``) predicates fall through to the slow path.

Build semantics
---------------
On first lookup after an invalidation the module walks the bank once:

* If the driver exposes ``list_all(bank, include_data=True)`` (mmap
  cache does -- see :mod:`salt.cache.mmap_cache`), a single pass
  enumerates every ``(sr_key, grain_dict)`` pair.
* Otherwise falls back to ``cache.list(bank)`` + per-key ``fetch``.

For each entry, each declared key is inspected; the value is normalised
and recorded. List values (``tags = ["prod", "us-east"]``) are indexed
per element so ``tags:prod`` works. Non-hashable values (dicts) are
skipped with a DEBUG log.

Invalidation
------------
Reuses the same cheap O(1) bank-generation signal implemented in
:mod:`salt.utils.grain_target_cache` -- mmap occupied-count header,
falling back to bank-directory ``st_mtime_ns``, finally to a sentinel
"always rebuild" tag. On generation change the current index is dropped
and the next lookup rebuilds from the primary bank.

Thread safety
-------------
Guarded by a single ``RLock``. Rebuilds compute the full new index
locally then atomically assign; concurrent readers that hold a
reference to the previous list of sr_keys may continue iterating it
without seeing partial state.
"""

import logging
import threading

import salt.utils.grain_target_cache

log = logging.getLogger(__name__)


# Sentinel generation used when the primary bank exposes no cheap
# signal; treating it as "always stale" forces a rebuild per query but
# preserves correctness.
_GEN_UNKNOWN = salt.utils.grain_target_cache._GEN_UNKNOWN  # noqa: SLF001


def _normalize(value):
    """
    Coerce a scalar grain value into a hashable key component.

    Strings pass through verbatim; everything else (ints, bools,
    floats, tuples of scalars) is stringified. Lists and dicts are
    handled upstream by the build loop -- this helper assumes a
    scalar-ish input.
    """
    if isinstance(value, str):
        return value
    return str(value)


class GrainReverseIndex:
    """
    Per-process reverse-value index cache keyed by
    ``(cachedir, bank, frozenset(declared_keys))``.

    Each entry is ``(generation, reverse_map)`` where ``reverse_map``
    is ``{(grain_key, value_str): [sr_key, ...]}`` and ``generation``
    is the bank-generation signal sampled at build time.

    Not instantiated directly by production callers -- use :func:`get`
    for the module-level singleton. Tests that need isolation can
    construct their own instance.
    """

    def __init__(self):
        self._entries = {}
        self._lock = threading.RLock()

    @staticmethod
    def _cache_key(cache, bank, declared_keys):
        cachedir = getattr(cache, "cachedir", None) or ""
        return (cachedir, bank, frozenset(declared_keys))

    def invalidate(self, cachedir=None, bank=None):
        """
        Drop cached entries.

        With no arguments drops everything. With ``cachedir`` and
        ``bank`` drops every index entry for that bank (across all
        declared-key sets).
        """
        with self._lock:
            if cachedir is None and bank is None:
                self._entries.clear()
                return
            for key in list(self._entries):
                if key[0] == (cachedir or "") and key[1] == bank:
                    self._entries.pop(key, None)

    def _build(self, cache, bank, declared_key_set):
        """
        Enumerate *bank* once and return a freshly-built reverse map.

        Uses the driver-native ``list_all`` when available; falls back
        to ``cache.list`` + per-key ``cache.fetch``. Any build error
        propagates to the caller, which logs at WARNING and returns an
        empty map so the slow path can still serve the query.
        """
        reverse = {}
        rows = None
        try:
            rows_mapping = cache.list_all(bank, include_data=True)
        except AttributeError:
            rows_mapping = None
        except Exception:  # pylint: disable=broad-except
            # Driver-level failure -- fall back to list+fetch so an
            # mmap-specific bug can't take down the index for other
            # drivers.
            log.debug(
                "grain_reverse_index: list_all(%r) failed; "
                "falling back to per-key fetch",
                bank,
                exc_info=True,
            )
            rows_mapping = None

        if rows_mapping is not None:
            try:
                rows = rows_mapping.items()
            except AttributeError:
                rows = None

        if rows is None:
            try:
                sr_keys = cache.list(bank) or []
            except Exception:  # pylint: disable=broad-except
                log.debug(
                    "grain_reverse_index: cache.list(%r) failed; "
                    "returning empty index",
                    bank,
                    exc_info=True,
                )
                return reverse

            def _iter_list_fetch():
                for sr_key in sr_keys:
                    try:
                        gdict = cache.fetch(bank, sr_key)
                    except Exception:  # pylint: disable=broad-except
                        continue
                    yield sr_key, gdict

            rows = _iter_list_fetch()

        for sr_key, gdict in rows:
            if not isinstance(gdict, dict):
                continue
            for declared_key in declared_key_set:
                if declared_key not in gdict:
                    continue
                raw_value = gdict.get(declared_key)
                if raw_value is None:
                    continue
                self._index_one(reverse, declared_key, raw_value, str(sr_key))
        return reverse

    @staticmethod
    def _index_one(reverse, declared_key, raw_value, sr_key):
        """
        Record ``sr_key`` under ``(declared_key, <normalised value>)``.

        Lists / tuples are indexed per element so predicates like
        ``tags:prod`` work when the grain value is
        ``["prod", "us-east"]``. Non-scalar, non-list members (nested
        dicts) are skipped with a DEBUG log -- the slow path still
        matches them via ``subdict_match`` if needed.
        """
        if isinstance(raw_value, (list, tuple)):
            members = raw_value
        else:
            members = (raw_value,)
        for member in members:
            if isinstance(member, dict):
                log.debug(
                    "grain_reverse_index: skipping nested dict value "
                    "for grain_key=%r sr_key=%r",
                    declared_key,
                    sr_key,
                )
                continue
            try:
                key = (declared_key, _normalize(member))
            except Exception:  # pylint: disable=broad-except
                log.debug(
                    "grain_reverse_index: cannot normalise value "
                    "for grain_key=%r sr_key=%r",
                    declared_key,
                    sr_key,
                    exc_info=True,
                )
                continue
            reverse.setdefault(key, []).append(sr_key)

    def _get_entry(self, cache, bank, declared_keys):
        """
        Return the cached ``reverse_map`` for ``(bank, declared_keys)``,
        rebuilding if the bank-generation signal has advanced or the
        entry is missing.

        An empty map is still a valid, cached result -- callers that
        get back ``[]`` from :meth:`lookup` should not retry until the
        next generation bump.
        """
        declared_key_set = frozenset(declared_keys)
        if not declared_key_set:
            return {}
        cache_key = self._cache_key(cache, bank, declared_key_set)
        with self._lock:
            current_gen = (
                salt.utils.grain_target_cache._bank_generation(  # noqa: SLF001
                    cache, bank
                )
            )
            entry = self._entries.get(cache_key)
            if entry is not None:
                cached_gen, cached_map = entry
                if cached_gen is not _GEN_UNKNOWN and cached_gen == current_gen:
                    return cached_map
            try:
                reverse = self._build(cache, bank, declared_key_set)
            except Exception:  # pylint: disable=broad-except
                log.warning(
                    "grain_reverse_index: build failed for bank=%r "
                    "keys=%r; falling back to slow path for this query",
                    bank,
                    sorted(declared_key_set),
                    exc_info=True,
                )
                reverse = {}
            self._entries[cache_key] = (current_gen, reverse)
            return reverse

    def lookup(self, cache, bank, declared_keys, grain_key, value):
        """
        Return the list of sr_keys whose ``grain_key`` grain equals
        ``value`` (literal scalar; no glob / regex).

        * Returns ``[]`` when the key is unknown, the value is unseen,
          or the index is empty.
        * Caller must check ``grain_key in declared_keys`` upstream;
          we trust the caller for that but a mismatch simply returns
          ``[]`` because the pair will never have been indexed.
        """
        reverse = self._get_entry(cache, bank, declared_keys)
        if not reverse:
            return []
        try:
            value_str = _normalize(value)
        except Exception:  # pylint: disable=broad-except
            return []
        return list(reverse.get((grain_key, value_str), ()))

    def values_for_key(self, cache, bank, declared_keys, grain_key):
        """
        Return every distinct value observed for ``grain_key`` across
        the indexed bank.

        Intended for the glob / PCRE paths: the caller walks the
        returned values applying ``fnmatch`` / ``re.search`` and then
        calls :meth:`lookup` per match. Returns ``[]`` if the index is
        empty or the grain key was never seen.
        """
        reverse = self._get_entry(cache, bank, declared_keys)
        if not reverse:
            return []
        return [v for (k, v) in reverse if k == grain_key]


# Module-level singleton. Tests that need isolation can instantiate
# their own index; production callers share the one below so a single
# CkMinions process pays the enumeration cost only once per generation.
_default = GrainReverseIndex()


def get():
    """Return the module-level :class:`GrainReverseIndex` singleton."""
    return _default


def lookup(cache, bank, declared_keys, grain_key, value):
    """Shortcut for ``get().lookup(...)``."""
    return _default.lookup(cache, bank, declared_keys, grain_key, value)


def values_for_key(cache, bank, declared_keys, grain_key):
    """Shortcut for ``get().values_for_key(...)``."""
    return _default.values_for_key(cache, bank, declared_keys, grain_key)


def invalidate(cachedir=None, bank=None):
    """Shortcut for ``get().invalidate(cachedir, bank)``."""
    _default.invalidate(cachedir=cachedir, bank=bank)
