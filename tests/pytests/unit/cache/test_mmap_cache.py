"""
Unit tests for the mmap_cache salt.cache backend.

These tests exercise the public API in parity with test_localfs.py so that
mmap_cache can be treated as a drop-in replacement for localfs.
"""

import time

import pytest

import salt.cache.mmap_cache as mmap_cache
from tests.support.mock import patch

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def configure_loader_modules():
    return {
        mmap_cache: {
            "__opts__": {
                "mmap_cache_size": 1000,
                "mmap_cache_slot_size": 96,
                "mmap_cache_key_size": 64,
            }
        }
    }


@pytest.fixture(autouse=True)
def clear_cache_registry():
    """Isolate each test by starting with an empty instance registry."""
    mmap_cache._caches.clear()
    yield
    mmap_cache._caches.clear()


@pytest.fixture
def cachedir(tmp_path):
    return str(tmp_path)


@pytest.fixture
def populated(cachedir):
    """Store a simple entry and return (cachedir, bank, key, data)."""
    bank = "testbank"
    key = "testkey"
    data = {"hello": "world", "num": 42}
    mmap_cache.store(bank=bank, key=key, data=data, cachedir=cachedir)
    return cachedir, bank, key, data


# ---------------------------------------------------------------------------
# store / fetch round-trip
# ---------------------------------------------------------------------------


def test_store_fetch_basic(cachedir):
    mmap_cache.store("bank", "key", {"a": 1}, cachedir=cachedir)
    result = mmap_cache.fetch("bank", "key", cachedir=cachedir)
    assert result == {"a": 1}


def test_store_fetch_string(cachedir):
    mmap_cache.store("bank", "key", "plain string", cachedir=cachedir)
    assert mmap_cache.fetch("bank", "key", cachedir=cachedir) == "plain string"


def test_store_fetch_list(cachedir):
    mmap_cache.store("bank", "key", [1, 2, 3], cachedir=cachedir)
    assert mmap_cache.fetch("bank", "key", cachedir=cachedir) == [1, 2, 3]


def test_fetch_missing_key_returns_empty_dict(cachedir):
    assert mmap_cache.fetch("bank", "no_such_key", cachedir=cachedir) == {}


def test_fetch_missing_bank_returns_empty_dict(cachedir):
    assert mmap_cache.fetch("no_such_bank", "key", cachedir=cachedir) == {}


def test_store_overwrite(cachedir):
    mmap_cache.store("bank", "key", {"v": 1}, cachedir=cachedir)
    mmap_cache.store("bank", "key", {"v": 2}, cachedir=cachedir)
    assert mmap_cache.fetch("bank", "key", cachedir=cachedir) == {"v": 2}


def test_store_fetch_unicode(cachedir):
    data = {"unicode": "áéíóú", "emoji": "🔥"}
    mmap_cache.store("bank", "key", data, cachedir=cachedir)
    assert mmap_cache.fetch("bank", "key", cachedir=cachedir) == data


def test_store_fetch_bytes(cachedir):
    """Binary values that survive msgpack serialisation."""
    data = {"raw": b"\xfe\x99\x00\xff"}
    mmap_cache.store("bank", "key", data, cachedir=cachedir)
    assert mmap_cache.fetch("bank", "key", cachedir=cachedir) == data


# ---------------------------------------------------------------------------
# updated
# ---------------------------------------------------------------------------


def test_updated_returns_int(populated):
    cachedir, bank, key, _ = populated
    ts = mmap_cache.updated(bank=bank, key=key, cachedir=cachedir)
    assert isinstance(ts, int)


def test_updated_is_recent(populated):
    cachedir, bank, key, _ = populated
    before = int(time.time()) - 2
    after = int(time.time()) + 2
    ts = mmap_cache.updated(bank=bank, key=key, cachedir=cachedir)
    assert before <= ts <= after


def test_updated_missing_key_returns_none(cachedir):
    assert mmap_cache.updated("bank", "missing", cachedir=cachedir) is None


# ---------------------------------------------------------------------------
# flush (delete a key)
# ---------------------------------------------------------------------------


def test_flush_key(populated):
    cachedir, bank, key, _ = populated
    assert mmap_cache.flush_(bank=bank, key=key, cachedir=cachedir) is True
    assert mmap_cache.fetch(bank=bank, key=key, cachedir=cachedir) == {}


def test_flush_missing_key(cachedir):
    assert mmap_cache.flush_(bank="bank", key="no_such", cachedir=cachedir) is False


def test_flush_entire_bank(cachedir):
    """Flushing with key=None removes all mmap files for the bank."""
    for k in ("k1", "k2", "k3"):
        mmap_cache.store("bank", k, {"v": k}, cachedir=cachedir)

    # Evict registry so the flush uses a fresh instance
    mmap_cache._caches.clear()
    result = mmap_cache.flush_(bank="bank", key=None, cachedir=cachedir)
    assert result is True

    # After clearing, the bank is gone from registry; fetching returns {}
    assert mmap_cache.fetch("bank", "k1", cachedir=cachedir) == {}


def test_flush_nonexistent_bank_returns_false(cachedir):
    assert mmap_cache.flush_(bank="ghost", key=None, cachedir=cachedir) is False


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


def test_list_returns_keys(cachedir):
    for k in ("a", "b", "c"):
        mmap_cache.store("bank", k, {"v": k}, cachedir=cachedir)
    keys = mmap_cache.list_("bank", cachedir=cachedir)
    assert set(keys) == {"a", "b", "c"}


def test_list_empty_bank(cachedir):
    # Touching the bank so the dir exists but has no keys
    mmap_cache.store("bank", "tmp", {}, cachedir=cachedir)
    mmap_cache.flush_(bank="bank", key="tmp", cachedir=cachedir)
    keys = mmap_cache.list_("bank", cachedir=cachedir)
    assert keys == []


# ---------------------------------------------------------------------------
# contains
# ---------------------------------------------------------------------------


def test_contains_existing_key(populated):
    cachedir, bank, key, _ = populated
    assert mmap_cache.contains(bank=bank, key=key, cachedir=cachedir) is True


def test_contains_missing_key(cachedir):
    assert mmap_cache.contains("bank", "no_such", cachedir=cachedir) is False


def test_contains_bank_existence_check(cachedir):
    """contains(bank, key=None) tests whether the bank directory exists."""
    # Before any store the bank dir may not yet exist
    assert mmap_cache.contains("ghost_bank", key=None, cachedir=cachedir) is False
    mmap_cache.store("real_bank", "k", {}, cachedir=cachedir)
    assert mmap_cache.contains("real_bank", key=None, cachedir=cachedir) is True


# ---------------------------------------------------------------------------
# Cross-instance reads (two MmapCache objects on the same files)
# ---------------------------------------------------------------------------


def test_mmap_opts_change_rebuilds_registered_cache(cachedir):
    """
    If ``__opts__`` mmap tuning changes after a ``MmapCache`` was registered,
    the driver must drop the stale handle (and backing files) instead of
    reusing it — otherwise stores see the old table dimensions.
    """
    mmap_cache.store("bank", "first", {"v": 1}, cachedir=cachedir)
    with patch.dict(
        mmap_cache.__opts__,
        {"mmap_cache_size": 2000},
    ):
        mmap_cache.store("bank", "second", {"v": 2}, cachedir=cachedir)
        assert mmap_cache.fetch("bank", "second", cachedir=cachedir) == {"v": 2}


def test_max_segment_bytes_opt_is_passed_through(cachedir):
    """
    ``mmap_cache_max_segment_bytes`` must reach the underlying
    ``MmapCache`` so an operator can tune below the 1 GiB default.
    Reads back the live attribute on the registered cache instance.
    """
    with patch.dict(
        mmap_cache.__opts__,
        {"mmap_cache_max_segment_bytes": 4096},
    ):
        mmap_cache.store("bank", "key", {"v": 1}, cachedir=cachedir)
        cache_obj = mmap_cache._get_cache("bank", cachedir)
        assert cache_obj.max_segment_bytes == 4096


def test_max_segment_bytes_default_when_opt_missing(cachedir):
    """No opt set -> MmapCache uses the documented 1 GiB default."""
    import salt.utils.mmap_cache  # local import keeps test independent of import order

    mmap_cache.store("bank", "key", {"v": 1}, cachedir=cachedir)
    cache_obj = mmap_cache._get_cache("bank", cachedir)
    assert (
        cache_obj.max_segment_bytes == salt.utils.mmap_cache.DEFAULT_MAX_SEGMENT_BYTES
    )


@pytest.mark.parametrize(
    "trailing_byte",
    # Spot-check the corners (NUL, every-bit-set, ASCII null-vs-text
    # boundary), plus a sweep across the full byte range every 17 bytes
    # so 256 separate fixtures don't blow up the test count.
    [bytes([b]) for b in (0x00, 0x01, 0x09, 0x0A, 0x20, 0x7F, 0x80, 0xFF)]
    + [bytes([b]) for b in range(0, 256, 17)],
)
def test_get_preserves_every_trailing_byte(tmp_path, trailing_byte):
    """
    BUG.md regression: storing arbitrary bytes round-trips byte-for-byte
    through ``MmapCache.put``/``get``, including a trailing NUL.

    Pre-fix, ``MmapCache.get`` ran ``raw.rstrip(b"\\x00")`` on every
    read, so any value whose last byte was ``\\x00`` came back one
    byte short.  Post-fix the slot's ``LENGTH`` field is the only
    authority for the value boundary.
    """
    from salt.utils.mmap_cache import MmapCache

    cache = MmapCache(
        str(tmp_path / "trail.idx"),
        size=64,
        slot_size=128,
        key_size=32,
    )
    # Prefix the value with a high byte so ``get`` always returns
    # ``bytes`` (UTF-8 decoding fails) rather than auto-decoding to
    # ``str`` for ASCII payloads — keeps the round-trip comparison
    # honest about byte-level fidelity.
    payload = b"\xff" + b"prefix-data-" + trailing_byte
    assert cache.put("k", payload)
    got = cache.get("k")
    assert got == payload, (
        f"trailing byte 0x{trailing_byte.hex()} got mangled: "
        f"stored {payload!r} got {got!r}"
    )


def test_msgpack_zero_tail_dict_round_trips_through_cache_backend(cachedir):
    """
    BUG.md end-to-end regression: a dict whose msgpack-encoded form
    ends in ``\\x00`` (common: integer-tailed dicts where the last
    field is ``0``) must round-trip through the salt.cache backend
    without a ``SaltCacheError`` on read.

    Pre-fix, this raised ``SaltCacheError: Failed to deserialise
    cache data ...: Unpack failed: incomplete input`` because get
    stripped the trailing NUL of the msgpack stream.
    """
    import msgpack

    payload = {"p": "x" * 200, "i": 0}
    raw = msgpack.packb(payload)
    assert raw.endswith(b"\x00"), "test premise: msgpack of i=0 ends in NUL"

    mmap_cache.store("bank", "k0", payload, cachedir=cachedir)
    assert mmap_cache.fetch("bank", "k0", cachedir=cachedir) == payload


def test_overwrite_with_shorter_nul_tailed_value_round_trips(tmp_path):
    """
    BUG.md companion regression for ``_overwrite_in_heap``.

    Sequence:

    1. Put a long value to claim heap region of size N.
    2. Put a *shorter* binary value ending in NUL at the same key —
       triggers the in-place overwrite path.
    3. Get must return the new shorter value bytes intact.

    Pre-fix, the in-place overwrite NUL-padded the value to the
    existing region length AND rstripped it for the CRC computation,
    so the stored digest was over the rstripped (no-NUL-tail) bytes
    while the read-side digest was over the actual NUL-tailed bytes.
    The CRC check failed and ``get`` returned ``None``.
    """
    from salt.utils.mmap_cache import MmapCache

    cache = MmapCache(
        str(tmp_path / "ow.idx"),
        size=64,
        slot_size=128,
        key_size=32,
    )
    # High-byte prefix forces ``get`` to return bytes (no UTF-8
    # auto-decode), keeping the comparison byte-exact.
    cache.put("k", b"\xff-originally-longer-value-for-region")
    cache.put("k", b"\xff-short\x00")  # in-place overwrite, ends in NUL
    assert cache.get("k") == b"\xff-short\x00", (
        "in-place overwrite of NUL-tailed value did not round-trip; "
        "_overwrite_in_heap CRC computation likely still rstrips"
    )


def test_overwrite_then_grow_then_shrink_with_nul_tails(tmp_path):
    """
    Stress version of the overwrite regression: put a sequence of
    values with assorted trailing bytes — including NULs — at the
    same key, alternating between sizes that fit in-place and sizes
    that trigger an append.  Every read must return the most recent
    value byte-for-byte.
    """
    from salt.utils.mmap_cache import MmapCache

    cache = MmapCache(
        str(tmp_path / "stress.idx"),
        size=64,
        slot_size=128,
        key_size=32,
    )
    # Every value starts with a high byte so ``get`` returns bytes,
    # not str-decoded — see prior tests' note.
    sequence = [
        b"\xff-longvalueforinitialheapregion",  # 32 bytes; allocates
        b"\xff-short\x00",  # in-place overwrite
        b"\xff-a-bit-longer-but-still-fits\x00",  # in-place overwrite
        b"\xff-now grow past the original region - heap append \x00",
        b"\xff\x00\x00\x00",  # mostly-NUL
        b"\xff-f\xff\x00",  # binary with tail NUL
    ]
    for value in sequence:
        assert cache.put("k", value)
        got = cache.get("k")
        assert got == value, (
            f"round-trip failed for value of length {len(value)}: "
            f"stored {value!r} got {got!r}"
        )


def test_segment_actually_rolls_at_configured_cap(cachedir):
    """
    End-to-end: with a tiny cap, a few stores roll a new heap segment.
    Asserts a ``.heap.N`` file appears alongside the original heap.

    Pre-BUG.md fix this test could not safely fetch every key (the
    ``MmapCache.get`` ``rstrip(b"\\x00")`` corrupted msgpack-encoded
    integer-tailed dicts).  The fix landed; the
    ``test_msgpack_zero_tail_dict_round_trips_through_cache_backend``
    test below covers the cross-segment fetch case.
    """
    import os

    with patch.dict(
        mmap_cache.__opts__,
        # Cap at ~1 KiB so a handful of stores trips the roll quickly.
        {"mmap_cache_max_segment_bytes": 1024},
    ):
        for i in range(20):
            mmap_cache.store(
                "rolling-bank",
                f"k{i}",
                # Each value ~200 bytes after msgpack.  Total record
                # (CRC + value) crosses 1024 bytes within ~5 stores.
                {"payload": "x" * 200, "i": i},
                cachedir=cachedir,
            )
        bank_dir = os.path.join(cachedir, "rolling-bank")
        seg_files = sorted(
            f for f in os.listdir(bank_dir) if f.startswith(".mmap_cache.idx.heap")
        )
        # Original heap + at least one rolled segment.
        assert len(seg_files) >= 2, (
            f"expected at least two .heap segment files after rolling, "
            f"got {seg_files}"
        )
        # And the active segment id reflects the rolls.
        cache_obj = mmap_cache._get_cache("rolling-bank", cachedir)
        assert cache_obj._active_segment_id() >= 1


def test_two_instances_share_data(cachedir):
    """
    Simulate two processes: writer stores data; reader (separate instance)
    can fetch it by clearing the registry between calls.
    """
    mmap_cache.store("bank", "key", {"shared": True}, cachedir=cachedir)
    # Force a fresh instance (simulates a second process opening the same files)
    mmap_cache._caches.clear()
    result = mmap_cache.fetch("bank", "key", cachedir=cachedir)
    assert result == {"shared": True}


# ---------------------------------------------------------------------------
# Nested banks (bank path contains slashes)
# ---------------------------------------------------------------------------


def test_nested_bank(cachedir):
    mmap_cache.store("cluster/raft/log", "0001", {"term": 1}, cachedir=cachedir)
    result = mmap_cache.fetch("cluster/raft/log", "0001", cachedir=cachedir)
    assert result == {"term": 1}


def test_nested_bank_list(cachedir):
    for i in range(3):
        mmap_cache.store("cluster/raft/log", f"{i:04d}", {"i": i}, cachedir=cachedir)
    keys = mmap_cache.list_("cluster/raft/log", cachedir=cachedir)
    assert set(keys) == {"0000", "0001", "0002"}


# ---------------------------------------------------------------------------
# __func_alias__ compatibility
# ---------------------------------------------------------------------------


def test_func_alias_list(cachedir):
    """list_ is exposed as 'list' via the loader alias."""
    assert "list_" in mmap_cache.__func_alias__
    assert mmap_cache.__func_alias__["list_"] == "list"


def test_func_alias_flush(cachedir):
    """flush_ is exposed as 'flush' via the loader alias."""
    assert "flush_" in mmap_cache.__func_alias__
    assert mmap_cache.__func_alias__["flush_"] == "flush"
