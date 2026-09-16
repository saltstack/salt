"""
Reproducer for the pyzmq ``Context.__del__`` wedge observed on the salt-minion.

Symptom
-------
A live salt-minion, still holding an ESTABLISHED TCP session to its master on
tcp://master:4505 and :4506, stops responding to ``manage.up`` and never
executes another job.  ``systemctl is-active salt-minion`` reports ``active``,
``/proc/<pid>/status`` reports ``State: S (sleeping)`` and non-zero RSS, but the
process makes ~0 syscalls/second at the kernel level (empirical baseline: a
healthy minion runs ~130 syscalls/s; a wedged minion runs ~2 syscalls/s).
The wedge lasts until the minion is restarted; an in-the-wild instance ran for
30+ hours before manual intervention.

Root cause
----------
pyzmq 24+ changed ``zmq.sugar.context.Context.__del__`` from calling
thread-safe (but hang-prone) ``term()`` to calling the "less safe"
``destroy()``.  ``destroy()`` iterates the context's open sockets and calls
``socket.close()`` on each.  With the pyzmq default ``LINGER = -1`` and any
queued-but-undelivered message in a socket's outbound buffer,
``socket.close()`` blocks in libzmq's ``zmq_ctx_term()`` waiting for that
message to drain.  When ``Context.__del__`` fires from a callback inside an
active asyncio ioloop -- exactly the case observed in the wild when the
minion's main ioloop ran a callback that triggered GC of a leaked context --
the loop freezes for the duration of ``zmq_ctx_term()``.

Salt-side invariant
-------------------
Both 3006.x and 3008.x pin ``pyzmq >= 27.1.0``, so the buggy finalizer path
is active in both branches.  Neither branch defines ``__del__`` on any class
in ``salt/transport/zeromq.py`` (``grep '^    def __del__'`` returns nothing).
Every ``zmq.Context()`` / ``zmq.asyncio.Context()`` created inside the
transport layer must be paired with an explicit ``context.destroy(linger=0)``
(or an equivalent ``close(0)`` + ``term()`` pair) on the shutdown path -- so
that no ``Context`` reaches Python GC while still owning open sockets with
queued sends.  The tests below document what breaks when that discipline
lapses.

Test structure
--------------
1. ``test_pyzmq_context_del_hangs_baseline``
   Bare pyzmq reproducer.  Skip-if-fixed guard: if the running pyzmq no
   longer exhibits the primitive, we skip the ioloop test and the salt
   regression guard remains meaningful.

2. ``test_ioloop_freezes_when_leaked_context_finalized_in_callback``
   The observed failure mode: a leaked ``zmq.Context`` with a queued
   undeliverable send is dropped inside an asyncio callback, and
   ``gc.collect()`` runs from that callback.  A canary coroutine's tick
   counter is measured before/after -- healthy = many ticks, wedged = 0.
   Marked ``xfail(strict=True)`` because the pyzmq primitive is currently
   broken; the mark flips to pass the moment pyzmq or salt patches the
   underlying behavior.

3. ``test_explicit_destroy_linger_zero_prevents_ioloop_freeze``
   Same setup as (2), but the callback calls ``context.destroy(linger=0)``
   before dropping the ref.  Documents the fix pattern that every
   ``zmq.Context`` allocation inside salt/transport/zeromq.py should
   follow.  Passes on the current codebase.

4. ``test_salt_zeromq_transport_defines_no_dunder_del``
   Static regression guard: ``salt.transport.zeromq`` must not define
   ``__del__`` on any class -- GC ordering during interpreter shutdown and
   inside active ioloops makes finalizers on transport objects unsafe.
   Reintroducing ``__del__`` was the ancestor of prior leaked-socketpair
   incidents (see #68637).

References
----------
- pyzmq #1003 "PyZMQ polls forever on garbage collection at exit"
- pyzmq #1757 "zmq.Context as a context manager hangs if sockets are left open"
- pyzmq #1761 "Call ctx.destroy() in Context.__exit__" (24.0)
- Production incident: cycle71 maas-63 env, mgmt-vc minion, 30+ h wedge,
  pid 2058306, salt 3008.2, pyzmq 27.1.0.  Diagnosed by gdb-injecting
  ``sys._current_frames()`` -- MainThread stuck at
  ``zmq.sugar.context.__del__ -> destroy -> term -> libzmq zmq_ctx_term``.
- pyzmq 24.0 changelog:

    Using a zmq.Context as a context manager or deleting a context
    without closing it now calls zmq.Context.destroy at exit instead
    of zmq.Context.term. In almost all cases, this will turn what
    used to be a hang into a warning. However, there may be some
    cases where sockets are actively used in threads, which could
    result in a crash. To use sockets across threads, it is critical
    to properly and explicitly close your contexts and sockets, which
    will always avoid this issue.

  Our case is one of the "some cases": the fix is on the caller's side,
  in salt.
"""

from __future__ import annotations

import asyncio
import gc
import inspect
import sys
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

# If a "should-be-instant" operation takes longer than this, the wedge
# has reproduced.  In the observed incident the wedge was effectively infinite.
WEDGE_TIMEOUT_S = 4.0

# Port 1 (tcpmux) is virtually never listening on any modern host.  ZMQ's
# ``connect()`` succeeds asynchronously, and ``send()`` queues into the
# socket's outbound buffer with no peer to receive it -- the exact state
# that makes ``socket.close()`` block on LINGER.
DEAD_MASTER_URI = "tcp://127.0.0.1:1"


def _leak_zmq_context_with_queued_send() -> None:
    """Allocate a ``zmq.Context`` with a REQ socket that has a queued
    undeliverable message, and let all local references drop.  The
    ``Context.__del__`` finalizer runs when refcount reaches zero (at
    function return) or, if the object is caught in a cycle, at the next
    ``gc.collect()``.
    """
    ctx = zmq.Context()
    sock = ctx.socket(zmq.REQ)
    # -1 is pyzmq's default; explicit here for the reader.  With LINGER=0
    # the wedge disappears -- that is exactly the fix pattern the salt
    # transport must apply.
    sock.setsockopt(zmq.LINGER, -1)
    sock.connect(DEAD_MASTER_URI)
    sock.send(b"queued-but-never-delivered", flags=zmq.NOBLOCK)
    # No sock.close(0), no ctx.destroy(linger=0).  Refs drop at return.


def _run_bounded(thunk, timeout_s: float):
    """Run ``thunk`` in a daemon thread and return ``(completed, elapsed)``.

    ``completed`` is True if the thread finished within ``timeout_s``, False
    if it was still running when we gave up.  ``elapsed`` is the wall-clock
    time for the completed run, or ``timeout_s`` when we timed out.

    We must not join the thread on timeout -- the thread is blocked in a
    C-level ``zmq_ctx_term()`` and cannot respond to Python-level signals
    or exceptions.  The daemon flag ensures it dies with the interpreter,
    so the wedge does not leak between tests.  (The daemon thread does
    hold the zmq context resources until then; each test picks a fresh
    port and its own context, so cross-test interference is negligible.)
    """
    done = threading.Event()
    started_at = None

    def _worker():
        nonlocal started_at
        started_at = time.monotonic()
        try:
            thunk()
            gc.collect()
        finally:
            done.set()

    t = threading.Thread(target=_worker, daemon=True, name="wedge-probe")
    t.start()
    finished = done.wait(timeout_s)
    if finished:
        return True, time.monotonic() - started_at
    return False, timeout_s


# ---------------------------------------------------------------------------
# 1) Bare pyzmq primitive.
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "pyzmq >= 24 Context.__del__ calls destroy() which calls "
        "socket.close() on each open socket.  With LINGER=-1 (pyzmq "
        "default) and a queued undeliverable send, socket.close() blocks "
        "in libzmq zmq_ctx_term().  When pyzmq or libzmq fix this "
        "primitive, this test flips to passing -- strict=True then fails "
        "the test to signal the maintainer to remove the xfail marker."
    ),
)
@pytest.mark.timeout(int(WEDGE_TIMEOUT_S * 3))
def test_pyzmq_context_del_hangs_baseline():
    """Bare pyzmq reproducer.  Wedges > WEDGE_TIMEOUT_S on the currently
    shipped pyzmq (>= 27.1.0 in both salt 3006.x and 3008.x branches);
    that is the primitive the ioloop test below inherits.

    Runs the leak in a bounded daemon thread because a wedged
    ``zmq_ctx_term()`` blocks in C and cannot be interrupted by
    Python-level pytest-timeout signals; joining the main test thread
    into that call would hang the whole session.
    """
    completed, elapsed = _run_bounded(
        _leak_zmq_context_with_queued_send, WEDGE_TIMEOUT_S
    )

    if completed and elapsed < WEDGE_TIMEOUT_S:
        # Primitive appears fixed -- test passes, and strict xfail then
        # fails the test to signal "remove this marker".
        return

    # Wedge reproduced (either still running past WEDGE_TIMEOUT_S or
    # completed only after >= WEDGE_TIMEOUT_S).  Fail so the xfail marker
    # catches this as expected-fail.
    pytest.fail(
        f"pyzmq {zmq.__version__} Context.__del__ "
        f"{'did not complete within' if not completed else 'took'} "
        f"{elapsed:.1f}s on a leaked context with a REQ socket holding "
        f"a queued undeliverable send.  Wedge reproduced."
    )


# ---------------------------------------------------------------------------
# 2) Production failure mode: pyzmq finalizer fires inside an ioloop callback.
# ---------------------------------------------------------------------------


def _build_ioloop_probe(leak_fn):
    """Return an ``async def`` probe coroutine that runs a heartbeat
    canary, schedules a plain callback which calls ``leak_fn()`` +
    ``gc.collect()``, and records baseline/final tick counts into a
    shared ``heartbeat`` dict.

    The probe is designed to run inside a daemon thread wrapped around
    ``asyncio.run(...)``.  When the callback wedges the loop, the probe
    never returns -- but the shared ``heartbeat`` still carries the last
    tick count observed before the freeze, which the main thread reads
    to distinguish "loop frozen inside wedge" from "loop never started".
    """
    heartbeat = {"ticks": 0, "baseline": None, "final": None}

    async def _canary():
        while True:
            heartbeat["ticks"] += 1
            await asyncio.sleep(0.05)

    async def _probe():
        canary_task = asyncio.create_task(_canary())
        try:
            await asyncio.sleep(0.2)  # warm up the canary
            heartbeat["baseline"] = heartbeat["ticks"]

            def _cb():
                leak_fn()
                gc.collect()

            # Plain synchronous callback -- exactly the shape the salt-
            # minion's main ioloop was executing when the bug fired in
            # the observed incident.
            asyncio.get_running_loop().call_soon(_cb)

            # 1 second observation window.  Healthy loop = ~20 ticks;
            # wedged loop = 0 ticks (the sleep itself cannot fire
            # because the loop is frozen inside zmq_ctx_term()).
            await asyncio.sleep(1.0)
            heartbeat["final"] = heartbeat["ticks"]
        finally:
            canary_task.cancel()
            try:
                await canary_task
            except asyncio.CancelledError:
                pass

    return _probe, heartbeat


@pytest.mark.xfail(
    strict=True,
    reason=(
        "pyzmq 24+ Context.__del__ calls destroy() which iterates open "
        "sockets and calls socket.close() with the default LINGER=-1.  If "
        "a socket has a queued undeliverable message, close() blocks in "
        "libzmq's zmq_ctx_term().  When this finalizer runs from an asyncio "
        "callback (the salt-minion's main ioloop was inside such a callback "
        "when the wedge fired in the wild), the entire event loop "
        "freezes.  Fix path: every zmq.Context/zmq.asyncio.Context "
        "allocation in salt/transport/zeromq.py must call "
        "context.destroy(linger=0) on its shutdown path, and callers must "
        "call channel.close() before dropping references -- so no Context "
        "reaches Python GC while still owning open sockets.  When the fix "
        "lands, this test flips to passing; strict=True then fails the "
        "test to signal the maintainer to remove this xfail marker."
    ),
)
@pytest.mark.timeout(int(WEDGE_TIMEOUT_S * 4))
def test_ioloop_freezes_when_leaked_context_finalized_in_callback():
    """The observed failure mode: leaked Context finalized inside an
    ioloop callback freezes the loop.

    Uses a daemon thread around ``asyncio.run()`` so we can bound the
    observation window from outside the frozen loop -- ``asyncio.wait_for``
    can't help because the wait_for timeout callback also needs the
    (frozen) loop to fire it.  The daemon thread is left to die with the
    interpreter; each test picks a fresh port and its own context.
    """
    probe, heartbeat = _build_ioloop_probe(_leak_zmq_context_with_queued_send)
    done = threading.Event()

    def _run_probe():
        try:
            asyncio.run(probe())
        finally:
            done.set()

    threading.Thread(target=_run_probe, daemon=True, name="wedge-ioloop").start()

    finished = done.wait(WEDGE_TIMEOUT_S * 2)

    if not finished:
        # Probe never returned -- the loop is wedged as expected.  Read
        # shared state to confirm the wedge shape, then fail so the
        # xfail marker catches it.
        assert heartbeat["baseline"] is not None, (
            f"probe never reached baseline; different failure mode "
            f"(heartbeat={heartbeat!r})"
        )
        pytest.fail(
            f"asyncio loop wedged for > {WEDGE_TIMEOUT_S * 2}s after a "
            f"callback leaked a zmq.Context (baseline ticks: "
            f"{heartbeat['baseline']}; final observed: {heartbeat['ticks']}). "
            f"This is the exact observed failure mode on maas-63 mgmt-vc "
            f"(pid 2058306, 30+ h wedge, salt 3008.2, pyzmq 27.1.0)."
        )

    # Probe returned within our observation window -- either the wedge
    # was fixed (pyzmq or salt-side) or something else went wrong.
    assert (
        heartbeat["final"] is not None
    ), f"probe returned but never set 'final' (heartbeat={heartbeat!r})"
    ticks_after = heartbeat["final"] - heartbeat["baseline"]
    # A healthy loop advances ~20 ticks in 1 second (asyncio.sleep(0.05));
    # a wedged loop advances 0 or 1.  Threshold of 10 gives comfortable
    # separation.
    assert ticks_after > 10, (
        f"asyncio loop advanced only {ticks_after} ticks in the 1 second "
        f"after a callback leaked a zmq.Context and called gc.collect().  "
        f"The loop is frozen inside zmq_ctx_term()/socket.close().  This "
        f"is the exact observed failure mode on maas-63 mgmt-vc "
        f"(pid 2058306, 30+ h wedge, salt 3008.2, pyzmq 27.1.0)."
    )


# ---------------------------------------------------------------------------
# 3) The fix pattern: explicit context.destroy(linger=0) before drop.
# ---------------------------------------------------------------------------


def _leak_but_destroy_linger_zero() -> None:
    """Same allocation as ``_leak_zmq_context_with_queued_send``, but with
    the fix applied: ``ctx.destroy(linger=0)`` before drop, which discards
    undelivered messages and terminates the context synchronously.  This
    is the pattern every ``zmq.Context()`` / ``zmq.asyncio.Context()``
    allocation inside ``salt/transport/zeromq.py`` should follow.
    """
    ctx = zmq.Context()
    sock = ctx.socket(zmq.REQ)
    sock.connect(DEAD_MASTER_URI)
    sock.send(b"queued-but-never-delivered", flags=zmq.NOBLOCK)
    # THE FIX:
    ctx.destroy(linger=0)


@pytest.mark.timeout(int(WEDGE_TIMEOUT_S * 4))
def test_explicit_destroy_linger_zero_prevents_ioloop_freeze():
    """With ``context.destroy(linger=0)`` called before the context ref
    drops, the ioloop keeps running smoothly through the same callback
    that wedges the loop in the previous test.  Documents the fix pattern
    salt-transport must adopt at every ``zmq.Context()`` /
    ``zmq.asyncio.Context()`` allocation site.
    """
    probe, heartbeat = _build_ioloop_probe(_leak_but_destroy_linger_zero)
    done = threading.Event()

    def _run_probe():
        try:
            asyncio.run(probe())
        finally:
            done.set()

    threading.Thread(target=_run_probe, daemon=True, name="fix-ioloop").start()

    assert done.wait(WEDGE_TIMEOUT_S * 2), (
        f"probe did not complete within {WEDGE_TIMEOUT_S * 2}s -- the "
        f"destroy(linger=0) fix does not prevent the wedge, or something "
        f"else is slowing the test host.  heartbeat={heartbeat!r}"
    )
    assert (
        heartbeat["final"] is not None
    ), f"probe returned but never set 'final' (heartbeat={heartbeat!r})"
    ticks_after = heartbeat["final"] - heartbeat["baseline"]
    assert ticks_after > 10, (
        f"asyncio loop advanced only {ticks_after} ticks after the "
        f"``destroy(linger=0)`` callback -- either the fix is incomplete "
        f"or the loop is being slowed by something else in this test env."
    )


# ---------------------------------------------------------------------------
# 4) Static regression guard: no __del__ on salt.transport.zeromq classes.
# ---------------------------------------------------------------------------


def test_salt_zeromq_transport_defines_no_dunder_del():
    """Salt removed all ``__del__`` methods from ``salt/transport/zeromq.py``
    intentionally; GC ordering during interpreter shutdown and inside
    active ioloops makes finalizers on transport objects unsafe.  If a
    future change reintroduces ``__del__`` on any class in this module,
    revert it and use explicit ``close()`` + ``context.destroy(linger=0)``
    on the shutdown path instead.  Reintroducing ``__del__`` was the
    ancestor of prior leaked-socketpair storms (see PR history around
    #68637).
    """
    offenders = []
    for name, obj in inspect.getmembers(salt.transport.zeromq, inspect.isclass):
        if obj.__module__ != salt.transport.zeromq.__name__:
            continue
        if "__del__" in obj.__dict__:
            offenders.append(name)
    assert not offenders, (
        f"salt.transport.zeromq classes reintroduced __del__: {offenders}.  "
        f"This was intentionally removed (see #68637).  Use "
        f"explicit close() + context.destroy(linger=0) instead."
    )
