"""
Tests for ``salt.transport.zeromq._finalize_zmq_context``.

Regression tests for issue #70353: the finalizer ran ``Context.destroy()``,
which only closes the sockets still tracked in ``Context._sockets`` and then
calls the blocking ``term()``.  When the finalizer fires from a cyclic GC run,
a socket in the same unreachable garbage has already been dropped from that
``WeakSet`` but is not closed yet, so ``term()`` waited for it forever and
deadlocked the minion's ioloop.
"""

import subprocess
import sys
import textwrap
import threading

import pytest
import zmq
import zmq.asyncio

import salt.transport.zeromq

# TEST-NET-1, never answers
UNREACHABLE = "tcp://192.0.2.1:4506"


def _term_threads():
    return [t for t in threading.enumerate() if t.name == "salt-zmq-context-term"]


def _wait_for_term_threads():
    for thread in _term_threads():
        thread.join(timeout=5)


@pytest.fixture
def context():
    ctx = zmq.asyncio.Context()
    yield ctx
    # Never call term() while one started by the finalizer is still running:
    # libzmq only signals one of two concurrent zmq_ctx_term() callers.
    _wait_for_term_threads()
    if not ctx.closed and not _term_threads():
        ctx.destroy(linger=0)


def _untracked_socket(ctx):
    """
    An open socket that ``ctx`` no longer tracks: the state a socket is in
    while the cyclic GC is between clearing weakrefs and running finalizers.
    """
    sock = ctx.socket(zmq.REQ)
    sock.linger = 0
    sock.connect(UNREACHABLE)
    ctx._sockets.discard(sock)
    return sock


def _finalize(ctx, sock=None):
    """
    Run the finalizer on a daemon thread so a regression fails the test
    instead of hanging it.  ``sock`` is closed if the finalizer blocks, which
    lets a ``term()`` waiting on it return.
    """
    finalizer = threading.Thread(
        target=salt.transport.zeromq._finalize_zmq_context,
        args=(ctx,),
        daemon=True,
    )
    finalizer.start()
    finalizer.join(timeout=5)
    blocked = finalizer.is_alive()
    if blocked and sock is not None:
        sock.close()
        finalizer.join(timeout=5)
    assert not blocked, "_finalize_zmq_context blocked in term()"


def test_finalize_does_not_block_on_untracked_open_socket(context):
    sock = _untracked_socket(context)
    try:
        _finalize(context, sock)
    finally:
        sock.close()


def test_finalize_terminates_context_once_socket_is_closed(context):
    sock = _untracked_socket(context)
    _finalize(context, sock)
    assert not context.closed
    sock.close()
    _wait_for_term_threads()
    assert context.closed


def test_finalize_closes_tracked_sockets(context):
    sock = context.socket(zmq.REQ)
    sock.linger = 0
    sock.connect(UNREACHABLE)
    _finalize(context)
    assert sock.closed
    _wait_for_term_threads()
    assert context.closed


def test_finalize_ignores_closed_or_missing_context():
    salt.transport.zeromq._finalize_zmq_context(None)
    ctx = zmq.asyncio.Context()
    ctx.term()
    salt.transport.zeromq._finalize_zmq_context(ctx)


def test_gc_of_unclosed_socket_cycle_does_not_deadlock():
    """
    Drive the real GC ordering: an owner with the finalizer registered and an
    unclosed socket that is only reachable from a reference cycle (in the
    issue, a coroutine frame stranded on a closed event loop).  Runs in a
    subprocess so a regression fails on the timeout instead of hanging the
    test run.
    """
    code = textwrap.dedent(
        f"""
        import gc
        import weakref

        import zmq
        import zmq.asyncio

        from salt.transport.zeromq import _finalize_zmq_context


        class Owner:
            pass


        class Frame:
            pass


        ctx = zmq.asyncio.Context()
        owner = Owner()
        weakref.finalize(owner, _finalize_zmq_context, ctx)
        sock = ctx.socket(zmq.REQ)
        sock.linger = 0
        sock.connect({UNREACHABLE!r})
        frame = Frame()
        frame.socket = sock
        frame.context = ctx
        frame.owner = owner
        frame.cycle = frame
        del owner, sock, frame, ctx
        gc.collect()
        print("collected")
        """
    )
    try:
        ret = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except subprocess.TimeoutExpired:
        pytest.fail("gc.collect() deadlocked in _finalize_zmq_context")
    assert ret.returncode == 0, ret.stderr
    assert "collected" in ret.stdout
