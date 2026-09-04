"""
Error-path and edge-case tests for MmapCache.

These tests target branches that the happy-path suite cannot reach:
- OSError during index / heap file initialisation
- open() with write-mode size mismatch
- open() OSError (non-ENOENT)
- _read_from_heap OSError
- _overwrite_in_heap OSError → put() returns False
- delete() OSError
- atomic_rebuild() OSError + temp-file cleanup
- atomic_rebuild() finally-guard when os.fdopen raises before consuming fd
- close() with segment heap mmaps open
- _lock() without fcntl (fallback yield)
- get_stats() when cache file is absent
- _get_cache_id() st_ino == 0 fallback
- full table (put returns False when index is completely full)
- heap size OSError in get_stats
"""

import errno
import os

import pytest

import salt.utils.files
import salt.utils.mmap_cache as mmap_cache_mod
from salt.utils.mmap_cache import MmapCache
from tests.support.mock import MagicMock, patch

_SIZE = 10
_KEY_SIZE = 16
_SLOT_SIZE = 48  # >= _min_slot_size(16) = 37


@pytest.fixture
def cache_path(tmp_path):
    return str(tmp_path / "err_cache.idx")


@pytest.fixture
def cache(cache_path):
    c = MmapCache(cache_path, size=_SIZE, slot_size=_SLOT_SIZE, key_size=_KEY_SIZE)
    yield c
    c.close()


# ---------------------------------------------------------------------------
# _init_index_file OSError
# ---------------------------------------------------------------------------


def test_init_index_file_oserror_returns_false(cache_path):
    c = MmapCache(cache_path, size=_SIZE, slot_size=_SLOT_SIZE, key_size=_KEY_SIZE)
    # File does not exist yet; patch fopen to raise on create
    with patch("salt.utils.files.fopen", side_effect=OSError("disk full")):
        result = c._init_index_file()
    assert result is False


# ---------------------------------------------------------------------------
# _init_heap_file OSError
# ---------------------------------------------------------------------------


def test_init_heap_file_oserror_returns_false(cache_path):
    c = MmapCache(cache_path, size=_SIZE, slot_size=_SLOT_SIZE, key_size=_KEY_SIZE)
    with patch("salt.utils.files.fopen", side_effect=OSError("disk full")):
        result = c._init_heap_file()
    assert result is False


# ---------------------------------------------------------------------------
# open() — init_index_file fails → open returns False
# ---------------------------------------------------------------------------


def test_open_write_returns_false_when_init_index_fails(cache_path):
    c = MmapCache(cache_path, size=_SIZE, slot_size=_SLOT_SIZE, key_size=_KEY_SIZE)
    with patch.object(c, "_init_index_file", return_value=False):
        assert c.open(write=True) is False


def test_open_write_returns_false_when_init_heap_fails(cache_path):
    c = MmapCache(cache_path, size=_SIZE, slot_size=_SLOT_SIZE, key_size=_KEY_SIZE)
    with patch.object(c, "_init_index_file", return_value=True):
        with patch.object(c, "_init_heap_file", return_value=False):
            assert c.open(write=True) is False


# ---------------------------------------------------------------------------
# open() — write-mode size mismatch on an existing file
# ---------------------------------------------------------------------------


def test_open_write_size_mismatch_returns_false(cache_path):
    """If the file exists but is the wrong size, write-open must fail."""
    # Create a file with unexpected size
    with salt.utils.files.fopen(cache_path, "wb") as f:
        f.write(b"\x00" * 64)

    c = MmapCache(cache_path, size=_SIZE, slot_size=_SLOT_SIZE, key_size=_KEY_SIZE)
    # Patch _init_index_file so it doesn't overwrite the truncated file
    with patch.object(c, "_init_index_file", return_value=True):
        with patch.object(c, "_init_heap_file", return_value=True):
            assert c.open(write=True) is False


# ---------------------------------------------------------------------------
# open() — non-ENOENT OSError on mmap.mmap call
# ---------------------------------------------------------------------------


def test_open_read_non_enoent_oserror_returns_false(cache_path):
    c = MmapCache(cache_path, size=_SIZE, slot_size=_SLOT_SIZE, key_size=_KEY_SIZE)
    # First create the file properly so it exists
    c.open(write=True)
    c.close()

    with patch("mmap.mmap", side_effect=OSError(errno.EACCES, "permission denied")):
        assert c.open(write=False) is False


def test_open_read_enoent_oserror_returns_false(cache_path):
    """An ENOENT OSError on read-open must silently return False."""
    c = MmapCache(cache_path, size=_SIZE, slot_size=_SLOT_SIZE, key_size=_KEY_SIZE)
    c.open(write=True)
    c.close()

    err = OSError(errno.ENOENT, "gone")
    with patch("salt.utils.files.fopen", side_effect=err):
        assert c.open(write=False) is False


# ---------------------------------------------------------------------------
# open() — heap size OSError is swallowed
# ---------------------------------------------------------------------------


def test_open_heap_getsize_oserror_is_swallowed(cache_path):
    c = MmapCache(cache_path, size=_SIZE, slot_size=_SLOT_SIZE, key_size=_KEY_SIZE)
    with patch("os.path.getsize", side_effect=OSError("no heap")):
        result = c.open(write=True)
    assert result is True
    assert c._heap_size == 0
    c.close()


# ---------------------------------------------------------------------------
# close() with segment heap mmaps set
# ---------------------------------------------------------------------------


def test_close_clears_seg_heap_mm(cache_path):
    c = MmapCache(cache_path, size=_SIZE, slot_size=_SLOT_SIZE, key_size=_KEY_SIZE)
    fake_mm = MagicMock()
    c._seg_mms = [[fake_mm, None, 0]]
    c._seg_mm_stale = [False]
    c.close()
    fake_mm.close.assert_called_once()
    assert c._seg_mms == []
    assert c._seg_mm_stale == []


def test_close_seg_heap_mm_buffererror_is_swallowed(cache_path):
    c = MmapCache(cache_path, size=_SIZE, slot_size=_SLOT_SIZE, key_size=_KEY_SIZE)
    fake_mm = MagicMock()
    fake_mm.close.side_effect = BufferError("still in use")
    c._seg_mms = [[fake_mm, None, 0]]
    c._seg_mm_stale = [False]
    c.close()  # must not raise
    assert c._seg_mms == []


# ---------------------------------------------------------------------------
# _read_from_heap OSError → get() returns default
# ---------------------------------------------------------------------------


def test_get_returns_default_when_heap_read_fails(cache):
    cache.put("k", "v")
    # Patch _read_from_heap directly so the mmap-backed fast path is bypassed
    with patch.object(cache, "_read_from_heap", return_value=None):
        result = cache.get("k", default="fallback")
    assert result == "fallback"


# ---------------------------------------------------------------------------
# _overwrite_in_heap OSError → put() returns False
# ---------------------------------------------------------------------------


def test_put_returns_false_when_overwrite_fails(cache):
    cache.put("k", "longvalue")
    with patch.object(cache, "_overwrite_in_heap", return_value=False):
        result = cache.put("k", "short")
    assert result is False


# ---------------------------------------------------------------------------
# put() OSError — triggered via _append_to_heap raising
# ---------------------------------------------------------------------------


def test_put_returns_false_on_oserror(cache):
    cache.open(write=True)
    with patch.object(cache, "_append_to_heap", side_effect=OSError("disk full")):
        result = cache.put("new_key", "v")
    assert result is False


# ---------------------------------------------------------------------------
# delete() OSError — triggered via _lock raising inside the context manager
# ---------------------------------------------------------------------------


def test_delete_returns_false_on_oserror(cache):
    cache.put("k", "v")
    # Patch flock to raise so the lock context manager propagates an OSError
    import fcntl as _fcntl

    with patch.object(_fcntl, "flock", side_effect=OSError("lock failed")):
        result = cache.delete("k")
    assert result is False


# ---------------------------------------------------------------------------
# Full table → put returns False
# ---------------------------------------------------------------------------


def test_put_returns_false_when_table_full(cache_path):
    """With size=2, filling both slots then inserting a new key must fail."""
    c = MmapCache(cache_path, size=2, slot_size=_SLOT_SIZE, key_size=_KEY_SIZE)
    c.put("key_a", "v")
    c.put("key_b", "v")
    # Table is now full with 2 distinct keys; a third key has nowhere to go.
    result = c.put("key_c", "v")
    assert result is False
    c.close()


# ---------------------------------------------------------------------------
# atomic_rebuild() — OSError triggers cleanup
# ---------------------------------------------------------------------------


def test_atomic_rebuild_oserror_cleans_up_tmp_files(cache_path):
    c = MmapCache(cache_path, size=_SIZE, slot_size=_SLOT_SIZE, key_size=_KEY_SIZE)
    c.put("k", "v")

    with patch("os.replace", side_effect=OSError("replace failed")):
        result = c.atomic_rebuild([("k2", "v2")])

    assert result is False
    # No stray temp files should remain
    tmp_files = [
        f
        for f in os.listdir(os.path.dirname(cache_path))
        if f.startswith(".mmcache_idx_")
    ]
    assert tmp_files == []
    c.close()


# ---------------------------------------------------------------------------
# atomic_rebuild() — finally guard closes tmp_idx_fd when os.fdopen raises
# ---------------------------------------------------------------------------


def test_atomic_rebuild_finally_closes_fd_on_fdopen_failure(cache_path):
    c = MmapCache(cache_path, size=_SIZE, slot_size=_SLOT_SIZE, key_size=_KEY_SIZE)

    closed_fds = []
    real_close = os.close

    def tracking_close(fd):
        closed_fds.append(fd)
        real_close(fd)

    with patch("os.fdopen", side_effect=OSError("fdopen failed")):
        with patch("os.close", side_effect=tracking_close):
            result = c.atomic_rebuild([])

    assert result is False
    # The tmp fd must have been closed by the finally guard
    assert len(closed_fds) >= 1
    c.close()


# ---------------------------------------------------------------------------
# get_stats() when cache is not openable
# ---------------------------------------------------------------------------


def test_get_stats_returns_zeros_when_not_openable(cache_path):
    c = MmapCache(cache_path, size=_SIZE, slot_size=_SLOT_SIZE, key_size=_KEY_SIZE)
    # File never created → open returns False
    stats = c.get_stats()
    assert stats["occupied"] == 0
    assert stats["heap_size_bytes"] == 0


# ---------------------------------------------------------------------------
# get_stats() — heap getsize OSError returns 0
# ---------------------------------------------------------------------------


def test_get_stats_heap_getsize_oserror(cache):
    cache.put("k", "v")
    with patch("os.path.getsize", side_effect=OSError("no heap")):
        stats = cache.get_stats()
    assert stats["heap_size_bytes"] == 0


# ---------------------------------------------------------------------------
# _get_cache_id() — st_ino == 0 falls back to mtime/ctime/size tuple
# ---------------------------------------------------------------------------


def test_get_cache_id_ino_zero_returns_tuple(cache_path):
    c = MmapCache(cache_path, size=_SIZE, slot_size=_SLOT_SIZE, key_size=_KEY_SIZE)
    c.open(write=True)

    fake_stat = MagicMock()
    fake_stat.st_ino = 0
    fake_stat.st_mtime = 1.0
    fake_stat.st_ctime = 2.0
    fake_stat.st_size = 999

    with patch("os.stat", return_value=fake_stat):
        cache_id = c._get_cache_id()

    assert cache_id == (1.0, 2.0, 999)
    c.close()


def test_get_cache_id_oserror_returns_none(cache_path):
    c = MmapCache(cache_path, size=_SIZE, slot_size=_SLOT_SIZE, key_size=_KEY_SIZE)
    with patch("os.stat", side_effect=OSError("gone")):
        assert c._get_cache_id() is None


# ---------------------------------------------------------------------------
# _lock() without fcntl — falls back to bare yield
# ---------------------------------------------------------------------------


def test_lock_without_fcntl_still_yields(cache_path):
    c = MmapCache(cache_path, size=_SIZE, slot_size=_SLOT_SIZE, key_size=_KEY_SIZE)
    c.open(write=True)

    entered = []
    with patch.object(mmap_cache_mod, "fcntl", None):
        with c._lock():
            entered.append(True)

    assert entered == [True]
    c.close()


# ---------------------------------------------------------------------------
# list_items() — heap read failure for an entry is silently skipped
# ---------------------------------------------------------------------------


def test_list_items_skips_unreadable_heap_entry(cache):
    cache.put("good", "value")
    cache.put("bad", "value")

    original_read = cache._read_from_heap

    def failing_read(offset, length):
        # Fail reads for the second key's heap region
        raw = original_read(offset, length)
        if raw and raw.rstrip(b"\x00") == b"value" and offset > 0:
            return None
        return raw

    with patch.object(cache, "_read_from_heap", side_effect=failing_read):
        items = cache.list_items()

    # At least "good" should survive; "bad" may be dropped
    keys = [k for k, _ in items]
    assert "good" in keys
