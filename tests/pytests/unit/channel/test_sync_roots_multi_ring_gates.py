"""
Unit tests for the NEW-6 (sync_roots) and NEW-7a (multi-ring) fan-out
gates.  Both wrap ``self.pushers`` through
``filter_joined_pushers`` with ``pending_event=None`` so un-joined
peers are skipped with a WARN and catch up via the join-time
state-sync (sync_roots) or Raft AppendEntries (multi-ring).  See the
primary design §Fix 4 / §Fix 5 and the reviewer's Q4 (runner.py
in-scope for operator contract).
"""

import pytest

import salt.cache._cluster_replicator as _crep
from tests.support.mock import MagicMock, patch


class _FakePusher:
    """Minimal duck-typed Pusher stand-in for the gate (pull_host only)."""

    def __init__(self, pull_host):
        self.pull_host = pull_host
        self.published = []

    async def publish(self, event):
        self.published.append(event)

    def __repr__(self):
        return f"_FakePusher({self.pull_host!r})"


@pytest.fixture
def opts():
    return {
        "id": "master-1",
        "cluster_id": "cluster-A",
        "cluster_cache_replicate_require_joined": True,
    }


@pytest.fixture(autouse=True)
def _reset_pending():
    _crep._reset_pending_state()
    # ``_SKIP_LOG_LAST`` coalesces skip-warnings; clear it so each test
    # sees fresh WARN emissions for the peer(s) it exercises.
    with _crep._SKIP_LOG_LOCK:
        _crep._SKIP_LOG_LAST.clear()
    yield
    _crep._reset_pending_state()
    with _crep._SKIP_LOG_LOCK:
        _crep._SKIP_LOG_LAST.clear()


# ---------------------------------------------------------------------------
# NEW-6: sync_roots gate
# ---------------------------------------------------------------------------


def test_sync_roots_gate_filters_unjoined(opts):
    """
    Three pushers, two joined via ``_discover_replies``.  The gate
    keeps the two joined pushers; the third is in ``skipped``.
    ``pending_event=None`` means no entries are enqueued.
    """
    pushers = [_FakePusher("peer-A"), _FakePusher("peer-B"), _FakePusher("peer-C")]
    discover_replies = {"peer-A", "peer-B"}
    kept, skipped = _crep.filter_joined_pushers(
        pushers,
        discover_replies,
        {},
        opts,
        context="sync-roots",
        pending_event=None,
    )
    assert [p.pull_host for p in kept] == ["peer-A", "peer-B"]
    assert [p.pull_host for p in skipped] == ["peer-C"]
    # sync_roots is multi-event; no replay queue should be populated.
    for host in ("peer-A", "peer-B", "peer-C"):
        assert _crep.pending_queue_depth(host) == 0


def test_sync_roots_gate_warns_when_all_peers_unjoined(opts, caplog):
    """
    Every peer un-joined -> ``kept`` is empty.  The caller logs a
    WARN enumerating skipped peers; sync_roots returns gracefully
    because the catch-up path is state-sync on their next handshake.
    """
    pushers = [_FakePusher("peer-A"), _FakePusher("peer-B")]
    with caplog.at_level("WARNING"):
        kept, skipped = _crep.filter_joined_pushers(
            pushers, set(), {}, opts, context="sync-roots", pending_event=None
        )
    assert kept == []
    assert sorted(p.pull_host for p in skipped) == ["peer-A", "peer-B"]
    # ``filter_joined_pushers`` emits its own per-peer skip log; verify
    # the message is at WARN and names each peer.
    msgs = "\n".join(rec.message for rec in caplog.records)
    assert "peer-A" in msgs
    assert "peer-B" in msgs


def test_sync_roots_gate_disabled_via_opt(opts):
    """
    With ``cluster_cache_replicate_require_joined=False`` the gate is
    inactive: every pusher is kept and no skipped set is produced.
    """
    opts = dict(opts, cluster_cache_replicate_require_joined=False)
    pushers = [_FakePusher("peer-A"), _FakePusher("peer-B")]
    kept, skipped = _crep.filter_joined_pushers(
        pushers, set(), {}, opts, context="sync-roots", pending_event=None
    )
    assert [p.pull_host for p in kept] == ["peer-A", "peer-B"]
    assert skipped == []


# ---------------------------------------------------------------------------
# NEW-7a: multi-ring gate
# ---------------------------------------------------------------------------


def test_multi_ring_gate_filters_unjoined(opts):
    """
    Three pushers, one joined via ``peer_keys`` only.  The gate
    accepts either signal, so the one joined via ``peer_keys`` is
    kept; the other two are in ``skipped``.  No pending-queue
    population (Raft AppendEntries is the catch-up path).
    """
    pushers = [_FakePusher("peer-A"), _FakePusher("peer-B"), _FakePusher("peer-C")]
    peer_keys = {"peer-B": b"session-key"}
    kept, skipped = _crep.filter_joined_pushers(
        pushers,
        set(),
        peer_keys,
        opts,
        context="multi-ring-request",
        pending_event=None,
    )
    assert [p.pull_host for p in kept] == ["peer-B"]
    assert [p.pull_host for p in skipped] == ["peer-A", "peer-C"]
    for host in ("peer-A", "peer-B", "peer-C"):
        assert _crep.pending_queue_depth(host) == 0


def test_multi_ring_gate_all_unjoined_warns(opts, caplog):
    """
    Every peer un-joined -> gate returns empty kept; multi-ring
    fan-out still proceeds on the LOCAL propose path (RaftService
    handles leader detection).  The gate just suppresses a doomed
    network send + the decrypt-failed log noise on peers.
    """
    pushers = [_FakePusher("peer-A"), _FakePusher("peer-B")]
    with caplog.at_level("WARNING"):
        kept, skipped = _crep.filter_joined_pushers(
            pushers,
            set(),
            {},
            opts,
            context="multi-ring-request",
            pending_event=None,
        )
    assert kept == []
    assert sorted(p.pull_host for p in skipped) == ["peer-A", "peer-B"]
    # Each peer is named in the skip log.
    msgs = "\n".join(rec.message for rec in caplog.records)
    assert "peer-A" in msgs
    assert "peer-B" in msgs


def test_multi_ring_pending_event_none_does_not_enqueue(opts):
    """
    Explicit assertion: ``pending_event=None`` must NOT populate the
    per-peer replay queue.  A multi-ring-request replayed later would
    duplicate a propose attempt (idempotent at Raft but noisy).
    """
    pushers = [_FakePusher("peer-A")]
    _crep.filter_joined_pushers(
        pushers, set(), {}, opts, context="multi-ring-request", pending_event=None
    )
    assert _crep.pending_queue_depth("peer-A") == 0


# ---------------------------------------------------------------------------
# Runner-return shape (Q4)
# ---------------------------------------------------------------------------


def test_sync_roots_runner_return_carries_skipped_peers_note():
    """
    ``cluster.sync_roots`` returns a dict whose ``skipped_peers_note``
    key points the operator at the master-log signal for un-joined
    peers.  Backwards-compat: ``status`` key is still
    ``"fan-out initiated"``.
    """
    import salt.runners.cluster as cluster_runner

    event_mock = MagicMock()
    event_cm = MagicMock()
    event_cm.__enter__ = MagicMock(return_value=event_mock)
    event_cm.__exit__ = MagicMock(return_value=False)
    opts = {"cluster_id": "cluster-A", "sock_dir": "/tmp/_test_sock"}
    with patch.object(cluster_runner, "__opts__", opts, create=True), patch(
        "salt.utils.event.get_event", return_value=event_cm
    ):
        result = cluster_runner.sync_roots(roots="both")
    assert result["status"] == "fan-out initiated"
    assert "skipped_peers_note" in result
    assert "handshake" in result["skipped_peers_note"]


def test_fire_cluster_event_return_carries_skipped_peers_note():
    """
    ``_fire_cluster_event`` (shared by the multi-ring runners) adds a
    ``skipped_peers_note`` informational key to its return payload
    (Q4).  Existing callers that script against ``.get("status")``
    continue to work.
    """
    import salt.runners.cluster as cluster_runner

    event_mock = MagicMock()
    event_cm = MagicMock()
    event_cm.__enter__ = MagicMock(return_value=event_mock)
    event_cm.__exit__ = MagicMock(return_value=False)
    opts = {"cluster_id": "cluster-A", "sock_dir": "/tmp/_test_sock"}
    with patch.object(cluster_runner, "__opts__", opts, create=True), patch(
        "salt.utils.event.get_event", return_value=event_cm
    ):
        result = cluster_runner._fire_cluster_event(
            "cluster/runner/ring_create", {"name": "test", "voters": []}
        )
    assert result["status"] == "fan-out initiated"
    assert result["tag"] == "cluster/runner/ring_create"
    assert "skipped_peers_note" in result
    assert "Raft AppendEntries" in result["skipped_peers_note"]
