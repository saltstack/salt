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
