"""
Unit tests for the per-peer flush-latch that serialises a handshake-
driven ``flush_pending_for_peer`` drain with concurrent live publishes
to the same peer.

See ``salt/cache/_cluster_replicator.py::flush_pending_for_peer`` +
``publish_with_latch`` + ``_get_peer_latch`` for the drain + latch
plumbing, and the two live-publish sites in
``salt/channel/server.py`` that route live writes through
``publish_with_latch``.
"""

import asyncio

import pytest

import salt.cache._cluster_replicator as _crep


class _FakePusher:
    """Minimal Pusher stand-in that records published events in-order."""

    def __init__(self, pull_host):
        self.pull_host = pull_host
        self.published = []

    async def publish(self, event):
        self.published.append(event)


class _BlockingPusher:
    """
    Pusher whose ``publish`` blocks on an ``asyncio.Event`` so the
    test can orchestrate a drain + concurrent live publish.
    """

    def __init__(self, pull_host):
        self.pull_host = pull_host
        self.published = []
        self.gate = asyncio.Event()

    async def publish(self, event):
        # Wait on the gate on the FIRST publish; later publishes
        # proceed immediately so re-entry doesn't deadlock the test.
        if not self.gate.is_set():
            await self.gate.wait()
        self.published.append(event)


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
    with _crep._SKIP_LOG_LOCK:
        _crep._SKIP_LOG_LAST.clear()
    yield
    _crep._reset_pending_state()
    with _crep._SKIP_LOG_LOCK:
        _crep._SKIP_LOG_LAST.clear()


# ---------------------------------------------------------------------------
# Flush-latch serialises handshake-driven drain + live publish
# ---------------------------------------------------------------------------


def test_concurrent_drain_and_publish_preserves_order_live_wins_over_stale(opts):
    """
    The per-peer flush-latch ensures a live publish WAITS for an in-
    flight handshake-driven drain to complete.  Under last-writer-wins
    semantics on the peer, this preserves "live wins over stale"
    because the live entry lands LAST on the socket.

    Scenario:
        T0: queue 3 stale entries for peer-A.
        T1: start a drain (holds the latch across all 3 publishes).
        T2: concurrent live publish for peer-A arrives; must wait.
        T3: drain finishes 3 publishes; releases latch.
        T4: live publish completes.

    Assertion: pusher.published is ``[stale-0, stale-1, stale-2, live]``,
    in that order.
    """
    pusher = _BlockingPusher("peer-A")

    # Enqueue 3 stale entries.
    for i in range(3):
        _crep.enqueue_pending(
            "peer-A",
            _crep.PendingEvent(kind="cache", event=f"stale-{i}".encode(), tag="t"),
            opts=opts,
        )

    async def _run():
        # Start the drain -- it awaits the gate on its FIRST publish.
        drain_task = asyncio.create_task(
            _crep.flush_pending_for_peer("peer-A", [pusher], opts=opts)
        )
        # Yield so the drain task starts and blocks on pusher.gate.
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        # Start the live publish -- it should block on the latch.
        live_task = asyncio.create_task(
            _crep.publish_with_latch("peer-A", pusher, b"live")
        )
        await asyncio.sleep(0)
        # Neither task has made progress yet.
        assert pusher.published == []

        # Let the drain's publishes proceed.
        pusher.gate.set()

        flushed = await drain_task
        await live_task
        return flushed

    loop = asyncio.new_event_loop()
    try:
        # Re-init the latch in this loop's context -- _reset_pending_state
        # clears, _get_peer_latch instantiates on first touch inside this
        # loop so the asyncio.Lock is bound to the right loop.
        flushed = loop.run_until_complete(_run())
    finally:
        loop.close()
    assert flushed == 3
    assert pusher.published == [b"stale-0", b"stale-1", b"stale-2", b"live"]


def test_publish_with_latch_without_concurrent_drain(opts):
    """
    Fast-path: no drain running -> ``publish_with_latch`` acquires the
    (uncontended) latch and publishes immediately.
    """
    pusher = _FakePusher("peer-A")

    async def _run():
        await _crep.publish_with_latch("peer-A", pusher, b"evt")

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_run())
    finally:
        loop.close()
    assert pusher.published == [b"evt"]


def test_flush_pending_for_peer_acquires_same_latch_as_live():
    """
    Guards against a regression where ``flush_pending_for_peer`` and
    ``publish_with_latch`` hold DIFFERENT lock objects -- in which
    case the "live wins over stale" invariant collapses.
    """
    # Same peer -> SAME latch object.
    latch_a1 = _crep._get_peer_latch("peer-A")
    latch_a2 = _crep._get_peer_latch("peer-A")
    assert latch_a1 is latch_a2
    # Different peers -> different latches.
    latch_b = _crep._get_peer_latch("peer-B")
    assert latch_a1 is not latch_b
