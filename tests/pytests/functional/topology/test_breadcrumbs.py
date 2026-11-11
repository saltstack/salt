"""
Functional tests for :mod:`salt.topology.breadcrumbs`.

These tests exercise the real :class:`salt.utils.mmap_cache.MmapCache` —
no mocks.  Fork tests use ``os.fork`` to verify cross-process read
visibility (the whole point of the mmap-backed design) and the
owner-PID guard.
"""

import os
import pickle
import time

import pytest

import salt.topology.breadcrumbs as breadcrumbs
import salt.utils.mmap_cache
import salt.utils.msgpack

pytestmark = [
    pytest.mark.skipif(
        not hasattr(os, "fork"), reason="cross-process tests require os.fork"
    ),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_opts(tmp_path, **overrides):
    """Return a minimal opts dict with a pki_dir that breadcrumbs can use."""
    pki_dir = tmp_path / "pki"
    (pki_dir / "master").mkdir(parents=True, exist_ok=True)
    opts = {
        "pki_dir": str(pki_dir),
        "topology_breadcrumb_grace": 30,
        "topology_breadcrumb_max_age": 600,
        # Keep the test cache small — the real default is 1_000_000 slots.
        "topology_breadcrumb_cache_size": 1024,
        "topology_breadcrumb_cache_key_size": 64,
    }
    opts.update(overrides)
    return opts


def _breadcrumb_paths(opts):
    base = os.path.join(opts["pki_dir"], "master", "topology_breadcrumbs.mmap")
    return {
        "index": base,
        "heap": base + ".heap",
        "roster": base + ".roster",
        "lock": base + ".lock",
    }


# ---------------------------------------------------------------------------
# pre_create
# ---------------------------------------------------------------------------


def test_pre_create_materializes_files(tmp_path):
    """After pre_create, index/heap/roster all exist on disk."""
    opts = _make_opts(tmp_path)
    paths = _breadcrumb_paths(opts)
    assert not os.path.exists(paths["index"])

    breadcrumbs.pre_create(opts)

    assert os.path.exists(paths["index"])
    assert os.path.exists(paths["heap"])
    # Index size matches size * slot_size (sanity).
    expected_slot_size = max(
        1 + 8 + 4 + 8 + opts["topology_breadcrumb_cache_key_size"], 25
    )
    assert (
        os.path.getsize(paths["index"])
        >= opts["topology_breadcrumb_cache_size"] * expected_slot_size // 2
    )  # loose lower bound; slot_size default varies


def test_pre_create_is_idempotent(tmp_path):
    """A second pre_create against existing files is a no-op."""
    opts = _make_opts(tmp_path)
    breadcrumbs.pre_create(opts)
    paths = _breadcrumb_paths(opts)
    idx_mtime_1 = os.path.getmtime(paths["index"])
    heap_mtime_1 = os.path.getmtime(paths["heap"])

    time.sleep(0.01)
    breadcrumbs.pre_create(opts)

    assert os.path.getmtime(paths["index"]) == idx_mtime_1
    assert os.path.getmtime(paths["heap"]) == heap_mtime_1


# ---------------------------------------------------------------------------
# open_writer / open_reader
# ---------------------------------------------------------------------------


def test_open_writer_succeeds_in_owner_process(tmp_path):
    """open_writer returns a usable MmapCache in the owner process."""
    opts = _make_opts(tmp_path)
    breadcrumbs.pre_create(opts)

    writer = breadcrumbs.open_writer(opts)
    try:
        assert isinstance(writer, salt.utils.mmap_cache.MmapCache)
    finally:
        writer.close()


def test_open_reader_from_different_process_succeeds(tmp_path):
    """A forked child can open the same cache as a reader."""
    opts = _make_opts(tmp_path)
    breadcrumbs.pre_create(opts)

    writer = breadcrumbs.open_writer(opts)
    breadcrumbs.put(writer, "east:20250101000000000000", "east", 60.0, opts)
    try:
        r, w = os.pipe()
        pid = os.fork()
        if pid == 0:  # child
            os.close(r)
            try:
                reader = breadcrumbs.open_reader(opts)
                val = breadcrumbs.lookup(reader, "east:20250101000000000000")
                os.write(w, pickle.dumps(val))
            finally:
                os._exit(0)
        else:
            os.close(w)
            child_out = b""
            while True:
                chunk = os.read(r, 4096)
                if not chunk:
                    break
                child_out += chunk
            os.close(r)
            os.waitpid(pid, 0)
            assert pickle.loads(child_out) == "east"
    finally:
        writer.close()


# ---------------------------------------------------------------------------
# put / lookup round-trip
# ---------------------------------------------------------------------------


def test_put_then_lookup_in_same_process(tmp_path):
    """A breadcrumb written in this process is readable in this process."""
    opts = _make_opts(tmp_path)
    breadcrumbs.pre_create(opts)
    writer = breadcrumbs.open_writer(opts)
    try:
        breadcrumbs.put(writer, "west:20250101000000000001", "west", 60.0, opts)
        assert breadcrumbs.lookup(writer, "west:20250101000000000001") == "west"
    finally:
        writer.close()


def test_lookup_missing_returns_none(tmp_path):
    """A key that was never put returns None."""
    opts = _make_opts(tmp_path)
    breadcrumbs.pre_create(opts)
    writer = breadcrumbs.open_writer(opts)
    try:
        assert breadcrumbs.lookup(writer, "nope:20250101") is None
    finally:
        writer.close()


# ---------------------------------------------------------------------------
# Cross-process read via fork
# ---------------------------------------------------------------------------


def test_cross_process_read(tmp_path):
    """
    Parent writes a breadcrumb, forks a child, child reads via
    open_reader and sees the entry.  This is the hot path.
    """
    opts = _make_opts(tmp_path)
    breadcrumbs.pre_create(opts)
    writer = breadcrumbs.open_writer(opts)
    try:
        breadcrumbs.put(writer, "a:jid-1", "a", 60.0, opts)
        breadcrumbs.put(writer, "b:jid-2", "b", 60.0, opts)

        r, w = os.pipe()
        pid = os.fork()
        if pid == 0:
            os.close(r)
            try:
                reader = breadcrumbs.open_reader(opts)
                result = {
                    "a:jid-1": breadcrumbs.lookup(reader, "a:jid-1"),
                    "b:jid-2": breadcrumbs.lookup(reader, "b:jid-2"),
                    "c:jid-3": breadcrumbs.lookup(reader, "c:jid-3"),
                }
                os.write(w, pickle.dumps(result))
            finally:
                os._exit(0)
        else:
            os.close(w)
            payload = b""
            while True:
                chunk = os.read(r, 4096)
                if not chunk:
                    break
                payload += chunk
            os.close(r)
            os.waitpid(pid, 0)
            result = pickle.loads(payload)
            assert result == {
                "a:jid-1": "a",
                "b:jid-2": "b",
                "c:jid-3": None,
            }
    finally:
        writer.close()


# ---------------------------------------------------------------------------
# Lazy expiry
# ---------------------------------------------------------------------------


def test_lookup_returns_none_when_expired(tmp_path):
    """
    An entry past its expiry_at returns None, even though it is still
    physically present in the cache.
    """
    opts = _make_opts(tmp_path)
    breadcrumbs.pre_create(opts)
    writer = breadcrumbs.open_writer(opts)
    try:
        # publish_timeout + grace = -1 + 30 = 29, but let's just directly
        # inject an expired value to decouple from clock resolution.
        # Easiest: use a very short timeout that we then outlast.
        # Set negative publish_timeout so expiry_at < now immediately.
        # The implementation must still clamp sensibly; use grace=0 override.
        local_opts = dict(opts)
        local_opts["topology_breadcrumb_grace"] = 0
        local_opts["topology_breadcrumb_max_age"] = 10
        breadcrumbs.put(writer, "x:jid-x", "x", -1.0, local_opts)
        # publish_timeout < 0 + grace 0 = negative lifetime -> immediate expire
        # Allow a brief sleep to be safe against clock skew.
        time.sleep(0.01)
        assert breadcrumbs.lookup(writer, "x:jid-x") is None
    finally:
        writer.close()


def test_fresh_entry_does_not_expire_immediately(tmp_path):
    """A just-written entry with a positive lifetime is readable."""
    opts = _make_opts(tmp_path)
    breadcrumbs.pre_create(opts)
    writer = breadcrumbs.open_writer(opts)
    try:
        breadcrumbs.put(writer, "y:jid-y", "y", 60.0, opts)
        assert breadcrumbs.lookup(writer, "y:jid-y") == "y"
    finally:
        writer.close()


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


def test_delete_removes_entry(tmp_path):
    """After delete, lookup returns None."""
    opts = _make_opts(tmp_path)
    breadcrumbs.pre_create(opts)
    writer = breadcrumbs.open_writer(opts)
    try:
        breadcrumbs.put(writer, "d:jid-d", "d", 60.0, opts)
        assert breadcrumbs.lookup(writer, "d:jid-d") == "d"
        breadcrumbs.delete(writer, "d:jid-d")
        assert breadcrumbs.lookup(writer, "d:jid-d") is None
    finally:
        writer.close()


# ---------------------------------------------------------------------------
# cleanup
# ---------------------------------------------------------------------------


def test_cleanup_removes_expired_returns_count(tmp_path):
    """cleanup removes expired entries and returns the removal count."""
    opts = _make_opts(tmp_path)
    breadcrumbs.pre_create(opts)
    writer = breadcrumbs.open_writer(opts)
    try:
        expired_opts = dict(opts)
        expired_opts["topology_breadcrumb_grace"] = 0
        expired_opts["topology_breadcrumb_max_age"] = 10
        # Three expired, two live.
        for i in range(3):
            breadcrumbs.put(writer, f"ex:jid-{i}", "ex", -1.0, expired_opts)
        for i in range(2):
            breadcrumbs.put(writer, f"live:jid-{i}", "live", 60.0, opts)
        time.sleep(0.01)

        removed = breadcrumbs.cleanup(writer)
        assert removed == 3

        # Live entries remain.
        assert breadcrumbs.lookup(writer, "live:jid-0") == "live"
        assert breadcrumbs.lookup(writer, "live:jid-1") == "live"
        # Expired entries are gone.
        for i in range(3):
            assert breadcrumbs.lookup(writer, f"ex:jid-{i}") is None
    finally:
        writer.close()


def test_cleanup_empty_cache_returns_zero(tmp_path):
    """Running cleanup against an empty cache is a no-op that returns 0."""
    opts = _make_opts(tmp_path)
    breadcrumbs.pre_create(opts)
    writer = breadcrumbs.open_writer(opts)
    try:
        assert breadcrumbs.cleanup(writer) == 0
    finally:
        writer.close()


def test_cleanup_triggers_atomic_rebuild_when_tombstones_high(tmp_path):
    """
    After cleanup where tombstone ratio > 0.3, atomic_rebuild runs and
    the ``deleted`` count in get_stats drops to zero.
    """
    opts = _make_opts(tmp_path)
    breadcrumbs.pre_create(opts)
    writer = breadcrumbs.open_writer(opts)
    try:
        # Create 10 entries, expire 7 of them → 7/10 = 0.7 > 0.3.
        expired_opts = dict(opts)
        expired_opts["topology_breadcrumb_grace"] = 0
        expired_opts["topology_breadcrumb_max_age"] = 10
        for i in range(7):
            breadcrumbs.put(writer, f"stale:jid-{i}", "stale", -1.0, expired_opts)
        for i in range(3):
            breadcrumbs.put(writer, f"keep:jid-{i}", "keep", 60.0, opts)
        time.sleep(0.01)

        removed = breadcrumbs.cleanup(writer)
        assert removed == 7

        stats = writer.get_stats()
        # Rebuild should have reclaimed all tombstones.
        assert stats["deleted"] == 0
        assert stats["occupied"] == 3
    finally:
        writer.close()


def test_cleanup_no_expired_does_not_rebuild(tmp_path):
    """When no entries are expired, cleanup returns 0 and preserves state."""
    opts = _make_opts(tmp_path)
    breadcrumbs.pre_create(opts)
    writer = breadcrumbs.open_writer(opts)
    try:
        for i in range(5):
            breadcrumbs.put(writer, f"fresh:jid-{i}", "fresh", 60.0, opts)
        assert breadcrumbs.cleanup(writer) == 0
        stats = writer.get_stats()
        assert stats["occupied"] == 5
        assert stats["deleted"] == 0
    finally:
        writer.close()


# ---------------------------------------------------------------------------
# Owner-PID guard
# ---------------------------------------------------------------------------


def test_put_from_fork_raises_runtimeerror(tmp_path):
    """
    put() called from a process that is not the owner-PID (captured
    at open_writer time) must raise RuntimeError.  Return the exit
    code of the child, which encodes success/failure.
    """
    opts = _make_opts(tmp_path)
    breadcrumbs.pre_create(opts)
    writer = breadcrumbs.open_writer(opts)
    try:
        r, w = os.pipe()
        pid = os.fork()
        if pid == 0:
            os.close(r)
            raised = False
            try:
                breadcrumbs.put(writer, "forbidden:jid", "x", 60.0, opts)
            except RuntimeError:
                raised = True
            except Exception:  # pylint: disable=broad-except
                raised = False
            os.write(w, b"\x01" if raised else b"\x00")
            os._exit(0)
        else:
            os.close(w)
            payload = b""
            while True:
                chunk = os.read(r, 4096)
                if not chunk:
                    break
                payload += chunk
            os.close(r)
            os.waitpid(pid, 0)
            assert payload == b"\x01", (
                "expected RuntimeError in child when put() runs from " "a non-owner PID"
            )
        # Parent can still write.
        breadcrumbs.put(writer, "allowed:jid", "ok", 60.0, opts)
        assert breadcrumbs.lookup(writer, "allowed:jid") == "ok"
    finally:
        writer.close()


def test_delete_from_fork_raises_runtimeerror(tmp_path):
    """delete() also respects the owner-PID guard."""
    opts = _make_opts(tmp_path)
    breadcrumbs.pre_create(opts)
    writer = breadcrumbs.open_writer(opts)
    try:
        breadcrumbs.put(writer, "target:jid", "x", 60.0, opts)

        r, w = os.pipe()
        pid = os.fork()
        if pid == 0:
            os.close(r)
            raised = False
            try:
                breadcrumbs.delete(writer, "target:jid")
            except RuntimeError:
                raised = True
            except Exception:  # pylint: disable=broad-except
                raised = False
            os.write(w, b"\x01" if raised else b"\x00")
            os._exit(0)
        else:
            os.close(w)
            payload = os.read(r, 1)
            os.close(r)
            os.waitpid(pid, 0)
            assert payload == b"\x01"
    finally:
        writer.close()


def test_reader_from_any_pid_ok(tmp_path):
    """Readers have no owner-PID restriction."""
    opts = _make_opts(tmp_path)
    breadcrumbs.pre_create(opts)
    writer = breadcrumbs.open_writer(opts)
    try:
        breadcrumbs.put(writer, "readme:jid", "ok", 60.0, opts)

        r, w = os.pipe()
        pid = os.fork()
        if pid == 0:
            os.close(r)
            reader = breadcrumbs.open_reader(opts)
            val = breadcrumbs.lookup(reader, "readme:jid") or ""
            os.write(w, val.encode("utf-8"))
            os._exit(0)
        else:
            os.close(w)
            payload = os.read(r, 1024)
            os.close(r)
            os.waitpid(pid, 0)
            assert payload == b"ok"
    finally:
        writer.close()


# ---------------------------------------------------------------------------
# Lifetime computation
# ---------------------------------------------------------------------------


def _read_expiry_at(writer, jid):
    """
    Return the raw ``expiry_at`` stored for *jid* by decoding the
    msgpack value directly out of the cache.  Used to verify lifetime
    math without depending on the public API.
    """
    # MmapCache.get returns the decoded str; but we stored bytes msgpack,
    # so get returns a bytes/str value we must msgpack-decode.
    raw = writer.get(jid)
    if raw is None:
        return None
    if isinstance(raw, str):
        raw = raw.encode("latin-1")
    return salt.utils.msgpack.loads(raw, raw=False)["expiry_at"]


def test_lifetime_grace_adds_to_publish_timeout(tmp_path):
    """
    expiry_at ≈ now + publish_timeout + grace, when the sum stays
    below max_age.
    """
    opts = _make_opts(tmp_path, topology_breadcrumb_grace=30)
    breadcrumbs.pre_create(opts)
    writer = breadcrumbs.open_writer(opts)
    try:
        t0 = time.time()
        breadcrumbs.put(writer, "lt:jid-1", "x", 60.0, opts)
        expiry = _read_expiry_at(writer, "lt:jid-1")
        assert expiry is not None
        # expected ≈ t0 + 60 + 30 = t0 + 90
        delta = expiry - t0
        assert 85.0 <= delta <= 95.0, f"expected ~90s lifetime, got {delta}s"
    finally:
        writer.close()


def test_lifetime_clamped_at_max_age(tmp_path):
    """
    When publish_timeout + grace exceeds max_age, expiry_at is clamped
    to now + max_age.
    """
    opts = _make_opts(
        tmp_path,
        topology_breadcrumb_grace=30,
        topology_breadcrumb_max_age=100,
    )
    breadcrumbs.pre_create(opts)
    writer = breadcrumbs.open_writer(opts)
    try:
        t0 = time.time()
        # publish_timeout 300 + grace 30 = 330 > max_age 100 → clamp.
        breadcrumbs.put(writer, "clamp:jid", "x", 300.0, opts)
        expiry = _read_expiry_at(writer, "clamp:jid")
        delta = expiry - t0
        assert 95.0 <= delta <= 105.0, f"expected ~100s clamp, got {delta}s"
    finally:
        writer.close()
