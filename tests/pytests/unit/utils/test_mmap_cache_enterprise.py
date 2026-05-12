"""
Tests for the three enterprise-readiness items:

  Item 1 — Thread safety (threading.RLock + fcntl)
  Item 2 — Per-entry xxHash XXH3-64 checksums (verify_checksums=True/False)
  Item 3 — Roster/index divergence recovery (_roster_recover)
"""

import os
import struct
import threading
import time

import pytest
import xxhash

import salt.utils.files
from salt.utils.mmap_cache import _CRC_FMT, _CRC_SIZE, _ROSTER_ENTRY_SIZE, MmapCache

_SIZE = 200
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
# Item 1: Thread safety
# ---------------------------------------------------------------------------


def test_thread_lock_attribute_exists(cache):
    """MmapCache must expose _thread_lock (RLock)."""
    assert hasattr(cache, "_thread_lock")
    assert isinstance(cache._thread_lock, type(threading.RLock()))


def test_concurrent_puts_no_data_loss(cache_path):
    """N threads each writing distinct keys must all be readable afterwards."""
    n_threads = 8
    keys_per_thread = 20

    cache = MmapCache(
        cache_path,
        size=500,
        slot_size=_SLOT_SIZE,
        key_size=_KEY_SIZE,
    )
    errors = []

    def writer(tid):
        for i in range(keys_per_thread):
            key = f"t{tid}_k{i}"
            if not cache.put(key, f"val_{tid}_{i}"):
                errors.append(f"put failed: {key}")

    threads = [threading.Thread(target=writer, args=(t,)) for t in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    cache.close()
    assert not errors, f"Put failures: {errors}"

    cache2 = MmapCache(
        cache_path,
        size=500,
        slot_size=_SLOT_SIZE,
        key_size=_KEY_SIZE,
    )
    missing = []
    for tid in range(n_threads):
        for i in range(keys_per_thread):
            key = f"t{tid}_k{i}"
            if cache2.get(key) is None:
                missing.append(key)
    cache2.close()
    assert not missing, f"Keys missing after concurrent puts: {missing}"


def test_concurrent_mixed_ops_no_deadlock(cache_path):
    """Concurrent readers and writers must not deadlock within 5 s."""
    cache = MmapCache(
        cache_path,
        size=500,
        slot_size=_SLOT_SIZE,
        key_size=_KEY_SIZE,
    )
    stop = threading.Event()
    errors = []

    for i in range(10):
        cache.put(f"seed_{i}", f"v{i}")

    def reader():
        while not stop.is_set():
            cache.list_keys()
            cache.get("seed_0")

    def writer():
        i = 0
        while not stop.is_set():
            cache.put(f"w_{i}", f"wv_{i}")
            i += 1

    threads = [threading.Thread(target=reader) for _ in range(3)] + [
        threading.Thread(target=writer) for _ in range(2)
    ]
    for t in threads:
        t.start()

    time.sleep(0.5)
    stop.set()

    for t in threads:
        t.join(timeout=5)
        if t.is_alive():
            errors.append(f"Thread {t.name} did not finish (possible deadlock)")

    cache.close()
    assert not errors, errors


def test_thread_lock_is_reentrant(cache):
    """RLock must be re-entrant so that nested acquisitions within one thread work."""
    acquired = []
    with cache._thread_lock:
        acquired.append(1)
        with cache._thread_lock:
            acquired.append(2)
    assert acquired == [1, 2]


# ---------------------------------------------------------------------------
# Item 2: Per-entry CRC32 (verify_checksums)
# ---------------------------------------------------------------------------


def test_verify_checksums_default_is_true(cache_path):
    c = MmapCache(cache_path, size=_SIZE, slot_size=_SLOT_SIZE, key_size=_KEY_SIZE)
    assert c.verify_checksums is True
    c.close()


def test_verify_checksums_false_skips_crc(cache_path):
    c = MmapCache(
        cache_path,
        size=_SIZE,
        slot_size=_SLOT_SIZE,
        key_size=_KEY_SIZE,
        verify_checksums=False,
    )
    c.put("k", "hello")
    # Heap should contain raw bytes only — no checksum prefix
    with salt.utils.files.fopen(cache_path + ".heap", "rb") as f:
        raw = f.read()
    assert raw == b"hello"
    assert c.get("k") == "hello"
    c.close()


def test_verify_checksums_true_stores_crc_prefix(cache_path):
    c = MmapCache(
        cache_path,
        size=_SIZE,
        slot_size=_SLOT_SIZE,
        key_size=_KEY_SIZE,
        verify_checksums=True,
    )
    c.put("k", "hello")
    with salt.utils.files.fopen(cache_path + ".heap", "rb") as f:
        raw = f.read()
    # First 8 bytes are XXH3-64 LE, next bytes are the value
    assert len(raw) == _CRC_SIZE + len(b"hello")
    stored_digest = struct.unpack_from(_CRC_FMT, raw, 0)[0]
    assert stored_digest == xxhash.xxh3_64_intdigest(b"hello")
    assert raw[_CRC_SIZE:] == b"hello"
    c.close()


def test_get_returns_value_when_crc_valid(cache_path):
    c = MmapCache(
        cache_path,
        size=_SIZE,
        slot_size=_SLOT_SIZE,
        key_size=_KEY_SIZE,
        verify_checksums=True,
    )
    c.put("mykey", "myvalue")
    assert c.get("mykey") == "myvalue"
    c.close()


def test_get_returns_none_on_crc_corruption(cache_path, caplog):
    """Flipping a byte in the heap payload must cause get() to return None."""
    import logging

    c = MmapCache(
        cache_path,
        size=_SIZE,
        slot_size=_SLOT_SIZE,
        key_size=_KEY_SIZE,
        verify_checksums=True,
    )
    c.put("k", "important_data")
    c.close()

    # Corrupt the heap: flip a byte in the value region (after the checksum)
    heap_path = cache_path + ".heap"
    with salt.utils.files.fopen(heap_path, "r+b") as f:
        f.seek(_CRC_SIZE)
        b = f.read(1)
        f.seek(_CRC_SIZE)
        f.write(bytes([b[0] ^ 0xFF]))

    c2 = MmapCache(
        cache_path,
        size=_SIZE,
        slot_size=_SLOT_SIZE,
        key_size=_KEY_SIZE,
        verify_checksums=True,
    )
    with caplog.at_level(logging.ERROR, logger="salt.utils.mmap_cache"):
        result = c2.get("k")
    assert result is None
    assert "Checksum mismatch" in caplog.text
    c2.close()


def test_get_returns_none_on_crc_header_corruption(cache_path, caplog):
    """Flipping bytes in the stored checksum must cause get() to return None."""
    import logging

    c = MmapCache(
        cache_path,
        size=_SIZE,
        slot_size=_SLOT_SIZE,
        key_size=_KEY_SIZE,
        verify_checksums=True,
    )
    c.put("k", "data")
    c.close()

    heap_path = cache_path + ".heap"
    with salt.utils.files.fopen(heap_path, "r+b") as f:
        # Flip all 8 checksum bytes
        f.seek(0)
        crc_bytes = bytearray(f.read(_CRC_SIZE))
        for i in range(_CRC_SIZE):
            crc_bytes[i] ^= 0xFF
        f.seek(0)
        f.write(bytes(crc_bytes))

    c2 = MmapCache(
        cache_path,
        size=_SIZE,
        slot_size=_SLOT_SIZE,
        key_size=_KEY_SIZE,
        verify_checksums=True,
    )
    with caplog.at_level(logging.ERROR, logger="salt.utils.mmap_cache"):
        result = c2.get("k")
    assert result is None
    assert "Checksum mismatch" in caplog.text
    c2.close()


def test_truncated_heap_returns_none(cache_path, caplog):
    """A heap file truncated to fewer bytes than _CRC_SIZE must return None."""
    import logging

    c = MmapCache(
        cache_path,
        size=_SIZE,
        slot_size=_SLOT_SIZE,
        key_size=_KEY_SIZE,
        verify_checksums=True,
    )
    c.put("k", "somevalue")
    c.close()

    # Truncate heap to just 2 bytes
    heap_path = cache_path + ".heap"
    with salt.utils.files.fopen(heap_path, "r+b") as f:
        f.truncate(2)

    c2 = MmapCache(
        cache_path,
        size=_SIZE,
        slot_size=_SLOT_SIZE,
        key_size=_KEY_SIZE,
        verify_checksums=True,
    )
    with caplog.at_level(logging.ERROR, logger="salt.utils.mmap_cache"):
        result = c2.get("k")
    assert result is None
    assert "truncated" in caplog.text.lower() or "Checksum mismatch" in caplog.text
    c2.close()


def test_inplace_overwrite_crc_consistent(cache_path):
    """In-place overwrite must update the checksum so the new value reads back."""
    c = MmapCache(
        cache_path,
        size=_SIZE,
        slot_size=_SLOT_SIZE,
        key_size=_KEY_SIZE,
        verify_checksums=True,
    )
    c.put("k", "long_value_here")
    heap_before = os.path.getsize(cache_path + ".heap")

    c.put("k", "short")
    heap_after = os.path.getsize(cache_path + ".heap")

    assert heap_after == heap_before, "In-place overwrite must not grow heap"
    assert c.get("k") == "short"
    c.close()


def test_checksums_disabled_no_crc_overhead(cache_path):
    """With checksums disabled, heap size equals the raw value size."""
    c = MmapCache(
        cache_path,
        size=_SIZE,
        slot_size=_SLOT_SIZE,
        key_size=_KEY_SIZE,
        verify_checksums=False,
    )
    value = "x" * 100
    c.put("k", value)
    heap_size = os.path.getsize(cache_path + ".heap")
    assert heap_size == len(value.encode())
    c.close()


def test_none_value_stored_without_heap_entry(cache_path):
    """A None value must store length=0 and return True without heap access."""
    c = MmapCache(
        cache_path,
        size=_SIZE,
        slot_size=_SLOT_SIZE,
        key_size=_KEY_SIZE,
        verify_checksums=True,
    )
    c.put("flag", None)
    heap_size = os.path.getsize(cache_path + ".heap")
    assert heap_size == 0, "None value must not write to heap"
    assert c.get("flag") is True
    c.close()


def test_atomic_rebuild_respects_verify_checksums(cache_path):
    """atomic_rebuild must write checksum-prefixed heap records when checksums are on."""
    c = MmapCache(
        cache_path,
        size=_SIZE,
        slot_size=_SLOT_SIZE,
        key_size=_KEY_SIZE,
        verify_checksums=True,
    )
    data = [("key1", "value1"), ("key2", "value2")]
    c.atomic_rebuild(iter(data))

    heap_path = cache_path + ".heap"
    heap_size = os.path.getsize(heap_path)
    # Each value has an 8-byte XXH3-64 prefix
    expected = sum(_CRC_SIZE + len(v.encode()) for _, v in data)
    assert heap_size == expected

    for key, expected_val in data:
        assert c.get(key) == expected_val
    c.close()


# ---------------------------------------------------------------------------
# Item 3: Roster / index divergence (_roster_recover)
# ---------------------------------------------------------------------------


def _write_index_only(cache_path, key, value, size, slot_size, key_size):
    """
    Put a key via a cache with checksums disabled, then delete the roster file.
    This simulates a crash after the index write but before the roster append.
    """
    c = MmapCache(
        cache_path,
        size=size,
        slot_size=slot_size,
        key_size=key_size,
        verify_checksums=False,
    )
    c.put(key, value)
    c.close()
    # Blow away the roster to simulate the divergence
    roster_path = cache_path + ".roster"
    if os.path.exists(roster_path):
        os.remove(roster_path)


def test_roster_recover_missing_roster(cache_path, caplog):
    """open(write=True) must rebuild a missing roster from the index."""
    import logging

    _write_index_only(cache_path, "k1", "v1", _SIZE, _SLOT_SIZE, _KEY_SIZE)

    with caplog.at_level(logging.WARNING, logger="salt.utils.mmap_cache"):
        c = MmapCache(
            cache_path,
            size=_SIZE,
            slot_size=_SLOT_SIZE,
            key_size=_KEY_SIZE,
            verify_checksums=False,
        )
        # Trigger open(write=True)
        c.put("k2", "v2")

    assert "divergence" in caplog.text.lower() or os.path.exists(cache_path + ".roster")
    keys = c.list_keys()
    assert "k1" in keys
    assert "k2" in keys
    c.close()


def test_roster_recover_empty_roster_with_occupied_index(cache_path, caplog):
    """An empty roster while the header says occupied > 0 triggers recovery."""
    import logging

    c = MmapCache(
        cache_path,
        size=_SIZE,
        slot_size=_SLOT_SIZE,
        key_size=_KEY_SIZE,
        verify_checksums=False,
    )
    for i in range(5):
        c.put(f"key{i}", f"val{i}")
    c.close()

    # Zero-out the roster file (but keep it present)
    roster_path = cache_path + ".roster"
    with salt.utils.files.fopen(roster_path, "wb") as f:
        f.truncate(0)

    with caplog.at_level(logging.WARNING, logger="salt.utils.mmap_cache"):
        c2 = MmapCache(
            cache_path,
            size=_SIZE,
            slot_size=_SLOT_SIZE,
            key_size=_KEY_SIZE,
            verify_checksums=False,
        )
        c2.put("key5", "val5")

    keys = set(c2.list_keys())
    for i in range(6):
        assert f"key{i}" in keys, f"key{i} missing after roster recovery"
    c2.close()


def test_roster_recover_partial_roster(cache_path, caplog):
    """Roster with fewer entries than occupied triggers recovery."""
    import logging

    c = MmapCache(
        cache_path,
        size=_SIZE,
        slot_size=_SLOT_SIZE,
        key_size=_KEY_SIZE,
        verify_checksums=False,
    )
    for i in range(10):
        c.put(f"key{i}", f"val{i}")
    c.close()

    # Truncate roster to only 3 entries
    roster_path = cache_path + ".roster"
    with salt.utils.files.fopen(roster_path, "r+b") as f:
        f.truncate(3 * _ROSTER_ENTRY_SIZE)

    with caplog.at_level(logging.WARNING, logger="salt.utils.mmap_cache"):
        c2 = MmapCache(
            cache_path,
            size=_SIZE,
            slot_size=_SLOT_SIZE,
            key_size=_KEY_SIZE,
            verify_checksums=False,
        )
        c2.put("key10", "val10")

    keys = set(c2.list_keys())
    for i in range(11):
        assert f"key{i}" in keys, f"key{i} missing after partial roster recovery"
    c2.close()


def test_roster_recover_logs_warning(cache_path, caplog):
    """_roster_recover must log a WARNING when it detects divergence."""
    import logging

    c = MmapCache(
        cache_path,
        size=_SIZE,
        slot_size=_SLOT_SIZE,
        key_size=_KEY_SIZE,
        verify_checksums=False,
    )
    c.put("k", "v")
    c.close()

    os.remove(cache_path + ".roster")

    with caplog.at_level(logging.WARNING, logger="salt.utils.mmap_cache"):
        c2 = MmapCache(
            cache_path,
            size=_SIZE,
            slot_size=_SLOT_SIZE,
            key_size=_KEY_SIZE,
            verify_checksums=False,
        )
        c2.put("k2", "v2")
    assert any("divergence" in r.message.lower() for r in caplog.records)
    c2.close()


def test_roster_recover_noop_when_consistent(cache_path, caplog):
    """_roster_recover must NOT log a warning when roster and index are in sync."""
    import logging

    c = MmapCache(
        cache_path,
        size=_SIZE,
        slot_size=_SLOT_SIZE,
        key_size=_KEY_SIZE,
        verify_checksums=False,
    )
    for i in range(5):
        c.put(f"key{i}", f"val{i}")
    c.close()

    with caplog.at_level(logging.WARNING, logger="salt.utils.mmap_cache"):
        c2 = MmapCache(
            cache_path,
            size=_SIZE,
            slot_size=_SLOT_SIZE,
            key_size=_KEY_SIZE,
            verify_checksums=False,
        )
        # Trigger open(write=True)
        c2.put("extra", "val")
    assert not any("divergence" in r.message.lower() for r in caplog.records)
    c2.close()


def test_get_still_works_after_roster_recovery(cache_path):
    """get() must return correct values for all keys after roster repair."""
    c = MmapCache(
        cache_path,
        size=_SIZE,
        slot_size=_SLOT_SIZE,
        key_size=_KEY_SIZE,
        verify_checksums=False,
    )
    expected = {f"key{i}": f"val{i}" for i in range(8)}
    for k, v in expected.items():
        c.put(k, v)
    c.close()

    os.remove(cache_path + ".roster")

    c2 = MmapCache(
        cache_path,
        size=_SIZE,
        slot_size=_SLOT_SIZE,
        key_size=_KEY_SIZE,
        verify_checksums=False,
    )
    c2.put("extra", "xtra")
    for k, v in expected.items():
        assert c2.get(k) == v, f"Wrong value for {k}"
    c2.close()


def test_roster_recover_fixes_header_occupied_count(cache_path):
    """If the index scan finds a different count than the header, correct it."""
    c = MmapCache(
        cache_path,
        size=_SIZE,
        slot_size=_SLOT_SIZE,
        key_size=_KEY_SIZE,
        verify_checksums=False,
    )
    for i in range(5):
        c.put(f"key{i}", f"val{i}")
    c.close()

    # Corrupt the header occupied count to 99
    import mmap as _mmap

    from salt.utils.mmap_cache import _HDR_OCCUPIED_OFF, _OFFSET_FMT

    with salt.utils.files.fopen(cache_path, "r+b") as f:
        mm = _mmap.mmap(f.fileno(), 0, access=_mmap.ACCESS_WRITE)
        struct.pack_into(_OFFSET_FMT, mm, _HDR_OCCUPIED_OFF, 99)
        mm.flush()
        mm.close()
    # Blow away the roster too so recovery is triggered
    os.remove(cache_path + ".roster")

    c2 = MmapCache(
        cache_path,
        size=_SIZE,
        slot_size=_SLOT_SIZE,
        key_size=_KEY_SIZE,
        verify_checksums=False,
    )
    c2.put("trigger", "x")

    stats = c2.get_stats()
    # After recovery the occupied count must reflect reality (5 original + trigger)
    assert stats["occupied"] == 6
    c2.close()
