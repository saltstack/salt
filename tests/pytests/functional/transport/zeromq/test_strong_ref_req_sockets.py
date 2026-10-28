"""
Regression tests for ``RequestClient``'s strong-ref socket tracking
(#70353 part 2).

The pyzmq ``Context.__del__`` wedge in #70353 is reached via a cyclic GC
pass: an ``AsyncAuth._authenticate`` coroutine stranded on a closed
``SyncWrapper`` loop keeps a reference to the ``RequestClient``, which
keeps a reference to the ``zmq.asyncio.Context``.  When the GC trips the
cycle, it clears weakrefs *before* it runs finalizers, so by the time
the ``weakref.finalize`` callback for the context fires, the context's
own ``_sockets`` WeakSet is empty -- but the underlying ``Socket``
objects are still open (``Socket.__del__`` only runs later in the same
GC pass).  ``context.destroy()``'s "close every tracked socket, then
``term()``" therefore terminates while a Salt-owned socket is still
open, and ``zmq_ctx_term()`` wedges the thread running GC.

Part 1 of the fix (``SyncWrapper.close`` helper-thread drain) breaks
the cycle in the common case.  Part 2 -- tested here -- is a
belt-and-suspenders guarantee for the cases part 1 misses: the
``RequestClient`` tracks every socket it opens in a strong-ref list on
the instance, hands that list to the finalizer, and the finalizer
closes those sockets with ``LINGER=0`` before calling ``term()``.  No
daemon thread, no leaked context.

Each test runs the finalizer-driven teardown on a bounded daemon thread
so a regression fails the test rather than hanging the whole run.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import textwrap
import threading
import time

import pytest
import zmq

import salt.transport.zeromq

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skipif(
        sys.platform != "linux",
        reason="Timing-sensitive; run only on Linux where GC/finalizer "
        "scheduling is deterministic enough for the wedge threshold.",
    ),
]

# TEST-NET-1, documented as never routed; connect() + send() queue
# bytes into the socket's outbound buffer with no peer to drain them,
# which is the exact state that makes close() under LINGER=-1 block.
UNREACHABLE = "tcp://192.0.2.1:4506"

# If the finalizer-driven teardown takes longer than this, the wedge
# has reproduced (production wedges were effectively infinite).
WEDGE_TIMEOUT_S = 4.0


def _run_bounded(thunk, timeout_s=WEDGE_TIMEOUT_S):
    """Run ``thunk`` in a daemon thread, return ``(completed, elapsed)``.

    Must not join the thread on timeout -- the thread is wedged in a
    C-level ``zmq_ctx_term()`` and cannot be interrupted.  The daemon
    flag lets the interpreter exit while the thread is still stuck.
    """
    done = threading.Event()
    started_at = [None]

    def _worker():
        started_at[0] = time.monotonic()
        try:
            thunk()
        finally:
            done.set()

    t = threading.Thread(target=_worker, daemon=True, name="finalize-probe")
    t.start()
    finished = done.wait(timeout_s)
    if finished:
        return True, time.monotonic() - started_at[0]
    return False, timeout_s


def test_finalizer_closes_tracked_sockets_and_terms_fast():
    """Base case: a live context + a tracked open REQ socket with a
    queued undeliverable send.  The finalizer must close the socket
    with LINGER=0 and ``term()`` must return promptly on the calling
    thread.
    """
    ctx = zmq.Context()
    sock = ctx.socket(zmq.REQ)
    sock.linger = -1  # pyzmq default; what the wedge needs
    sock.connect(UNREACHABLE)
    sock.send(b"queued-but-never-delivered", flags=zmq.NOBLOCK)

    owned = [sock]

    completed, elapsed = _run_bounded(
        lambda: salt.transport.zeromq._finalize_zmq_context(ctx, owned),
        timeout_s=WEDGE_TIMEOUT_S,
    )

    assert completed, (
        f"_finalize_zmq_context did not return within {WEDGE_TIMEOUT_S}s; "
        "term() wedged on a Salt-tracked socket that should have been "
        "closed with LINGER=0 first."
    )
    assert sock.closed, "finalizer did not close the tracked REQ socket"
    assert ctx.closed, "finalizer returned but context is not closed"


def test_finalizer_closes_socket_dropped_from_context_tracker():
    """The exact #70353 shape: a cyclic GC pass has already cleared the
    weakref, so ``Context._sockets`` is empty, but the socket is still
    open.  ``context.destroy()`` would silently miss it and ``term()``
    would wedge.  Our strong-ref list on the ``RequestClient`` keeps
    the socket visible to the finalizer regardless.
    """
    ctx = zmq.Context()
    sock = ctx.socket(zmq.REQ)
    sock.linger = -1
    sock.connect(UNREACHABLE)
    sock.send(b"queued-but-never-delivered", flags=zmq.NOBLOCK)

    # Simulate "cyclic GC has cleared the WeakSet entry but Socket.__del__
    # has not run yet".  ``_sockets`` is a WeakSet; discard() mirrors
    # what the GC does to the weakref before finalizers run.
    ctx._sockets.discard(sock)

    owned = [sock]
    completed, elapsed = _run_bounded(
        lambda: salt.transport.zeromq._finalize_zmq_context(ctx, owned),
        timeout_s=WEDGE_TIMEOUT_S,
    )

    assert completed, (
        f"_finalize_zmq_context did not return within {WEDGE_TIMEOUT_S}s "
        "when the socket was already missing from ``Context._sockets``. "
        "This is the exact production failure mode from #70353."
    )
    assert sock.closed
    assert ctx.closed


def test_finalizer_tolerates_already_closed_resources():
    """The finalizer must be idempotent: a closed socket + closed
    context should not raise.  Explicit ``close()`` on the
    ``RequestClient`` runs ``context.destroy(0)`` first; the
    GC-triggered finalizer later still fires on the dead resources.
    """
    ctx = zmq.Context()
    sock = ctx.socket(zmq.REQ)
    sock.close()
    ctx.term()
    assert sock.closed and ctx.closed

    # Both already closed -- must be a no-op.
    salt.transport.zeromq._finalize_zmq_context(ctx, [sock])

    # None context (constructor failed before Context creation) -- no raise.
    salt.transport.zeromq._finalize_zmq_context(None, [])
    salt.transport.zeromq._finalize_zmq_context(None, None)


def test_request_client_tracks_sockets_on_owned_sockets_list():
    """Static invariant: the strong-ref list is populated by
    ``_init_socket`` so it is non-empty by the time the finalizer runs.
    """

    opts = {
        "master_uri": UNREACHABLE,
        "master_ip": "192.0.2.1",
        "master_port": 4506,
        "__role": "minion",
        "id": "test-70353",
        "acceptance_wait_time": 1,
    }

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        client = salt.transport.zeromq.RequestClient(opts, io_loop=loop)
        assert client._owned_sockets == []
        try:
            # Drive ``_init_socket`` without going through the full
            # ``connect`` dance; ``connect`` requires the ioloop be running.
            client._init_socket()
            assert client.socket is not None
            assert client._owned_sockets, (
                "RequestClient._init_socket did not append the REQ socket "
                "to self._owned_sockets.  The finalizer has nothing to close."
            )
            assert client.socket in client._owned_sockets
        finally:
            # Clean up the task + socket so the loop can close cleanly.
            if client.send_recv_task is not None:
                try:
                    client.send_recv_task.cancel()
                except RuntimeError:
                    pass
            if client.socket is not None:
                try:
                    client.socket.close()
                except Exception:  # pylint: disable=broad-except
                    pass
            if client.context is not None and not client.context.closed:
                try:
                    client.context.destroy(linger=0)
                except Exception:  # pylint: disable=broad-except
                    pass
    finally:
        asyncio.set_event_loop(None)
        loop.close()


def test_gc_of_cyclic_request_client_does_not_wedge():
    """The end-to-end #70353 reproducer, in a subprocess.

    Build a reference cycle whose single live-root is a coroutine frame
    that holds the ``RequestClient`` (which holds the context and the
    REQ socket with a queued send).  Drop every external reference,
    then run ``gc.collect()`` -- which clears weakrefs first, then
    runs finalizers.  On a 3008.x base without the strong-ref list,
    this wedges in ``zmq_ctx_term()`` and the subprocess times out.
    With the fix, the finalizer closes the Salt-tracked socket with
    LINGER=0 and ``term()`` returns promptly.

    Runs in a subprocess so a regression trips the ``timeout`` kwarg
    instead of hanging the whole test session.
    """
    code = textwrap.dedent(
        f"""
        import asyncio
        import faulthandler
        import gc
        import sys
        import weakref

        import zmq
        import zmq.asyncio

        from salt.transport.zeromq import _finalize_zmq_context

        faulthandler.dump_traceback_later(20, exit=True)

        # zmq.asyncio.Socket.send() needs a running / current event loop
        # to construct its Future.  Set one up so Owner.__init__ can
        # queue the undeliverable send that puts the socket into the
        # exact state that would wedge zmq_ctx_term().
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)


        class Owner:
            # Stand-in for RequestClient: holds strong refs to the
            # context + an owned-sockets list, registers the finalizer.
            def __init__(self):
                self.context = zmq.asyncio.Context()
                self.socket = self.context.socket(zmq.REQ)
                self.socket.linger = -1
                self.socket.connect({UNREACHABLE!r})
                self.socket.send(b"queued", flags=zmq.NOBLOCK)
                self._owned_sockets = [self.socket]
                weakref.finalize(
                    self, _finalize_zmq_context,
                    self.context, self._owned_sockets,
                )


        class Frame:
            # Stands in for the stranded AsyncAuth._authenticate
            # coroutine frame that pins the RequestClient.
            pass


        owner = Owner()
        frame = Frame()
        frame.owner = owner
        frame.cycle = frame  # cycle so refcount alone cannot collect
        del owner, frame
        gc.collect()
        print("collected", flush=True)
        """
    )
    try:
        ret = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except subprocess.TimeoutExpired:
        pytest.fail(
            "gc.collect() wedged in _finalize_zmq_context -> zmq_ctx_term(). "
            "This is the exact production failure mode from #70353."
        )
    assert ret.returncode == 0, (
        f"subprocess exited non-zero (rc={ret.returncode}); "
        f"stdout={ret.stdout!r} stderr={ret.stderr!r}"
    )
    assert "collected" in ret.stdout, (
        f"subprocess did not reach the post-gc print; "
        f"stdout={ret.stdout!r} stderr={ret.stderr!r}"
    )


def test_finalizer_runs_on_calling_thread_no_daemon_thread():
    """The alternative to #70415's part-2 approach is specifically to
    avoid handing ``term()`` off to a daemon thread.  Record the thread
    IDs that run ``term()`` during the finalizer and assert that no
    ``salt-zmq-context-term`` daemon thread shows up.
    """
    before = {t.name for t in threading.enumerate()}

    ctx = zmq.Context()
    sock = ctx.socket(zmq.REQ)
    sock.linger = -1
    sock.connect(UNREACHABLE)
    sock.send(b"queued", flags=zmq.NOBLOCK)

    calling_thread = threading.get_ident()
    seen_thread = [None]

    orig_term = type(ctx).term

    def _probe_term(self):
        seen_thread[0] = threading.get_ident()
        return orig_term(self)

    # Monkey-patch ``term`` on this one context's class instance to see
    # which thread actually runs it.
    try:
        type(ctx).term = _probe_term  # pyzmq Context.term
        salt.transport.zeromq._finalize_zmq_context(ctx, [sock])
    finally:
        type(ctx).term = orig_term

    assert seen_thread[0] == calling_thread, (
        f"term() ran on thread {seen_thread[0]!r} but the finalizer was "
        f"invoked on {calling_thread!r}.  The fix is supposed to run "
        "term() on the calling thread, not a daemon thread."
    )

    after = {t.name for t in threading.enumerate()}
    new_threads = after - before
    assert "salt-zmq-context-term" not in new_threads, (
        f"finalizer spawned a daemon thread named ``salt-zmq-context-term``; "
        f"the strong-ref alternative is not supposed to need one. "
        f"new_threads={new_threads!r}"
    )
