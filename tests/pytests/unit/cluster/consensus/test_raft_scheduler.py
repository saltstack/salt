"""Tests for Raft timeout schedulers."""

import asyncio
import time

import pytest

from salt.cluster.consensus.raft.scheduler import (
    AsyncTimeoutScheduler,
    ManualTimeoutScheduler,
    ThreadedTimeoutScheduler,
    TimeoutHandle,
    TimeoutScheduler,
)
from tests.support.mock import Mock


def _run_async(async_fn):
    asyncio.run(async_fn())


@pytest.fixture
def threaded_scheduler():
    scheduler = ThreadedTimeoutScheduler()
    scheduler.start()
    try:
        yield scheduler
    finally:
        scheduler.stop()


def test_threaded_timeout_scheduler(threaded_scheduler):
    moc = Mock()
    threaded_scheduler.schedule(0.01, moc)
    time.sleep(0.021)
    moc.assert_called_once()


def test_timeout_scheduler():
    scheduler = TimeoutScheduler()
    moc = Mock()
    scheduler.schedule(0.0001, moc)
    time.sleep(0.00012)
    scheduler.process_timeouts()
    moc.assert_called_once()


def test_timeout_handle_cancel_is_idempotent():
    sch = ManualTimeoutScheduler()
    called = []

    def cb():
        called.append(1)

    h = sch.schedule(1.0, cb)
    assert isinstance(h, TimeoutHandle)
    h.cancel()
    h.cancel()
    sch.time = 2.0
    sch.process_timeouts()
    assert called == []


def test_manual_timeout_scheduler_order():
    sch = ManualTimeoutScheduler()
    calls = []
    sch.schedule(0.5, lambda: calls.append("b"))
    sch.schedule(0.1, lambda: calls.append("a"))
    assert sch.advance_clock_to_next_timeout() is True
    sch.process_timeouts()
    assert calls == ["a"]
    assert sch.advance_clock_to_next_timeout() is True
    sch.process_timeouts()
    assert calls == ["a", "b"]


def test_async_timeout_scheduler_callback():
    async def _body():
        loop = asyncio.get_running_loop()
        scheduler = AsyncTimeoutScheduler(loop)
        moc = Mock()
        scheduler.schedule(0.0001, moc)
        await asyncio.sleep(0.00012)
        moc.assert_called_once()

    _run_async(_body)


def test_async_timeout_scheduler_coroutine():
    async def _body():
        async def callback():
            callback.called = True

        callback.called = False

        loop = asyncio.get_running_loop()
        scheduler = AsyncTimeoutScheduler(loop)
        scheduler.schedule(0.0001, callback)
        await asyncio.sleep(0.002)
        assert callback.called is True

    _run_async(_body)


# ---------------------------------------------------------------------------
# Coverage gaps: ThreadedTimeoutScheduler exception path, ManualTimeoutScheduler
# advance_clock_to_next_timeout, AsyncTimeoutScheduler.stop,
# TimeoutHandle manual cancel with lock, TimeoutScheduler.process_timeouts
# ---------------------------------------------------------------------------


def test_threaded_scheduler_exception_in_callback_is_caught():
    """Exception in a threaded callback is logged but does not kill the thread."""
    import time

    from salt.cluster.consensus.raft.scheduler import ThreadedTimeoutScheduler

    scheduler = ThreadedTimeoutScheduler()
    scheduler.start()
    try:
        called = []

        def bad_callback():
            called.append(1)
            raise RuntimeError("boom in callback")

        scheduler.schedule(0.001, bad_callback)
        time.sleep(0.05)
        assert called, "bad_callback must have been called"
        # Thread must still be alive after the exception
        assert scheduler._thread.is_alive()
    finally:
        scheduler.stop()


def test_manual_timeout_scheduler_advance_clock_empty():
    """advance_clock_to_next_timeout returns None when no timeouts are queued."""
    from salt.cluster.consensus.raft.scheduler import ManualTimeoutScheduler

    scheduler = ManualTimeoutScheduler()
    result = scheduler.advance_clock_to_next_timeout()
    assert result is None


def test_manual_timeout_scheduler_advance_clock_advances_to_next():
    from salt.cluster.consensus.raft.scheduler import ManualTimeoutScheduler

    scheduler = ManualTimeoutScheduler()
    fired = []
    scheduler.schedule(0.1, lambda: fired.append(1))
    result = scheduler.advance_clock_to_next_timeout()
    assert result is True
    assert scheduler.time == 0.1
    scheduler.process_timeouts()
    assert fired == [1]


def test_async_timeout_scheduler_stop_is_noop():
    """AsyncTimeoutScheduler.stop() must not raise."""
    import asyncio

    from salt.cluster.consensus.raft.scheduler import AsyncTimeoutScheduler

    loop = asyncio.new_event_loop()
    try:
        scheduler = AsyncTimeoutScheduler(loop=loop)
        scheduler.stop()  # must be a no-op
    finally:
        loop.close()


def test_timeout_scheduler_process_timeouts_fires_past_due():
    """TimeoutScheduler.process_timeouts fires callbacks that are past due."""
    import time

    from salt.cluster.consensus.raft.scheduler import TimeoutScheduler

    scheduler = TimeoutScheduler()
    fired = []
    # Schedule with 0 delay → immediately past due
    t = time.monotonic()
    scheduler.timeouts[t - 0.1] = lambda: fired.append(1)
    scheduler.process_timeouts()
    assert fired == [1]


def test_timeout_handle_manual_cancel_with_lock():
    """TimeoutHandle cancels correctly via the scheduler lock path."""
    from salt.cluster.consensus.raft.scheduler import ManualTimeoutScheduler

    scheduler = ManualTimeoutScheduler()
    fired = []
    handle = scheduler.schedule(0.1, lambda: fired.append(1))
    handle.cancel()
    scheduler.advance_clock_to_next_timeout()
    scheduler.process_timeouts()
    assert fired == [], "cancelled callback must not fire"


def test_timeout_handle_cancel_via_threaded_lock():
    """TimeoutHandle.cancel uses the scheduler lock when present (ThreadedTimeoutScheduler)."""
    import time

    from salt.cluster.consensus.raft.scheduler import ThreadedTimeoutScheduler

    scheduler = ThreadedTimeoutScheduler()
    scheduler.start()
    try:
        fired = []
        handle = scheduler.schedule(0.05, lambda: fired.append(1))
        handle.cancel()
        time.sleep(0.1)
        assert fired == [], "cancelled handle must not fire"
    finally:
        scheduler.stop()


def test_async_scheduler_coroutine_callback():
    """AsyncTimeoutScheduler fires coroutine callbacks via create_task."""
    import asyncio

    from salt.cluster.consensus.raft.scheduler import AsyncTimeoutScheduler

    async def _body():
        loop = asyncio.get_event_loop()
        scheduler = AsyncTimeoutScheduler(loop=loop)
        fired = []

        async def coro_cb():
            fired.append(1)

        scheduler.schedule(0.001, coro_cb)
        await asyncio.sleep(0.02)
        assert fired == [1]

    asyncio.run(_body())


def test_async_scheduler_cancelled_wrapper_returns_early():
    """AsyncTimeoutScheduler: cancelled wrapper exits without calling callback."""
    import asyncio

    from salt.cluster.consensus.raft.scheduler import AsyncTimeoutScheduler

    async def _body():
        loop = asyncio.get_event_loop()
        scheduler = AsyncTimeoutScheduler(loop=loop)
        fired = []

        def cb():
            fired.append(1)

        handle = scheduler.schedule(0.001, cb)
        handle.cancel()
        await asyncio.sleep(0.02)
        assert fired == [], "callback must not fire after cancel"

    asyncio.run(_body())
