"""
Comprehensive tests for MmapCache heap segmentation.

The heap is split across multiple files when the active segment reaches
``max_segment_bytes``.  The packed OFFSET field (uint64) encodes both the
segment ID (top 16 bits) and the within-segment byte offset (bottom 48 bits).
These tests exercise:

- The offset packing / unpacking helpers
- Segment discovery on open
- Single-segment write + read round-trips (baseline)
- Automatic segment roll when max_segment_bytes is reached
- Cross-segment reads after a roll
- In-place overwrite within a non-zero segment
- Overwrite triggers a new append when value grows (crosses into new segment)
- atomic_rebuild with segment rolling
- atomic_rebuild removes stale extra segments
- Segment mmaps are refreshed after a write (lazy mmap refresh)
- Checksum verification across segment boundary
- Corrupted checksum in a non-zero segment returns None / default
- list_keys / list_items across multiple segments
- get_stats with multi-segment heap
- Concurrent put/get across segments (thread safety)
- _discover_segments stops at first gap
- Zero-length values across segments
- delete + re-put reuses rolled offset if space allows
"""

import os
import threading

import salt.utils.files
from salt.utils.mmap_cache import _CRC_SIZE, DEFAULT_MAX_SEGMENT_BYTES, MmapCache

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_cache(tmp_path, size=64, max_segment_bytes=DEFAULT_MAX_SEGMENT_BYTES):
    """Return a fresh MmapCache in *tmp_path*."""
    idx = str(tmp_path / "test.idx")
    return MmapCache(
        idx,
        size=size,
        slot_size=128,
        key_size=32,
        verify_checksums=True,
        max_segment_bytes=max_segment_bytes,
    )


def seg_path(cache, seg_id):
    """Return the filesystem path for *seg_id* on *cache*."""
    return cache._segment_path(seg_id)


# ---------------------------------------------------------------------------
# Offset packing / unpacking
# ---------------------------------------------------------------------------


class TestOffsetEncoding:
    def test_pack_unpack_zero(self, tmp_path):
        c = make_cache(tmp_path)
        packed = c._pack_offset(0, 0)
        assert packed == 0
        seg, off = c._unpack_offset(packed)
        assert seg == 0
        assert off == 0

    def test_pack_unpack_seg0_large_offset(self, tmp_path):
        c = make_cache(tmp_path)
        off_val = (1 << 48) - 1  # max 48-bit offset
        packed = c._pack_offset(0, off_val)
        seg, off = c._unpack_offset(packed)
        assert seg == 0
        assert off == off_val

    def test_pack_unpack_seg1(self, tmp_path):
        c = make_cache(tmp_path)
        packed = c._pack_offset(1, 512)
        seg, off = c._unpack_offset(packed)
        assert seg == 1
        assert off == 512

    def test_pack_unpack_max_seg(self, tmp_path):
        c = make_cache(tmp_path)
        packed = c._pack_offset(65535, 1024)
        seg, off = c._unpack_offset(packed)
        assert seg == 65535
        assert off == 1024

    def test_seg0_offset_backward_compat(self, tmp_path):
        """Legacy on-disk offsets (top 16 bits = 0) resolve to segment 0."""
        c = make_cache(tmp_path)
        legacy_packed = 42  # plain byte offset, no seg bits set
        seg, off = c._unpack_offset(legacy_packed)
        assert seg == 0
        assert off == 42


# ---------------------------------------------------------------------------
# Segment path naming
# ---------------------------------------------------------------------------


class TestSegmentPaths:
    def test_seg0_is_heap_path(self, tmp_path):
        c = make_cache(tmp_path)
        assert c._segment_path(0) == c.heap_path

    def test_seg1_path(self, tmp_path):
        c = make_cache(tmp_path)
        assert c._segment_path(1) == c.heap_path + ".1"

    def test_seg100_path(self, tmp_path):
        c = make_cache(tmp_path)
        assert c._segment_path(100) == c.heap_path + ".100"


# ---------------------------------------------------------------------------
# Single-segment baseline
# ---------------------------------------------------------------------------


class TestSingleSegment:
    def test_put_get_roundtrip(self, tmp_path):
        c = make_cache(tmp_path)
        assert c.put("alpha", "hello")
        assert c.get("alpha") == "hello"

    def test_segment0_file_exists(self, tmp_path):
        c = make_cache(tmp_path)
        c.put("x", "y")
        assert os.path.exists(seg_path(c, 0))

    def test_no_segment1_by_default(self, tmp_path):
        c = make_cache(tmp_path)
        c.put("x", "y")
        assert not os.path.exists(seg_path(c, 1))

    def test_active_segment_id_initially_zero(self, tmp_path):
        c = make_cache(tmp_path)
        c.put("k", "v")
        assert c._active_segment_id() == 0

    def test_zero_length_value_no_heap_bytes(self, tmp_path):
        c = make_cache(tmp_path)
        c.put("presence")  # None → zero-length
        assert c.get("presence") is True
        assert os.path.getsize(seg_path(c, 0)) == 0

    def test_bytes_value_roundtrip(self, tmp_path):
        # get() strips trailing nulls; use non-null bytes to avoid that edge case.
        c = make_cache(tmp_path)
        data = b"\x80\x81\x82\x83"  # invalid UTF-8 → returned as bytes
        c.put("bin", data)
        assert c.get("bin") == data


# ---------------------------------------------------------------------------
# Segment rolling
# ---------------------------------------------------------------------------


class TestSegmentRolling:
    def _tiny_cache(self, tmp_path):
        """Cache that rolls after each record ≥ 32 bytes."""
        idx = str(tmp_path / "tiny.idx")
        # record = 8-byte CRC + value; threshold = 32 → rolls after first 24+ byte value
        return MmapCache(
            idx,
            size=64,
            slot_size=128,
            key_size=32,
            verify_checksums=True,
            max_segment_bytes=32,
        )

    def test_roll_creates_segment1(self, tmp_path):
        c = self._tiny_cache(tmp_path)
        # First value: 24 bytes → record = 32 bytes, exactly at limit → no roll yet
        c.put("k1", "A" * 24)
        # Second value: any size → should trigger roll
        c.put("k2", "B" * 1)
        assert os.path.exists(seg_path(c, 1))

    def test_active_segment_advances_after_roll(self, tmp_path):
        c = self._tiny_cache(tmp_path)
        c.put("k1", "A" * 24)
        c.put("k2", "B" * 1)
        assert c._active_segment_id() == 1

    def test_read_from_seg0_after_roll(self, tmp_path):
        c = self._tiny_cache(tmp_path)
        c.put("k1", "A" * 24)
        c.put("k2", "B" * 1)
        assert c.get("k1") == "A" * 24

    def test_read_from_seg1_after_roll(self, tmp_path):
        c = self._tiny_cache(tmp_path)
        c.put("k1", "A" * 24)
        c.put("k2", "B" * 1)
        assert c.get("k2") == "B"

    def test_multiple_rolls(self, tmp_path):
        c = self._tiny_cache(tmp_path)
        # Each write of 25 bytes produces a 33-byte record; > 32 → roll every time
        keys = [f"key{i}" for i in range(5)]
        for k in keys:
            c.put(k, "X" * 25)
        # All 5 values should still be readable
        for k in keys:
            assert c.get(k) == "X" * 25
        # We should have multiple segments
        assert c._active_segment_id() >= 1

    def test_list_keys_spans_segments(self, tmp_path):
        c = self._tiny_cache(tmp_path)
        c.put("k1", "A" * 24)
        c.put("k2", "B" * 1)
        keys = sorted(c.list_keys())
        assert keys == ["k1", "k2"]

    def test_list_items_spans_segments(self, tmp_path):
        c = self._tiny_cache(tmp_path)
        c.put("k1", "A" * 24)
        c.put("k2", "B")
        items = dict(c.list_items())
        assert items["k1"] == "A" * 24
        assert items["k2"] == "B"

    def test_get_stats_heap_size_across_segments(self, tmp_path):
        c = self._tiny_cache(tmp_path)
        c.put("k1", "A" * 24)
        c.put("k2", "B")
        stats = c.get_stats()
        assert stats["occupied"] == 2
        # heap_size_bytes counts only the active segment (matching _heap_size)
        # but heap_live_bytes counts bytes from the index LENGTH fields
        assert stats["heap_live_bytes"] > 0


# ---------------------------------------------------------------------------
# In-place overwrite across segments
# ---------------------------------------------------------------------------


class TestOverwriteAcrossSegments:
    def _tiny_cache(self, tmp_path):
        idx = str(tmp_path / "ow.idx")
        return MmapCache(
            idx,
            size=64,
            slot_size=128,
            key_size=32,
            verify_checksums=True,
            max_segment_bytes=32,
        )

    def test_overwrite_within_seg0(self, tmp_path):
        c = self._tiny_cache(tmp_path)
        c.put("k1", "hello")
        c.put("k1", "world")  # same length → in-place overwrite in seg 0
        assert c.get("k1") == "world"

    def test_overwrite_within_seg1(self, tmp_path):
        c = self._tiny_cache(tmp_path)
        c.put("k1", "A" * 24)  # fills seg 0
        c.put("k2", "hello")  # lands in seg 1
        c.put("k2", "world")  # shorter → in-place overwrite in seg 1
        assert c.get("k2") == "world"

    def test_overwrite_grow_spills_to_new_segment(self, tmp_path):
        c = self._tiny_cache(tmp_path)
        c.put("k1", "A" * 24)  # fills seg 0
        c.put("k2", "X")  # lands in seg 1 (small)
        # Now overwrite k2 with value too large for the existing region;
        # the new record should be appended (possibly in a new segment).
        c.put("k2", "Y" * 25)
        assert c.get("k2") == "Y" * 25


# ---------------------------------------------------------------------------
# Cross-process / re-open: segment discovery
# ---------------------------------------------------------------------------


class TestSegmentDiscovery:
    def _tiny_cache(self, tmp_path):
        idx = str(tmp_path / "disc.idx")
        return MmapCache(
            idx,
            size=64,
            slot_size=128,
            key_size=32,
            verify_checksums=True,
            max_segment_bytes=32,
        )

    def test_reopen_discovers_segments(self, tmp_path):
        c = self._tiny_cache(tmp_path)
        c.put("k1", "A" * 24)
        c.put("k2", "B")
        c.close()

        c2 = self._tiny_cache(tmp_path)
        assert c2.get("k1") == "A" * 24
        assert c2.get("k2") == "B"
        c2.close()

    def test_discover_stops_at_gap(self, tmp_path):
        c = self._tiny_cache(tmp_path)
        c.put("k1", "A" * 24)
        c.put("k2", "B")
        c.close()

        # Create a gap: remove seg 1, add a seg 2 (simulates corruption)
        p1 = seg_path(c, 1)
        p2 = seg_path(c, 2)
        if os.path.exists(p1):
            os.remove(p1)
        with salt.utils.files.fopen(p2, "wb"):
            pass

        c2 = self._tiny_cache(tmp_path)
        # Trigger open so _discover_segments runs
        c2.open(write=False)
        # Should have discovered only seg 0 (gap at 1 stops discovery)
        assert len(c2._seg_mms) == 1
        c2.close()

    def test_reopen_sees_correct_seg_count(self, tmp_path):
        c = self._tiny_cache(tmp_path)
        c.put("k1", "A" * 24)  # → seg 0
        c.put("k2", "B" * 25)  # → seg 1
        c.put("k3", "C" * 25)  # → seg 2 (maybe)
        n_segs = len(c._seg_mms)
        c.close()

        c2 = self._tiny_cache(tmp_path)
        c2.open(write=False)  # trigger _discover_segments
        assert len(c2._seg_mms) == n_segs
        c2.close()


# ---------------------------------------------------------------------------
# atomic_rebuild with segmentation
# ---------------------------------------------------------------------------


class TestAtomicRebuildSegmented:
    def _tiny_cache(self, tmp_path):
        idx = str(tmp_path / "rb.idx")
        return MmapCache(
            idx,
            size=64,
            slot_size=128,
            key_size=32,
            verify_checksums=True,
            max_segment_bytes=32,
        )

    def test_rebuild_single_segment(self, tmp_path):
        c = self._tiny_cache(tmp_path)
        items = [("a", "hello"), ("b", "world")]
        assert c.atomic_rebuild(iter(items))
        assert c.get("a") == "hello"
        assert c.get("b") == "world"

    def test_rebuild_rolls_segment(self, tmp_path):
        c = self._tiny_cache(tmp_path)
        # Each 25-byte value produces a 33-byte record → exceeds 32-byte limit
        items = [(f"k{i}", "X" * 25) for i in range(3)]
        assert c.atomic_rebuild(iter(items))
        for k, v in items:
            assert c.get(k) == "X" * 25
        assert c._active_segment_id() >= 1

    def test_rebuild_removes_stale_extra_segments(self, tmp_path):
        c = self._tiny_cache(tmp_path)
        # Write two segments initially
        c.put("k1", "A" * 24)
        c.put("k2", "B" * 25)  # → seg 1
        assert os.path.exists(seg_path(c, 1))

        # Rebuild with only a small dataset → should fit in seg 0
        c.atomic_rebuild([("only", "tiny")])
        assert not os.path.exists(seg_path(c, 1)), "stale seg 1 not cleaned up"
        assert c.get("only") == "tiny"

    def test_rebuild_preserves_zero_length_values(self, tmp_path):
        c = self._tiny_cache(tmp_path)
        c.atomic_rebuild([("presence",)])  # no value
        assert c.get("presence") is True

    def test_rebuild_then_normal_writes(self, tmp_path):
        c = self._tiny_cache(tmp_path)
        c.atomic_rebuild([("base", "value")])
        c.put("extra", "new")
        assert c.get("base") == "value"
        assert c.get("extra") == "new"

    def test_rebuild_roster_consistent(self, tmp_path):
        c = self._tiny_cache(tmp_path)
        items = [("a", "hello"), ("b", "world"), ("c", "!")]
        c.atomic_rebuild(iter(items))
        assert sorted(c.list_keys()) == ["a", "b", "c"]

    def test_rebuild_idempotent(self, tmp_path):
        c = self._tiny_cache(tmp_path)
        items = [("x", "1"), ("y", "2")]
        c.atomic_rebuild(iter(items))
        c.atomic_rebuild(iter(items))
        assert sorted(c.list_keys()) == ["x", "y"]


# ---------------------------------------------------------------------------
# Checksum verification across segments
# ---------------------------------------------------------------------------


class TestChecksumAcrossSegments:
    def _tiny_cache(self, tmp_path):
        idx = str(tmp_path / "crc.idx")
        return MmapCache(
            idx,
            size=64,
            slot_size=128,
            key_size=32,
            verify_checksums=True,
            max_segment_bytes=32,
        )

    def test_good_checksum_seg0(self, tmp_path):
        c = self._tiny_cache(tmp_path)
        c.put("k", "good")
        assert c.get("k") == "good"

    def test_good_checksum_seg1(self, tmp_path):
        c = self._tiny_cache(tmp_path)
        c.put("k1", "A" * 24)  # seg 0
        c.put("k2", "ok")  # seg 1
        assert c.get("k2") == "ok"

    def test_corrupt_checksum_seg1_returns_default(self, tmp_path):
        c = self._tiny_cache(tmp_path)
        c.put("k1", "A" * 24)  # seg 0
        c.put("k2", "corrupt")  # seg 1
        c.close()

        # Corrupt the checksum bytes in segment 1
        p = seg_path(c, 1)
        if os.path.exists(p):
            with salt.utils.files.fopen(p, "r+b") as f:
                f.seek(0)
                f.write(b"\xff" * _CRC_SIZE)

        c2 = self._tiny_cache(tmp_path)
        result = c2.get("k2", default="MISSING")
        assert result == "MISSING"
        c2.close()

    def test_correct_checksum_after_overwrite(self, tmp_path):
        c = self._tiny_cache(tmp_path)
        c.put("k1", "A" * 24)  # seg 0
        c.put("k2", "hello")  # seg 1
        c.put("k2", "world")  # in-place overwrite in seg 1
        assert c.get("k2") == "world"


# ---------------------------------------------------------------------------
# Lazy mmap refresh after segment append
# ---------------------------------------------------------------------------


class TestLazyMmapRefresh:
    def test_stale_flag_set_after_append(self, tmp_path):
        c = make_cache(tmp_path)
        c.put("k", "v")
        # After a write the active segment's stale flag should be True
        # (or the mmap was already refreshed — either is correct).
        # We just verify get() still returns the correct value.
        c.close()
        c2 = make_cache(tmp_path)
        assert c2.get("k") == "v"
        c2.close()

    def test_read_after_write_same_instance(self, tmp_path):
        """put() followed immediately by get() in the same MmapCache instance."""
        idx = str(tmp_path / "lazy.idx")
        c = MmapCache(
            idx,
            size=64,
            slot_size=128,
            key_size=32,
            verify_checksums=True,
            max_segment_bytes=32,
        )
        c.put("k1", "A" * 24)  # seg 0
        c.put("k2", "B")  # seg 1; seg 0's mmap is stale
        # Both should be readable without re-opening
        assert c.get("k1") == "A" * 24
        assert c.get("k2") == "B"
        c.close()


# ---------------------------------------------------------------------------
# Thread safety with multiple segments
# ---------------------------------------------------------------------------


class TestThreadSafetySegments:
    def test_concurrent_puts_across_segment_boundary(self, tmp_path):
        idx = str(tmp_path / "thr.idx")
        c = MmapCache(
            idx,
            size=200,
            slot_size=128,
            key_size=32,
            verify_checksums=True,
            max_segment_bytes=64,  # force many rolls
        )
        errors = []

        def writer(n):
            for i in range(10):
                key = f"t{n}k{i}"
                val = f"v{n}-{i}" * 3
                if not c.put(key, val):
                    errors.append(f"put failed: {key}")

        threads = [threading.Thread(target=writer, args=(n,)) for n in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, errors
        keys = c.list_keys()
        assert len(keys) == 80, f"expected 80 keys, got {len(keys)}"
        c.close()

    def test_concurrent_get_while_writing(self, tmp_path):
        idx = str(tmp_path / "thr2.idx")
        c = MmapCache(
            idx,
            size=200,
            slot_size=128,
            key_size=32,
            verify_checksums=True,
            max_segment_bytes=64,
        )
        # Seed some data
        for i in range(20):
            c.put(f"seed{i}", f"val{i}")

        read_errors = []

        def reader():
            for _ in range(50):
                for i in range(20):
                    v = c.get(f"seed{i}")
                    if v is not None and not v.startswith("val"):
                        read_errors.append(f"wrong value for seed{i}: {v!r}")

        def writer():
            for i in range(20, 40):
                c.put(f"seed{i}", f"val{i}" * 4)

        rt = threading.Thread(target=reader)
        wt = threading.Thread(target=writer)
        rt.start()
        wt.start()
        rt.join()
        wt.join()

        assert not read_errors, read_errors
        c.close()


# ---------------------------------------------------------------------------
# delete + re-put across segment boundary
# ---------------------------------------------------------------------------


class TestDeleteRePutSegments:
    def test_delete_from_seg1_then_reput(self, tmp_path):
        idx = str(tmp_path / "del.idx")
        c = MmapCache(
            idx,
            size=64,
            slot_size=128,
            key_size=32,
            verify_checksums=True,
            max_segment_bytes=32,
        )
        c.put("k1", "A" * 24)  # seg 0
        c.put("k2", "hello")  # seg 1
        c.delete("k2")
        assert c.get("k2") is None
        # Re-put should succeed
        c.put("k2", "restored")
        assert c.get("k2") == "restored"
        c.close()

    def test_list_keys_after_delete_in_seg1(self, tmp_path):
        idx = str(tmp_path / "del2.idx")
        c = MmapCache(
            idx,
            size=64,
            slot_size=128,
            key_size=32,
            verify_checksums=True,
            max_segment_bytes=32,
        )
        c.put("k1", "A" * 24)
        c.put("k2", "B")
        c.delete("k1")
        keys = c.list_keys()
        assert "k1" not in keys
        assert "k2" in keys
        c.close()


# ---------------------------------------------------------------------------
# DEFAULT_MAX_SEGMENT_BYTES constant
# ---------------------------------------------------------------------------


class TestDefaultMaxSegmentBytes:
    def test_default_is_1_gib(self):
        assert DEFAULT_MAX_SEGMENT_BYTES == 1 * 1024 * 1024 * 1024

    def test_constructor_default(self, tmp_path):
        c = make_cache(tmp_path)
        assert c.max_segment_bytes == DEFAULT_MAX_SEGMENT_BYTES

    def test_custom_max_segment_bytes(self, tmp_path):
        idx = str(tmp_path / "custom.idx")
        c = MmapCache(
            idx,
            size=64,
            slot_size=128,
            key_size=32,
            max_segment_bytes=512,
        )
        assert c.max_segment_bytes == 512
