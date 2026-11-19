"""
Functional regression test for the AsyncAuth drain-on-cancel contract
(saltstack/salt issue #70857).

What the issue describes
------------------------
When the sole caller of ``AsyncAuth.authenticate()`` gives up (for
example ``asyncio.wait_for`` times out) and the event loop is stopped
right after, the sign-in task is left in the ``cancelling`` state and
still holds its REQ socket.  The next ``gc.collect()`` runs
``_finalize_zmq_context``, whose ``destroy()`` blocks in
``zmq_ctx_term()`` forever because the socket is still open.  On a
minion this freezes the process -- the same end state as #70353 and
#70624.

The contract this test pins
---------------------------
After ``asyncio.wait_for(auth.authenticate(), ...)`` raises
``TimeoutError`` and the loop is closed, ``gc.collect()`` must return
promptly (bounded by ``_GC_BUDGET_SECONDS``, well under the 30-second
``_finalize_zmq_context`` observation window Charlie reported).  That
is only true if the shared sign-in task's unwind (the ``with
AsyncReqChannel`` __exit__ -> ``socket.close()``) ran before the loop
closed -- i.e. the drain happened inside the caller's cancellation
path.

Design notes
------------
This replays Charlie's repro script (#70857) against the real zmq
transport.  A ROUTER socket accepts the connection and never answers,
so the sign-in parks forever and the caller necessarily times out.
No master or master-side crypto is needed -- the unwind path of the
minion's sign_in task is the only thing under test.

The test is marked ``slow_test`` + ``skip_on_spawning_platform`` to
match the rest of the AsyncAuth functional-test suite and to match the
Python-3.12+ scope of the bug (the orphan-reaper in asyncio's ``_target``
does not catch the leftover task on 3.12+; on 3.10 the wedge is less
reproducible).
"""

import asyncio
import gc
import logging
import pathlib
import shutil
import threading
import time

import pytest
import zmq

import salt.config
import salt.crypt
import salt.utils.platform

log = logging.getLogger(__name__)


# Charlie's reported wedge is a 30-second hang (bounded by his
# ``dump_traceback_later(30)`` watchdog).  Anything well under that
# proves the drain worked.  2 seconds is plenty: the real teardown on
# a non-wedged loop is sub-millisecond.
_GC_BUDGET_SECONDS = 2.0


pytestmark = [
    pytest.mark.skip_on_spawning_platform(
        reason=(
            "Needs fork-safe multiprocessing; the entire functional "
            "channel suite carries this restriction."
        ),
    ),
    pytest.mark.timeout_unless_on_windows(60),
    pytest.mark.slow_test,
]


MINION_ID = "test-asyncauth-drain-minion"


@pytest.fixture
def drain_pki_root(tmp_path):
    if salt.utils.platform.is_darwin():
        root = pathlib.Path("/tmp").resolve() / tmp_path.name
    else:
        root = tmp_path
    root.mkdir(parents=True, exist_ok=True)
    (root / "pki").mkdir(exist_ok=True)
    (root / "cache").mkdir(exist_ok=True)
    (root / "sock").mkdir(exist_ok=True)
    try:
        yield root
    finally:
        if salt.utils.platform.is_darwin():
            shutil.rmtree(str(root), ignore_errors=True)


@pytest.fixture
def silent_router():
    """A zmq ROUTER that accepts the minion's REQ connect and never
    replies.  Sign-in parks forever on the recv, which is exactly what
    Charlie's script arranges.
    """
    ctx = zmq.Context()
    sock = ctx.socket(zmq.ROUTER)
    port = sock.bind_to_random_port("tcp://127.0.0.1")
    try:
        yield port
    finally:
        try:
            sock.close(linger=0)
        except Exception:  # pylint: disable=broad-except
            pass
        try:
            ctx.destroy(linger=0)
        except Exception:  # pylint: disable=broad-except
            pass


def _run_drain_scenario(workdir, port):
    """
    The actual repro.  Returns ``(gc_seconds, hung)``:

    - ``gc_seconds`` -- wall time taken by the ``gc.collect()`` call
      after the loop is closed.
    - ``hung`` -- ``True`` if that call exceeded ``_GC_BUDGET_SECONDS``.

    Runs inside a daemon thread so a hang does not freeze the pytest
    process; the daemon dies with the test's main thread.
    """
    opts = salt.config.minion_config(None)
    opts.update(
        {
            "id": MINION_ID,
            "master": "127.0.0.1",
            "master_ip": "127.0.0.1",
            "master_port": port,
            "master_uri": f"tcp://127.0.0.1:{port}",
            "pki_dir": str(workdir / "pki"),
            "cachedir": str(workdir / "cache"),
            "sock_dir": str(workdir / "sock"),
            "auth_timeout": 30,
            "auth_tries": 1,
            "acceptance_wait_time": 1,
            "__role": "minion",
        }
    )
    salt.crypt.AsyncAuth.creds_map.clear()
    # Reset the per-io_loop singleton map so this scenario doesn't see
    # leftover instances from other tests on the same process.
    salt.crypt.AsyncAuth.instance_map.clear()

    loop = asyncio.new_event_loop()

    async def _main():
        auth = salt.crypt.AsyncAuth(opts, io_loop=loop)
        try:
            # The wait_for timeout is deliberately short -- we want to
            # stop the caller well before the sign_in's own
            # ``auth_timeout=30`` would fire.
            await asyncio.wait_for(auth.authenticate(), timeout=2)
        except (asyncio.TimeoutError, Exception):  # pylint: disable=broad-except
            pass
        return auth

    try:
        auth = loop.run_until_complete(_main())
    finally:
        loop.close()

    # Drop every strong reference held by the test frame.  Whatever
    # the sign-in task / channel / socket still reference becomes
    # cyclic garbage.
    del auth

    # Time the GC.  Under the drain-on-cancel contract, the socket is
    # already closed and ``_finalize_zmq_context`` has nothing to do.
    t0 = time.monotonic()
    gc.collect()
    elapsed = time.monotonic() - t0
    return elapsed, elapsed > _GC_BUDGET_SECONDS


def test_gc_collect_does_not_block_in_zmq_ctx_term_70857(drain_pki_root, silent_router):
    """
    Directly mirrors Charlie's repro script: wait_for(authenticate(), 2),
    close the loop, drop references, gc.collect().  Must return within
    a bounded budget.

    Under the current implementation this test is expected to FAIL on
    Python 3.12+ -- the sign-in task is left in ``cancelling`` state,
    the REQ socket stays open, and ``_finalize_zmq_context`` blocks in
    ``zmq_ctx_term()`` for the full 30 seconds Charlie observed.  Under
    the drain-on-cancel fix, the socket is already closed by the time
    ``gc.collect()`` runs, so the call returns in milliseconds.
    """
    # Run the scenario in a daemon thread so a hang in gc doesn't
    # freeze pytest itself -- we want to observe the hang and report
    # it, not inherit it.
    result = {}

    def _worker():
        try:
            elapsed, hung = _run_drain_scenario(drain_pki_root, silent_router)
            result["elapsed"] = elapsed
            result["hung"] = hung
        except Exception as exc:  # pylint: disable=broad-except
            result["error"] = exc

    t = threading.Thread(target=_worker, name="asyncauth-drain-worker", daemon=True)
    t.start()
    # Give the worker generous headroom over the GC budget so a
    # non-wedged run completes cleanly, and a wedged run is caught
    # (by observing ``t.is_alive()``) rather than by inheriting the
    # hang.
    t.join(timeout=_GC_BUDGET_SECONDS * 15)

    if t.is_alive():
        pytest.fail(
            f"gc.collect() still running after "
            f"{_GC_BUDGET_SECONDS * 15:.1f}s -- "
            "sign-in task was left in cancelling state with an open "
            "zmq socket, and _finalize_zmq_context is blocked in "
            "zmq_ctx_term() (#70857)"
        )

    if "error" in result:
        raise result["error"]

    assert not result["hung"], (
        f"gc.collect() took {result['elapsed']:.2f}s -- exceeded "
        f"the {_GC_BUDGET_SECONDS}s budget; "
        "the sign-in task did not drain its socket before the loop "
        "closed, and _finalize_zmq_context is spending time in "
        "zmq_ctx_term() (#70857)"
    )
    log.info("gc.collect() returned in %.4fs", result["elapsed"])


def test_no_pending_tasks_after_cancelled_authenticate_70857(
    drain_pki_root, silent_router
):
    """
    Stronger variant of the above: assert ``asyncio.all_tasks(loop)``
    is empty right after ``run_until_complete`` returns.  If any task
    is pending -- Charlie observed ``AsyncAuth._authenticate`` and
    ``RequestClient._send_recv`` -- the drain didn't happen.

    This isolates the "orphan task" symptom from the "zmq_ctx_term
    hang" symptom.  Failing this test means the fix regressed; passing
    this test but failing the gc test above would mean the orphan was
    somehow cleaned up another way.
    """
    opts = salt.config.minion_config(None)
    opts.update(
        {
            "id": MINION_ID,
            "master": "127.0.0.1",
            "master_ip": "127.0.0.1",
            "master_port": silent_router,
            "master_uri": f"tcp://127.0.0.1:{silent_router}",
            "pki_dir": str(drain_pki_root / "pki"),
            "cachedir": str(drain_pki_root / "cache"),
            "sock_dir": str(drain_pki_root / "sock"),
            "auth_timeout": 30,
            "auth_tries": 1,
            "acceptance_wait_time": 1,
            "__role": "minion",
        }
    )
    salt.crypt.AsyncAuth.creds_map.clear()
    salt.crypt.AsyncAuth.instance_map.clear()

    loop = asyncio.new_event_loop()
    pending_names = []

    async def _main():
        auth = salt.crypt.AsyncAuth(opts, io_loop=loop)
        try:
            await asyncio.wait_for(auth.authenticate(), timeout=2)
        except (asyncio.TimeoutError, Exception):  # pylint: disable=broad-except
            pass
        return auth

    try:
        _auth = loop.run_until_complete(_main())
        tasks = [t for t in asyncio.all_tasks(loop) if not t.done()]
        pending_names = sorted(t.get_coro().__qualname__ for t in tasks)
    finally:
        loop.close()

    assert pending_names == [], (
        f"caller gave up but these tasks remained pending on the "
        f"loop: {pending_names}. "
        "Each pending task holds its share of transport state -- the "
        "zmq REQ socket is still open until the task's ``with`` "
        "block __exit__ runs (#70857)."
    )
