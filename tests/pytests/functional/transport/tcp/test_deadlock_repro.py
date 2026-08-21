"""
Regression / repro test for issue #69986 -- MWorker deadlock via nested
SyncWrapper in ``salt.transport.tcp.PublishServer.publish`` when
``salt.utils.event.SaltEvent.fire_event`` is called from a running
asyncio loop (the MWorker ``request_handler`` scenario).

Structured as a subprocess-driven smoke test: the actual deadlock is
run in a child ``multiprocessing.Process`` so the parent can enforce a
hard wall-clock kill on a wedged child (a thread-based pytest-timeout
cannot unwind a ``threading.Thread.join()`` on the outer asyncio
loop's thread, which is exactly the deadlock we are proving).

Repro model
-----------

Production symptom: every MWorker deadlocks with two threads pinned in
``threading.Thread.join()`` inside nested ``SyncWrapper._wrap`` frames::

    request_handler asyncio loop  (MWorker._handle_payload etc.)
      -> MasterEvent.fire_event(...)      (_run_io_loop_sync=True)
        -> self.pusher.publish(msg)         # SyncWrapper(PublishServer)
             _wrap sees running loop => spawn thread + thread.join()
             thread runs PublishServer.publish(msg) via IOLoop.run_sync
               -> self.pub_sock.send(payload)   # SyncWrapper(_TCPPubServerPublisher)
                    _wrap sees running loop => spawn thread + thread.join()
                    thread runs _TCPPubServerPublisher.send via IOLoop.run_sync
                      -> await self.stream.write(pack)

When ``stream.write`` stalls (kernel TCP send buffer full because the
puller stopped reading -- the exact #66282 scenario), the inner
``run_sync`` never returns, so the middle ``thread.join()`` blocks, so
the outer ``thread.join()`` blocks.  The outer ``thread.join()`` runs
inside an ``async def`` on the MWorker's request-handler loop, so that
loop is fully wedged.

Repro technique
---------------

1. Bind a dumb loopback listener that accepts but never reads.
   ``SO_RCVBUF`` is shrunk so the kernel TCP window closes quickly.
2. In a child process, construct a ``MasterEvent`` (which builds the
   ``SyncWrapper(PublishServer)`` pusher exactly like MWorker does).
3. Fire ``event.fire_event(...)`` from inside an ``async def`` task.
4. Run a heartbeat task on the same outer loop.

Signal: on unpatched ``origin/3008.x`` the heartbeat freezes because
the outer loop is pinned by ``asynchronous.py:260 wrap ->
thread.join()``.  On the correct fix the heartbeat keeps ticking (the
fire_event fast path fires-and-forgets on the running loop, no
thread.join()).

Run::

    /home/dan/src/salt/venv310/bin/pytest \\
        tests/pytests/functional/transport/tcp/test_deadlock_repro.py -x -v
"""

import multiprocessing
import socket
import threading
import time

import pytest


def _find_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _child_run(opts, sock_dir, heartbeat_ticks, publish_done):
    """
    Runs in the child process.  Mirrors the MWorker call shape:
    ``MasterEvent.fire_event`` from inside an ``async def``, on a
    loop that also runs a heartbeat task.
    """
    import asyncio

    import salt.utils.event

    event = salt.utils.event.get_master_event(opts, sock_dir=sock_dir, listen=False)

    async def _heartbeat(stop_event):
        while not stop_event.is_set():
            with heartbeat_ticks.get_lock():
                heartbeat_ticks.value += 1
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=0.05)
            except asyncio.TimeoutError:
                pass

    async def _publish():
        # 256KB payloads * 50 iterations; the fixture below shrinks
        # the receiver's SO_RCVBUF to 4KB so the kernel TCP window
        # closes within the first few iterations.  On unpatched code
        # the SyncWrapper wedge fires on the very first fire_event.
        for i in range(50):
            event.fire_event({"i": i, "pad": "x" * 262144}, tag=f"repro/{i}")
            await asyncio.sleep(0.02)  # yield outer loop
        publish_done.value = 1

    async def _main():
        # Kick off both tasks and let them run for the full sample
        # window (~6s).  Do NOT cancel heartbeat early on
        # ``_publish``'s completion -- the parent's sample window is
        # what times the test out.
        stop = asyncio.Event()
        hb = asyncio.create_task(_heartbeat(stop))
        await asyncio.sleep(0.1)
        pub_task = asyncio.create_task(_publish())
        try:
            # Give the parent time to sample heartbeat during and
            # after ``_publish``.  6s covers the parent's 1.5s
            # baseline + 2s sample + margin.
            await asyncio.sleep(6.0)
        finally:
            stop.set()
            pub_task.cancel()
            hb.cancel()
            try:
                await asyncio.wait_for(hb, timeout=1)
            except Exception:  # pylint: disable=broad-except
                pass

    asyncio.run(_main())


@pytest.mark.timeout(90, method="thread")
def test_fire_event_async_context_does_not_wedge_outer_loop(tmp_path):
    """
    Repro for #69986.

    Runs the offending call sequence in a child process:
    ``MasterEvent.fire_event`` from an ``async def`` while a
    heartbeat task ticks on the same loop.  Parent samples the shared
    heartbeat counter and asserts progress.

    Failure signature on unpatched ``origin/3008.x``:
      * heartbeat stops ticking within the first publish call because
        the outer asyncio loop is pinned at
        ``asynchronous.py:260 wrap -> thread.join()``.

    Success signature on the correct fix:
      * heartbeat keeps ticking (>=20 ticks in a 2s window).
    """
    pull_port = _find_free_port()
    pub_port = _find_free_port()
    sock_dir = str(tmp_path)
    opts = {
        "ipc_mode": "tcp",
        "ipc_write_buffer": 0,
        "publish_port": pub_port,
        "tcp_master_pub_port": pub_port,
        "tcp_master_pull_port": pull_port,
        "master_ip": "127.0.0.1",
        "transport": "tcp",
        "id": "test-master",
        "sock_dir": sock_dir,
        "order_masters": False,
        "publish_signing_algorithm": "PKCS1v15-SHA1",
        "acceptance_wait_time": 1,
        "acceptance_wait_time_max": 1,
        "loop_interval": 1,
        "max_event_size": 2 * 1024 * 1024,
        "tcp_keepalive": True,
        "tcp_keepalive_idle": 300,
        "tcp_keepalive_cnt": -1,
        "tcp_keepalive_intvl": -1,
    }

    # Dumb pull listener: accept but never read, shrink recv buffer.
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
    listener.bind(("127.0.0.1", pull_port))
    listener.listen(16)

    stop_accept = threading.Event()
    accepted = []

    def _accept_loop():
        while not stop_accept.is_set():
            try:
                listener.settimeout(0.5)
                conn, _ = listener.accept()
                conn.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
                accepted.append(conn)
            except TimeoutError:
                continue
            except OSError:
                break

    accept_thread = threading.Thread(
        target=_accept_loop, name="dumb-pull-acceptor", daemon=True
    )
    accept_thread.start()

    try:
        ctx = multiprocessing.get_context("fork")
        heartbeat_ticks = ctx.Value("i", 0)
        publish_done = ctx.Value("i", 0)
        proc = ctx.Process(
            target=_child_run,
            args=(opts, sock_dir, heartbeat_ticks, publish_done),
            daemon=True,
        )
        proc.start()

        # Give the child time to boot and start heartbeat + publish.
        time.sleep(1.5)
        baseline = heartbeat_ticks.value

        # Sample every 100ms for 2s to see if heartbeat is still
        # progressing WHILE publish is running (or wedged).
        samples = []
        for _ in range(20):
            samples.append(heartbeat_ticks.value)
            time.sleep(0.1)
        progress = samples[-1] - baseline

        proc.join(timeout=10)
        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=5)
            if proc.is_alive():
                proc.kill()
                proc.join()

        assert progress >= 20, (
            f"Outer asyncio loop wedged during fire_event (issue #69986): "
            f"heartbeat progressed only {progress} ticks in 2s while "
            f"SaltEvent.fire_event held the loop via nested SyncWrapper "
            f"thread.join(). baseline={baseline} samples={samples}"
        )
    finally:
        stop_accept.set()
        try:
            listener.close()
        except OSError:
            pass
        for c in accepted:
            try:
                c.close()
            except OSError:
                pass
        accept_thread.join(timeout=5)
