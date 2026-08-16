"""
Complementary repro for #69986: does calling PublishServer.publish
DIRECTLY (not through SyncWrapper) from an async context also wedge?

This isolates whether the deadlock is intrinsic to PublishServer.publish
or arises from the SyncWrapper wrapping.
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


def _child_run(opts, pub_port, pull_port, heartbeat_ticks, publish_done):
    import asyncio

    import salt.transport.tcp

    server = salt.transport.tcp.PublishServer(
        opts,
        pub_host="127.0.0.1",
        pub_port=pub_port,
        pull_host="127.0.0.1",
        pull_port=pull_port,
    )

    async def _heartbeat(stop_event):
        while not stop_event.is_set():
            with heartbeat_ticks.get_lock():
                heartbeat_ticks.value += 1
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=0.05)
            except asyncio.TimeoutError:
                pass

    async def _publish():
        payload = b"x" * (256 * 1024)
        # DIRECT await -- bypass SyncWrapper entirely.  On unpatched
        # code, PublishServer.publish still internally routes through
        # SyncWrapper(_TCPPubServerPublisher), so the outer loop
        # wedges anyway.  On the fix, publish takes the async fast
        # path (raw _TCPPubServerPublisher on the running loop).
        for _ in range(200):
            await server.publish(payload)
        publish_done.value = 1

    async def _main():
        stop = asyncio.Event()
        hb = asyncio.create_task(_heartbeat(stop))
        await asyncio.sleep(0.1)
        pub_task = asyncio.create_task(_publish())
        try:
            # Keep the loop alive for the parent's sample window.
            await asyncio.sleep(6.0)
        finally:
            stop.set()
            pub_task.cancel()
            hb.cancel()

    asyncio.run(_main())


@pytest.mark.timeout(60, method="thread")
def test_direct_publish_from_async_context(tmp_path):
    pull_port = _find_free_port()
    pub_port = _find_free_port()
    opts = {
        "ipc_mode": "tcp",
        "ipc_write_buffer": 0,
        "publish_port": pub_port,
        "tcp_master_pub_port": pub_port,
        "tcp_master_pull_port": pull_port,
        "master_ip": "127.0.0.1",
        "transport": "tcp",
        "id": "test-master",
        "sock_dir": str(tmp_path),
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

    accept_thread = threading.Thread(target=_accept_loop, daemon=True)
    accept_thread.start()

    try:
        ctx = multiprocessing.get_context("fork")
        heartbeat_ticks = ctx.Value("i", 0)
        publish_done = ctx.Value("i", 0)
        proc = ctx.Process(
            target=_child_run,
            args=(opts, pub_port, pull_port, heartbeat_ticks, publish_done),
            daemon=True,
        )
        proc.start()
        time.sleep(1.5)
        baseline = heartbeat_ticks.value
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
            f"Direct-call publish wedged outer loop: progress={progress}, "
            f"baseline={baseline}, samples={samples}"
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
