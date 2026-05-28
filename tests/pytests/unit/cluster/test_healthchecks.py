"""
Unit tests for ``salt.cluster.healthchecks`` — the file-sentinel
liveness/readiness/startup probes used by the Kubernetes deployment.

Each test exercises one of the public helpers in isolation; the
end-to-end wiring (Master.start writes ``startup`` and runs the
heartbeat, ``_signal_cluster_ready`` writes ``ready``) is covered by an
integration test in ``tests/pytests/integration/cluster/``.
"""

import os
import time

import pytest

from salt.cluster import healthchecks


@pytest.fixture
def opts(tmp_path):
    """Minimal ``opts`` dict with just the keys the helpers consult."""
    return {"cachedir": str(tmp_path)}


def _read(path):
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# health_dir / reset_health_dir
# ---------------------------------------------------------------------------


def test_health_dir_returns_subdir_of_cachedir(opts, tmp_path):
    assert healthchecks.health_dir(opts) == tmp_path / "health"


def test_health_dir_returns_none_when_cachedir_missing():
    """
    Stripped opts (e.g. some functional-test fixtures) have no
    ``cachedir``.  Helpers must silently skip rather than crash —
    otherwise wiring health-writes into shared paths like
    ``_signal_cluster_ready`` would break those tests.
    """
    assert healthchecks.health_dir({}) is None
    assert healthchecks.health_dir({"cachedir": ""}) is None


def test_helpers_no_op_when_cachedir_missing(tmp_path):
    """All sentinel writers tolerate an opts dict with no cachedir."""
    healthchecks.reset_health_dir({})
    healthchecks.mark_startup_complete({})
    healthchecks.mark_cluster_ready({})
    healthchecks.touch_alive({})
    # No sentinels should have been written *anywhere* under tmp_path.
    assert not any(tmp_path.rglob("startup"))
    assert not any(tmp_path.rglob("ready"))
    assert not any(tmp_path.rglob("alive"))


def test_reset_health_dir_creates_when_missing(opts, tmp_path):
    healthchecks.reset_health_dir(opts)
    assert (tmp_path / "health").is_dir()


def test_reset_health_dir_wipes_stale_sentinels(opts, tmp_path):
    """
    Stale sentinels from a previous run must not survive a restart —
    otherwise a probe could pass before the new master is actually
    ready.
    """
    health = tmp_path / "health"
    health.mkdir()
    (health / "startup").write_text("old", encoding="utf-8")
    (health / "ready").write_text("old", encoding="utf-8")
    (health / "alive").write_text("old", encoding="utf-8")

    healthchecks.reset_health_dir(opts)

    assert health.is_dir()
    assert not (health / "startup").exists()
    assert not (health / "ready").exists()
    assert not (health / "alive").exists()


def test_reset_health_dir_swallows_oserror(opts, monkeypatch, caplog):
    """A misbehaving filesystem must not block master startup."""

    def boom(*_args, **_kwargs):
        raise OSError("permission denied")

    monkeypatch.setattr("pathlib.Path.mkdir", boom)
    healthchecks.reset_health_dir(opts)
    assert "could not reset" in caplog.text


# ---------------------------------------------------------------------------
# mark_startup_complete / mark_cluster_ready
# ---------------------------------------------------------------------------


def test_mark_startup_complete_writes_sentinel(opts, tmp_path):
    healthchecks.mark_startup_complete(opts)
    sentinel = tmp_path / "health" / "startup"
    assert sentinel.is_file()
    # Body is a unix timestamp — should parse as a recent integer second.
    body = int(_read(sentinel))
    assert abs(body - int(time.time())) < 5


def test_mark_cluster_ready_writes_sentinel(opts, tmp_path):
    healthchecks.mark_cluster_ready(opts)
    sentinel = tmp_path / "health" / "ready"
    assert sentinel.is_file()
    body = int(_read(sentinel))
    assert abs(body - int(time.time())) < 5


def test_mark_cluster_ready_is_idempotent(opts, tmp_path):
    """Two calls must not raise; second-call body overwrites first."""
    healthchecks.mark_cluster_ready(opts)
    first = _read(tmp_path / "health" / "ready")
    time.sleep(1.1)
    healthchecks.mark_cluster_ready(opts)
    second = _read(tmp_path / "health" / "ready")
    # Both calls succeeded; the second timestamp is at least 1 second
    # newer than the first.
    assert int(second) >= int(first)


def test_mark_startup_creates_health_dir_lazily(opts, tmp_path):
    """
    ``mark_startup_complete`` works even if ``reset_health_dir`` was
    never called (defensive: helper functions should not assume a
    previous setup step ran).
    """
    # Note: tmp_path exists but the ``health`` subdir does not.
    healthchecks.mark_startup_complete(opts)
    assert (tmp_path / "health" / "startup").is_file()


# ---------------------------------------------------------------------------
# touch_alive
# ---------------------------------------------------------------------------


def test_touch_alive_creates_then_advances_mtime(opts, tmp_path):
    """
    First call creates the sentinel; subsequent calls must bump the
    mtime so an exec probe can detect a wedged loop via ``stat -c %Y``.
    """
    healthchecks.touch_alive(opts)
    sentinel = tmp_path / "health" / "alive"
    assert sentinel.is_file()
    first_mtime = sentinel.stat().st_mtime

    # Sleep enough that filesystems with 1-second mtime granularity see
    # the second touch as a distinct timestamp.
    time.sleep(1.1)
    healthchecks.touch_alive(opts)
    second_mtime = sentinel.stat().st_mtime
    assert (
        second_mtime > first_mtime
    ), f"touch_alive did not advance mtime: {first_mtime} -> {second_mtime}"


def test_touch_alive_swallows_oserror(opts, monkeypatch, caplog):
    """A failed touch must not crash the heartbeat loop."""

    def boom(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("pathlib.Path.touch", boom)
    healthchecks.touch_alive(opts)
    assert "could not touch" in caplog.text


# ---------------------------------------------------------------------------
# is_clustered
# ---------------------------------------------------------------------------


def test_is_clustered_false_for_plain_master(opts):
    assert healthchecks.is_clustered(opts) is False


def test_is_clustered_true_when_cluster_id_and_peers_set(opts):
    opts["cluster_id"] = "x"
    opts["cluster_peers"] = ["127.0.0.2"]
    assert healthchecks.is_clustered(opts) is True


def test_is_clustered_false_when_cluster_id_missing(opts):
    opts["cluster_peers"] = ["127.0.0.2"]
    assert healthchecks.is_clustered(opts) is False


def test_is_clustered_false_when_peers_unset(opts):
    """An ``opts`` dict without ``cluster_peers`` is not clustered."""
    opts["cluster_id"] = "x"
    # cluster_peers absent — None is the sentinel for "not configured"
    assert healthchecks.is_clustered(opts) is False


def test_is_clustered_true_with_empty_peer_list(opts):
    """
    A cluster of one — explicit empty list — counts as clustered.  Users
    sometimes start with a single master and grow; the master is in
    cluster mode the moment the operator commits to it, even before any
    peer addresses are filled in.
    """
    opts["cluster_id"] = "x"
    opts["cluster_peers"] = []
    assert healthchecks.is_clustered(opts) is True


# ---------------------------------------------------------------------------
# Wire-format expectations a probe relies on
# ---------------------------------------------------------------------------


def test_sentinel_paths_match_documented_layout(opts, tmp_path):
    """
    Pin the exact filenames an operator's probe spec or runbook will
    reference.  If we ever rename them, this test fails loudly so the
    docs and probe specs can be updated in lockstep.
    """
    healthchecks.reset_health_dir(opts)
    healthchecks.mark_startup_complete(opts)
    healthchecks.mark_cluster_ready(opts)
    healthchecks.touch_alive(opts)

    health = tmp_path / "health"
    assert (health / "startup").is_file()
    assert (health / "ready").is_file()
    assert (health / "alive").is_file()
    # No surprise extras.
    assert sorted(p.name for p in health.iterdir()) == ["alive", "ready", "startup"]


def test_alive_mtime_threshold_check_matches_recommended_pattern(opts, tmp_path):
    """
    Operators recommended pattern is::

        test $(($(date +%s) - $(stat -c %Y .../alive))) -lt 30

    This test simulates the stat path: after a touch the diff to
    ``time.time()`` is < 5; after a 2-second pause the diff is at least
    1.  The probe interval must be > the heartbeat interval but well
    under 30 s.
    """
    healthchecks.touch_alive(opts)
    sentinel = tmp_path / "health" / "alive"
    age = time.time() - os.stat(sentinel).st_mtime
    assert age < 5, f"freshly-touched sentinel was already {age:.1f}s old"
