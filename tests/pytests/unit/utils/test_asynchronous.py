"""
Tests for salt.utils.asynchronous.SyncWrapper.

Includes regression tests for issue #65702: on Python 3.12+ the worker
thread spawned by ``SyncWrapper._wrap`` had no asyncio event loop
installed.  Any wrapped coroutine that touched
``asyncio.get_event_loop`` (notably pyzmq's future-based sockets, which
back every master-initiated job) raised
``RuntimeError: There is no current event loop in thread 'Thread-N
(_target)'`` and aborted the publish.
"""

import asyncio

import pytest
import tornado.gen
import tornado.ioloop

import salt.utils.asynchronous as asynchronous


class HelperA:
    async_methods = [
        "sleep",
    ]

    def __init__(self, io_loop=None):
        pass

    @tornado.gen.coroutine
    def sleep(self):
        yield tornado.gen.sleep(0.1)
        raise tornado.gen.Return(True)


class HelperB:
    async_methods = [
        "sleep",
    ]

    def __init__(self, a=None, io_loop=None):
        if a is None:
            a = asynchronous.SyncWrapper(HelperA)
        self.a = a

    @tornado.gen.coroutine
    def sleep(self):
        yield tornado.gen.sleep(0.1)
        self.a.sleep()
        raise tornado.gen.Return(False)


class _LoopProbe:
    """
    Minimal async helper whose coroutine calls ``asyncio.get_event_loop``
    from inside the SyncWrapper worker thread - the same call pyzmq's
    ``zmq.eventloop.future`` machinery performs on every send/poll.
    """

    async_methods = ["check_loop"]

    def __init__(self, io_loop=None):
        pass

    @tornado.gen.coroutine
    def check_loop(self):
        # On Python 3.12+ this raises RuntimeError unless an asyncio loop
        # has been installed on the current thread.  Pre-3.12 it returns
        # (and may auto-create) the loop.
        loop = asyncio.get_event_loop()
        raise tornado.gen.Return(loop is not None)


@pytest.mark.no_blocking(
    reason="HelperA.sleep yields tornado.gen.sleep(0.1); the coroutine "
    "resume callback intentionally holds the loop for 100 ms, which is "
    "exactly what the SyncWrapper contract permits and this test asserts. "
    "The asyncio slow-callback detector cannot distinguish this legitimate "
    "sync-in-async wrapping from a handler bug — see tests/pytests/unit/"
    "conftest.py::_asyncio_blocking_detection."
)
def test_helpers():
    """
    Test that the helper classes do what we expect within a regular asynchronous env
    """
    asyncio_loop = asyncio.new_event_loop()
    io_loop = tornado.ioloop.IOLoop(asyncio_loop=asyncio_loop, make_current=False)
    ret = io_loop.run_sync(lambda: HelperA().sleep())
    assert ret is True

    ret = io_loop.run_sync(lambda: HelperB().sleep())
    assert ret is False


def test_basic_wrap():
    """
    Test that we can wrap an asynchronous caller.
    """
    sync = asynchronous.SyncWrapper(HelperA)
    ret = sync.sleep()
    assert ret is True


def test_basic_wrap_series():
    """
    Test that we can wrap an asynchronous caller and call the method in series.
    """
    sync = asynchronous.SyncWrapper(HelperA)
    ret = sync.sleep()
    assert ret is True
    ret = sync.sleep()
    assert ret is True


@pytest.mark.no_blocking(
    reason="HelperB.sleep yields tornado.gen.sleep(0.1) then blocks on a "
    "SyncWrapper call — legitimate SyncWrapper stacking, not a handler "
    "bug. See test_helpers for the full rationale."
)
def test_double():
    """
    Test when the asynchronous wrapper object itself creates a wrap of another thing

    This works fine since the second wrap is based on the first's IOLoop so we
    don't have to worry about complex start/stop mechanics
    """
    sync = asynchronous.SyncWrapper(HelperB)
    ret = sync.sleep()
    assert ret is False


@pytest.mark.no_blocking(
    reason="Same SyncWrapper stacking pattern as test_double; see "
    "test_helpers for rationale."
)
def test_double_sameloop():
    """
    Test asynchronous wrappers initiated from the same IOLoop, to ensure that
    we don't wire up both to the same IOLoop (since it causes MANY problems).
    """
    a = asynchronous.SyncWrapper(HelperA)
    sync = asynchronous.SyncWrapper(HelperB, (a,))
    ret = sync.sleep()
    assert ret is False


def test_sync_wrapper_thread_has_asyncio_loop_65702():
    """
    SyncWrapper's worker thread must expose an asyncio event loop so that
    libraries which call ``asyncio.get_event_loop`` (e.g. pyzmq's
    future-based sockets used by master-initiated job publishes) work on
    Python 3.12+.
    """
    sync = asynchronous.SyncWrapper(_LoopProbe)
    try:
        assert sync.check_loop() is True
    finally:
        sync.close()


class _AsyncioTaskScheduler:
    """
    Async helper whose coroutine schedules a bare task on the asyncio
    loop that ``SyncWrapper._target`` installed as ``current`` for the
    worker thread -- mirrors what pyzmq's ``zmq.eventloop.future``
    machinery and tornado's asyncio bridge do internally when a wrapped
    coroutine touches a socket.  The scheduled task is not awaited
    from within the tornado ``run_sync``: tornado drives its own
    coroutine to completion, but any task landed on
    ``SyncWrapper.asyncio_loop`` is never iterated because that loop
    only ever has ``asyncio.set_event_loop`` called on it, never
    ``run_forever`` / ``run_until_complete``.
    """

    async_methods = ["schedule_and_return"]

    def __init__(self, io_loop=None):
        pass

    @tornado.gen.coroutine
    def schedule_and_return(self):
        async def _child():
            # Never resolves within the outer ``run_sync`` window;
            # models a background poll / socket-read coroutine that
            # pyzmq's future-based sockets spawn and don't await
            # from inside the wrapped call.
            await asyncio.sleep(1000)
            return 1

        loop = asyncio.get_event_loop()
        loop.create_task(_child())
        raise tornado.gen.Return(True)


def test_sync_wrapper_reaps_pending_tasks_after_run_sync():
    """
    Regression test for #70169: ``SyncWrapper._target`` installs
    ``self.asyncio_loop`` as the current asyncio loop on its worker
    thread but drives the wrapped coroutine through tornado's
    ``io_loop.run_sync``.  Any ``asyncio.Task`` created inside the
    wrapped coroutine on the asyncio-side is never iterated and pins
    its coroutine + ``contextvars.Context`` until ``close()``.  Under
    long-lived driver processes (``EventReturn``, ``BatchManager``)
    that never call ``close()`` in steady state, the retention
    accumulates for the process lifetime.
    """
    # Route through ``_target`` (the cross-thread dispatch path) by
    # calling from inside a running asyncio loop -- that is the
    # ``asyncio.get_running_loop()`` branch in ``_wrap`` that spawns a
    # worker thread and calls ``asyncio.set_event_loop(asyncio_loop)``.
    sync = asynchronous.SyncWrapper(_AsyncioTaskScheduler)
    outer_loop = asyncio.new_event_loop()
    try:

        async def _driver():
            for _ in range(50):
                assert sync.schedule_and_return() is True

        outer_loop.run_until_complete(_driver())
        pending = [t for t in asyncio.all_tasks(sync.asyncio_loop) if not t.done()]
        assert not pending, (
            f"SyncWrapper leaked {len(pending)} pending asyncio Task(s) on its "
            "asyncio_loop after 50 dispatches; each pins its coroutine + "
            "contextvars.Context and is never garbage collected until close()"
        )
    finally:
        outer_loop.close()
        sync.close()
