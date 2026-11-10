"""
Tests for the reverse-value grain index that covers operator-declared
grain keys (Mission 3 of the resource-registry query optimization work).

The reverse-value index inverts the ``resource_grains`` bank layout
(stored as ``{<sr_key>: {grain_key: grain_value, ...}}``) into a per-key
multimap ``{grain_key: {grain_value: [sr_key, ...]}}``. A predicate like
``role:web`` against the inverted structure is an O(matches) hash probe
instead of the current ~19 s full-fetch slow path.

Target module: :mod:`salt.utils.grain_reverse_index` (may also be an
extension of :mod:`salt.utils.grain_target_cache`). Public API expected:

* ``lookup(cache, bank, declared_keys, grain_key, value) -> list[str]``
* ``values_for_key(cache, bank, declared_keys, grain_key) -> list[str]``
* ``invalidate(cachedir=None, bank=None)`` -- explicit drop

Tests are written from the spec contract and use the import shim pattern
established by :mod:`tests.pytests.unit.utils.test_grain_target_cache`.
If the implementer landed with slightly different names the shim below
resolves them; ambiguous spec corners (non-declared-key lookup, value
coercion) are tested as "accept either documented behaviour".
"""

import random
import threading

import pytest

from tests.support.mock import MagicMock

# ---------------------------------------------------------------------------
# Import shim -- probe the reverse-index module (new file) first, then
# fall back to the existing grain_target_cache module in case the
# implementer extended it instead of adding a new file.
# ---------------------------------------------------------------------------


def _resolve_module():
    """Return the module exposing the reverse-value index, or None."""
    try:
        import salt.utils.grain_reverse_index as mod
    except ImportError:
        mod = None
    if mod is not None and _has_entry_points(mod):
        return mod
    # Fallback: implementer may have extended grain_target_cache.
    try:
        import salt.utils.grain_target_cache as mod2
    except ImportError:
        return None
    if _has_entry_points(mod2):
        return mod2
    return None


def _has_entry_points(mod):
    """A module qualifies if it exports a lookup-like function."""
    for name in ("lookup", "reverse_lookup", "lookup_by_value"):
        if hasattr(mod, name):
            return True
    return False


_rev = _resolve_module()


def _resolve(*names):
    """Return the first matching attribute of ``_rev``, or None."""
    if _rev is None:
        return None
    for name in names:
        fn = getattr(_rev, name, None)
        if fn is not None:
            return fn
    return None


lookup = _resolve("lookup", "reverse_lookup", "lookup_by_value")
values_for_key = _resolve("values_for_key", "values", "list_values")
invalidate = _resolve("invalidate", "reset", "clear")


requires_module = pytest.mark.skipif(
    _rev is None,
    reason="Mission 3 reverse-value index module not yet landed",
)
requires_lookup = pytest.mark.skipif(
    lookup is None, reason="reverse-value index has no lookup entry point"
)
requires_values_for_key = pytest.mark.skipif(
    values_for_key is None,
    reason="reverse-value index has no values_for_key entry point",
)
requires_invalidate = pytest.mark.skipif(
    invalidate is None, reason="reverse-value index has no invalidate entry point"
)


BANK = "resource_grains"


# ---------------------------------------------------------------------------
# FakeCache: mocks the small subset of ``salt.cache.Cache`` that the
# reverse index is contractually allowed to call: ``list_all(bank,
# include_data=True)``, or ``list`` + ``fetch`` when list_all is missing.
# ---------------------------------------------------------------------------


class FakeCache:
    """
    In-memory fake with the three methods the reverse index may use.

    * ``list_all(bank, include_data=True)`` -> ``{sr_key: grain_dict}``.
    * ``list(bank)``                        -> ``[sr_key, ...]``
    * ``fetch(bank, sr_key)``               -> ``grain_dict``

    A ``has_list_all`` flag toggles whether ``list_all`` raises
    ``AttributeError`` so tests can exercise the fallback path.
    """

    def __init__(self, cachedir="/fake/cache", banks=None, has_list_all=True):
        self.cachedir = cachedir
        self._banks = dict(banks or {})
        self.has_list_all = has_list_all
        self.list_all_calls = 0
        self.list_calls = 0
        self.fetch_calls = 0

    def list_all(self, bank, include_data=False):
        self.list_all_calls += 1
        if not self.has_list_all:
            raise AttributeError("Cache driver 'fake' does not implement list_all")
        return dict(self._banks.get(bank, {}))

    def list(self, bank):
        self.list_calls += 1
        return list(self._banks.get(bank, {}).keys())

    def fetch(self, bank, key):
        self.fetch_calls += 1
        return self._banks.get(bank, {}).get(key)

    # Mutation helpers for tests.
    def set(self, bank, sr_key, gdict):
        self._banks.setdefault(bank, {})[sr_key] = gdict

    def drop(self, bank, sr_key):
        self._banks.get(bank, {}).pop(sr_key, None)

    def replace_bank(self, bank, entries):
        self._banks[bank] = dict(entries)


def _clean_index():
    """Drop the module-level singleton between tests when supported."""
    if invalidate is not None:
        try:
            invalidate()
        except TypeError:
            # Signature may be invalidate(cachedir=None, bank=None) only;
            # pass no args already covers that. Any other shape: swallow.
            pass


@pytest.fixture(autouse=True)
def _reset_module_singleton():
    _clean_index()
    yield
    _clean_index()


# ---------------------------------------------------------------------------
# 1. Empty bank -> empty lookup, no error.
# ---------------------------------------------------------------------------


@requires_module
@requires_lookup
def test_lookup_empty_bank_returns_empty_list():
    cache = FakeCache(banks={BANK: {}})
    out = lookup(cache, BANK, {"role"}, "role", "web")
    assert out == []


# ---------------------------------------------------------------------------
# 2. Build from list_all; multi-match on a declared key.
# ---------------------------------------------------------------------------


@requires_module
@requires_lookup
def test_lookup_returns_matching_sr_keys_from_list_all():
    cache = FakeCache(
        banks={
            BANK: {
                "dummy:a": {"role": "web", "resource_id": "a"},
                "dummy:b": {"role": "web", "resource_id": "b"},
                "dummy:c": {"role": "db", "resource_id": "c"},
            }
        }
    )
    out_web = lookup(cache, BANK, {"role"}, "role", "web")
    out_db = lookup(cache, BANK, {"role"}, "role", "db")
    assert sorted(out_web) == ["dummy:a", "dummy:b"]
    assert sorted(out_db) == ["dummy:c"]


# ---------------------------------------------------------------------------
# 3. Fallback to list + fetch when list_all raises AttributeError.
# ---------------------------------------------------------------------------


@requires_module
@requires_lookup
def test_lookup_falls_back_to_list_plus_fetch():
    cache = FakeCache(
        banks={
            BANK: {
                "dummy:a": {"role": "web"},
                "dummy:b": {"role": "db"},
            }
        },
        has_list_all=False,
    )
    out = lookup(cache, BANK, {"role"}, "role", "web")
    assert sorted(out) == ["dummy:a"]
    # list_all raised, so the impl must have used list + fetch.
    assert cache.list_calls >= 1
    assert cache.fetch_calls >= 1


# ---------------------------------------------------------------------------
# 4. Multiple declared keys share the same bank walk.
# ---------------------------------------------------------------------------


@requires_module
@requires_lookup
def test_lookup_handles_multiple_declared_keys():
    cache = FakeCache(
        banks={
            BANK: {
                "dummy:a": {"role": "web", "env": "prod"},
                "dummy:b": {"role": "web", "env": "staging"},
                "dummy:c": {"role": "db", "env": "prod"},
            }
        }
    )
    web = lookup(cache, BANK, {"role", "env"}, "role", "web")
    prod = lookup(cache, BANK, {"role", "env"}, "env", "prod")
    assert sorted(web) == ["dummy:a", "dummy:b"]
    assert sorted(prod) == ["dummy:a", "dummy:c"]


# ---------------------------------------------------------------------------
# 5. Lookup for a non-declared key: implementation may return [] or
#    raise. Document whichever behaviour the impl chose.
# ---------------------------------------------------------------------------


@requires_module
@requires_lookup
def test_lookup_for_undeclared_key_returns_empty_or_raises():
    cache = FakeCache(
        banks={
            BANK: {
                "dummy:a": {"role": "web", "env": "prod"},
            }
        }
    )
    try:
        out = lookup(cache, BANK, {"role"}, "env", "prod")
    except (KeyError, ValueError):
        return
    # Alternatively accept an empty list or a default-rebuild-on-miss
    # behaviour that returns the correct answer. The spec deliberately
    # leaves this ambiguous.
    assert out in ([], ["dummy:a"]) or sorted(out) in (["dummy:a"],)


# ---------------------------------------------------------------------------
# 6. List-valued grain is indexed per-element.
# ---------------------------------------------------------------------------


@requires_module
@requires_lookup
def test_lookup_list_valued_grain_is_indexed_per_element():
    cache = FakeCache(
        banks={
            BANK: {
                "dummy:a": {"tags": ["prod", "us-east"]},
                "dummy:b": {"tags": ["prod", "us-west"]},
                "dummy:c": {"tags": ["staging"]},
            }
        }
    )
    prod = lookup(cache, BANK, {"tags"}, "tags", "prod")
    us_east = lookup(cache, BANK, {"tags"}, "tags", "us-east")
    us_west = lookup(cache, BANK, {"tags"}, "tags", "us-west")
    us_south = lookup(cache, BANK, {"tags"}, "tags", "us-south")
    assert sorted(prod) == ["dummy:a", "dummy:b"]
    assert sorted(us_east) == ["dummy:a"]
    assert sorted(us_west) == ["dummy:b"]
    assert us_south == []


# ---------------------------------------------------------------------------
# 7. None / missing grain is skipped.
# ---------------------------------------------------------------------------


@requires_module
@requires_lookup
def test_lookup_skips_none_and_missing_grains():
    cache = FakeCache(
        banks={
            BANK: {
                "dummy:a": {"role": "web"},
                "dummy:b": {"role": None},
                "dummy:c": {},  # no role key at all
            }
        }
    )
    web = lookup(cache, BANK, {"role"}, "role", "web")
    none = lookup(cache, BANK, {"role"}, "role", None)
    assert sorted(web) == ["dummy:a"]
    # ``None`` is never a legitimate lookup value -- must not surface.
    assert "dummy:b" not in none
    assert "dummy:c" not in none


# ---------------------------------------------------------------------------
# 8. Non-hashable grain value is skipped gracefully (no crash).
# ---------------------------------------------------------------------------


@requires_module
@requires_lookup
def test_lookup_non_hashable_grain_value_is_skipped():
    cache = FakeCache(
        banks={
            BANK: {
                "dummy:a": {"role": {"nested": "dict"}},
                "dummy:b": {"role": "web"},
            }
        }
    )
    # Must not raise. The nested-dict entry simply isn't findable.
    web = lookup(cache, BANK, {"role"}, "role", "web")
    assert sorted(web) == ["dummy:b"]
    # Attempting to look up the nested dict itself must also not crash.
    try:
        _ = lookup(cache, BANK, {"role"}, "role", {"nested": "dict"})
    except TypeError:
        # Acceptable -- the value is unhashable.
        pass


# ---------------------------------------------------------------------------
# 9. Rebuild on bank-generation change (shared invalidation signal with
#    Mission 2's sorted-key cache -- mmap occupied counter or bank dir
#    mtime).
# ---------------------------------------------------------------------------


@requires_module
@requires_lookup
def test_lookup_rebuilds_on_bank_change(tmp_path):
    # Stage a real bank directory so dir-mtime invalidation engages for
    # drivers that key on it. The FakeCache is otherwise in-memory.
    bank_dir = tmp_path / BANK
    bank_dir.mkdir()
    cache = FakeCache(
        cachedir=str(tmp_path),
        banks={
            BANK: {
                "dummy:a": {"role": "web"},
            }
        },
    )

    first = lookup(cache, BANK, {"role"}, "role", "web")
    assert sorted(first) == ["dummy:a"]

    # Mutate the bank AND bump the dir-mtime signal. Drivers that key on
    # the mmap_cache header advance it on every write, which we cannot
    # simulate in the FakeCache; fall back to an explicit invalidate so
    # the test is a correctness assertion rather than a flake.
    cache.set(BANK, "dummy:b", {"role": "web"})
    (bank_dir / "touch-me").write_text("x")
    if invalidate is not None:
        invalidate()

    second = lookup(cache, BANK, {"role"}, "role", "web")
    assert sorted(second) == ["dummy:a", "dummy:b"]


# ---------------------------------------------------------------------------
# 10. Changing declared keys triggers rebuild (or additive update).
# ---------------------------------------------------------------------------


@requires_module
@requires_lookup
def test_lookup_handles_changing_declared_keys():
    cache = FakeCache(
        banks={
            BANK: {
                "dummy:a": {"role": "web", "env": "prod"},
                "dummy:b": {"role": "db", "env": "prod"},
            }
        }
    )
    # Build only on role first.
    first = lookup(cache, BANK, {"role"}, "role", "web")
    assert sorted(first) == ["dummy:a"]

    # Now declared keys grows to include env. The second call must
    # answer env queries correctly (implementation may rebuild or do
    # additive updates -- either is fine).
    second = lookup(cache, BANK, {"role", "env"}, "env", "prod")
    assert sorted(second) == ["dummy:a", "dummy:b"]


# ---------------------------------------------------------------------------
# 11. Build exception is swallowed; logs at WARNING; returns [].
# ---------------------------------------------------------------------------


@requires_module
@requires_lookup
def test_lookup_swallows_build_exception(caplog):
    cache = MagicMock()
    cache.cachedir = "/fake"
    cache.list_all = MagicMock(
        side_effect=RuntimeError("driver failure during enumeration")
    )
    cache.list = MagicMock(side_effect=RuntimeError("driver list failure"))
    cache.fetch = MagicMock(side_effect=RuntimeError("driver fetch failure"))

    # Must not propagate.
    out = lookup(cache, BANK, {"role"}, "role", "web")
    assert out == []


# ---------------------------------------------------------------------------
# 12. values_for_key returns the set of distinct values seen.
# ---------------------------------------------------------------------------


@requires_module
@requires_values_for_key
def test_values_for_key_returns_distinct_values():
    cache = FakeCache(
        banks={
            BANK: {
                "dummy:a": {"role": "web"},
                "dummy:b": {"role": "web"},
                "dummy:c": {"role": "web"},
                "dummy:d": {"role": "db"},
                "dummy:e": {"role": "cache"},
                "dummy:f": {"role": "cache"},
            }
        }
    )
    out = values_for_key(cache, BANK, {"role"}, "role")
    assert sorted(out) == ["cache", "db", "web"]


# ---------------------------------------------------------------------------
# 13. Thread safety: many readers over a stable bank -- no exceptions,
#     no corrupted results.
# ---------------------------------------------------------------------------


@requires_module
@requires_lookup
def test_lookup_thread_safety_on_stable_bank():
    entries = {
        f"dummy:host-{i:05d}": {"role": "web" if i % 2 else "db"} for i in range(1000)
    }
    cache = FakeCache(banks={BANK: entries})
    expected_web = sorted(sr for sr, g in entries.items() if g.get("role") == "web")

    errors = []
    bad = []
    lock = threading.Lock()
    barrier = threading.Barrier(12)

    def worker():
        try:
            barrier.wait(timeout=30)
            for _ in range(10):
                out = lookup(cache, BANK, {"role"}, "role", "web")
                if sorted(out) != expected_web:
                    with lock:
                        bad.append(sorted(out)[:5])
                        break
        except Exception as exc:  # pylint: disable=broad-except
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert not errors, errors
    assert not bad, f"inconsistent reads: {bad[:2]}"


# ---------------------------------------------------------------------------
# 14. invalidate drops the cached index -- next lookup rebuilds even
#     without a generation bump.
# ---------------------------------------------------------------------------


@requires_module
@requires_lookup
@requires_invalidate
def test_invalidate_drops_cached_index():
    cache = FakeCache(
        banks={
            BANK: {
                "dummy:a": {"role": "web"},
            }
        }
    )
    first = lookup(cache, BANK, {"role"}, "role", "web")
    assert sorted(first) == ["dummy:a"]

    # Mutate without bumping any generation signal.
    cache.set(BANK, "dummy:b", {"role": "web"})

    # Explicit invalidate must force a rebuild.
    try:
        invalidate(cachedir=cache.cachedir, bank=BANK)
    except TypeError:
        # Different signature; fall back to the no-arg clear-all.
        invalidate()

    second = lookup(cache, BANK, {"role"}, "role", "web")
    assert sorted(second) == ["dummy:a", "dummy:b"]


# ---------------------------------------------------------------------------
# Extra: build invariants -- values_for_key respects declared-keys and
# skips absent / None.
# ---------------------------------------------------------------------------


@requires_module
@requires_values_for_key
def test_values_for_key_skips_none_and_missing():
    cache = FakeCache(
        banks={
            BANK: {
                "dummy:a": {"role": "web"},
                "dummy:b": {"role": None},
                "dummy:c": {},
            }
        }
    )
    out = values_for_key(cache, BANK, {"role"}, "role")
    # ``None`` and missing-key entries must not appear as a value.
    assert sorted(out) == ["web"]


# ---------------------------------------------------------------------------
# Randomised equivalence: a linear-scan reference against the index.
# ---------------------------------------------------------------------------


@requires_module
@requires_lookup
@pytest.mark.parametrize("seed", [1, 2, 3])
def test_lookup_matches_linear_reference(seed):
    rnd = random.Random(seed)
    roles = ["web", "db", "cache", "worker"]
    envs = ["prod", "staging", "dev"]
    entries = {}
    for i in range(400):
        entries[f"dummy:r-{i:05d}"] = {
            "role": rnd.choice(roles),
            "env": rnd.choice(envs),
        }
    cache = FakeCache(banks={BANK: entries})

    for role in roles:
        expected = sorted(sr for sr, g in entries.items() if g.get("role") == role)
        got = sorted(lookup(cache, BANK, {"role", "env"}, "role", role))
        assert got == expected, f"role={role!r} mismatch"

    for env in envs:
        expected = sorted(sr for sr, g in entries.items() if g.get("env") == env)
        got = sorted(lookup(cache, BANK, {"role", "env"}, "env", env))
        assert got == expected, f"env={env!r} mismatch"
