"""
Regression tests for the ``PubServer`` close-path Unpacker + drainer leak
on 3008.x.

Two independent retention paths were observed by tracemalloc on a live
salt-minion under sustained ``state.apply`` load (issue #70175):

1. ``PubServer._stream_read`` allocated one ``salt.utils.msgpack.Unpacker``
   (~1 MiB internal read buffer) per accepted stream.  On subscriber
   disconnect the coroutine's Task was cancelled, but the coroutine
   frame -- which holds the ``unpacker`` and ``client`` locals -- was
   pinned by a reference cycle::

       client -> client._read_task -> task._coro -> coroutine frame -> client

   Cyclic GC eventually collected it, but under bursty per-job
   subscriber churn tracemalloc showed +35 pinned ``Unpacker`` instances
   / +37 MiB retained after only 20 jobs.

2. ``PubServer._writers[client]`` -- an ``asyncio.Queue`` + drain-Task
   tuple created by ``_get_or_create_drainer`` -- was popped by
   ``_discard_slow_client`` on the drain-timeout path but NOT by
   ``_discard_on_close._cb()`` on the clean-close path.  Each cleanly
   disconnected subscriber leaked its Queue + Task pair (~25 kB apiece).

The fix in ``salt/transport/tcp.py``:

  * ``_stream_read`` gains a ``try/finally`` that does ``del unpacker``
    and ``client._read_task = None`` so the retention chain is broken
    immediately on coroutine exit -- no wait for the next cyclic-GC pass.
  * ``_discard_on_close._cb()`` also clears ``client._read_task`` (for
    the case where the coroutine has not yet resumed to observe the
    cancellation) and pops the ``self._writers`` entry, cancelling the
    drain task.

The two tests below assert those post-fix invariants.  Both were
verified to FAIL on ``origin/3008.x`` without the patch and PASS with
the patch (see PR description).
"""

import asyncio
import gc
import weakref

import pytest
import tornado.iostream

import salt.transport.tcp

pytestmark = [
    pytest.mark.core_test,
]


class _EOFStream:
    """
    Minimal ``IOStream``-lookalike whose ``read_bytes`` immediately raises
    ``StreamClosedError``.  Drives ``PubServer._stream_read`` through the
    ``_StreamClosedError`` branch -> ``break`` -> ``finally`` on the very
    first read, mimicking a peer that closed just after connect.
    """

    def __init__(self):
        self._closed = False

    def read_bytes(self, *args, **kwargs):
        raise tornado.iostream.StreamClosedError()

    def closed(self):
        return self._closed

    def close(self):
        self._closed = True


async def test_stream_read_releases_unpacker_and_task_ref_on_close(
    master_opts, io_loop
):
    """
    Post-fix contract: when ``_stream_read`` exits (either normally via
    ``StreamClosedError`` or via cancellation), the per-connection
    ``msgpack.Unpacker`` and the ``client._read_task`` back-reference
    must be released *immediately* -- without waiting for the cyclic
    garbage collector to break the ``client -> _read_task -> coro frame
    -> client`` cycle.

    Test strategy: disable the cyclic collector for the duration of the
    check so only refcount-based collection is available.  Track the
    ``Subscriber`` via ``weakref``.  On the patched code the ``finally``
    block clears ``client._read_task`` and drops the ``unpacker`` local
    from the frame, refcounts drop to zero, and the weakref returns
    ``None`` after a single event-loop turn.  On unpatched 3008.x the
    cycle survives (only cyclic GC could collect it) and the weakref
    stays live.
    """
    server = salt.transport.tcp.PubServer(master_opts, io_loop=io_loop)
    try:
        stream = _EOFStream()
        subscriber = salt.transport.tcp.Subscriber(stream, "eof-client")
        server.clients.add(subscriber)
        subscriber_ref = weakref.ref(subscriber)

        # Mimic ``handle_stream``: schedule ``_stream_read`` and record
        # the Task on the subscriber so the ``finally`` clause has
        # something to clear.
        subscriber._read_task = io_loop.asyncio_loop.create_task(
            server._stream_read(subscriber)
        )
        task_ref = weakref.ref(subscriber._read_task)

        # Freeze the cyclic collector -- we're specifically asserting
        # that the fix does not rely on cyclic-GC to release memory.
        gc.disable()
        try:
            # Let the task run.  The _EOFStream raises on the first read
            # so ``_stream_read`` exits its while loop and runs finally.
            await subscriber._read_task
            # One extra turn so any post-return bookkeeping (e.g. Task
            # ``__del__``) settles.
            await asyncio.sleep(0)

            assert (
                subscriber not in server.clients
            ), "Subscriber not removed from PubServer.clients on stream close"
            assert subscriber._read_task is None, (
                "Subscriber._read_task was not cleared on _stream_read exit "
                "-- the client -> _read_task -> coro frame -> client cycle "
                "still holds the coroutine frame (and its 1 MiB Unpacker) "
                "past coroutine exit; see issue #70175"
            )

            # Drop our own strong refs and confirm refcount collection
            # alone reclaims the Subscriber (and thus its Unpacker,
            # which lives on the coroutine frame the Task's __del__
            # already released).
            del subscriber
            del stream
            await asyncio.sleep(0)

            assert subscriber_ref() is None, (
                "Subscriber survives refcount collection -- the reference "
                "cycle client <-> _read_task <-> coro frame is still intact "
                "and only cyclic GC (disabled here) could break it.  On the "
                "patched code the ``finally`` clause in _stream_read does "
                "``del unpacker; client._read_task = None`` which breaks "
                "the cycle immediately."
            )
            # The Task itself should also be reclaimable at this point --
            # nothing in the coroutine frame references it back.
            assert (
                task_ref() is None
            ), "Read Task survives -- coroutine frame is still pinning it"
        finally:
            gc.enable()
    finally:
        server.close()


async def test_discard_on_close_pops_writers_entry_and_cancels_drainer(
    master_opts, io_loop
):
    """
    Post-fix contract: the close-callback returned by
    ``PubServer._discard_on_close`` must pop the subscriber's entry from
    ``self._writers`` and cancel the associated drain task, matching
    what ``_discard_slow_client`` already does on the timeout path.

    Current (unpatched) 3008.x behavior leaks the ``(asyncio.Queue,
    drain-Task)`` tuple -- ~25 kB per cleanly disconnected subscriber
    under per-job connection churn.
    """
    server = salt.transport.tcp.PubServer(master_opts, io_loop=io_loop)
    try:
        stream = _EOFStream()
        subscriber = salt.transport.tcp.Subscriber(stream, "drainer-client")
        server.clients.add(subscriber)

        # Force-create the writers entry -- normally
        # ``publish_payload`` does this lazily on first write.
        queue, drain_task = server._get_or_create_drainer(subscriber)
        assert subscriber in server._writers
        assert not drain_task.done()

        # Fire the close callback exactly like the tornado IOStream
        # would when the peer disconnects.
        cb = server._discard_on_close(subscriber)
        cb()

        # Give asyncio one turn to deliver the ``.cancel()`` we asked
        # for on the drain task.
        await asyncio.sleep(0)

        assert subscriber not in server._writers, (
            "Subscriber entry not popped from PubServer._writers on the "
            "close-callback path -- each cleanly disconnected subscriber "
            "leaks its (Queue, drain-Task) pair (~25 kB) until process "
            "exit; see issue #70175"
        )
        assert drain_task.cancelled() or drain_task.done(), (
            "Drain task not cancelled on the close-callback path -- the "
            "drainer coroutine survives (with its captured client + queue "
            "closures) even though the subscriber is gone"
        )
        assert (
            subscriber not in server.clients
        ), "Subscriber not discarded from PubServer.clients on close callback"
        # ``_read_task`` was never set on this subscriber (we didn't
        # schedule ``_stream_read``) but the callback should be
        # idempotent w.r.t. the attribute -- clearing None is fine.
        assert subscriber._read_task is None
    finally:
        server.close()
