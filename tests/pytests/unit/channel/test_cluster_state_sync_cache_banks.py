"""
Unit tests for the join-time catch-up of replicate-mode cache banks.

Covers four behaviours:

* ``enumerate_replicate_banks`` walks the cachedir and filters out
  ``jobs`` / ``cluster/consensus`` / ``cluster/state_sync``.
* ``iter_cache_bank_chunks`` respects the per-chunk byte budget.
* ``install_bank_sync_chunk`` writes with ``_already_replicated=True``
  so the receiver does not re-broadcast.
* The barrier methods on ``MasterPubServerChannel`` queue a live
  delegate-cache-write until the matching ``bank_sync:<bank>``
  channel eofs and then replay the queue.
"""

import salt.cache
import salt.cluster.state_sync as ss

# ---------------------------------------------------------------------------
# enumerate_replicate_banks
# ---------------------------------------------------------------------------


def test_enumerate_replicate_banks_skips_internal_banks(tmp_path, monkeypatch):
    """
    ``jobs``, ``cluster/consensus`` and ``cluster/state_sync`` must not
    appear in the catch-up list even if their directories exist in the
    cachedir.
    """
    cachedir = tmp_path / "cache"
    cachedir.mkdir()
    for name in ("grains", "resources", "jobs", "minions"):
        (cachedir / name).mkdir()
    # The ``cluster`` subtree is skipped wholesale.
    (cachedir / "cluster").mkdir()
    (cachedir / "cluster" / "consensus").mkdir()
    (cachedir / "cluster" / "state_sync").mkdir()
    opts = {"cachedir": str(cachedir), "cluster_cache_routing": {}}
    banks = ss.enumerate_replicate_banks(opts)
    assert "jobs" not in banks
    assert "cluster" not in banks
    # ``grains`` / ``resources`` / ``minions`` all fall through the
    # longest-prefix matcher as "replicate" by default.
    assert "grains" in banks
    assert "resources" in banks
    assert "minions" in banks


def test_enumerate_replicate_banks_honours_operator_routing(tmp_path):
    """
    Operator-set ``cluster_cache_routing`` entries must suppress
    replicate for named banks.
    """
    cachedir = tmp_path / "cache"
    cachedir.mkdir()
    for name in ("grains", "secret_bank"):
        (cachedir / name).mkdir()
    opts = {
        "cachedir": str(cachedir),
        "cluster_cache_routing": {"secret_bank": "none"},
    }
    banks = ss.enumerate_replicate_banks(opts)
    assert "grains" in banks
    assert "secret_bank" not in banks


def test_enumerate_replicate_banks_empty_cachedir(tmp_path):
    opts = {"cachedir": str(tmp_path / "does_not_exist")}
    assert ss.enumerate_replicate_banks(opts) == []


# ---------------------------------------------------------------------------
# iter_cache_bank_chunks (byte-budget chunking)
# ---------------------------------------------------------------------------


class _FakeBankCache:
    """Minimal ``salt.cache.Cache``-compatible stub for chunker tests."""

    def __init__(self, dump):
        self._dump = dump

    def list_all(self, bank, include_data=True):
        return self._dump

    def store(self, bank, key, value, expires=None, _already_replicated=False):
        self.last_store = (bank, key, value, _already_replicated)


def test_iter_cache_bank_chunks_respects_byte_budget(monkeypatch):
    """
    With a small ``byte_budget`` every chunk should carry at most one
    big item.
    """
    big = "x" * 4096
    dump = {f"key-{i}": big for i in range(10)}
    fake = _FakeBankCache(dump)
    monkeypatch.setattr(salt.cache, "Cache", lambda opts, driver=None: fake)
    chunks = list(
        ss.iter_cache_bank_chunks({"cachedir": "/tmp"}, "grains", byte_budget=512)
    )
    # Every chunk holds >=1 entry; many chunks overall.
    assert all(len(chunk) >= 1 for chunk in chunks)
    assert len(chunks) >= 2
    # Every original key must appear exactly once across all chunks.
    seen = [item["key"] for chunk in chunks for item in chunk]
    assert sorted(seen) == sorted(dump.keys())


def test_iter_cache_bank_chunks_empty_bank_yields_one_empty(monkeypatch):
    fake = _FakeBankCache({})
    monkeypatch.setattr(salt.cache, "Cache", lambda opts, driver=None: fake)
    chunks = list(ss.iter_cache_bank_chunks({"cachedir": "/tmp"}, "grains"))
    assert chunks == [[]]


# ---------------------------------------------------------------------------
# install_bank_sync_chunk sets _already_replicated=True
# ---------------------------------------------------------------------------


def test_install_bank_sync_chunk_sets_already_replicated(monkeypatch):
    """
    The join-time install path must not re-broadcast -- every
    ``cache.store`` call carries ``_already_replicated=True``.
    """
    fake = _FakeBankCache({})
    monkeypatch.setattr(salt.cache, "Cache", lambda opts, driver=None: fake)
    items = [{"key": "mid-a", "value": {"grain": "x"}}]
    written = ss.install_bank_sync_chunk({"cachedir": "/tmp"}, "grains", items)
    assert written == 1
    assert fake.last_store == ("grains", "mid-a", {"grain": "x"}, True)


# ---------------------------------------------------------------------------
# Barrier: queue-then-replay on MasterPubServerChannel
# ---------------------------------------------------------------------------


class _BarrierHarness:
    """
    Minimal harness that exposes just the barrier helpers from
    ``MasterPubServerChannel`` so they can be exercised without the
    full publish-daemon machinery.  Mirrors the attributes those
    helpers actually touch.
    """

    def __init__(self):
        self.opts = {"id": "master-A"}
        self._cache_bank_barriers = {}
        self.applied = []

    # Pull the barrier methods off the real class so this harness
    # drifts in lockstep if the implementation changes.
    from salt.channel.server import MasterPubServerChannel

    _cache_bank_barrier_active = MasterPubServerChannel._cache_bank_barrier_active
    _queue_cache_bank_delta = MasterPubServerChannel._queue_cache_bank_delta
    _release_cache_bank_barrier = MasterPubServerChannel._release_cache_bank_barrier
    _drain_cache_bank_barrier = MasterPubServerChannel._drain_cache_bank_barrier


def test_barrier_queues_live_delta_until_eof(monkeypatch):
    """
    A live ``delegate-cache-write`` for a bank that still has a
    pending catch-up stream is queued, then applied on the matching
    ``bank_sync:<bank>`` eof.
    """
    harness = _BarrierHarness()
    harness._cache_bank_barriers = {"S": {"grains": []}}
    applied = []

    def fake_apply(opts, payload):
        applied.append(payload)
        return True

    monkeypatch.setattr(
        "salt.cache._cluster_replicator._handle_delegate_cache_write",
        fake_apply,
    )

    # Bank matches -> queued, not applied.
    payload1 = {"bank": "grains", "key": "mid-a", "data": {"grain": "x"}}
    assert harness._cache_bank_barrier_active("grains") is True
    harness._queue_cache_bank_delta("grains", payload1)
    assert harness._cache_bank_barriers["S"]["grains"] == [payload1]
    assert applied == []

    # Compound bank (grains/mid-b) matches longest-prefix on "grains".
    payload2 = {"bank": "grains/mid-b", "key": "mid-b", "data": {"g": "y"}}
    assert harness._cache_bank_barrier_active("grains/mid-b") is True
    harness._queue_cache_bank_delta("grains/mid-b", payload2)
    assert len(harness._cache_bank_barriers["S"]["grains"]) == 2

    # eof arrives -> both queued payloads are replayed in order.
    harness._release_cache_bank_barrier("S", "grains")
    assert applied == [payload1, payload2]
    # Barrier for this session is gone.
    assert "S" not in harness._cache_bank_barriers


def test_barrier_inactive_outside_pending_set():
    """
    A bank name not in any session's barrier set reports
    ``_cache_bank_barrier_active`` False (so the normal apply path
    is used).
    """
    harness = _BarrierHarness()
    harness._cache_bank_barriers = {"S": {"grains": []}}
    assert harness._cache_bank_barrier_active("resources") is False


def test_barrier_drain_fires_everything(monkeypatch):
    """
    ``_drain_cache_bank_barrier`` must flush all pending banks for a
    session (used by on_complete when the deadline forces completion).
    """
    harness = _BarrierHarness()
    applied = []

    def fake_apply(opts, payload):
        applied.append(payload)
        return True

    monkeypatch.setattr(
        "salt.cache._cluster_replicator._handle_delegate_cache_write",
        fake_apply,
    )

    harness._cache_bank_barriers = {
        "S": {
            "grains": [{"bank": "grains", "key": "a"}],
            "resources": [{"bank": "resources", "key": "b"}],
        }
    }
    harness._drain_cache_bank_barrier("S")
    assert sorted(p["bank"] for p in applied) == ["grains", "resources"]
    assert "S" not in harness._cache_bank_barriers
