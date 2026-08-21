"""
Companion check for the #69986 fix.  Confirms that events are actually
delivered to the puller (not silently dropped by an unawaited
coroutine).  Fails on any "fix" that trades deadlock for silent event
loss.
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


def _child_fire_events(opts, sock_dir, publish_done):
    import asyncio

    import salt.utils.event

    event = salt.utils.event.get_master_event(opts, sock_dir=sock_dir, listen=False)

    async def _publish():
        for i in range(5):
            event.fire_event({"i": i, "pad": "x" * 128}, tag=f"delivery/{i}")
            await asyncio.sleep(0.02)
        await asyncio.sleep(0.5)  # let scheduled tasks drain
        publish_done.value = 1

    asyncio.run(_publish())


@pytest.mark.timeout(30, method="thread")
def test_fire_event_from_async_context_actually_delivers(tmp_path):
    """
    After fire_event() returns from async context, the events MUST
    actually reach the puller.  If a "fix" returns unawaited coroutines
    from ``pusher.publish``, events are silently dropped and this test
    catches it.
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
        "max_event_size": 1048576,
        "tcp_keepalive": True,
        "tcp_keepalive_idle": 300,
        "tcp_keepalive_cnt": -1,
        "tcp_keepalive_intvl": -1,
    }

    # Real listener that DRAINS everything.  We only want to verify
    # bytes arrive.
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", pull_port))
    listener.listen(16)

    received_bytes = bytearray()
    stop_accept = threading.Event()

    def _accept_and_drain():
        conns = []
        try:
            while not stop_accept.is_set():
                try:
                    listener.settimeout(0.2)
                    conn, _ = listener.accept()
                    conns.append(conn)
                    conn.setblocking(False)
                except TimeoutError:
                    pass
                except OSError:
                    break
                for c in list(conns):
                    try:
                        data = c.recv(65536)
                        if data:
                            received_bytes.extend(data)
                    except (BlockingIOError, InterruptedError):
                        pass
                    except OSError:
                        conns.remove(c)
        finally:
            for c in conns:
                try:
                    c.close()
                except OSError:
                    pass

    acc = threading.Thread(target=_accept_and_drain, daemon=True)
    acc.start()

    try:
        ctx = multiprocessing.get_context("fork")
        publish_done = ctx.Value("i", 0)
        proc = ctx.Process(
            target=_child_fire_events,
            args=(opts, sock_dir, publish_done),
            daemon=True,
        )
        proc.start()
        proc.join(timeout=15)
        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=3)
            if proc.is_alive():
                proc.kill()
                proc.join()

        # Give the drainer thread a moment to catch any last bytes.
        time.sleep(0.5)

        assert publish_done.value == 1, "child did not complete publishes"
        # Sanity: at least ONE of the 5 event tags shows up in the
        # bytes.  If the fix returns unawaited coroutines from
        # pusher.publish, received_bytes will be empty (or only
        # contain the connect handshake).
        found_tags = sum(
            1 for i in range(5) if f"delivery/{i}".encode() in received_bytes
        )
        assert found_tags >= 1, (
            f"No events delivered to puller: received_bytes={len(received_bytes)} "
            f"bytes; found_tags={found_tags}/5.  A 'fix' that returns "
            f"unawaited coroutines from pusher.publish silently drops events."
        )
    finally:
        stop_accept.set()
        try:
            listener.close()
        except OSError:
            pass
        acc.join(timeout=5)
