"""
Regression tests for salt.utils.asynchronous.SyncWrapper.

Issue #65702: on Python 3.12+ the worker thread spawned by
``SyncWrapper._wrap`` had no asyncio event loop installed.  Any wrapped
coroutine that touched ``asyncio.get_event_loop`` (notably pyzmq's
future-based sockets, which back every master-initiated job) raised
``RuntimeError: There is no current event loop in thread 'Thread-N
(_target)'`` and aborted the publish.
"""

import asyncio
import time

import salt.ext.tornado.gen
import salt.utils.asynchronous as asynchronous


class _LoopProbe:
    """
    Minimal async helper whose coroutine calls ``asyncio.get_event_loop``
    from inside the SyncWrapper worker thread - the same call pyzmq's
    ``zmq.eventloop.future`` machinery performs on every send/poll.
    """

    async_methods = ["check_loop"]

    def __init__(self, io_loop=None):
        pass

    @salt.ext.tornado.gen.coroutine
    def check_loop(self):
        # On Python 3.12+ this raises RuntimeError unless an asyncio loop
        # has been installed on the current thread.  Pre-3.12 it returns
        # (and may auto-create) the loop.
        loop = asyncio.get_event_loop()
        raise salt.ext.tornado.gen.Return(loop is not None)


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


class _VariablePaceWorker:
    """
    Minimal async helper with one coroutine that outlives any reasonable
    caller patience and one that answers promptly.
    """

    async_methods = ["slow_call", "quick_call"]

    def __init__(self, io_loop=None):
        pass

    @salt.ext.tornado.gen.coroutine
    def slow_call(self):
        yield salt.ext.tornado.gen.sleep(5)
        raise salt.ext.tornado.gen.Return("slow done")

    @salt.ext.tornado.gen.coroutine
    def quick_call(self):
        yield salt.ext.tornado.gen.sleep(0.05)
        raise salt.ext.tornado.gen.Return("quick done")


def test_sync_wrapper_timeout_raises_instead_of_deadlocking_69824():
    """
    Issue #69824: ``SyncWrapper._wrap`` joined its worker thread with no
    timeout, so a wrapped coroutine that never resolved (a wedged event-bus
    publish) turned into a permanent, silent deadlock of the calling
    MWorker. With a bounded timeout the caller must get a ``TimeoutError``
    instead of blocking forever.
    """
    sync = asynchronous.SyncWrapper(_VariablePaceWorker, timeout=0.2)
    try:
        start = time.monotonic()
        try:
            sync.slow_call()
            raise AssertionError("slow_call() should have raised TimeoutError")
        except TimeoutError:
            pass
        assert time.monotonic() - start < 2, "TimeoutError arrived too late"
    finally:
        sync.close()


def test_sync_wrapper_without_timeout_still_waits_for_completion_69824():
    """
    The default ``SyncWrapper`` (no timeout) must keep its historical
    behaviour: wait for the wrapped coroutine and return its result.
    """
    sync = asynchronous.SyncWrapper(_VariablePaceWorker)
    try:
        assert sync.quick_call() == "quick done"
    finally:
        sync.close()
