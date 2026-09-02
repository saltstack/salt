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
from tests.support.mock import patch


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


class HelperPending:
    """A helper whose wrapped coroutine leaves a task pending on the loop."""

    async_methods = [
        "start_background",
    ]

    def __init__(self, io_loop=None):
        self.io_loop = io_loop

    @tornado.gen.coroutine
    def start_background(self):
        # Leave a long-lived task behind on this wrapper's own loop, so
        # ``close()`` has something to drain.
        asyncio.ensure_future(asyncio.sleep(3600))
        raise tornado.gen.Return(True)


def test_close_drains_tasks_belonging_to_the_wrappers_own_loop():
    """
    ``close()`` runs outside the loop it is tearing down -- the calling
    thread's current loop is a different one.  ``asyncio.gather`` no longer
    takes a ``loop`` argument, so it resolves the loop from the calling
    context, and on Python 3.14 gathering tasks that belong to another loop
    raises ``ValueError: The future belongs to a different loop than the one
    specified as the loop argument``.  Earlier versions took the loop from the
    first future and let it through, so this surfaced as a wall of
    "Error during asyncio shutdown" for every proxy minion on 3.14.

    Building the gather inside the loop drains the tasks on every version.
    """
    sync = asynchronous.SyncWrapper(HelperPending)
    sync.start_background()

    pending = [t for t in asyncio.all_tasks(sync.asyncio_loop) if not t.done()]
    assert pending, "expected a task pending on the wrapper's loop"

    # The failure only happens when ``close()`` is called from inside a
    # *different running* loop, which is how it is reached in a proxy minion:
    # ``asyncio.gather`` then resolves the running loop rather than the tasks'
    # own loop and rejects them.  Drive it that way.
    #
    # Asserting on the tasks alone would not catch this either -- they are
    # cancelled before the gather, so they end up done() regardless.  The
    # symptom is the swallowed exception, so assert nothing was logged.
    async def _close_from_another_running_loop():
        with patch.object(asynchronous.log, "error") as log_error:
            sync.close()
        return log_error.call_args_list

    driver = asyncio.new_event_loop()
    try:
        errors = driver.run_until_complete(_close_from_another_running_loop())
    finally:
        driver.close()

    # Only the swallowed exception is asserted on.  The tasks themselves
    # cannot be driven to completion here -- a loop cannot be run from inside
    # another running loop -- so their state is not the thing under test.
    assert not errors, errors
