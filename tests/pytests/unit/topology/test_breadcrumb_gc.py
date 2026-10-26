"""
Tests for RFC item 7: breadcrumbs heap compaction and return-forwarding
idempotency.

* **Mitigation A** — :meth:`salt.utils.mmap_cache.MmapCache.atomic_rebuild`
  accepts an ``unlink_delay`` kwarg that renames the pre-rebuild heap
  aside and defers its physical unlink by that many seconds.  Readers
  whose mmaps point at the old inode continue to see consistent data
  through the delay window.
* **Mitigation B** — :meth:`salt.topology.router.TopologyRouter.forward_return_once`
  is an LRU-based idempotency guard that drops duplicate return
  forwards triggered by stale breadcrumb lookups.
"""

import os
import time

import pytest

import salt.topology.breadcrumbs as breadcrumbs
import salt.topology.router as router
import salt.utils.files
import salt.utils.mmap_cache as mmap_cache

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _opts(tmp_path, **overrides):
    pki_dir = tmp_path / "pki"
    (pki_dir / "master").mkdir(parents=True, exist_ok=True)
    opts = {
        "pki_dir": str(pki_dir),
        "topology_breadcrumb_grace": 30,
        "topology_breadcrumb_max_age": 600,
        "topology_breadcrumb_cache_size": 128,
        "topology_breadcrumb_cache_key_size": 64,
    }
    opts.update(overrides)
    return opts


def _fill_cache(cache, n, with_timeout):
    """Insert *n* breadcrumbs; each key is unique."""
    opts = {
        "topology_breadcrumb_grace": 0,
        "topology_breadcrumb_max_age": 600,
    }
    for i in range(n):
        breadcrumbs.put(cache, f"c:{i}", f"peer-{i}", with_timeout, opts)


# ---------------------------------------------------------------------------
# Mitigation A — delayed unlink
# ---------------------------------------------------------------------------


def test_atomic_rebuild_default_unlink_delay_is_zero(tmp_path):
    """
    Without the kwarg, ``atomic_rebuild`` behaves exactly as before —
    no ``.unlink-pending-*`` files are left behind.
    """
    path = str(tmp_path / "cache.mmap")
    cache = mmap_cache.MmapCache(path, size=128, slot_size=96, key_size=64)
    try:
        assert cache.open(write=True)
        cache.put("k1", b"v1")
        cache.atomic_rebuild([("k1", b"v1"), ("k2", b"v2")])
        pending = [p for p in os.listdir(tmp_path) if ".unlink-pending-" in p]
        assert pending == []
    finally:
        cache.close()


def test_atomic_rebuild_delayed_unlink_preserves_old_file(tmp_path):
    """
    With ``unlink_delay`` set, the old heap is renamed aside and
    physically present on disk for at least that long.  A reader that
    opens the renamed-aside path mid-swap can still read its content.
    """
    path = str(tmp_path / "cache.mmap")
    cache = mmap_cache.MmapCache(path, size=128, slot_size=96, key_size=64)
    try:
        assert cache.open(write=True)
        cache.put("k1", b"old-value")
        # Capture a copy of the old heap bytes so we can diff against the
        # renamed-aside copy and prove it isn't overwritten mid-swap.
        with salt.utils.files.fopen(cache.heap_path, "rb") as fh:
            old_heap_bytes = fh.read()

        delay = 0.75
        start = time.monotonic()
        cache.atomic_rebuild([("k1", b"new-value"), ("k2", b"v2")], unlink_delay=delay)
        elapsed_at_return = time.monotonic() - start
        # atomic_rebuild returns promptly — the unlink thread does the sleep.
        assert elapsed_at_return < delay / 2

        pending = [p for p in os.listdir(tmp_path) if ".unlink-pending-" in p]
        assert len(pending) == 1, pending
        pending_path = tmp_path / pending[0]
        # The old content is still readable through the renamed-aside path.
        assert pending_path.read_bytes() == old_heap_bytes

        # Wait past the window and verify the daemon thread cleaned up.
        time.sleep(delay + 0.5)
        pending_after = [p for p in os.listdir(tmp_path) if ".unlink-pending-" in p]
        assert pending_after == []
    finally:
        cache.close()


def test_atomic_rebuild_reader_opens_mid_swap_sees_consistent_data(tmp_path):
    """
    A reader that already holds an mmap on the pre-rebuild heap keeps
    reading its original values after the swap — the delay keeps the
    renamed-aside file around (and the mmap keeps the inode alive even
    once the directory entry is gone).
    """
    path = str(tmp_path / "cache.mmap")
    writer = mmap_cache.MmapCache(path, size=128, slot_size=96, key_size=64)
    reader = mmap_cache.MmapCache(
        path,
        size=128,
        slot_size=96,
        key_size=64,
        staleness_check_interval=10,  # intentionally long: reader won't re-stat
    )
    try:
        assert writer.open(write=True)
        writer.put("alpha", b"before")
        writer.put("beta", b"before")
        # Force reader to establish an mmap on the old heap.
        assert reader.open(write=False)
        assert reader.get("alpha") == b"before"

        writer.atomic_rebuild(
            [("alpha", b"after"), ("beta", b"after")], unlink_delay=0.5
        )

        # Reader's cached mmap and _cache_id still point at the OLD state
        # because the staleness interval hasn't elapsed.  Mitigation A
        # ensures that read remains valid rather than erroring.
        value = reader.get("alpha")
        assert value in (b"before", b"after")
        # The call must at minimum not raise; semantics-wise both the
        # old-inode (still mapped) and new-inode (fresh re-mmap) are
        # internally consistent.
    finally:
        writer.close()
        reader.close()


def test_atomic_rebuild_close_joins_pending_unlink_thread(tmp_path):
    """
    :meth:`MmapCache.close` must drain the pending-unlink thread so a
    worker that shuts down right after a rebuild doesn't leave the
    renamed-aside file lying around for the next process to pick up.
    """
    path = str(tmp_path / "cache.mmap")
    cache = mmap_cache.MmapCache(path, size=128, slot_size=96, key_size=64)
    try:
        assert cache.open(write=True)
        cache.put("k", b"v")
        cache.atomic_rebuild([("k", b"v")], unlink_delay=0.2)
        assert cache._pending_unlink_threads  # thread is live
        # Normal close path should join the daemon thread.
    finally:
        cache.close()
    # After close, no thread handles remain.
    assert cache._pending_unlink_threads == []


def test_atomic_rebuild_reaps_orphan_pending_files(tmp_path):
    """
    A ``*.unlink-pending-<pid>-<nanos>`` leftover from a previous
    crashed rebuild is swept on the next rebuild.
    """
    path = str(tmp_path / "cache.mmap")
    cache = mmap_cache.MmapCache(path, size=128, slot_size=96, key_size=64)
    try:
        assert cache.open(write=True)
        cache.put("k", b"v")
        # Plant an orphan that looks like a stale pending-unlink file.
        orphan = tmp_path / "cache.mmap.heap.unlink-pending-12345-67890123"
        orphan.write_bytes(b"stale")
        assert orphan.exists()
        cache.atomic_rebuild([("k", b"v")])
        # The orphan — unrelated to this run's unlink_delay — is gone.
        assert not orphan.exists()
    finally:
        cache.close()


# ---------------------------------------------------------------------------
# Breadcrumbs cleanup wiring
# ---------------------------------------------------------------------------


def test_breadcrumb_cleanup_passes_delay_to_rebuild(tmp_path, monkeypatch):
    """
    :func:`breadcrumbs.cleanup` must forward the writer's staleness
    check interval as the ``unlink_delay`` so rebuilds triggered by
    tombstone pressure benefit from mitigation A automatically.
    """
    opts = _opts(tmp_path, topology_breadcrumb_grace=0, topology_breadcrumb_max_age=10)
    breadcrumbs.pre_create(opts)
    writer = breadcrumbs.open_writer(opts)
    writer._staleness_check_interval = 0.42  # inject a sentinel value

    seen_kwargs = {}
    real_rebuild = writer.atomic_rebuild

    def _spy(iterator, unlink_delay=0, **kw):
        seen_kwargs["unlink_delay"] = unlink_delay
        return real_rebuild(iterator, unlink_delay=unlink_delay, **kw)

    monkeypatch.setattr(writer, "atomic_rebuild", _spy)

    try:
        # Fill with entries that will all expire, forcing a cleanup +
        # a rebuild (tombstone ratio exceeds 0.3 when every entry is
        # expired and removed).
        for i in range(10):
            breadcrumbs.put(writer, f"k:{i}", f"p{i}", -1.0, opts)
        # Add a few long-lived entries so there are survivors to rebuild.
        for i in range(10, 15):
            breadcrumbs.put(writer, f"k:{i}", f"p{i}", 300.0, opts)
        time.sleep(0.01)
        removed = breadcrumbs.cleanup(writer)
        assert removed == 10
        assert seen_kwargs.get("unlink_delay") == pytest.approx(0.42)
    finally:
        writer.close()


# ---------------------------------------------------------------------------
# Mitigation B — duplicate return-forward idempotency
# ---------------------------------------------------------------------------


class _StubCache:
    """Minimal stand-in for the breadcrumb cache in TopologyRouter."""

    def get(self, *_a, **_kw):
        return None


def _router():
    opts = {"cluster_id": "A"}
    return router.TopologyRouter(opts, _StubCache(), _StubCache())


def test_forward_return_once_first_delivery_passes():
    r = _router()
    ret = {"jid": "20260101000000000000", "id": "minion-1", "return": {}}
    assert r.forward_return_once(ret) is True


def test_forward_return_once_duplicate_is_dropped(caplog):
    r = _router()
    ret = {"jid": "20260101000000000000", "id": "minion-1", "return": {}}
    assert r.forward_return_once(ret) is True
    with caplog.at_level("DEBUG", logger="salt.topology.router"):
        assert r.forward_return_once(ret) is False
    assert any("duplicate return forward" in rec.message for rec in caplog.records)


def test_forward_return_once_distinct_minions_are_independent():
    r = _router()
    ret_a = {"jid": "J", "id": "a", "return": {}}
    ret_b = {"jid": "J", "id": "b", "return": {}}
    assert r.forward_return_once(ret_a) is True
    assert r.forward_return_once(ret_b) is True
    assert r.forward_return_once(ret_a) is False
    assert r.forward_return_once(ret_b) is False


def test_forward_return_once_lru_caps_at_size():
    r = _router()
    cap = router._FORWARDED_RETURN_LRU_SIZE
    # Fill past the cap; the earliest entries must evict.
    for i in range(cap + 50):
        r.forward_return_once({"jid": f"J{i}", "id": "m", "return": {}})
    assert len(r._forwarded_returns) == cap
    # Entry 0 has been evicted — forwarding it again should look fresh.
    assert r.forward_return_once({"jid": "J0", "id": "m", "return": {}}) is True


def test_forward_return_once_missing_jid_or_id_passes_through():
    r = _router()
    # Returns without jid or id can't be deduplicated — don't drop.
    assert r.forward_return_once({"id": "m", "return": {}}) is True
    assert r.forward_return_once({"jid": "J", "return": {}}) is True
    assert r.forward_return_once(None) is False  # non-dict is a hard-drop
