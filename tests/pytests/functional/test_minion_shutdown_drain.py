"""
Functional regression tests for the minion-shutdown-drain fix
(saltstack/salt issue #70857).

Scope
-----
A salt-minion can freeze in ``zmq_ctx_term()`` when the event loop is
closed with a sign-in task still mid-cancel.  The orphan task holds a
REQ socket; the next ``gc.collect()`` runs the REQ context's
``weakref.finalize`` callback which blocks in libzmq's blocking term.

Charlie Zha (@charzl) documented two signal/shutdown trees that reach
this state (see issue #70857):

- **Tree 1** -- ``destroy()`` runs first (cancels tasks), then
  ``tune_in()``'s ``finally`` closes the loop.  ``Task.cancel()`` is
  only cooperative, so the queued ``_on_waiter_done`` callback / the
  ``async with AsyncReqChannel`` ``__aexit__`` chain never gets loop
  iterations to run before the close discards them.
- **Tree 2** -- ``tune_in()`` exits by exception first (the loop
  closes in the ``finally``), *then* ``destroy()`` is called and
  ``bg.cancel()`` raises ``RuntimeError: Event loop is closed``.
  Nothing cleans up either task or its socket.

The fix (``salt/minion.py``: ``_drain_pending_tasks_before_close``
plus the drain added to ``MinionManager.stop_async`` and the ``finally``
in all three ``tune_in`` sites) closes the loop only after every task
has been cancelled *and awaited* -- so each task's ``async with``
``__aexit__`` chain runs, ``close_async()`` drains the send coroutine
and closes the socket, the zmq context is destroyed inline, and
``gc.collect()`` has nothing to finalize.

Tests
-----
Both tests run inside a daemon thread so a hang (the exact bug
behaviour) is *observed* rather than *inherited* by pytest.  The
thread's ``join(timeout)`` fires an explicit ``pytest.fail`` if
``gc.collect()`` does not return within a bounded budget.
"""

import asyncio
import gc
import logging
import pathlib
import shutil
import threading
import time

import pytest
import tornado.ioloop
import zmq

import salt.config
import salt.crypt
import salt.utils.platform

log = logging.getLogger(__name__)


# Charlie's observed wedge is a 30-second hard-stop (bounded by his
# repro's ``dump_traceback_later(30)`` watchdog).  Anything well under
# that proves the drain worked.  2 s is generous: a healthy teardown is
# sub-millisecond.
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


@pytest.fixture
def workdir(tmp_path):
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
    """
    A zmq ROUTER that accepts the minion's REQ connect and never
    replies.  The sign-in parks forever on the recv -- Charlie's
    #70857 repro setup.
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


def _build_minion_opts(workdir, port):
    opts = salt.config.minion_config(None)
    opts.update(
        {
            "id": "shutdown-drain-minion",
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
    return opts


def _reset_global_state():
    salt.crypt.AsyncAuth.creds_map.clear()
    try:
        salt.crypt.AsyncAuth.instance_map.clear()
    except AttributeError:
        pass


def _run_wait_for_scenario(workdir, port):
    """
    Charlie's exact #70857 repro: wait_for an authenticate() with a
    short timeout, let it fire, close the loop via the minion's
    shutdown path (``_drain_pending_tasks_before_close``), then force a
    GC.

    Returns ``(gc_seconds, hung)``.
    """
    opts = _build_minion_opts(workdir, port)
    _reset_global_state()

    tornado_loop = tornado.ioloop.IOLoop()

    async def _main():
        auth = salt.crypt.AsyncAuth(opts, io_loop=tornado_loop)
        try:
            await asyncio.wait_for(auth.authenticate(), timeout=2)
        except (asyncio.TimeoutError, Exception):  # pylint: disable=broad-except
            pass
        return auth

    try:
        auth = tornado_loop.run_sync(_main)
    finally:
        # This is the key call under test.  Without the drain,
        # ``io_loop.close()`` below would discard the still-cancelling
        # sign-in task and orphan its REQ socket.
        from salt.minion import _drain_pending_tasks_before_close

        _drain_pending_tasks_before_close(tornado_loop)
        tornado_loop.close()

    del auth

    t0 = time.monotonic()
    gc.collect()
    elapsed = time.monotonic() - t0
    return elapsed, elapsed > _GC_BUDGET_SECONDS


def _run_in_worker_thread(fn, *args, timeout):
    """
    Run ``fn`` in a daemon thread with a hard ``join(timeout)``.  A hang
    in ``gc.collect()`` -- the exact #70857 symptom -- is observed via
    ``t.is_alive()`` rather than inherited by the pytest process.
    """
    result = {}

    def _worker():
        try:
            result["value"] = fn(*args)
        except Exception as exc:  # pylint: disable=broad-except
            result["error"] = exc

    t = threading.Thread(target=_worker, name="shutdown-drain-worker", daemon=True)
    t.start()
    t.join(timeout=timeout)
    return t, result


def test_gc_collect_does_not_block_after_wait_for_timeout_70857(workdir, silent_router):
    """
    Charlie's repro, driven through salt's own drain helper.

    Caller calls ``wait_for(auth.authenticate(), 2)`` against a
    silent-master ROUTER.  TimeoutError fires.  ``_drain_pending_
    tasks_before_close`` is invoked (this is what the minion's
    ``tune_in`` ``finally`` does under the fix).  The loop is closed.
    ``gc.collect()`` must return within ``_GC_BUDGET_SECONDS``.

    Without the fix, ``gc.collect()`` blocks forever in
    ``zmq_ctx_term()`` because the orphan sign-in task's REQ socket
    is still open.
    """
    t, result = _run_in_worker_thread(
        _run_wait_for_scenario,
        workdir,
        silent_router,
        timeout=_GC_BUDGET_SECONDS * 15,
    )

    if t.is_alive():
        pytest.fail(
            f"gc.collect() still running after "
            f"{_GC_BUDGET_SECONDS * 15:.1f}s -- sign-in task was left "
            "in cancelling state with an open zmq socket, and "
            "_finalize_zmq_context is blocked in zmq_ctx_term() (#70857)"
        )

    if "error" in result:
        raise result["error"]

    elapsed, hung = result["value"]
    assert not hung, (
        f"gc.collect() took {elapsed:.2f}s -- exceeded the "
        f"{_GC_BUDGET_SECONDS}s budget; the shutdown drain did not "
        "close the sign-in task's socket before the loop closed"
    )
    log.info("gc.collect() returned in %.4fs", elapsed)


def _run_cancel_then_close_scenario(workdir, port):
    """
    Tree-1-shaped repro: start a sign-in task, cancel it, close the
    loop, force GC.  Mirrors ``MinionManager.destroy()`` followed by
    ``tune_in``'s ``finally`` with no loop iterations in between.
    """
    opts = _build_minion_opts(workdir, port)
    _reset_global_state()

    tornado_loop = tornado.ioloop.IOLoop()
    captured = {}

    async def _start_signin():
        auth = salt.crypt.AsyncAuth(opts, io_loop=tornado_loop)
        future = auth.authenticate()
        # Give the sign-in task a tick to start its ``async with
        # AsyncReqChannel`` block and open the REQ socket.
        await asyncio.sleep(0.2)
        captured["auth"] = auth
        captured["future"] = future

    tornado_loop.run_sync(_start_signin)

    # Now mimic the destroy()+close pattern, routed through the drain
    # helper (which is where the fix lands in both tune_in and
    # stop_async).
    try:
        captured["future"].cancel()
        from salt.minion import _drain_pending_tasks_before_close

        _drain_pending_tasks_before_close(tornado_loop)
    finally:
        tornado_loop.close()

    captured.clear()

    t0 = time.monotonic()
    gc.collect()
    elapsed = time.monotonic() - t0
    return elapsed, elapsed > _GC_BUDGET_SECONDS


def test_gc_collect_does_not_block_after_cancel_then_close_70857(
    workdir, silent_router
):
    """
    Tree-1 shape: explicit cancel, then close.  Same assertion as the
    wait_for case: the drain helper must unwind the task's ``async
    with`` so no orphan socket survives into gc.
    """
    t, result = _run_in_worker_thread(
        _run_cancel_then_close_scenario,
        workdir,
        silent_router,
        timeout=_GC_BUDGET_SECONDS * 15,
    )

    if t.is_alive():
        pytest.fail(
            "gc.collect() blocked after cancel-then-close shutdown; "
            "the drain helper did not fully unwind the sign-in task"
        )

    if "error" in result:
        raise result["error"]

    elapsed, hung = result["value"]
    assert not hung, (
        f"gc.collect() took {elapsed:.2f}s; the cancel-then-close "
        "path left an orphan socket"
    )


def test_drain_helper_handles_closed_loop_safely(workdir, silent_router):
    """
    Defensive: calling ``_drain_pending_tasks_before_close`` on an
    already-closed loop must be a no-op, not an error.  This is the
    Tree-2 case ``minion.destroy()`` can hit after ``tune_in`` has
    already closed the loop.
    """
    tornado_loop = tornado.ioloop.IOLoop()
    tornado_loop.close()

    from salt.minion import _drain_pending_tasks_before_close

    # Must not raise.
    _drain_pending_tasks_before_close(tornado_loop)
