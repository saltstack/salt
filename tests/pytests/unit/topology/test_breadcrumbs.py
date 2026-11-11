"""
Unit tests for :mod:`salt.topology.breadcrumbs`.

Covers pure-logic helpers (lifetime clamp, owner-PID guard) and
cleanup edge cases that don't need the fork machinery.  Uses a
real :class:`salt.utils.mmap_cache.MmapCache` instance against a
tmp_path so there are no mocks.
"""

import os
import time

import pytest

import salt.topology.breadcrumbs as breadcrumbs

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _opts(tmp_path, **overrides):
    pki_dir = tmp_path / "pki"
    (pki_dir / "master").mkdir(parents=True, exist_ok=True)
    opts = {
        "pki_dir": str(pki_dir),
        "topology_breadcrumb_grace": 30,
        "topology_breadcrumb_max_age": 600,
        "topology_breadcrumb_cache_size": 512,
        "topology_breadcrumb_cache_key_size": 64,
    }
    opts.update(overrides)
    return opts


# ---------------------------------------------------------------------------
# Lifetime clamp edge cases
# ---------------------------------------------------------------------------


def test_lifetime_grace_adds_to_timeout():
    """timeout + grace below max_age → sum used."""
    opts = {
        "topology_breadcrumb_grace": 30,
        "topology_breadcrumb_max_age": 600,
    }
    now = 1_000_000.0
    expiry = breadcrumbs._compute_expiry_at(60.0, opts, now=now)
    assert expiry == pytest.approx(now + 90.0)


def test_lifetime_clamped_at_max_age():
    """timeout + grace above max_age → clamp."""
    opts = {
        "topology_breadcrumb_grace": 30,
        "topology_breadcrumb_max_age": 100,
    }
    now = 1_000_000.0
    expiry = breadcrumbs._compute_expiry_at(300.0, opts, now=now)
    assert expiry == pytest.approx(now + 100.0)


def test_lifetime_zero_timeout_still_gets_grace():
    """A zero publish_timeout gives exactly ``grace`` seconds of lifetime."""
    opts = {
        "topology_breadcrumb_grace": 10,
        "topology_breadcrumb_max_age": 600,
    }
    now = 1_000_000.0
    expiry = breadcrumbs._compute_expiry_at(0.0, opts, now=now)
    assert expiry == pytest.approx(now + 10.0)


def test_lifetime_negative_timeout_can_produce_past_expiry():
    """
    A negative publish_timeout with small grace produces a past
    expiry_at.  The policy choice is "store it anyway, let lookup/
    cleanup drop it" --- we don't want put() to silently refuse
    inputs that then look like a working breadcrumb to the caller.
    """
    opts = {
        "topology_breadcrumb_grace": 0,
        "topology_breadcrumb_max_age": 600,
    }
    now = 1_000_000.0
    expiry = breadcrumbs._compute_expiry_at(-5.0, opts, now=now)
    assert expiry == pytest.approx(now - 5.0)


def test_lifetime_defaults_when_opts_missing():
    """
    If opts carries neither grace nor max_age, the RFC-documented
    defaults (30s grace, 600s max_age) are used.
    """
    now = 1_000_000.0
    expiry = breadcrumbs._compute_expiry_at(60.0, {}, now=now)
    # 60 + 30 = 90, below default max_age 600.
    assert expiry == pytest.approx(now + 90.0)


def test_lifetime_defaults_clamp_at_max_age():
    """Even without opts, a huge timeout is clamped at the default max_age."""
    now = 1_000_000.0
    expiry = breadcrumbs._compute_expiry_at(10_000.0, {}, now=now)
    assert expiry == pytest.approx(now + 600.0)


# ---------------------------------------------------------------------------
# cleanup edge cases
# ---------------------------------------------------------------------------


def test_cleanup_empty_cache(tmp_path):
    """cleanup on a brand-new cache returns 0 and does not raise."""
    opts = _opts(tmp_path)
    breadcrumbs.pre_create(opts)
    writer = breadcrumbs.open_writer(opts)
    try:
        assert breadcrumbs.cleanup(writer) == 0
    finally:
        writer.close()


def test_cleanup_all_expired(tmp_path):
    """When every entry is expired, cleanup removes all of them."""
    opts = _opts(tmp_path, topology_breadcrumb_grace=0, topology_breadcrumb_max_age=10)
    breadcrumbs.pre_create(opts)
    writer = breadcrumbs.open_writer(opts)
    try:
        for i in range(5):
            breadcrumbs.put(writer, f"ex:{i}", "e", -1.0, opts)
        time.sleep(0.01)
        removed = breadcrumbs.cleanup(writer)
        assert removed == 5
        for i in range(5):
            assert breadcrumbs.lookup(writer, f"ex:{i}") is None
    finally:
        writer.close()


def test_cleanup_no_expired(tmp_path):
    """When no entries are expired, cleanup is a no-op returning 0."""
    opts = _opts(tmp_path)
    breadcrumbs.pre_create(opts)
    writer = breadcrumbs.open_writer(opts)
    try:
        for i in range(4):
            breadcrumbs.put(writer, f"keep:{i}", "k", 60.0, opts)
        assert breadcrumbs.cleanup(writer) == 0
        for i in range(4):
            assert breadcrumbs.lookup(writer, f"keep:{i}") == "k"
    finally:
        writer.close()


# ---------------------------------------------------------------------------
# Owner-PID guard
# ---------------------------------------------------------------------------


def test_reader_has_no_owner_pid(tmp_path):
    """Readers aren't PID-locked: ``_check_owner`` is a no-op on them."""
    opts = _opts(tmp_path)
    breadcrumbs.pre_create(opts)
    reader = breadcrumbs.open_reader(opts)
    try:
        assert not hasattr(reader, "_breadcrumb_owner_pid")
        # Should not raise even if we pretend to be a different pid.
        breadcrumbs._check_owner(reader)
    finally:
        reader.close()


def test_writer_check_owner_from_owner_pid_ok(tmp_path):
    """Writer created in this pid passes ``_check_owner``."""
    opts = _opts(tmp_path)
    breadcrumbs.pre_create(opts)
    writer = breadcrumbs.open_writer(opts)
    try:
        assert writer._breadcrumb_owner_pid == os.getpid()
        breadcrumbs._check_owner(writer)  # does not raise
    finally:
        writer.close()


def test_writer_check_owner_from_other_pid_raises(tmp_path):
    """
    When ``_breadcrumb_owner_pid`` differs from ``os.getpid()``,
    ``_check_owner`` raises :exc:`RuntimeError`.
    """
    opts = _opts(tmp_path)
    breadcrumbs.pre_create(opts)
    writer = breadcrumbs.open_writer(opts)
    try:
        # Simulate a stale owner-pid rather than forking.
        writer._breadcrumb_owner_pid = os.getpid() + 999_999
        with pytest.raises(RuntimeError, match="pid"):
            breadcrumbs._check_owner(writer)
        with pytest.raises(RuntimeError, match="pid"):
            breadcrumbs.put(writer, "no:write", "x", 60.0, opts)
        with pytest.raises(RuntimeError, match="pid"):
            breadcrumbs.delete(writer, "no:write")
        with pytest.raises(RuntimeError, match="pid"):
            breadcrumbs.cleanup(writer)
    finally:
        writer.close()


# ---------------------------------------------------------------------------
# Cache path layout
# ---------------------------------------------------------------------------


def test_cache_path_includes_master_subdir(tmp_path):
    """The cache lives under ``<pki_dir>/master/`` per RFC."""
    opts = _opts(tmp_path)
    path = breadcrumbs._cache_path(opts)
    expected = os.path.join(opts["pki_dir"], "master", "topology_breadcrumbs.mmap")
    assert path == expected


def test_cache_kwargs_pull_from_opts(tmp_path):
    """Sizing kwargs come from the two opts keys."""
    opts = _opts(
        tmp_path,
        topology_breadcrumb_cache_size=2048,
        topology_breadcrumb_cache_key_size=128,
    )
    kwargs = breadcrumbs._cache_kwargs(opts)
    assert kwargs["size"] == 2048
    assert kwargs["key_size"] == 128


def test_cache_kwargs_default_when_opts_missing():
    """When sizing opts are absent, the RFC defaults are used."""
    kwargs = breadcrumbs._cache_kwargs({})
    assert kwargs["size"] == 1_000_000
    assert kwargs["key_size"] == 64
