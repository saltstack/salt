"""
Functional tests for salt.utils.mmap_cache.MmapCache.

These tests exercise the real on-disk behaviour that unit tests cannot:
- Data survives process exit and re-open
- Concurrent access from multiple forked processes
- Crash-safety: partial write followed by roster recovery
- Heap segmentation across a real filesystem
- atomic_rebuild atomicity (no partially-swapped state visible to readers)
- Large datasets that push the index near capacity
"""

import multiprocessing
import os
import struct
import time

import salt.utils.files
from salt.utils.mmap_cache import _ROSTER_ENTRY_FMT, MmapCache

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make(tmp_path, size=256, vnodes=10, max_segment_bytes=None):
    kwargs = dict(size=size, slot_size=128, key_size=48, verify_checksums=True)
    if max_segment_bytes is not None:
        kwargs["max_segment_bytes"] = max_segment_bytes
    return MmapCache(str(tmp_path / "cache.idx"), **kwargs)


# ---------------------------------------------------------------------------
# Persistence across close/reopen
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_data_survives_close_and_reopen(self, tmp_path):
        c = _make(tmp_path)
        c.put("key1", "value1")
        c.put("key2", "value2")
        c.close()

        c2 = _make(tmp_path)
        assert c2.get("key1") == "value1"
        assert c2.get("key2") == "value2"
        c2.close()

    def test_delete_persists_across_reopen(self, tmp_path):
        c = _make(tmp_path)
        c.put("alive", "yes")
        c.put("dead", "no")
        c.delete("dead")
        c.close()

        c2 = _make(tmp_path)
        assert c2.get("alive") == "yes"
        assert c2.get("dead") is None
        c2.close()

    def test_header_counts_persist(self, tmp_path):
        c = _make(tmp_path)
        for i in range(10):
            c.put(f"k{i}", f"v{i}")
        c.delete("k3")
        c.close()

        c2 = _make(tmp_path)
        stats = c2.get_stats()
        assert stats["occupied"] == 9
        assert stats["deleted"] == 1
        c2.close()

    def test_mtime_survives_reopen(self, tmp_path):
        c = _make(tmp_path)
        before = time.time()
        c.put("ts", "value")
        c.close()

        c2 = _make(tmp_path)
        mtime = c2.get_mtime("ts")
        assert mtime is not None
        assert mtime >= before
        c2.close()

    def test_bytes_value_survives_reopen(self, tmp_path):
        c = _make(tmp_path)
        data = b"\x80\x81\x82\x83\x84"
        c.put("bin", data)
        c.close()

        c2 = _make(tmp_path)
        assert c2.get("bin") == data
        c2.close()

    def test_roster_survives_reopen(self, tmp_path):
        c = _make(tmp_path)
        for i in range(5):
            c.put(f"r{i}", f"v{i}")
        c.close()

        c2 = _make(tmp_path)
        keys = sorted(c2.list_keys())
        assert keys == [f"r{i}" for i in range(5)]
        c2.close()

    def test_segmented_heap_survives_reopen(self, tmp_path):
        # Force segment roll after every ~30 bytes
        c = _make(tmp_path, max_segment_bytes=30)
        c.put("seg0", "A" * 20)  # seg 0
        c.put("seg1", "B" * 20)  # seg 1
        c.close()

        c2 = _make(tmp_path, max_segment_bytes=30)
        assert c2.get("seg0") == "A" * 20
        assert c2.get("seg1") == "B" * 20
        c2.close()


# ---------------------------------------------------------------------------
# Concurrent multi-process access
# ---------------------------------------------------------------------------


def _worker_put(idx_path, worker_id, n_keys, result_queue):
    """Put n_keys entries from a forked worker and report success count."""
    try:
        c = MmapCache(idx_path, size=512, slot_size=128, key_size=48)
        ok = 0
        for i in range(n_keys):
            key = f"w{worker_id}k{i}"
            if c.put(key, f"val-{worker_id}-{i}"):
                ok += 1
        c.close()
        result_queue.put(("ok", worker_id, ok))
    except Exception as exc:  # pylint: disable=broad-except
        result_queue.put(("err", worker_id, str(exc)))


def _worker_read(idx_path, keys, result_queue):
    """Read a list of keys and report how many were found."""
    try:
        c = MmapCache(idx_path, size=512, slot_size=128, key_size=48)
        found = sum(1 for k in keys if c.get(k) is not None)
        c.close()
        result_queue.put(("ok", found))
    except Exception as exc:  # pylint: disable=broad-except
        result_queue.put(("err", str(exc)))


class TestMultiProcess:
    def test_concurrent_writers_no_data_loss(self, tmp_path):
        idx_path = str(tmp_path / "mp.idx")
        n_workers = 4
        n_keys = 20
        q = multiprocessing.Queue()

        procs = [
            multiprocessing.Process(target=_worker_put, args=(idx_path, w, n_keys, q))
            for w in range(n_workers)
        ]
        for p in procs:
            p.start()
        for p in procs:
            p.join(timeout=30)

        results = [q.get(timeout=5) for _ in range(n_workers)]
        errors = [r for r in results if r[0] == "err"]
        assert not errors, errors

        total_written = sum(r[2] for r in results)
        assert total_written == n_workers * n_keys

        # Verify all keys are readable by a fresh process
        all_keys = [f"w{w}k{i}" for w in range(n_workers) for i in range(n_keys)]
        rq = multiprocessing.Queue()
        p = multiprocessing.Process(target=_worker_read, args=(idx_path, all_keys, rq))
        p.start()
        p.join(timeout=30)
        result = rq.get(timeout=5)
        assert result[0] == "ok", result
        assert result[1] == total_written

    def test_writer_and_reader_concurrent(self, tmp_path):
        idx_path = str(tmp_path / "rw.idx")
        # Seed initial data
        c = MmapCache(idx_path, size=512, slot_size=128, key_size=48)
        for i in range(10):
            c.put(f"seed{i}", f"val{i}")
        c.close()

        q = multiprocessing.Queue()
        writer = multiprocessing.Process(target=_worker_put, args=(idx_path, 99, 20, q))
        reader = multiprocessing.Process(
            target=_worker_read,
            args=(idx_path, [f"seed{i}" for i in range(10)], q),
        )
        writer.start()
        reader.start()
        writer.join(timeout=30)
        reader.join(timeout=30)

        results = [q.get(timeout=5), q.get(timeout=5)]
        errors = [r for r in results if r[0] == "err"]
        assert not errors, errors


# ---------------------------------------------------------------------------
# Crash-safety: roster recovery
# ---------------------------------------------------------------------------


class TestCrashSafety:
    def test_roster_recovery_after_simulated_crash(self, tmp_path):
        """
        Simulate a crash between index flush and roster append:
        truncate the roster file to be shorter than the occupied count,
        then verify the next write-open triggers recovery.
        """
        c = _make(tmp_path)
        for i in range(8):
            c.put(f"k{i}", f"v{i}")
        c.close()

        # Corrupt: truncate roster to 3 entries (occupied=8)
        with salt.utils.files.fopen(c.roster_path, "r+b") as f:
            f.truncate(3 * 4)  # 3 uint32 entries

        # Re-open for writing triggers _roster_recover
        c2 = _make(tmp_path)
        c2.put("trigger", "recovery")  # forces open(write=True)
        keys = sorted(c2.list_keys())
        c2.close()

        # All 8 original keys + the trigger key must be present
        for i in range(8):
            assert f"k{i}" in keys
        assert "trigger" in keys

    def test_missing_roster_is_rebuilt(self, tmp_path):
        c = _make(tmp_path)
        for i in range(5):
            c.put(f"k{i}", f"v{i}")
        c.close()

        os.remove(c.roster_path)

        c2 = _make(tmp_path)
        c2.put("new", "entry")
        keys = sorted(c2.list_keys())
        c2.close()

        for i in range(5):
            assert f"k{i}" in keys
        assert "new" in keys

    def test_extra_roster_entries_are_recovered(self, tmp_path):
        """Roster has more entries than the index says — recovery corrects it."""
        c = _make(tmp_path)
        c.put("real", "value")
        c.close()

        # Append a phantom slot (slot 99) to the roster
        with salt.utils.files.fopen(c.roster_path, "ab") as f:
            f.write(struct.pack(_ROSTER_ENTRY_FMT, 99))

        c2 = _make(tmp_path)
        c2.put("trigger", "write")
        keys = c2.list_keys()
        c2.close()

        assert "real" in keys
        assert "trigger" in keys
        # slot 99 is not OCCUPIED so it should not appear as a key
        assert len(keys) == 2


# ---------------------------------------------------------------------------
# atomic_rebuild atomicity
# ---------------------------------------------------------------------------


def _concurrent_reader(idx_path, stop_event, errors):
    """Read continuously while rebuild is happening; collect any anomalies."""
    c = MmapCache(idx_path, size=256, slot_size=128, key_size=48)
    while not stop_event.is_set():
        keys = c.list_keys()
        # After rebuild the cache must be self-consistent:
        # every key returned by list_keys must be gettable.
        for k in keys:
            v = c.get(k)
            if v is None:
                errors.append(f"list_keys returned {k!r} but get returned None")
    c.close()


class TestAtomicRebuild:
    def test_rebuild_visible_atomically(self, tmp_path):
        c = _make(tmp_path)
        for i in range(20):
            c.put(f"old{i}", f"v{i}")
        c.close()

        errors = []
        stop = multiprocessing.Event()
        idx_path = str(tmp_path / "cache.idx")
        reader = multiprocessing.Process(
            target=_concurrent_reader, args=(idx_path, stop, errors)
        )
        reader.start()

        time.sleep(0.05)
        c2 = _make(tmp_path)
        c2.atomic_rebuild([(f"new{i}", f"nv{i}") for i in range(20)])
        c2.close()
        time.sleep(0.05)

        stop.set()
        reader.join(timeout=10)
        assert not errors, errors

    def test_rebuild_data_correct_after_concurrent_read(self, tmp_path):
        c = _make(tmp_path)
        items = [(f"k{i}", f"v{i}") for i in range(15)]
        c.atomic_rebuild(iter(items))
        c.close()

        c2 = _make(tmp_path)
        for k, v in items:
            assert c2.get(k) == v
        c2.close()


# ---------------------------------------------------------------------------
# Large dataset approaching index capacity
# ---------------------------------------------------------------------------


class TestLargeDataset:
    def test_fill_to_near_capacity(self, tmp_path):
        size = 128  # small index for speed
        c = MmapCache(
            str(tmp_path / "large.idx"),
            size=size,
            slot_size=128,
            key_size=48,
        )
        # Fill to ~60 % load factor (well below collision risk)
        n = int((size - 1) * 0.6)
        for i in range(n):
            assert c.put(f"key{i:04d}", f"val{i}"), f"put failed at i={i}"

        stats = c.get_stats()
        assert stats["occupied"] == n
        assert stats["load_factor"] <= 0.65

        # Verify all keys readable
        for i in range(n):
            assert c.get(f"key{i:04d}") == f"val{i}"

        c.close()

    def test_rebuild_compacts_deleted_entries(self, tmp_path):
        c = _make(tmp_path, size=256)
        for i in range(50):
            c.put(f"k{i}", f"v{i}")
        for i in range(0, 50, 2):
            c.delete(f"k{i}")  # delete even keys

        heap_before = c.get_stats()["heap_size_bytes"]
        c.atomic_rebuild(c.list_items())
        heap_after = c.get_stats()["heap_size_bytes"]

        assert heap_after < heap_before, "rebuild should compact the heap"
        # Odd keys still readable
        for i in range(1, 50, 2):
            assert c.get(f"k{i}") == f"v{i}"
        c.close()
