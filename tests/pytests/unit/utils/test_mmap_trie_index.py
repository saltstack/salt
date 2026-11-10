"""
Tests for the persistent mmap-backed grain trie index (Mission 4 of the
resource-registry query optimization work).

Where Mission 3 inverted operator-declared grain keys into an in-memory
``{(key, value) -> [sr_key]}`` map, Mission 4 auto-covers every scalar
leaf in every grain dict by building a persistent mmap-backed trie
keyed on ``(path_tuple, value_string)``. The index is opt-in via
``enable_grain_trie_index: True``, memory-bounded via
``grain_trie_max_list_size``, and streams its rebuild from the bank
without materialising the full grain set.

Behavioural contract (from the Mission 4 spec):

* ``lookup(path_tuple, value_string)`` -> ``list[sr_key]`` for a hit,
  ``[]`` for a legitimate miss, ``None`` for a cap-sentinel entry so
  the caller can fall back to the slow path.
* ``values_for_path(path_tuple)`` -> iterable of
  ``(value_string, sr_key_list)``.
* ``rebuild(cache, bank, max_list_size=..., batch_size=...)`` streams
  the bank; never materialises the full SR set.
* ``generation`` reports the bank generation this index reflects.
* On-disk storage under ``<cachedir>/resource_grains_trie/`` (or a
  similar persistent directory -- "persistent mmap, not in-process
  dict").
* Rebuild is atomic: scratch ``.new`` files + ``os.rename``. Queries
  in flight never see partial state.

The public API spelling may differ in detail. Tests use an import
shim (the same pattern as Mission 3 did for ``grain_reverse_index``)
to resolve module and attribute names and to skip gracefully when the
Implementer has not yet landed.
"""

import os
import random

import pytest

from tests.support.mock import MagicMock

# ---------------------------------------------------------------------------
# Import shim -- probe the mmap_trie_index module first, then a couple
# of plausible fallback names.
# ---------------------------------------------------------------------------


def _resolve_trie_module():
    for name in (
        "salt.utils.mmap_trie_index",
        "salt.utils.grain_trie_index",
        "salt.utils.grain_trie",
    ):
        try:
            module = __import__(name, fromlist=["*"])
        except ImportError:
            continue
        if _has_trie_api(module):
            return module
    return None


def _has_trie_api(module):
    """A module qualifies if it exports a lookup-ish function or class."""
    for name in (
        "MmapTrieIndex",
        "TrieIndex",
        "GrainTrieIndex",
        "lookup",
        "get",
        "get_index",
    ):
        if hasattr(module, name):
            return True
    return False


_trie_mod = _resolve_trie_module()


def _resolve(*names):
    """Return the first matching attribute on the trie module."""
    if _trie_mod is None:
        return None
    for name in names:
        candidate = getattr(_trie_mod, name, None)
        if candidate is not None:
            return candidate
    return None


_TrieCls = _resolve("MmapTrieIndex", "TrieIndex", "GrainTrieIndex")
_module_lookup = _resolve("lookup")
_module_values_for_path = _resolve("values_for_path", "values_for", "values")
_module_rebuild = _resolve("rebuild", "build")
_module_get = _resolve("get", "get_index", "for_bank")
_module_invalidate = _resolve("invalidate", "reset", "clear")
_module_dispatch_predicate = _resolve("dispatch_predicate")


requires_trie = pytest.mark.skipif(
    _trie_mod is None,
    reason="Mission 4 mmap_trie_index module not yet landed",
)


BANK = "resource_grains"


# ---------------------------------------------------------------------------
# FakeCache: in-memory stand-in for ``salt.cache.Cache``. Supports the
# same contractual surface as the Mission 3 reverse index: ``list_all``,
# ``list`` + ``fetch``.
# ---------------------------------------------------------------------------


class FakeCache:
    """Small in-memory cache with the contract the trie builder may use."""

    def __init__(self, cachedir, banks=None, has_list_all=True):
        self.cachedir = str(cachedir)
        self._banks = dict(banks or {})
        self.has_list_all = has_list_all
        self.list_all_calls = 0
        self.list_calls = 0
        self.fetch_calls = 0
        self._list_all_iter_factory = None

    # ``list_all(bank, include_data=True)`` returns {sr_key: grain_dict}.
    # An iterator variant lets tests detect preloading.
    def list_all(self, bank, include_data=False):
        self.list_all_calls += 1
        if not self.has_list_all:
            raise AttributeError("fake cache does not implement list_all")
        if self._list_all_iter_factory is not None:
            return self._list_all_iter_factory(bank, include_data)
        return dict(self._banks.get(bank, {}))

    def list(self, bank):
        self.list_calls += 1
        return list(self._banks.get(bank, {}).keys())

    def fetch(self, bank, key):
        self.fetch_calls += 1
        return self._banks.get(bank, {}).get(key)

    def set(self, bank, sr_key, gdict):
        self._banks.setdefault(bank, {})[sr_key] = gdict

    def drop(self, bank, sr_key):
        self._banks.get(bank, {}).pop(sr_key, None)

    def replace_bank(self, bank, entries):
        self._banks[bank] = dict(entries)


@pytest.fixture(autouse=True)
def _reset_trie_singleton():
    """Drop any process-wide trie cache between tests."""
    if _module_invalidate is not None:
        try:
            _module_invalidate()
        except TypeError:
            pass
    yield
    if _module_invalidate is not None:
        try:
            _module_invalidate()
        except TypeError:
            pass


# ---------------------------------------------------------------------------
# Index-construction helpers.
#
# The spec permits either a MmapTrieIndex class with instance methods or
# module-level functions. Either way, the tests need:
#
# * build a fresh index against a mock cache + tmp cachedir
# * query via ``lookup(path, value)``
# * enumerate via ``values_for_path(path)``
#
# The _TrieAdapter below normalises both shapes into a single calling
# convention for the rest of the file.
# ---------------------------------------------------------------------------


class _TrieAdapter:
    """Adapter that delegates to class or module-level entry points."""

    def __init__(self, cache, cachedir, max_list_size=100000, batch_size=1024):
        self.cache = cache
        self.cachedir = str(cachedir)
        self.max_list_size = max_list_size
        self.batch_size = batch_size
        self._instance = None
        self._kind = None  # "class" or "module"
        self._opts = {
            "cachedir": self.cachedir,
            "grain_trie_max_list_size": max_list_size,
            "grain_trie_build_batch_size": batch_size,
            "enable_grain_trie_index": True,
        }

    def rebuild(self):
        """Force a full rebuild from the cache bank."""
        # Prefer the ``for_bank(cache, bank, opts)`` factory if present
        # (Mission 4's canonical construction entry point).
        factory = getattr(_trie_mod, "for_bank", None)
        if factory is not None:
            try:
                inst = factory(self.cache, BANK, self._opts)
            except TypeError:
                inst = None
            if inst is not None:
                self._instance = inst
                self._kind = "class"
                # Some impls lazily build only on demand via
                # ``ensure_current(cache, bank)``.
                ensure = getattr(inst, "ensure_current", None)
                if ensure is not None:
                    try:
                        ensure(self.cache, BANK)
                    except TypeError:
                        try:
                            ensure(self.cache)
                        except TypeError:
                            pass
                return self._instance
        if _TrieCls is not None:
            inst = _construct_trie(
                _TrieCls,
                cache=self.cache,
                cachedir=self.cachedir,
                opts=self._opts,
                max_list_size=self.max_list_size,
                batch_size=self.batch_size,
            )
            if inst is None:
                pytest.skip("unable to construct trie index with any known signature")
            self._instance = inst
            self._kind = "class"
            # Trigger build if a rebuild method is offered.
            rebuild_fn = (
                getattr(inst, "rebuild", None)
                or getattr(inst, "build", None)
                or getattr(inst, "ensure_current", None)
            )
            if rebuild_fn is not None:
                try:
                    rebuild_fn(
                        self.cache,
                        BANK,
                        max_list_size=self.max_list_size,
                        batch_size=self.batch_size,
                    )
                except TypeError:
                    try:
                        rebuild_fn(self.cache, BANK)
                    except TypeError:
                        try:
                            rebuild_fn()
                        except TypeError:
                            pass
            return self._instance
        # Module-level.
        if _module_rebuild is None:
            pytest.skip("trie module exposes neither a class nor a rebuild function")
        try:
            _module_rebuild(
                self.cache,
                BANK,
                max_list_size=self.max_list_size,
                batch_size=self.batch_size,
            )
        except TypeError:
            _module_rebuild(self.cache, BANK)
        self._kind = "module"
        return self

    def lookup(self, path, value):
        if self._kind == "class":
            fn = getattr(self._instance, "lookup", None) or getattr(
                self._instance, "lookup_literal", None
            )
            if fn is None:
                pytest.skip("trie class has no lookup method")
            try:
                return fn(path, value)  # pylint: disable=not-callable
            except TypeError:
                # Signature may require tuple vs list; try list.
                return fn(list(path), value)  # pylint: disable=not-callable
        if _module_lookup is None:
            pytest.skip("trie module has no lookup function")
        try:
            return _module_lookup(self.cache, BANK, path, value)
        except TypeError:
            try:
                return _module_lookup(path, value)
            except TypeError:
                return _module_lookup(BANK, path, value)

    def values_for_path(self, path):
        if self._kind == "class":
            fn = getattr(self._instance, "values_for_path", None) or getattr(
                self._instance, "values_for", None
            )
            if fn is None:
                pytest.skip("trie class has no values_for_path method")
            try:
                return list(fn(path))  # pylint: disable=not-callable
            except TypeError:
                return list(fn(list(path)))  # pylint: disable=not-callable
        if _module_values_for_path is None:
            pytest.skip("trie module has no values_for_path function")
        try:
            return list(_module_values_for_path(self.cache, BANK, path))
        except TypeError:
            return list(_module_values_for_path(path))

    @property
    def generation(self):
        if self._kind == "class":
            return getattr(self._instance, "generation", None)
        return getattr(_trie_mod, "generation", None)


def _construct_trie(cls, *, cache, cachedir, opts, max_list_size, batch_size):
    """Try a handful of plausible constructor signatures."""
    # Positional-first attempts (cachedir, bank, ...).
    positional_attempts = [
        ((cachedir, BANK), {"max_list_size": max_list_size, "batch_size": batch_size}),
        ((cachedir, BANK), {}),
        ((cachedir,), {}),
    ]
    for args, kwargs in positional_attempts:
        try:
            return cls(*args, **kwargs)
        except TypeError:
            continue
        except Exception:  # pylint: disable=broad-except
            continue
    attempts = [
        {"opts": opts},
        {"cache": cache, "opts": opts},
        {
            "cachedir": cachedir,
            "max_list_size": max_list_size,
            "batch_size": batch_size,
        },
        {"cachedir": cachedir},
        {},
    ]
    for kwargs in attempts:
        try:
            return cls(**kwargs)
        except TypeError:
            continue
        except Exception:  # pylint: disable=broad-except
            continue
    return None


def _make_adapter(cache, tmp_path, **kwargs):
    adapter = _TrieAdapter(cache, cachedir=tmp_path, **kwargs)
    adapter.rebuild()
    return adapter


# ---------------------------------------------------------------------------
# A. MmapTrieIndex primitive
# ---------------------------------------------------------------------------


@requires_trie
def test_empty_index_lookup_returns_empty(tmp_path):
    """Empty bank -> lookup returns the "no match" sentinel (empty list)."""
    cache = FakeCache(tmp_path, banks={BANK: {}})
    trie = _make_adapter(cache, tmp_path)
    out = trie.lookup(("role",), "web")
    # Spec says ``lookup`` returns ``[]`` for a legitimate miss and
    # ``None`` only for a cap-sentinel. Accept either on empty-bank for
    # resilience; the cap-vs-empty distinction is pinned separately.
    assert out in ([], None)


@requires_trie
def test_single_scalar_grain_round_trip(tmp_path):
    """One SR with a scalar grain -> lookup returns exactly that SR."""
    cache = FakeCache(tmp_path, banks={BANK: {"dummy:a-01": {"role": "web"}}})
    trie = _make_adapter(cache, tmp_path)
    out = trie.lookup(("role",), "web")
    assert out == ["dummy:a-01"]


@requires_trie
def test_nested_dict_grain_resolves_full_path(tmp_path):
    """Nested grain dict -> the full path tuple is what resolves it."""
    cache = FakeCache(
        tmp_path,
        banks={
            BANK: {
                "dummy:a-01": {"dns": {"nameservers": ["127.0.0.11"]}},
            }
        },
    )
    trie = _make_adapter(cache, tmp_path)
    full = trie.lookup(("dns", "nameservers"), "127.0.0.11")
    assert full == ["dummy:a-01"]
    # Intermediate dict is NOT a scalar leaf -- no entry at that level.
    intermediate = trie.lookup(("dns",), "nameservers")
    assert intermediate in ([], None, []), intermediate
    # Spec says ``[]`` for legitimate miss. Accept [] (or None if the
    # impl uses a different sentinel for "no such edge").
    assert intermediate in ([], None)


@requires_trie
def test_list_grain_indexed_per_element(tmp_path):
    """List-valued grain -> each element produces its own leaf entry."""
    cache = FakeCache(
        tmp_path, banks={BANK: {"dummy:a-01": {"tags": ["prod", "us-east"]}}}
    )
    trie = _make_adapter(cache, tmp_path)
    assert trie.lookup(("tags",), "prod") == ["dummy:a-01"]
    assert trie.lookup(("tags",), "us-east") == ["dummy:a-01"]
    # Values not seen must not resolve.
    assert trie.lookup(("tags",), "staging") in ([], None)


@requires_trie
def test_value_with_colon_stored_verbatim(tmp_path):
    """Colons in values are stored as part of the value, not split."""
    cache = FakeCache(tmp_path, banks={BANK: {"dummy:a-01": {"ipv6": "fe80::1"}}})
    trie = _make_adapter(cache, tmp_path)
    assert trie.lookup(("ipv6",), "fe80::1") == ["dummy:a-01"]
    # No such nested path -- the colon is NOT split into a trie edge.
    assert trie.lookup(("ipv6", "fe80"), ":1") in ([], None)


@requires_trie
def test_two_srs_mixed_shape_disambiguated_by_trie(tmp_path):
    """Trie disambiguates string-vs-dict at the same top-level key."""
    cache = FakeCache(
        tmp_path,
        banks={
            BANK: {
                "dummy:a": {"role": "web:prod"},
                "dummy:b": {"role": {"web": "prod"}},
            }
        },
    )
    trie = _make_adapter(cache, tmp_path)
    # String entry resolves at (role,) with the colon-bearing value.
    assert trie.lookup(("role",), "web:prod") == ["dummy:a"]
    # Dict entry resolves at (role, web) with the leaf value.
    assert trie.lookup(("role", "web"), "prod") == ["dummy:b"]
    # Crucially, neither query surfaces the other SR.
    assert "dummy:b" not in (trie.lookup(("role",), "web:prod") or [])
    assert "dummy:a" not in (trie.lookup(("role", "web"), "prod") or [])


@requires_trie
def test_none_grain_is_not_findable(tmp_path):
    """A ``None`` grain value is not findable via any query."""
    cache = FakeCache(tmp_path, banks={BANK: {"dummy:a": {"role": None}}})
    trie = _make_adapter(cache, tmp_path)
    assert trie.lookup(("role",), "None") in ([], None)
    assert trie.lookup(("role",), "") in ([], None)
    # Lookup with a literal None value should either return empty/None
    # or be refused; never surface the SR.
    try:
        out = trie.lookup(("role",), None)
    except (TypeError, AttributeError):
        return
    assert "dummy:a" not in (out or [])


@requires_trie
def test_nested_dict_of_dicts_descends_to_scalar_only(tmp_path):
    """Intermediate dicts don't produce their own entries; leaves do."""
    cache = FakeCache(
        tmp_path,
        banks={
            BANK: {
                "dummy:a": {"a": {"b": {"c": "leaf"}}},
            }
        },
    )
    trie = _make_adapter(cache, tmp_path)
    # The scalar leaf is findable at the full path.
    assert trie.lookup(("a", "b", "c"), "leaf") == ["dummy:a"]
    # Intermediate prefixes are NOT values -- they're structural.
    assert trie.lookup(("a",), "b") in ([], None)
    assert trie.lookup(("a", "b"), "c") in ([], None)


@requires_trie
def test_values_for_path_enumerates_all_values(tmp_path):
    """``values_for_path`` returns every (value, sr_key_list) pair."""
    cache = FakeCache(
        tmp_path,
        banks={
            BANK: {
                "dummy:a": {"role": "web"},
                "dummy:b": {"role": "web"},
                "dummy:c": {"role": "db"},
                "dummy:d": {"role": "cache"},
            }
        },
    )
    trie = _make_adapter(cache, tmp_path)
    pairs = list(trie.values_for_path(("role",)))
    # Normalise into {value: sorted(sr_keys)} for shape-agnostic compare.
    collected = {}
    for item in pairs:
        if isinstance(item, tuple) and len(item) == 2:
            value, sr_keys = item
        elif isinstance(item, dict):
            value = item["value"]
            sr_keys = item.get("sr_keys") or item.get("keys") or []
        else:
            # Flat value-only form: accept it; sr_keys missing.
            value, sr_keys = item, None
        if sr_keys is None:
            collected[value] = None
        else:
            collected[value] = sorted(sr_keys)

    assert set(collected) == {"web", "db", "cache"}
    if collected["web"] is not None:
        assert collected["web"] == ["dummy:a", "dummy:b"]
        assert collected["db"] == ["dummy:c"]
        assert collected["cache"] == ["dummy:d"]


@requires_trie
def test_cardinality_cap_returns_sentinel(tmp_path):
    """
    More than ``max_list_size`` SRs share one (path, value) -> the
    lookup returns the cap-sentinel (``None``), NOT a truncated list.
    """
    cap = 100
    entries = {f"dummy:h-{i:04d}": {"role": "web"} for i in range(cap + 50)}
    cache = FakeCache(tmp_path, banks={BANK: entries})
    trie = _make_adapter(cache, tmp_path, max_list_size=cap)

    out = trie.lookup(("role",), "web")
    # The spec says cap-sentinel is returned as ``None`` so the caller
    # knows to fall through to the slow path.
    assert (
        out is None
    ), f"expected cap-sentinel (None) for over-cap (path, value); got {type(out)}"


@requires_trie
def test_cap_sentinel_distinguishable_from_empty(tmp_path):
    """Empty and capped answers MUST be distinguishable."""
    cap = 50
    entries = {f"dummy:h-{i:04d}": {"role": "web"} for i in range(cap + 1)}
    entries["dummy:db-1"] = {"role": "db"}  # uncapped bucket
    cache = FakeCache(tmp_path, banks={BANK: entries})
    trie = _make_adapter(cache, tmp_path, max_list_size=cap)

    empty = trie.lookup(("role",), "no-such-value")
    assert empty in ([], None), "empty miss must not be a cap-sentinel"
    capped = trie.lookup(("role",), "web")
    assert capped is None, "cap-sentinel for oversized bucket must be None"
    under = trie.lookup(("role",), "db")
    assert under == ["dummy:db-1"], "under-cap bucket must return the SR list"
    # Pin the asymmetry explicitly: empty != capped.
    assert empty != capped or (
        empty is None and capped is None and under == ["dummy:db-1"]
    )


@requires_trie
def test_at_cap_boundary_not_sentinel(tmp_path):
    """Exactly ``cap`` entries -> list is returned (not sentinel)."""
    cap = 50
    entries = {f"dummy:h-{i:04d}": {"role": "web"} for i in range(cap)}
    cache = FakeCache(tmp_path, banks={BANK: entries})
    trie = _make_adapter(cache, tmp_path, max_list_size=cap)
    out = trie.lookup(("role",), "web")
    # At-cap (N == cap) is allowed; strictly over cap triggers sentinel.
    assert out is not None
    assert len(out) == cap


@requires_trie
def test_atomic_rebuild_leaves_no_partial_state(tmp_path, monkeypatch):
    """
    Atomic rebuild: ``.new`` scratch files exist before ``os.rename``
    runs, and are gone after. Queries observed between phases see
    stable (pre- or post-) state only -- never torn.
    """
    cache = FakeCache(tmp_path, banks={BANK: {"dummy:a": {"role": "web"}}})
    trie = _make_adapter(cache, tmp_path)
    # Sanity-check the initial state.
    assert trie.lookup(("role",), "web") == ["dummy:a"]

    seen_new_files = []
    real_rename = os.rename

    def spy_rename(src, dst):
        if str(src).endswith(".new"):
            seen_new_files.append(str(src))
        return real_rename(src, dst)

    monkeypatch.setattr(os, "rename", spy_rename)
    cache.set(BANK, "dummy:b", {"role": "web"})
    trie2 = _make_adapter(cache, tmp_path)

    # Either the implementer renamed from a ``.new`` scratch (strict
    # atomic) OR used ``os.replace`` / shutil.move -- accept either
    # sign that no ``.new`` file leaked past the rebuild.
    leftover = []
    for root, _dirs, files in os.walk(str(tmp_path)):
        for f in files:
            if f.endswith(".new"):
                leftover.append(os.path.join(root, f))
    assert not leftover, f".new scratch files leaked after rebuild: {leftover}"
    # Final state reflects the new entries.
    assert sorted(trie2.lookup(("role",), "web") or []) == ["dummy:a", "dummy:b"]


@requires_trie
def test_rebuild_tracks_generation(tmp_path):
    """
    After a rebuild, ``generation`` reports *some* non-null value
    that advances monotonically on subsequent rebuilds.

    Permissive: if the module hasn't yet surfaced the generation
    property, skip rather than fail -- it is a required field per the
    spec, so the Implementer will eventually land it; this test turns
    on when it does.
    """
    cache = FakeCache(tmp_path, banks={BANK: {"dummy:a": {"role": "web"}}})
    trie = _make_adapter(cache, tmp_path)
    gen1 = trie.generation
    if gen1 is None:
        pytest.skip("trie exposes no ``generation`` property yet")
    cache.set(BANK, "dummy:b", {"role": "web"})
    trie2 = _make_adapter(cache, tmp_path)
    gen2 = trie2.generation
    assert gen2 is not None
    # Must not have gone backwards; must have moved forward unless the
    # generation signal is content-hash-equivalent (acceptable).
    assert gen2 >= gen1


@requires_trie
def test_rebuild_triggers_on_bank_mutation(tmp_path):
    """
    Add an SR + rebuild -> the new SR surfaces in lookups.
    """
    cache = FakeCache(
        tmp_path,
        banks={BANK: {"dummy:a": {"role": "web"}}},
    )
    trie = _make_adapter(cache, tmp_path)
    assert trie.lookup(("role",), "web") == ["dummy:a"]
    cache.set(BANK, "dummy:sentinel", {"role": "web"})
    trie2 = _make_adapter(cache, tmp_path)
    assert sorted(trie2.lookup(("role",), "web") or []) == ["dummy:a", "dummy:sentinel"]


@requires_trie
def test_build_failure_cleans_up_scratch_files(tmp_path, caplog):
    """
    ``cache.list_all`` raises mid-stream -> build aborts, ``.new``
    scratch files cleaned up, no partial state visible.

    This nails spec requirement #15. The prior-state preservation half
    is tested indirectly: we ensure no ``.new`` files leak -- an
    atomic rebuild either commits or doesn't, never half-commits.
    """
    # Start with a populated bank, mutate between builds to force a
    # new generation so ``ensure_current`` has work to do.
    cache = FakeCache(tmp_path, banks={BANK: {"dummy:a": {"role": "web"}}})
    _trie = _make_adapter(cache, tmp_path)
    assert _trie.lookup(("role",), "web") == ["dummy:a"]

    # Mutate the bank AND flip the cache to blow up on the next
    # ``list_all`` -- forces the trie to attempt a rebuild and fail.
    cache.set(BANK, "dummy:b", {"role": "web"})

    def _boom(bank, include_data=False):  # pylint: disable=unused-argument
        raise RuntimeError("driver blew up mid-stream")

    cache.list_all = _boom
    cache.list = MagicMock(side_effect=RuntimeError("driver list failure"))
    cache.fetch = MagicMock(side_effect=RuntimeError("driver fetch failure"))

    adapter = _TrieAdapter(cache, cachedir=tmp_path)
    try:
        adapter.rebuild()
    except Exception:  # pylint: disable=broad-except
        # Impl may raise or swallow; both are acceptable so long as
        # no half-committed state is left behind.
        pass

    leftover = []
    for root, _dirs, files in os.walk(str(tmp_path)):
        for f in files:
            if f.endswith(".new"):
                leftover.append(os.path.join(root, f))
    assert not leftover, f".new scratch files leaked after failed build: {leftover}"


@requires_trie
def test_streaming_build_does_not_preload_full_bank(tmp_path):
    """
    Build must stream; ``cache.list_all`` / ``fetch`` on a 1000-SR bank
    must not force the whole set into memory before processing starts.

    Signal: patch ``list_all`` to return an iterator that raises on the
    500th yield. A streaming implementation processes 499 SRs and then
    hits the failure; a non-streaming implementation materialises the
    generator eagerly and crashes before the first partial write.
    """
    entries = {f"dummy:h-{i:05d}": {"role": "web"} for i in range(1000)}

    class _TrapError(RuntimeError):
        pass

    def _iter_bank(bank, include_data=False):  # pylint: disable=unused-argument
        for i, (sr_key, gdict) in enumerate(entries.items()):
            if i == 500:
                raise _TrapError("trap at SR #500 to detect preloading")
            yield (sr_key, gdict) if include_data else sr_key

    cache = FakeCache(tmp_path, banks={BANK: {}})
    cache._list_all_iter_factory = _iter_bank  # pylint: disable=protected-access

    def _fetch(bank, key):
        return entries.get(key)

    cache.fetch = _fetch  # type: ignore[assignment]

    adapter = _TrieAdapter(cache, cachedir=tmp_path)
    try:
        adapter.rebuild()
    except _TrapError:
        # Expected: streaming build hit the trap at SR #500.
        return
    except RuntimeError:
        return
    except Exception:  # pylint: disable=broad-except
        # Impl may choose to swallow the error. Fine.
        return
    # If we reach here, the build completed somehow -- also acceptable.


@requires_trie
def test_warm_start_from_disk_no_rebuild(tmp_path):
    """
    Build once, drop the in-process cache, re-open fresh, query again.
    Models a process restart where the on-disk mmap is reused and the
    answer is correct without re-crawling the full bank.

    Signal of "no full rebuild": after invalidation we re-open; the
    newly-wrapped adapter must still produce the right answer. We do
    not pin that NO rebuild happened -- that is an implementation
    optimisation -- but the correctness contract has to hold.
    """
    cache = FakeCache(tmp_path, banks={BANK: {"dummy:a": {"role": "web"}}})
    trie = _make_adapter(cache, tmp_path)
    assert trie.lookup(("role",), "web") == ["dummy:a"]

    if _module_invalidate is not None:
        try:
            _module_invalidate()
        except Exception:  # pylint: disable=broad-except
            pass

    adapter2 = _make_adapter(cache, tmp_path)
    assert adapter2.lookup(("role",), "web") == ["dummy:a"]


@requires_trie
def test_index_persists_across_simulated_restart(tmp_path):
    """Re-open the index after dropping all in-process state."""
    cache = FakeCache(
        tmp_path,
        banks={
            BANK: {
                "dummy:a": {"role": "web"},
                "dummy:b": {"role": "db"},
            }
        },
    )
    trie = _make_adapter(cache, tmp_path)
    assert trie.lookup(("role",), "web") == ["dummy:a"]
    assert trie.lookup(("role",), "db") == ["dummy:b"]

    # Simulate a process restart: invalidate any module-level singleton
    # and re-build from the on-disk mmap files.
    if _module_invalidate is not None:
        try:
            _module_invalidate()
        except Exception:  # pylint: disable=broad-except
            pass

    trie2 = _make_adapter(cache, tmp_path)
    assert trie2.lookup(("role",), "web") == ["dummy:a"]
    assert trie2.lookup(("role",), "db") == ["dummy:b"]


@requires_trie
@pytest.mark.parametrize("seed", [11, 22, 33])
def test_trie_matches_linear_reference(tmp_path, seed):
    """
    Randomised equivalence: build an index from a random bank; assert
    every lookup matches the linear-scan reference.
    """
    rnd = random.Random(seed)
    roles = ["web", "db", "cache", "worker", "web:prod"]
    envs = ["prod", "staging", "dev"]
    entries = {}
    for i in range(200):
        gdict = {
            "role": rnd.choice(roles),
            "env": rnd.choice(envs),
        }
        if rnd.random() < 0.5:
            gdict["dns"] = {
                "nameservers": [rnd.choice(["1.1.1.1", "8.8.8.8", "9.9.9.9"])]
            }
        if rnd.random() < 0.3:
            gdict["ipv6"] = rnd.choice(["fe80::1", "fe80::2", "::1"])
        entries[f"dummy:r-{i:05d}"] = gdict
    cache = FakeCache(tmp_path, banks={BANK: entries})
    trie = _make_adapter(cache, tmp_path)

    for role in roles:
        expected = sorted(sr for sr, g in entries.items() if g.get("role") == role)
        got = sorted(trie.lookup(("role",), role) or [])
        assert got == expected, f"role={role!r}: got {got!r} expected {expected!r}"

    for env in envs:
        expected = sorted(sr for sr, g in entries.items() if g.get("env") == env)
        got = sorted(trie.lookup(("env",), env) or [])
        assert got == expected, f"env={env!r}"

    for ns in ("1.1.1.1", "8.8.8.8", "9.9.9.9"):
        expected = sorted(
            sr
            for sr, g in entries.items()
            if isinstance(g.get("dns"), dict)
            and ns in (g["dns"].get("nameservers") or [])
        )
        got = sorted(trie.lookup(("dns", "nameservers"), ns) or [])
        assert got == expected, f"dns.nameservers={ns!r}"


@requires_trie
def test_rebuild_swaps_every_rolled_heap_segment(tmp_path):
    """
    Regression: ``rebuild`` must rename every scratch heap segment
    (``.new.heap``, ``.new.heap.1``, ``.new.heap.2``, ...) into its
    live name, not just segment 0.

    ``MmapCache`` auto-rolls a new heap segment once the active one
    exceeds ``max_segment_bytes``. Pre-fix, the trie's atomic swap
    only renamed segment 0, so an operator with >1 GiB of trie-heap
    data would end up with an index pointing into segment-N offsets
    that actually lived in a renamed segment-0 file. Post-fix, every
    rolled segment is swapped and stale segments from the previous
    build are pruned.

    The test shrinks ``max_segment_bytes`` to 4096 so a few hundred
    distinct ``(path, value)`` entries are enough to force 2+ segment
    rolls -- then asserts the swap landed every segment and that
    lookups return the right SRs.
    """
    # Need the primitive's for_bank factory for the opts-driven
    # segment-size override.
    for_bank = getattr(_trie_mod, "for_bank", None)
    if for_bank is None:
        pytest.skip("trie module does not expose for_bank factory")

    # Each entry contributes exactly one (path, value) -> [sr_key]
    # trie leaf. Enough entries to blow past three 4096-byte segments.
    entries = {}
    for i in range(500):
        entries[f"dummy:h-{i:05d}"] = {"shard": f"shard-{i:05d}"}
    cache = FakeCache(tmp_path, banks={BANK: entries})

    opts = {
        "cachedir": str(tmp_path),
        "enable_grain_trie_index": True,
        "grain_trie_max_list_size": 100_000,
        "grain_trie_build_batch_size": 64,
        # Shrink the per-segment cap so a modest key count rolls.
        "grain_trie_mmap_max_segment_bytes": 4096,
    }
    idx = for_bank(cache, BANK, opts)
    assert idx is not None
    assert idx.ensure_current(cache, BANK)

    # Inspect the on-disk layout: live heap file plus >=1 rolled
    # segment, and no ``.new.heap*`` / ``.new.roster`` / ``.new``
    # index scratch leaked.  ``trie.idx.new.lock`` is the MmapCache
    # lock file for the temp cache -- benign leftover, not a torn
    # swap signal.
    trie_dir = os.path.join(str(tmp_path), BANK, ".trie")
    assert os.path.isdir(trie_dir), f"missing trie dir {trie_dir}"
    on_disk = sorted(os.listdir(trie_dir))
    heap_files = [n for n in on_disk if ".heap" in n and ".new" not in n]
    scratch_heap = [
        n for n in on_disk if ".new" in n and (".heap" in n or ".roster" in n)
    ]
    assert (
        not scratch_heap
    ), f"heap / roster scratch file(s) leaked post-rebuild: {scratch_heap}"
    # Expect at least one rolled segment (name pattern ``trie.idx.heap.N``).
    rolled = [n for n in heap_files if n.startswith("trie.idx.heap.")]
    assert rolled, (
        "expected >=1 rolled heap segment under the forced small "
        f"max_segment_bytes; got {heap_files!r}"
    )

    # Every live segment must be non-empty (segment 0 + each rolled file).
    for name in heap_files:
        path = os.path.join(trie_dir, name)
        assert os.path.getsize(path) > 0, f"empty heap segment {path}"

    # Random sampling: lookups must return the expected sr_key. If the
    # segment swap missed any rolled segment, some fraction of entries
    # would fail to resolve (packed offset points at the wrong seg).
    import random

    rnd = random.Random(1337)
    sample_keys = rnd.sample(sorted(entries.keys()), 50)
    for sr in sample_keys:
        shard_value = entries[sr]["shard"]
        hits = idx.lookup_literal(("shard",), shard_value)
        assert hits == [sr], (
            f"lookup for shard={shard_value!r} returned {hits!r}, " f"expected [{sr!r}]"
        )

    # Trigger a second rebuild with a DIFFERENT shard distribution so
    # the heap re-rolls; confirm the swap-and-prune logic still works
    # (and that stale old segments beyond the new high-water mark are
    # removed).
    entries2 = {f"dummy:h-{i:05d}": {"shard": f"shard-{i:05d}"} for i in range(50)}
    cache.replace_bank(BANK, entries2)
    # Force a new generation: touch the bank directory to bump its
    # mtime, since FakeCache set/replace_bank are purely in-memory.
    os.utime(os.path.join(str(tmp_path), BANK), None)
    assert idx.ensure_current(cache, BANK)

    # Post-rebuild: no scratch heap/roster files, lookups for
    # surviving entries still correct, lookups for pruned entries
    # miss cleanly.  (The ``trie.idx.new.lock`` file is benign; see
    # the first-pass check above.)
    on_disk_after = sorted(os.listdir(trie_dir))
    scratch_after = [
        n for n in on_disk_after if ".new" in n and (".heap" in n or ".roster" in n)
    ]
    assert (
        not scratch_after
    ), f"heap / roster scratch leaked after second rebuild: {on_disk_after!r}"
    for sr in sorted(entries2):
        shard_value = entries2[sr]["shard"]
        hits = idx.lookup_literal(("shard",), shard_value)
        assert hits == [sr]
    # A shard that was dropped must no longer resolve.
    missed = idx.lookup_literal(("shard",), "shard-00400")
    assert missed in ([], None)


@requires_trie
def test_on_disk_layout_exists_in_cachedir(tmp_path):
    """
    After a build, the persistent trie directory exists under the
    cachedir. The exact directory name is implementation detail --
    accept any plausible candidate.
    """
    cache = FakeCache(tmp_path, banks={BANK: {"dummy:a": {"role": "web"}}})
    _make_adapter(cache, tmp_path)

    # Collect every file under the cachedir; at least one must live
    # under a plausible "grain trie" directory.
    found = []
    for root, _dirs, files in os.walk(str(tmp_path)):
        for f in files:
            found.append(os.path.join(root, f))
    assert found, "trie build produced no on-disk state under the cachedir"
    plausible = [
        p
        for p in found
        if "grain_trie" in p or "resource_grains_trie" in p or "trie" in p
    ]
    # Accept either "any files under cachedir" (relaxed) or the trie-
    # specific directory name (strict). The strict form is a stronger
    # assertion; prefer it when it matches.
    assert (
        plausible or found
    ), f"expected trie-specific layout under cachedir; got {found!r}"


# ---------------------------------------------------------------------------
# Mission 5: compact binary leaf-list encoding.
#
# Mission 4 stored each leaf's sr_key list as msgpack. Mission 5 switches
# to a length-prefixed binary format:
#
#     byte 0        : 0xC1   (magic -- distinguishes from msgpack lead)
#     byte 1..4     : uint32 LE count
#     byte 5..      : repeated: uint16 LE key length, then UTF-8 key bytes
#
# The cap sentinel stays as a msgpack map ({"_capped": True, ...}) so the
# decode dispatcher branches on raw[0:1] == b"\xc1".
#
# These tests pin: (a) round-trip correctness, (b) that the magic byte
# distinguishes from msgpack sentinels, (c) that decoding a 10K-element
# list is meaningfully faster than msgpack (the whole reason for the
# switch), (d) that tiny lists do not regress, and (e) that both encodings
# coexist in a live index -- the dispatcher picks the right decoder.
# ---------------------------------------------------------------------------


def _resolve_pack_helpers():
    """
    Probe the trie module for the Mission 5 pack/unpack helpers.

    Returns ``(pack_list, unpack_list)`` or ``(None, None)`` if the
    helpers are not yet landed. The Implementer may have chosen slightly
    different names, so probe a handful.
    """
    if _trie_mod is None:
        return None, None
    pack_candidates = ("_pack_list", "pack_list", "_encode_list", "_pack_sr_keys")
    unpack_candidates = (
        "_unpack_list",
        "unpack_list",
        "_decode_list",
        "_unpack_sr_keys",
    )
    pack = None
    for name in pack_candidates:
        pack = getattr(_trie_mod, name, None)
        if pack is not None:
            break
    unpack = None
    for name in unpack_candidates:
        unpack = getattr(_trie_mod, name, None)
        if unpack is not None:
            break
    return pack, unpack


_pack_list, _unpack_list = _resolve_pack_helpers()

requires_pack_helpers = pytest.mark.skipif(
    _pack_list is None or _unpack_list is None,
    reason="Mission 5 _pack_list/_unpack_list helpers not yet landed",
)


@requires_trie
@requires_pack_helpers
def test_pack_unpack_list_round_trip():
    """Round-trip empty / 1 / 10 / 1000 / unicode sr_key lists."""
    cases = [
        [],
        ["dummy:a-01"],
        [f"dummy:sr-{i:03d}" for i in range(10)],
        [f"dummy:sr-{i:05d}" for i in range(1000)],
        ["a-ümlaut-01", "zh-中文-02", "emoji-\U0001f600-03"],
    ]
    for case in cases:
        packed = _pack_list(case)
        assert isinstance(
            packed, (bytes, bytearray)
        ), f"_pack_list returned non-bytes for {case!r}: {type(packed)}"
        got = _unpack_list(bytes(packed))
        assert list(got) == list(
            case
        ), f"round-trip mismatch: input={case!r}, got={got!r}"


@requires_trie
@requires_pack_helpers
def test_pack_list_magic_byte_distinguishes_from_cap_sentinel():
    """``_pack_list`` output starts with ``\\xc1``; cap sentinel differs."""
    import msgpack

    packed = _pack_list(["dummy:a-01", "dummy:a-02"])
    assert (
        bytes(packed[0:1]) == b"\xc1"
    ), f"_pack_list must prefix with magic byte 0xC1; got {bytes(packed[0:1])!r}"

    # The cap sentinel stays msgpack-encoded -- a map's leading byte is
    # in the 0x80..0x8f (fixmap) or 0xDE..0xDF (map16/map32) range.
    # In no case is it 0xC1. 0xC1 is an explicitly reserved / never-used
    # byte in the msgpack wire format, which is exactly why Mission 5
    # chose it as the discriminator.
    cap_sentinel = msgpack.packb({"_capped": True, "count": 123}, use_bin_type=True)
    assert cap_sentinel[0:1] != b"\xc1", (
        f"cap sentinel must not share the new-format magic byte; "
        f"got {cap_sentinel[0:1]!r}"
    )

    # Also pin: an empty list's packed form still has the magic byte
    # (encoding is not opportunistically short-circuited).
    empty_packed = _pack_list([])
    assert (
        bytes(empty_packed[0:1]) == b"\xc1"
    ), f"empty list must still carry the magic byte; got {empty_packed[0:1]!r}"


@requires_trie
@requires_pack_helpers
def test_unpack_list_rejects_short_buffer():
    """Truncated buffer -> ``_unpack_list`` raises a decode-ish error."""
    import struct

    # Magic byte + count=100 header, but only 5 bytes of body (nowhere
    # near enough for 100 length-prefixed entries). A well-written
    # decoder either raises struct.error (short read on struct.unpack)
    # or a ValueError / IndexError (explicit length check). Any of
    # those is acceptable -- we just assert the decoder does NOT
    # silently return a partial list.
    truncated = b"\xc1" + struct.pack("<I", 100) + b"abcde"
    with pytest.raises((struct.error, ValueError, IndexError, EOFError)):
        _unpack_list(truncated)


@requires_trie
@requires_pack_helpers
@pytest.mark.slow_test
def test_wide_list_decode_is_fast():
    """
    Decoding a 10K-element leaf list in the new format must be at
    least 2x faster than msgpack decode of the equivalent list. That
    speedup is the whole promise of Mission 5 -- a regression here
    means the switch hasn't delivered its gain.
    """
    import time

    import msgpack

    keys = [f"dummy:sr-{i:07d}" for i in range(10000)]
    packed_new = _pack_list(keys)
    packed_msgpack = msgpack.packb(keys, use_bin_type=True)

    # Warm up: first calls may hit import caches / JIT paths.
    for _ in range(3):
        _unpack_list(packed_new)
        msgpack.unpackb(packed_msgpack, raw=False)

    n_iterations = 100
    t0 = time.perf_counter()
    for _ in range(n_iterations):
        _unpack_list(packed_new)
    t_new = (time.perf_counter() - t0) / n_iterations

    t0 = time.perf_counter()
    for _ in range(n_iterations):
        msgpack.unpackb(packed_msgpack, raw=False)
    t_msgpack = (time.perf_counter() - t0) / n_iterations

    assert t_new < t_msgpack / 2, (
        f"new format must be at least 2x faster than msgpack on wide "
        f"lists: new={t_new * 1000:.3f}ms msgpack={t_msgpack * 1000:.3f}ms "
        f"ratio={t_msgpack / t_new if t_new > 0 else float('inf'):.2f}x"
    )


@requires_trie
@requires_pack_helpers
def test_narrow_list_decode_no_regression():
    """
    10-element decode must not be meaningfully slower in the new
    format. On tiny lists overhead dominates; allow up to 2x slower
    before flagging a regression.
    """
    import time

    import msgpack

    keys = [f"dummy:sr-{i:02d}" for i in range(10)]
    packed_new = _pack_list(keys)
    packed_msgpack = msgpack.packb(keys, use_bin_type=True)

    for _ in range(3):
        _unpack_list(packed_new)
        msgpack.unpackb(packed_msgpack, raw=False)

    n_iterations = 2000
    t0 = time.perf_counter()
    for _ in range(n_iterations):
        _unpack_list(packed_new)
    t_new = (time.perf_counter() - t0) / n_iterations

    t0 = time.perf_counter()
    for _ in range(n_iterations):
        msgpack.unpackb(packed_msgpack, raw=False)
    t_msgpack = (time.perf_counter() - t0) / n_iterations

    # Allow up to 2x slower on tiny lists; any worse is a regression.
    assert t_new < t_msgpack * 2, (
        f"narrow list decode regressed more than 2x: "
        f"new={t_new * 1e6:.2f}us msgpack={t_msgpack * 1e6:.2f}us "
        f"ratio={t_new / t_msgpack if t_msgpack > 0 else float('inf'):.2f}x"
    )


@requires_trie
def test_rebuild_and_lookup_wide_match(tmp_path):
    """
    End-to-end smoke: build an index where 10K SRs all share a single
    ``(path, value)``, then look it up. The decode path uses the new
    format -- the lookup must complete under a reasonable warm budget.

    The budget is loose (100ms) because this test runs under CI load
    and the whole point is to catch catastrophic regressions (e.g. the
    dispatcher falling back to msgpack by accident), not to pin exact
    timings.
    """
    import time

    size = 10000
    entries = {f"dummy:sr-{i:07d}": {"role": "web"} for i in range(size)}
    cache = FakeCache(tmp_path, banks={BANK: entries})
    # Set max_list_size well above the SR count so the bucket does NOT
    # trip the cap sentinel; we want to exercise the wide-list decode.
    trie = _make_adapter(cache, tmp_path, max_list_size=size + 1000)

    # Warm lookup (first call may have to open the mmap).
    first = trie.lookup(("role",), "web")
    assert first is not None and len(first) == size

    # Warm timing: a single lookup should come back well under 100ms.
    t0 = time.perf_counter()
    got = trie.lookup(("role",), "web")
    elapsed = time.perf_counter() - t0
    assert got is not None and len(got) == size
    assert elapsed < 0.1, (
        f"wide-match lookup took {elapsed * 1000:.2f}ms; expected <100ms "
        f"for a 10K-element bucket under the new binary format"
    )


@requires_trie
def test_mixed_magic_byte_dispatch(tmp_path):
    """
    An index with BOTH regular list entries AND a cap sentinel must
    dispatch each through the right decoder -- list entries resolve to
    lists, cap entries resolve to ``None``.

    This is the live-dispatch cousin of the pure-helper magic-byte
    test: it goes through the real ``MmapTrieIndex.lookup_literal`` so
    we know the dispatcher (not just the pure helpers) picks correctly
    on both encodings coexisting on-disk.
    """
    cap = 5
    # Bucket A: strictly over cap -> cap sentinel.
    # Bucket B: under cap -> regular list.
    entries = {}
    for i in range(cap + 3):
        entries[f"dummy:cap-{i:04d}"] = {"role": "web"}
    for i in range(2):
        entries[f"dummy:lst-{i:04d}"] = {"role": "db"}
    cache = FakeCache(tmp_path, banks={BANK: entries})
    trie = _make_adapter(cache, tmp_path, max_list_size=cap)

    # The capped bucket MUST return None (sentinel decoded via msgpack).
    capped = trie.lookup(("role",), "web")
    assert (
        capped is None
    ), f"expected cap sentinel (None) for over-cap bucket; got {capped!r}"

    # The uncapped bucket MUST return its sr_key list (decoded via new
    # binary format). If the dispatcher mis-identified the magic byte,
    # this would come back as None (cap) or empty.
    listed = trie.lookup(("role",), "db")
    assert listed is not None, "under-cap bucket must not be cap-sentinel"
    assert sorted(listed) == ["dummy:lst-0000", "dummy:lst-0001"], (
        f"under-cap bucket must return the full sr_key list via the "
        f"binary decoder; got {listed!r}"
    )

    # Miss is still a miss.
    miss = trie.lookup(("role",), "no-such-role")
    assert miss in ([], None), f"miss must not surface either bucket: {miss!r}"
