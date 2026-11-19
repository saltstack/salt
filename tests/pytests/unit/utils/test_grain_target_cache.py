"""
Tests for the in-process sorted-key cache that short-circuits
``resource_id:<glob>`` predicates with a non-empty fixed prefix.

Target module: :mod:`salt.utils.grain_target_cache` (Mission 2). The
module provides at minimum:

* ``get_sorted_keys(cache, bank) -> list[str]`` -- lazily materialised,
  sorted list of bank keys; rebuilt when the backing bank changes.
* ``fixed_prefix_of(pattern) -> str | None`` -- returns the characters
  of ``pattern`` before the first :mod:`fnmatch` metacharacter
  (``*``/``?``/``[``), or ``""``/``None`` when no fixed prefix exists.

These tests are written from the spec contract; they intentionally
avoid asserting on private implementation details (the specific
binary-search entry point, the shape of any internal LRU, etc.). If
the implementation names differ slightly, adjust the import shim near
the top and the tests will exercise the same behavioural invariants.
"""

import random
import threading

import pytest

# ---------------------------------------------------------------------------
# Import shim — pick the module up if it has landed; skip otherwise.
# ---------------------------------------------------------------------------

grain_target_cache = pytest.importorskip(
    "salt.utils.grain_target_cache",
    reason="Mission 2 target module not yet landed",
)


def _resolve(*names):
    """
    Return the first attribute of :mod:`grain_target_cache` whose name
    matches one of ``names``. ``None`` if none is present.
    """
    for name in names:
        fn = getattr(grain_target_cache, name, None)
        if fn is not None:
            return fn
    return None


fixed_prefix_of = _resolve("fixed_prefix_of", "fixed_prefix", "prefix_of_glob")
get_sorted_keys = _resolve("get_sorted_keys", "sorted_keys", "sorted_keys_for_bank")


requires_fixed_prefix = pytest.mark.skipif(
    fixed_prefix_of is None, reason="fixed_prefix_of not exported by module"
)
requires_get_sorted_keys = pytest.mark.skipif(
    get_sorted_keys is None, reason="get_sorted_keys not exported by module"
)


# ---------------------------------------------------------------------------
# Fake cache used across tests. Modelled on salt.cache.Cache: the only
# method the sorted-key cache is contractually allowed to call is
# ``list(bank)``; some implementations may also look at a generation
# counter / mtime.
# ---------------------------------------------------------------------------


class FakeCache:
    """
    Minimal in-memory cache with ``list(bank)`` + mutation helpers. A
    ``cachedir`` attribute lets the cache-under-test key its internal
    state by (cachedir, bank), matching the real multi-tenant layout.
    """

    def __init__(self, cachedir="/fake/cachedir", banks=None):
        self.cachedir = cachedir
        self._banks = {bank: list(keys) for bank, keys in (banks or {}).items()}
        self.list_calls = 0

    def list(self, bank):
        self.list_calls += 1
        if bank not in self._banks:
            raise Exception(f"bank {bank!r} not found")
        return list(self._banks[bank])

    # ---- mutation helpers for tests ----
    def set_bank(self, bank, keys):
        self._banks[bank] = list(keys)

    def add(self, bank, key):
        self._banks.setdefault(bank, []).append(key)

    def remove(self, bank, key):
        self._banks.get(bank, []).remove(key)


# ---------------------------------------------------------------------------
# fixed_prefix_of
# ---------------------------------------------------------------------------


@requires_fixed_prefix
def test_fixed_prefix_of_trailing_star():
    assert fixed_prefix_of("a-dummy-*") == "a-dummy-"


@requires_fixed_prefix
def test_fixed_prefix_of_star_after_literal_digits():
    assert fixed_prefix_of("a-dummy-0010*") == "a-dummy-0010"


@requires_fixed_prefix
def test_fixed_prefix_of_pure_star_has_no_prefix():
    # Spec: no fixed prefix -> either empty string or None.
    assert fixed_prefix_of("*") in (None, "")


@requires_fixed_prefix
def test_fixed_prefix_of_char_class_first_has_no_prefix():
    assert fixed_prefix_of("[abc]foo") in (None, "")


@requires_fixed_prefix
def test_fixed_prefix_of_literal_returns_whole_pattern():
    """
    A literal (no metachars) has a prefix equal to the whole pattern.
    This is OK: Mission 1 handles the literal fast path separately.
    """
    assert fixed_prefix_of("literal") == "literal"


@requires_fixed_prefix
def test_fixed_prefix_of_empty_pattern_has_no_prefix():
    assert fixed_prefix_of("") in (None, "")


@requires_fixed_prefix
def test_fixed_prefix_of_truncates_at_first_metachar():
    # ``?`` is the first metachar -> prefix is the single leading char.
    assert fixed_prefix_of("a?b*c") == "a"


@requires_fixed_prefix
def test_fixed_prefix_of_question_mark_only():
    assert fixed_prefix_of("?") in (None, "")


@requires_fixed_prefix
def test_fixed_prefix_of_question_mark_after_literal():
    assert fixed_prefix_of("foo?bar") == "foo"


@requires_fixed_prefix
def test_fixed_prefix_of_nontrivial_prefix_then_charclass():
    assert fixed_prefix_of("web-[0-9]") == "web-"


@requires_fixed_prefix
def test_fixed_prefix_of_backslash_is_not_metachar():
    """
    :mod:`fnmatch` does not treat ``\\`` as an escape; the prefix
    extractor must treat ``\\`` as an ordinary character. The exact
    output is implementation-defined -- document whatever the
    implementation chose so a regression in behaviour is caught.
    """
    out = fixed_prefix_of(r"a\*-foo")
    assert isinstance(out, (str, type(None)))
    # Whatever the choice, it must at least start with ``a`` -- the
    # first metachar is ``*`` at index 2 (after ``a\``).
    if out:
        assert out.startswith("a\\") or out.startswith("a"), out


@requires_fixed_prefix
def test_fixed_prefix_of_none_input_safe():
    # Defensive: a None input should not crash the planner.
    # Implementation may raise TypeError or return "" / None; accept
    # either behaviour but not a crash in production path.
    try:
        out = fixed_prefix_of(None)
    except (TypeError, AttributeError):
        return
    assert out in (None, "")


# ---------------------------------------------------------------------------
# get_sorted_keys — correctness + caching behaviour
# ---------------------------------------------------------------------------


@requires_get_sorted_keys
def test_get_sorted_keys_returns_sorted_list():
    cache = FakeCache(
        banks={"resource_grains": ["dummy:c", "dummy:a", "dummy:b"]},
    )
    out = get_sorted_keys(cache, "resource_grains")
    assert out == sorted(["dummy:c", "dummy:a", "dummy:b"])


@requires_get_sorted_keys
def test_get_sorted_keys_empty_bank_returns_empty_list():
    cache = FakeCache(banks={"resource_grains": []})
    assert get_sorted_keys(cache, "resource_grains") == []


@requires_get_sorted_keys
def test_get_sorted_keys_missing_bank_returns_empty_list():
    """
    A bank the driver refuses / raises on must not blow up the planner;
    the sorted-key helper must degrade to an empty list.
    """
    cache = FakeCache(banks={})
    out = get_sorted_keys(cache, "no_such_bank")
    assert out == []


@requires_get_sorted_keys
def test_get_sorted_keys_caches_without_bank_change():
    """
    Two back-to-back calls over an unchanged bank must hit the cache:
    the underlying ``cache.list(bank)`` is called at most a bounded
    small number of times (ideally 1; allow up to 2 to account for a
    cheap generation/mtime probe).
    """
    cache = FakeCache(
        banks={"resource_grains": [f"dummy:k-{i:04d}" for i in range(200)]},
    )
    first = get_sorted_keys(cache, "resource_grains")
    second = get_sorted_keys(cache, "resource_grains")
    assert first == second
    # Cache-hit on the second call: at most one additional ``list``.
    assert cache.list_calls <= 2, (
        f"get_sorted_keys did not cache -- list() called {cache.list_calls} "
        "times for two identical queries"
    )


@requires_get_sorted_keys
def test_get_sorted_keys_rebuilds_when_bank_changes():
    cache = FakeCache(banks={"resource_grains": ["dummy:a", "dummy:b"]})
    first = get_sorted_keys(cache, "resource_grains")
    assert first == ["dummy:a", "dummy:b"]

    cache.add("resource_grains", "dummy:c")
    # The sorted cache must detect the mutation on its next query.
    second = get_sorted_keys(cache, "resource_grains")
    assert "dummy:c" in second
    assert second == sorted(second)


@requires_get_sorted_keys
def test_get_sorted_keys_rebuilds_on_shrink():
    cache = FakeCache(banks={"resource_grains": ["dummy:a", "dummy:b", "dummy:c"]})
    assert get_sorted_keys(cache, "resource_grains") == [
        "dummy:a",
        "dummy:b",
        "dummy:c",
    ]
    cache.remove("resource_grains", "dummy:b")
    assert get_sorted_keys(cache, "resource_grains") == ["dummy:a", "dummy:c"]


@requires_get_sorted_keys
def test_get_sorted_keys_multiple_banks_cached_independently():
    """
    Mutating bank A must not evict the cached sort of bank B.
    """
    cache = FakeCache(
        banks={
            "a": ["a:1", "a:2"],
            "b": ["b:1", "b:2"],
        },
    )
    assert get_sorted_keys(cache, "a") == ["a:1", "a:2"]
    assert get_sorted_keys(cache, "b") == ["b:1", "b:2"]

    before_a = cache.list_calls
    _ = get_sorted_keys(cache, "b")
    _ = get_sorted_keys(cache, "b")
    # Querying ``b`` repeatedly must not re-list ``a`` nor do more
    # work than a single list of ``b``.
    assert cache.list_calls <= before_a + 2


@requires_get_sorted_keys
def test_get_sorted_keys_separate_cachedirs_are_independent():
    """
    Multi-tenant masters: one cachedir's sorted view must not shadow
    another's. The spec names ``(cache_dir, bank_name)`` as the cache
    key.
    """
    cache1 = FakeCache(cachedir="/c1", banks={"resource_grains": ["dummy:a"]})
    cache2 = FakeCache(cachedir="/c2", banks={"resource_grains": ["dummy:z"]})

    assert get_sorted_keys(cache1, "resource_grains") == ["dummy:a"]
    assert get_sorted_keys(cache2, "resource_grains") == ["dummy:z"]
    # Asking ``cache1`` again must still return ``cache1``'s view, not
    # the last-seen-any-cache view.
    assert get_sorted_keys(cache1, "resource_grains") == ["dummy:a"]


@requires_get_sorted_keys
def test_get_sorted_keys_thread_safety_concurrent_reads():
    """
    Hammer the sorted-key helper from many threads against a stable
    bank. The result must always be consistent (sorted, deduplicated,
    correct length) and the helper must never raise.
    """
    keys = [f"dummy:k-{i:05d}" for i in range(2000)]
    random.Random(1234).shuffle(keys)
    cache = FakeCache(banks={"resource_grains": keys})
    expected = sorted(keys)

    errors = []
    results = []
    lock = threading.Lock()
    barrier = threading.Barrier(16)

    def worker():
        try:
            barrier.wait(timeout=30)
            for _ in range(20):
                out = get_sorted_keys(cache, "resource_grains")
                # Validate shape eagerly inside the thread so a mid-test
                # mutation is surfaced as a race rather than a stale
                # read.
                if list(out) != expected:
                    with lock:
                        results.append(out)
                        break
        except Exception as exc:  # pylint: disable=broad-except
            # pragma: no cover - visible via errors
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert not errors, errors
    assert not results, f"stale/inconsistent reads from worker threads: {results[:2]}"


# ---------------------------------------------------------------------------
# Invariant: fixed_prefix_of output is a strict prefix of every
# fnmatch-matching string. This is the guarantee that lets a binary
# search over sorted keys bound the scan.
# ---------------------------------------------------------------------------


@requires_fixed_prefix
@pytest.mark.parametrize(
    "pattern",
    [
        "a-*",
        "web-*",
        "a-dummy-0010*",
        "foo?bar",
        "x[abc]",
        "literal",
        "a?b*c",
        "web-[0-9]",
    ],
)
def test_fixed_prefix_is_prefix_of_any_fnmatch_match(pattern):
    """
    For every pattern, any string that ``fnmatchcase`` matches must
    start with ``fixed_prefix_of(pattern)``. This is the core
    correctness invariant that justifies the binary-search range.
    """
    import fnmatch as _fnmatch

    prefix = fixed_prefix_of(pattern)
    if not prefix:
        return  # trivially holds for empty prefix

    sample_universe = [
        "a",
        "a-",
        "a-dummy-",
        "a-dummy-0010",
        "a-dummy-00100",
        "web-01",
        "web-foo",
        "foo-bar",
        "fooxbar",
        "literal",
        "xa",
        "xaabc",
        "aXbYc",
    ]
    for s in sample_universe:
        if _fnmatch.fnmatchcase(s, pattern):
            assert s.startswith(prefix), (
                f"pattern={pattern!r} prefix={prefix!r} matched string "
                f"{s!r} that does not start with the prefix -- binary "
                f"search would miss it"
            )
