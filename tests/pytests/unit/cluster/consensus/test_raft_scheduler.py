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
