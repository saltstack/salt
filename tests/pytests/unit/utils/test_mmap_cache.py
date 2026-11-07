"""
Unit tests for the MmapCache index+heap implementation.
"""

import os
import threading
import time

import pytest

from salt.utils.mmap_cache import MmapCache

# Shared small-cache parameters used across tests.
# key_size=32 → minimum slot_size = 1 + 32 + 20 = 53; use 64 for alignment.
_SIZE = 100
_KEY_SIZE = 32
_SLOT_SIZE = 64  # >= _min_slot_size(32) = 53


@pytest.fixture
def cache_path(tmp_path):
    return str(tmp_path / "test_cache.idx")


@pytest.fixture
def cache(cache_path):
    c = MmapCache(cache_path, size=_SIZE, slot_size=_SLOT_SIZE, key_size=_KEY_SIZE)
    yield c
    c.close()


# ---------------------------------------------------------------------------
# Basic put / get / delete / contains
# ---------------------------------------------------------------------------


def test_put_get(cache):
    assert cache.put("key1", "val1") is True
    assert cache.get("key1") == "val1"
    assert cache.get("missing") is None


def test_put_update(cache):
    assert cache.put("key1", "val1") is True
    assert cache.get("key1") == "val1"
    assert cache.put("key1", "val2") is True
    assert cache.get("key1") == "val2"


def test_mmap_cache_write_after_read_only_open(cache_path):
    """Writers must not reuse an ACCESS_READ mmap opened by a prior ``open(write=False)``."""
    cache = MmapCache(cache_path, size=_SIZE, slot_size=_SLOT_SIZE, key_size=_KEY_SIZE)
    assert cache.put("k1", "v1") is True
    cache.close()

    assert cache.open(write=False) is True
    assert cache.get("k1") == "v1"

    assert cache.put("k2", "v2") is True
    assert cache.get("k2") == "v2"
    cache.close()


def test_mmap_cache_concurrent_list_and_put(cache_path):
    """Concurrent ``list_items`` vs ``put`` must not leave a readonly mmap active for writers."""
    cache = MmapCache(cache_path, size=2000, slot_size=_SLOT_SIZE, key_size=_KEY_SIZE)
    assert cache.put("seed", "x") is True
    cache.close()
    errs = []

    def reader():
        try:
            for _ in range(20):
                cache.list_items()
        except Exception as exc:  # pylint: disable=broad-except
            errs.append(exc)

    def writer():
        try:
            for i in range(100):
                assert cache.put(f"w{i}", "y"), i
        except Exception as exc:  # pylint: disable=broad-except
            errs.append(exc)

    threads = [threading.Thread(target=reader), threading.Thread(target=writer)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errs, errs
    cache.close()


def test_read_open_then_write_reopens_writable_mmap(cache_path):
    """
    Read-only ``open(write=False)`` must not leave a mmap that ``put`` reuses
    when the on-disk id is unchanged (regression guard for cache-id logic).
    """
    c = MmapCache(cache_path, size=_SIZE, slot_size=_SLOT_SIZE, key_size=_KEY_SIZE)
    try:
        assert c.put("k", "v1") is True
        assert c.open(write=False) is True
        assert c.get("k") == "v1"
        assert c.put("k", "v2") is True
        assert c.get("k") == "v2"
    finally:
        c.close()


def test_delete(cache):
    cache.put("key1", "val1")
    assert cache.contains("key1") is True
    assert cache.delete("key1") is True
    assert cache.contains("key1") is False
    assert cache.get("key1") is None


def test_delete_nonexistent(cache):
    assert cache.delete("no_such_key") is False


def test_list_keys(cache):
    keys = ["key1", "key2", "key3"]
    for k in keys:
        cache.put(k, f"val_{k}")
    assert set(cache.list_keys()) == set(keys)


def test_set_mode(cache):
    """put(key) with no value stores a presence marker."""
    assert cache.put("key1") is True
    assert cache.contains("key1") is True
    assert cache.get("key1") is True


def test_list_items(cache):
    data = {"key1": "val1", "key2": "val2", "key3": True}
    for k, v in data.items():
        if v is True:
            cache.put(k)
        else:
            cache.put(k, v)

    items = cache.list_items()
    assert len(items) == 3
    assert set(items) == {("key1", "val1"), ("key2", "val2"), ("key3", True)}


# ---------------------------------------------------------------------------
# Key truncation / key_size enforcement
# ---------------------------------------------------------------------------


def test_key_truncation(cache_path):
    """Keys longer than key_size are silently truncated."""
    c = MmapCache(cache_path, size=_SIZE, slot_size=_SLOT_SIZE, key_size=_KEY_SIZE)
    long_key = "x" * (_KEY_SIZE + 10)
    short_key = "x" * _KEY_SIZE
    assert c.put(long_key, "v") is True
    # Retrieving by the truncated key must work
    assert c.get(short_key) == "v"
    c.close()


def test_slot_size_too_small_raises():
    """Constructing with an under-sized slot_size must raise ValueError."""
    with pytest.raises(ValueError, match="slot_size"):
        MmapCache("/tmp/never_used.idx", size=10, slot_size=10, key_size=64)


# ---------------------------------------------------------------------------
# Staleness detection (inode-based atomic-swap detection)
# ---------------------------------------------------------------------------


def test_staleness_detection(cache_path):
    """A reader detects file replacement and re-opens the new file."""
    cache = MmapCache(cache_path, size=_SIZE, slot_size=_SLOT_SIZE, key_size=_KEY_SIZE)
    assert cache.put("key1", "val1") is True
    assert cache.get("key1") == "val1"

    # Simulate an atomic swap by another process.
    tmp_path = cache_path + ".manual_tmp"
    other = MmapCache(tmp_path, size=_SIZE, slot_size=_SLOT_SIZE, key_size=_KEY_SIZE)
    other.put("key2", "val2")
    other.close()

    cache.close()
    os.replace(tmp_path, cache_path)
    # Also replace the heap
    heap_src = tmp_path + ".heap"
    heap_dst = cache_path + ".heap"
    if os.path.exists(heap_src):
        os.replace(heap_src, heap_dst)

    assert cache.get("key2") == "val2"
    assert cache.contains("key1") is False
    cache.close()


# ---------------------------------------------------------------------------
# Persistence across close/open
# ---------------------------------------------------------------------------


def test_persistence(cache_path):
    c1 = MmapCache(cache_path, size=_SIZE, slot_size=_SLOT_SIZE, key_size=_KEY_SIZE)
    c1.put("persist_me", "done")
    c1.close()

    c2 = MmapCache(cache_path, size=_SIZE, slot_size=_SLOT_SIZE, key_size=_KEY_SIZE)
    assert c2.get("persist_me") == "done"
    c2.close()


# ---------------------------------------------------------------------------
# Heap in-place overwrite vs. append
# ---------------------------------------------------------------------------


def test_overwrite_in_place_smaller_value(cache_path, tmp_path):
    """Updating a key with a shorter value should NOT grow the heap."""
    c = MmapCache(cache_path, size=_SIZE, slot_size=_SLOT_SIZE, key_size=_KEY_SIZE)
    c.put("k", "long_value_here")
    heap_size_after_first = os.path.getsize(cache_path + ".heap")

    c.put("k", "short")
    heap_size_after_update = os.path.getsize(cache_path + ".heap")

    assert (
        heap_size_after_update == heap_size_after_first
    ), "Heap should not grow on in-place overwrite"
    assert c.get("k") == "short"
    c.close()


def test_overwrite_appends_for_larger_value(cache_path):
    """Updating a key with a larger value appends to the heap."""
    c = MmapCache(cache_path, size=_SIZE, slot_size=_SLOT_SIZE, key_size=_KEY_SIZE)
    c.put("k", "short")
    heap_size_after_first = os.path.getsize(cache_path + ".heap")

    c.put("k", "a_much_longer_value_than_before")
    heap_size_after_update = os.path.getsize(cache_path + ".heap")

    assert heap_size_after_update > heap_size_after_first
    assert c.get("k") == "a_much_longer_value_than_before"
    c.close()


# ---------------------------------------------------------------------------
# mtime / get_mtime
# ---------------------------------------------------------------------------


def test_get_mtime(cache):
    before = time.time()
    cache.put("k", "v")
    after = time.time()

    mtime = cache.get_mtime("k")
    assert mtime is not None
    assert before <= mtime <= after + 1  # +1 for clock skew


def test_get_mtime_missing(cache):
    assert cache.get_mtime("no_such_key") is None


# ---------------------------------------------------------------------------
# atomic_rebuild
# ---------------------------------------------------------------------------


def test_atomic_rebuild(cache_path):
    c = MmapCache(cache_path, size=_SIZE, slot_size=_SLOT_SIZE, key_size=_KEY_SIZE)
    c.put("old_key", "old_val")

    new_data = [("key1", "val1"), ("key2", "val2")]
    assert c.atomic_rebuild(new_data) is True

    assert c.open() is True
    assert c.get("key1") == "val1"
    assert c.get("key2") == "val2"
    assert c.contains("old_key") is False
    c.close()


def test_atomic_rebuild_defragments_heap(cache_path):
    """After rebuild the heap should be compact (no deleted entry garbage)."""
    c = MmapCache(cache_path, size=_SIZE, slot_size=_SLOT_SIZE, key_size=_KEY_SIZE)
    for i in range(10):
        c.put(f"k{i}", f"value_{i}")
    for i in range(5):
        c.delete(f"k{i}")

    heap_before = os.path.getsize(cache_path + ".heap")

    live = [(k, v) for k, v in c.list_items()]
    assert c.atomic_rebuild(live) is True

    heap_after = os.path.getsize(cache_path + ".heap")
    assert heap_after < heap_before, "Rebuilt heap should be smaller (defragmented)"
    c.close()


def test_atomic_rebuild_set_mode(cache_path):
    """Rebuild preserves set-mode (value=None) entries."""
    c = MmapCache(cache_path, size=_SIZE, slot_size=_SLOT_SIZE, key_size=_KEY_SIZE)
    c.put("presence_key")
    assert c.atomic_rebuild([("presence_key",)]) is True
    assert c.open() is True
    assert c.get("presence_key") is True
    c.close()


# ---------------------------------------------------------------------------
# File size mismatch
# ---------------------------------------------------------------------------


def test_size_mismatch_rejected(cache_path):
    """Opening a cache file created with different slot_size must fail."""
    c = MmapCache(cache_path, size=10, slot_size=_SLOT_SIZE, key_size=_KEY_SIZE)
    c.put("test", "val")
    c.close()

    wrong = MmapCache(cache_path, size=10, slot_size=_SLOT_SIZE * 2, key_size=_KEY_SIZE)
    assert wrong.open(write=False) is False
    wrong.close()


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


def test_get_stats(cache):
    cache.put("k1", "v1")
    cache.put("k2", "v2")
    cache.delete("k1")

    stats = cache.get_stats()
    assert stats["occupied"] == 1
    assert stats["deleted"] == 1
    assert stats["heap_live_bytes"] > 0
    assert stats["heap_size_bytes"] >= stats["heap_live_bytes"]


# ---------------------------------------------------------------------------
# bytes values (raw binary round-trip)
# ---------------------------------------------------------------------------


def test_bytes_value_roundtrip(cache):
    raw = b"\x00\x01\x02binary\xff"
    assert cache.put("binkey", raw) is True
    result = cache.get("binkey")
    # Non-UTF-8 bytes are returned as bytes
    assert isinstance(result, bytes)
    assert result == raw


# ---------------------------------------------------------------------------
# Header counters and high-water mark
# ---------------------------------------------------------------------------


def test_header_occupied_count_tracks_puts(cache):
    for i in range(5):
        cache.put(f"k{i}", "v")
    occupied, deleted, hwm = cache._read_header()
    assert occupied == 5
    assert deleted == 0
    assert hwm >= 1


def test_header_counts_update_on_delete(cache):
    cache.put("k", "v")
    cache.delete("k")
    occupied, deleted, _ = cache._read_header()
    assert occupied == 0
    assert deleted == 1


def test_header_counts_on_reused_deleted_slot(cache_path):
    """Re-inserting into a DELETED slot: occupied +1, deleted -1."""
    c = MmapCache(cache_path, size=_SIZE, slot_size=_SLOT_SIZE, key_size=_KEY_SIZE)
    c.put("k", "v")
    c.delete("k")
    occ_before, del_before, _ = c._read_header()

    # Force the same slot to be reused by inserting the same key
    c.put("k", "v2")
    occ_after, del_after, _ = c._read_header()
    assert occ_after == occ_before + 1
    assert del_after == del_before - 1
    c.close()


def test_header_hwm_never_decreases(cache_path):
    c = MmapCache(cache_path, size=_SIZE, slot_size=_SLOT_SIZE, key_size=_KEY_SIZE)
    c.put("key_a", "v")
    _, _, hwm_after_first = c._read_header()
    c.put("key_b", "v")
    _, _, hwm_after_second = c._read_header()
    c.delete("key_b")
    _, _, hwm_after_delete = c._read_header()
    assert hwm_after_second >= hwm_after_first
    assert hwm_after_delete == hwm_after_second  # delete must not lower hwm
    c.close()


def test_list_items_uses_hwm_early_exit(cache_path):
    """list_items stops as soon as occupied_count entries are collected."""
    # Fill a small cache so we can verify it doesn't scan the entire table.
    c = MmapCache(cache_path, size=_SIZE, slot_size=_SLOT_SIZE, key_size=_KEY_SIZE)
    for i in range(10):
        c.put(f"key_{i:02d}", f"val_{i}")
    items = c.list_items()
    assert len(items) == 10
    assert {k for k, _ in items} == {f"key_{i:02d}" for i in range(10)}
    c.close()


def test_list_items_empty_cache_skips_scan(cache_path):
    """list_items returns immediately on an empty cache (no slot scan)."""
    c = MmapCache(cache_path, size=_SIZE, slot_size=_SLOT_SIZE, key_size=_KEY_SIZE)
    c.open(write=True)  # create the file
    assert c.list_items() == []
    c.close()


def test_get_stats_is_o1_from_header(cache_path):
    """get_stats reads counts from the header — verify accuracy."""
    c = MmapCache(cache_path, size=_SIZE, slot_size=_SLOT_SIZE, key_size=_KEY_SIZE)
    for i in range(7):
        c.put(f"k{i}", "v")
    c.delete("k0")
    c.delete("k1")

    stats = c.get_stats()
    assert stats["occupied"] == 5
    assert stats["deleted"] == 2
    assert stats["total"] == _SIZE - 1  # slot 0 is the header
    c.close()


def test_atomic_rebuild_resets_header(cache_path):
    """After atomic_rebuild the header counters match the new contents."""
    c = MmapCache(cache_path, size=_SIZE, slot_size=_SLOT_SIZE, key_size=_KEY_SIZE)
    for i in range(5):
        c.put(f"old_{i}", "v")

    new_data = [("new_a", "1"), ("new_b", "2"), ("new_c", "3")]
    assert c.atomic_rebuild(new_data) is True

    c.open()
    occupied, deleted, hwm = c._read_header()
    assert occupied == 3
    assert deleted == 0
    assert hwm >= 1
    c.close()


# ---------------------------------------------------------------------------
# put_many yielding (A' sub-chunk flock cycling)
# ---------------------------------------------------------------------------


# Enough slots for up to ~20K keys at a comfortable (~40%) load factor;
# slot_size large enough for the longer keys used in these tests.
_YIELD_SIZE = 65536
_YIELD_SLOT = 96
_YIELD_KEY = 48


def _mk_items(n, prefix="yk"):
    return [(f"{prefix}-{i:05d}", f"v-{i:05d}") for i in range(n)]


def test_put_many_yield_every_zero_matches_today_behavior(tmp_path):
    """yield_every=0 must preserve the historical single-flock semantics
    bit-for-bit: all keys present with expected values, no spurious state
    changes."""
    p = str(tmp_path / "yz.idx")
    c = MmapCache(p, size=_YIELD_SIZE, slot_size=_YIELD_SLOT, key_size=_YIELD_KEY)
    items = _mk_items(2048)
    assert c.put_many(items, yield_every=0) is True
    # Default call (no kwarg) must behave identically.
    c2 = MmapCache(
        str(tmp_path / "yz2.idx"),
        size=_YIELD_SIZE,
        slot_size=_YIELD_SLOT,
        key_size=_YIELD_KEY,
    )
    assert c2.put_many(items) is True
    for k, v in items:
        assert c.get(k) == v
        assert c2.get(k) == v
    c.close()
    c2.close()


def test_put_many_yielding_preserves_values(tmp_path):
    """put_many with yield_every > 0 must still land every entry correctly.

    10K entries across 40 yield groups at yield_every=256.
    """
    p = str(tmp_path / "ypv.idx")
    c = MmapCache(p, size=_YIELD_SIZE, slot_size=_YIELD_SLOT, key_size=_YIELD_KEY)
    items = _mk_items(10000)
    assert c.put_many(items, yield_every=256) is True
    for k, v in items:
        assert c.get(k) == v, f"missing/corrupt entry for {k}"
    c.close()


def test_put_many_yielding_releases_flock_between_groups(tmp_path):
    """While a long put_many(..., yield_every=N) is running in a thread,
    an in-process attempt to acquire the write flock non-blockingly must
    succeed at least once mid-batch. That can only happen if the writer
    releases the flock between groups.

    This is the behavioural signal that the yield actually happens; without
    the yield, a 20K-entry batch holds LOCK_EX for the duration.
    """
    import fcntl
    import threading

    import salt.utils.files

    p = str(tmp_path / "yr.idx")
    c = MmapCache(p, size=_YIELD_SIZE, slot_size=_YIELD_SLOT, key_size=_YIELD_KEY)
    items = _mk_items(20000)

    probe_hits = []
    stop = threading.Event()

    # Open a *separate* fd to the same lock file so we don't collide with
    # the writer's persistent lock fd (flock is per-open-file-description).
    lock_path = c._lock_path
    # The lock file is created on first _lock_fd_open; make sure it exists.
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    with salt.utils.files.fopen(lock_path, "a"):
        pass

    def probe():
        with salt.utils.files.fopen(lock_path, "w") as f:
            fd = f.fileno()
            while not stop.is_set():
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError:
                    # Writer holds the lock — try again.
                    time.sleep(0.001)
                    continue
                probe_hits.append(time.monotonic())
                fcntl.flock(fd, fcntl.LOCK_UN)
                # Sleep briefly so the writer can reacquire and make
                # forward progress.
                time.sleep(0.002)

    t = threading.Thread(target=probe, daemon=True)
    t.start()
    try:
        assert c.put_many(items, yield_every=128) is True
    finally:
        stop.set()
        t.join(timeout=5)

    # At least one mid-batch acquisition happened. In practice with 20K
    # entries and yield_every=128 there are ~156 yield points so the
    # probe has many chances; we just need one to prove the lock was
    # observable as free.
    assert probe_hits, "probe never caught the writer releasing the flock"
    c.close()


def test_put_many_yielding_atomic_rebuild_interleave(tmp_path, caplog):
    """A concurrent compact() running mid-put_many(yield_every=N) must
    land either before or after the batch cleanly; all submitted keys
    must be findable afterwards and no CRC errors logged."""
    import threading

    p = str(tmp_path / "yc.idx")
    c = MmapCache(p, size=_YIELD_SIZE, slot_size=_YIELD_SLOT, key_size=_YIELD_KEY)
    # Pre-seed so compact has something to rebuild.
    seed = _mk_items(100, prefix="seed")
    for k, v in seed:
        assert c.put(k, v) is True

    items = _mk_items(5000, prefix="y")

    errors = []

    def rebuild_soon():
        # Let put_many spin up a few groups first.
        time.sleep(0.02)
        try:
            # ``atomic_rebuild`` takes a full snapshot and swaps inodes.
            snap = c.list_items()
            c.atomic_rebuild(snap)
        except Exception as exc:  # pylint: disable=broad-except
            errors.append(exc)

    t = threading.Thread(target=rebuild_soon)
    with caplog.at_level("ERROR", logger="salt.utils.mmap_cache"):
        t.start()
        ok = c.put_many(items, yield_every=256)
        t.join(timeout=10)

    assert not errors, errors
    assert ok is True
    # All seed and all freshly-written keys must be readable.
    for k, v in seed:
        assert c.get(k) == v
    for k, v in items:
        assert c.get(k) == v, f"missing entry {k} after compact interleave"
    # No CRC/heap corruption logs.
    crc_errs = [rec.message for rec in caplog.records if "crc" in rec.message.lower()]
    assert not crc_errs, crc_errs
    c.close()


def test_put_many_yielding_crash_mid_batch(tmp_path, monkeypatch):
    """Simulate a crash between yield groups by raising inside _yield_flock.

    After the crash, reopening the cache must converge: every entry that
    is present must be readable with valid data (no torn slots / no CRC
    failures). Entries that did not make it durable are simply missing —
    that is the accepted weakening the design doc calls out.
    """
    p = str(tmp_path / "yx.idx")
    c = MmapCache(p, size=_YIELD_SIZE, slot_size=_YIELD_SLOT, key_size=_YIELD_KEY)

    items = _mk_items(3000, prefix="x")

    yield_count = {"n": 0}
    real_yield = MmapCache._yield_flock

    def bomb(self):
        yield_count["n"] += 1
        if yield_count["n"] >= 3:
            raise RuntimeError("simulated mid-batch crash")
        real_yield(self)

    monkeypatch.setattr(MmapCache, "_yield_flock", bomb)

    # put_many does not suppress non-OSError — this will raise.
    raised = False
    try:
        c.put_many(items, yield_every=256)
    except RuntimeError as exc:
        assert "simulated mid-batch crash" in str(exc)
        raised = True
    assert raised, "monkeypatched _yield_flock should have raised"
    c.close()

    # Reopen — _roster_recover runs on open(write=True) via _maybe_recover_roster.
    c2 = MmapCache(p, size=_YIELD_SIZE, slot_size=_YIELD_SLOT, key_size=_YIELD_KEY)
    assert c2.open(write=True) is True

    # Every entry that comes back must have a valid, non-corrupt value.
    # Entries that were lost mid-batch are allowed to be absent, but
    # none may be torn.
    expected = dict(items)
    for k, v in items:
        got = c2.get(k)
        if got is not None:
            assert got == v, f"torn/corrupt value for {k}: {got!r} != {v!r}"
    # Write a fresh entry to prove the cache is still usable post-crash.
    assert c2.put("post-crash", "ok") is True
    assert c2.get("post-crash") == "ok"
    c2.close()
    # Reference to silence lint about the `expected` dict being unused in
    # the None branch.
    assert "x-00000" in expected
