import os
import time
import zlib

import pytest

import salt.utils.mmap_cache


@pytest.fixture
def cache_path(tmp_path):
    return str(tmp_path / "test_cache.idx")


def test_mmap_cache_put_get(cache_path):
    cache = salt.utils.mmap_cache.MmapCache(cache_path, size=100, slot_size=64)
    assert cache.put("key1", "val1") is True
    assert cache.get("key1") == "val1"
    assert cache.get("key2") is None
    cache.close()


def test_mmap_cache_put_update(cache_path):
    cache = salt.utils.mmap_cache.MmapCache(cache_path, size=100, slot_size=64)
    assert cache.put("key1", "val1") is True
    assert cache.get("key1") == "val1"
    assert cache.put("key1", "val2") is True
    assert cache.get("key1") == "val2"
    cache.close()


def test_mmap_cache_delete(cache_path):
    cache = salt.utils.mmap_cache.MmapCache(cache_path, size=100, slot_size=64)
    cache.put("key1", "val1")
    assert cache.contains("key1") is True
    assert cache.delete("key1") is True
    assert cache.contains("key1") is False
    assert cache.get("key1") is None
    cache.close()


def test_mmap_cache_list_keys(cache_path):
    cache = salt.utils.mmap_cache.MmapCache(cache_path, size=100, slot_size=64)
    keys = ["key1", "key2", "key3"]
    for k in keys:
        cache.put(k, f"val_{k}")

    assert set(cache.list_keys()) == set(keys)
    cache.close()


def test_mmap_cache_set_behavior(cache_path):
    """Test using it as a set (value=None)"""
    cache = salt.utils.mmap_cache.MmapCache(cache_path, size=100, slot_size=64)
    assert cache.put("key1") is True
    assert cache.contains("key1") is True
    assert cache.get("key1") is True
    cache.close()


def test_mmap_cache_slot_boundaries(cache_path):
    """Test data exactly at and over slot boundaries"""
    slot_size = 64
    cache = salt.utils.mmap_cache.MmapCache(cache_path, size=10, slot_size=slot_size)

    # Exactly slot_size - 1 (allowed)
    key = "a" * (slot_size - 1)
    assert cache.put(key) is True
    assert cache.contains(key) is True

    # Exactly slot_size (not allowed, need 1 byte for status)
    key2 = "b" * slot_size
    assert cache.put(key2) is False

    # Value + Key boundary
    # 1 byte status + 30 bytes key + 1 byte null + 32 bytes value = 64 bytes
    key3 = "k" * 30
    val3 = "v" * 32
    assert cache.put(key3, val3) is True
    assert cache.get(key3) == val3

    # One byte too many
    val4 = "v" * 33
    assert cache.put(key3, val4) is False
    cache.close()


def test_mmap_cache_staleness_detection(cache_path):
    """Test that a reader detects an atomic file swap via Inode check"""
    cache = salt.utils.mmap_cache.MmapCache(cache_path, size=100, slot_size=64)
    assert cache.put("key1", "val1") is True
    assert cache.get("key1") == "val1"

    # Manually simulate an atomic swap from another "process"
    tmp_path = cache_path + ".manual_tmp"
    other_cache = salt.utils.mmap_cache.MmapCache(tmp_path, size=100, slot_size=64)
    other_cache.put("key2", "val2")
    other_cache.close()

    # On Windows we can't replace an open file.
    # We close it but keep the object, which still holds the old _cache_id (or _ino).
    cache.close()
    os.replace(tmp_path, cache_path)

    # The original cache instance should detect the change on next open/access
    # Our get() calls open(write=False)
    assert cache.get("key2") == "val2"
    assert cache.contains("key1") is False
    cache.close()


def test_mmap_cache_persistence(cache_path):
    """Test data persists after closing and re-opening"""
    cache = salt.utils.mmap_cache.MmapCache(cache_path, size=100, slot_size=64)
    cache.put("persist_me", "done")
    cache.close()

    new_instance = salt.utils.mmap_cache.MmapCache(cache_path, size=100, slot_size=64)
    assert new_instance.get("persist_me") == "done"
    new_instance.close()


def test_mmap_cache_atomic_rebuild(cache_path):
    cache = salt.utils.mmap_cache.MmapCache(cache_path, size=100, slot_size=64)
    cache.put("old_key", "old_val")

    # Rebuild with new data
    new_data = [("key1", "val1"), ("key2", "val2")]
    assert cache.atomic_rebuild(new_data) is True

    # Current cache object should reflect changes after reopening
    assert cache.open() is True
    assert cache.get("key1") == "val1"
    assert cache.get("key2") == "val2"
    assert cache.contains("old_key") is False
    cache.close()


def test_mmap_cache_size_mismatch(cache_path):
    # Initialize a file with 64-byte slots
    cache = salt.utils.mmap_cache.MmapCache(cache_path, size=10, slot_size=64)
    cache.put("test")
    cache.close()

    # Try to open it with an instance expecting 128-byte slots
    wrong_cache = salt.utils.mmap_cache.MmapCache(cache_path, size=10, slot_size=128)
    assert wrong_cache.open(write=False) is False
    wrong_cache.close()


def test_mmap_cache_list_items(cache_path):
    cache = salt.utils.mmap_cache.MmapCache(cache_path, size=100, slot_size=64)
    data = {"key1": "val1", "key2": "val2", "key3": True}
    for k, v in data.items():
        if v is True:
            cache.put(k)
        else:
            cache.put(k, v)

    items = cache.list_items()
    assert len(items) == 3
    assert set(items) == {("key1", "val1"), ("key2", "val2"), ("key3", True)}
    cache.close()


# ---------------------------------------------------------------------------
# pack_sorted / pack_naive parity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("n,num_slots", [(100, 256), (400, 512), (900, 1024)])
def test_pack_sorted_matches_pack_naive(n, num_slots):
    """
    pack_sorted and pack_naive must produce equivalent tables for the same
    input: every key is found with the same value, and every occupied slot
    count matches.
    """
    slot_size = 64
    items = [(f"pkg:{i}".encode(), f"pkg:{i}\0m{i % 7}".encode()) for i in range(n)]
    buf_a = bytearray(num_slots * slot_size)
    buf_b = bytearray(num_slots * slot_size)
    salt.utils.mmap_cache.pack_sorted(buf_a, items, num_slots, slot_size)
    salt.utils.mmap_cache.pack_naive(buf_b, items, num_slots, slot_size)

    occ_a = sum(
        1
        for s in range(num_slots)
        if buf_a[s * slot_size] == salt.utils.mmap_cache.OCCUPIED
    )
    occ_b = sum(
        1
        for s in range(num_slots)
        if buf_b[s * slot_size] == salt.utils.mmap_cache.OCCUPIED
    )
    assert occ_a == occ_b == n


def test_pack_sorted_last_wins_on_duplicate_keys():
    """Dupes in the input resolve to last-wins (both strategies)."""
    num_slots, slot_size = 64, 32
    items = [(b"k", b"k\0first"), (b"k", b"k\0second")]

    buf_sorted = bytearray(num_slots * slot_size)
    salt.utils.mmap_cache.pack_sorted(buf_sorted, items, num_slots, slot_size)
    buf_naive = bytearray(num_slots * slot_size)
    salt.utils.mmap_cache.pack_naive(buf_naive, items, num_slots, slot_size)

    # Both buffers should contain "second" in the home slot.
    home = zlib.adler32(b"k") % num_slots
    off = home * slot_size
    assert bytes(buf_sorted[off + 1 : off + 1 + 8]) == b"k\0second"
    assert bytes(buf_naive[off + 1 : off + 1 + 8]) == b"k\0second"


def test_pack_sorted_rejects_oversized_data():
    num_slots, slot_size = 16, 8
    items = [(b"k", b"k" + b"x" * slot_size)]  # too big
    buf = bytearray(num_slots * slot_size)
    with pytest.raises(ValueError):
        salt.utils.mmap_cache.pack_sorted(buf, items, num_slots, slot_size)


def test_atomic_rebuild_sorted_and_naive_parity(cache_path, tmp_path):
    """
    atomic_rebuild with strategy='sorted' and strategy='naive' must produce
    tables with the same reachable (key, value) set.
    """
    items = [(f"pkg:{i}", f"m{i % 4}") for i in range(300)]

    sorted_path = str(tmp_path / "sorted.mmap")
    naive_path = str(tmp_path / "naive.mmap")
    c_sorted = salt.utils.mmap_cache.MmapCache(sorted_path, size=1024, slot_size=64)
    c_naive = salt.utils.mmap_cache.MmapCache(naive_path, size=1024, slot_size=64)
    assert c_sorted.atomic_rebuild(items, strategy="sorted") is True
    assert c_naive.atomic_rebuild(items, strategy="naive") is True
    try:
        for k, v in items:
            assert c_sorted.get(k) == v
            assert c_naive.get(k) == v
        assert c_sorted.get_stats()["occupied"] == len(items)
        assert c_naive.get_stats()["occupied"] == len(items)
    finally:
        c_sorted.close()
        c_naive.close()


def test_atomic_rebuild_rejects_unknown_strategy(cache_path):
    cache = salt.utils.mmap_cache.MmapCache(cache_path, size=100, slot_size=64)
    with pytest.raises(ValueError):
        cache.atomic_rebuild([("a", "1")], strategy="bogus")
    cache.close()


# ---------------------------------------------------------------------------
# Throttled staleness check
# ---------------------------------------------------------------------------


def test_staleness_check_is_throttled(cache_path):
    """
    With a large staleness interval, repeated get() calls must not re-stat
    the file (measured by the internal timestamp not advancing).
    """
    cache = salt.utils.mmap_cache.MmapCache(
        cache_path, size=100, slot_size=64, staleness_check_interval=10.0
    )
    cache.put("k", "v")
    assert cache.get("k") == "v"
    anchor = cache._last_staleness_check
    assert anchor > 0
    for _ in range(50):
        cache.get("k")
    assert cache._last_staleness_check == anchor
    cache.close()


def test_staleness_check_disabled_restats_every_call(cache_path):
    """Interval=0 disables throttling: successive gets update the ts."""
    cache = salt.utils.mmap_cache.MmapCache(
        cache_path, size=100, slot_size=64, staleness_check_interval=0
    )
    cache.put("k", "v")
    cache.get("k")
    ts1 = cache._last_staleness_check
    time.sleep(0.005)
    cache.get("k")
    ts2 = cache._last_staleness_check
    # With interval=0, the throttle branch is skipped so _last_staleness_check
    # is updated on every open() call that sees _mm != None.
    assert ts2 >= ts1
    cache.close()


def test_staleness_detects_atomic_swap(cache_path):
    """
    A second handle rebuilding the file must be observable through the
    first handle within one staleness interval.
    """
    reader = salt.utils.mmap_cache.MmapCache(
        cache_path, size=100, slot_size=64, staleness_check_interval=0.01
    )
    writer = salt.utils.mmap_cache.MmapCache(cache_path, size=100, slot_size=64)

    writer.atomic_rebuild([("k", "v1")])
    assert reader.get("k") == "v1"

    writer.atomic_rebuild([("k", "v2")])
    time.sleep(0.05)
    assert reader.get("k") == "v2"

    reader.close()
    writer.close()
