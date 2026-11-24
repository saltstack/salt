"""
Functional regression tests for saltstack/salt#70938 -- the ws
``PublishServer`` must not wedge the master when a subscriber (or the
IPC pull side) stalls.

These tests exercise the real ``salt.transport.ws`` publish code path
on real sockets (the pull-side ``asyncio.open_connection`` / aiohttp
``SockSite`` are both spun up in-process) and prove:

* ``PublishServer.publish(payload, timeout=N)`` raises ``TimeoutError``
  when the pull-side peer never drains, instead of waiting forever.
* ``PublishServer.publish_payload(payload, timeout=N)`` drops a stalled
  subscriber and keeps delivering to the healthy real-WebSocket
  subscribers already connected.
* ``timeout=None`` preserves the prior unbounded path so the back-
  compat shape is not broken by the fix.
* Multiple healthy subscribers all receive the payload on the happy
  path (no slow subscriber present).

The unit tests at ``tests/pytests/unit/transport/
test_ws_pub_server_send_timeout.py`` cover the same invariants against
stubs; these tests cover them against the real aiohttp framework and
real TCP sockets, which is where the asyncio.wait + late-observe
pattern actually has to hold together.

Without the fix in this PR the "slow subscriber does not block fan-out"
test will fail: either by TimeoutError propagating out of
``publish_payload`` (asyncio.wait_for on the unbounded pre-PR path
would require patching), or by the stalled client remaining in
``self.clients`` and the healthy subscriber never getting its message.
The simpler without-fix shape is: pre-PR ``publish_payload`` has NO
``timeout=`` kwarg, so the call raises ``TypeError`` -- which the
test catches as a failed pass of the regression invariant.
"""

import asyncio
import socket

import aiohttp
import pytest
import pytestshellutils.utils.ports

import salt.payload
import salt.transport.ws

pytestmark = [
    pytest.mark.slow_test,
]


class _WedgedWS:
    """``WebSocketResponse`` stand-in whose ``send_bytes`` never
    resolves.  Used to model a subscriber whose aiohttp write future
    is parked forever on a wedged peer."""

    def __init__(self):
        self.sent = []

    async def send_bytes(self, payload):
        self.sent.append(payload)
        await asyncio.Future()


def _free_port():
    return pytestshellutils.utils.ports.get_unused_localhost_port()


def _publish_server_bare():
    """Minimal ``PublishServer`` that bypasses ``__init__``'s
    ``multiprocessing.Event`` dance -- we don't need cross-process
    coordination for direct ``publish_payload``/``publish`` calls."""
    server = object.__new__(salt.transport.ws.PublishServer)
    server.pub_writer = None
    server.clients = set()
    return server


async def _run_pub_site(tmp_path):
    """Start a real aiohttp pub server (``handle_request`` loop) on a
    free localhost port.  Returns ``(server, pub_port, teardown)``."""
    pub_port = _free_port()
    opts = {"interface": "127.0.0.1"}
    server = salt.transport.ws.PublishServer(
        opts,
        pub_host="127.0.0.1",
        pub_port=pub_port,
        pull_host="127.0.0.1",
        pull_port=_free_port(),
    )

    # Bind the aiohttp pub site exactly like production ``publisher()``
    # does, but without the ``publish_daemon`` subprocess fork or the
    # multiprocessing shutdown event.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setblocking(False)
    sock.bind(("127.0.0.1", pub_port))
    sock.listen(128)
    aio_server = aiohttp.web.Server(server.handle_request)
    runner = aiohttp.web.ServerRunner(aio_server)
    await runner.setup()
    site = aiohttp.web.SockSite(runner, sock)
    await site.start()

    async def teardown():
        # Drop every client ws so handle_request tasks unwind.
        for ws in list(server.clients):
            try:
                await ws.close()
            except Exception:  # pylint: disable=broad-except
                pass
        try:
            await site.stop()
        finally:
            await runner.cleanup()

    return server, pub_port, teardown


async def _connect_ws_client(pub_port):
    session = aiohttp.ClientSession()
    ws = await session.ws_connect(f"http://127.0.0.1:{pub_port}/")
    return session, ws


async def _wait_for_client_registered(server, count, timeout=5.0):
    """``handle_request`` adds the ws to ``server.clients`` after
    ``ws.prepare``; wait until that side effect has happened."""
    deadline = asyncio.get_running_loop().time() + timeout
    while len(server.clients) < count:
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError(
                f"only {len(server.clients)} of {count} ws clients registered"
            )
        await asyncio.sleep(0.05)


async def test_publish_payload_fans_out_to_two_real_ws_subscribers(tmp_path):
    """Happy path: two real aiohttp WS subscribers both receive the
    payload.  Uses ``timeout=None`` to prove the back-compat path is
    unchanged."""
    server, pub_port, teardown = await _run_pub_site(tmp_path)
    try:
        session_a, ws_a = await _connect_ws_client(pub_port)
        session_b, ws_b = await _connect_ws_client(pub_port)
        try:
            await _wait_for_client_registered(server, 2)

            await server.publish_payload({"ok": True, "n": 1})

            msg_a = await asyncio.wait_for(ws_a.receive(), timeout=5)
            msg_b = await asyncio.wait_for(ws_b.receive(), timeout=5)

            assert msg_a.type == aiohttp.WSMsgType.BINARY
            assert msg_b.type == aiohttp.WSMsgType.BINARY
            assert salt.payload.loads(msg_a.data) == {"ok": True, "n": 1}
            assert salt.payload.loads(msg_b.data) == {"ok": True, "n": 1}
        finally:
            await ws_a.close()
            await ws_b.close()
            await session_a.close()
            await session_b.close()
    finally:
        await teardown()


async def test_publish_payload_drops_wedged_subscriber_and_delivers_to_real_client(
    tmp_path,
):
    """One wedged subscriber (``send_bytes`` stalls forever) alongside
    one real aiohttp WS subscriber.  The healthy real subscriber MUST
    receive the payload within the timeout window, and the wedged
    subscriber MUST be removed from ``server.clients``."""
    server, pub_port, teardown = await _run_pub_site(tmp_path)
    try:
        session, real_ws = await _connect_ws_client(pub_port)
        try:
            await _wait_for_client_registered(server, 1)
            wedged = _WedgedWS()
            server.clients.add(wedged)
            assert wedged in server.clients

            # The wedged peer would otherwise park the fan-out forever;
            # a 0.5s per-subscriber timeout drops it and the real
            # subscriber gets the payload.  Timeout is instance-scoped
            # so ``publish_payload`` keeps the base-class signature
            # (see ``test_transport_publishserver_has_method_signatures``).
            server._publish_payload_timeout = 0.5
            await asyncio.wait_for(
                server.publish_payload({"ok": True, "n": 2}),
                timeout=10,
            )

            # Healthy real ws got the payload.
            msg = await asyncio.wait_for(real_ws.receive(), timeout=5)
            assert msg.type == aiohttp.WSMsgType.BINARY
            assert salt.payload.loads(msg.data) == {"ok": True, "n": 2}

            # Wedged ws was dropped (same remediation as
            # ConnectionResetError).
            assert wedged not in server.clients
            # Wedged did get ``send_bytes`` called (it is what stalled).
            assert len(wedged.sent) == 1
        finally:
            await real_ws.close()
            await session.close()
    finally:
        await teardown()


async def test_publish_payload_timeout_none_delivers_to_real_client(tmp_path):
    """``timeout=None`` preserves the pre-#70938 code path: no
    ``asyncio.wait`` wrap, straight ``await send_bytes``.  Prove the
    happy real-ws subscriber still gets the payload on that path."""
    server, pub_port, teardown = await _run_pub_site(tmp_path)
    try:
        session, real_ws = await _connect_ws_client(pub_port)
        try:
            await _wait_for_client_registered(server, 1)
            # Leaving ``_publish_payload_timeout`` unset preserves the
            # pre-#70938 unbounded path (same as ``timeout=None``).
            await asyncio.wait_for(
                server.publish_payload({"ok": True, "n": 3}),
                timeout=10,
            )
            msg = await asyncio.wait_for(real_ws.receive(), timeout=5)
            assert msg.type == aiohttp.WSMsgType.BINARY
            assert salt.payload.loads(msg.data) == {"ok": True, "n": 3}
        finally:
            await real_ws.close()
            await session.close()
    finally:
        await teardown()


async def test_publish_timeout_raises_when_pull_peer_never_drains():
    """``PublishServer.publish(payload, timeout=0.1)`` must raise
    ``TimeoutError`` when the pull-side peer accepts the connection
    but never reads.  Fill the OS send buffer with a large payload so
    ``StreamWriter.drain`` is forced to block.

    This is the wire-level counterpart to
    ``test_publish_with_timeout_raises_timeout_error_on_wedged_drain``
    in the ws unit test file: same invariant, but against a real TCP
    socket where ``drain()`` resolves via the kernel send buffer, not
    an ``asyncio.Future`` stub."""
    pull_port = _free_port()

    # Non-draining listener: accept the connection and do nothing.
    # The kernel's SO_SNDBUF on the publisher side will fill up and
    # drain() will park.
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", pull_port))
    listener.listen(1)
    listener.setblocking(False)

    accepted = []

    async def _accept_once():
        loop = asyncio.get_running_loop()
        conn, _ = await loop.sock_accept(listener)
        # Shrink the accepting kernel's RECV buffer so the publisher's
        # SO_SNDBUF fills up quickly regardless of system tunings.
        conn.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
        accepted.append(conn)
        # Never read from `conn`.  Deliberate.

    server = _publish_server_bare()
    server.pub_host = "127.0.0.1"
    server.pull_host = "127.0.0.1"
    server.pull_port = pull_port
    server.pull_path = None
    server._connecting = None

    accept_task = asyncio.create_task(_accept_once())
    try:
        # 16 MiB payload is large enough that no reasonable default
        # SO_SNDBUF + asyncio StreamWriter high-water mark absorbs it
        # synchronously; drain() will have to await.  The non-reading
        # peer with a tiny SO_RCVBUF keeps the publisher's send queue
        # full.
        big_payload = b"x" * (16 * 1024 * 1024)

        # Kick off publish: it drives the connect() to the listener,
        # writes the payload into the stream, and awaits drain().
        # Concurrently, the accept_task accepts the connection on the
        # other end so the publisher's connect completes.  The accept
        # task then holds the socket open without reading, so drain()
        # parks forever.  The internal timeout=0.1 must raise.
        inner_timeout = 0.1
        start = asyncio.get_running_loop().time()
        publish_task = asyncio.create_task(
            server.publish(big_payload, timeout=inner_timeout)
        )

        # Wait for the accept side to resolve so the stream is actually
        # established before we assert on the timeout.
        await asyncio.wait_for(accept_task, timeout=5)

        # Outer wait_for is only the harness bound; the PR's fix is
        # what must fire the inner TimeoutError well before the outer.
        outer_timeout = 5
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(publish_task, timeout=outer_timeout)
        elapsed = asyncio.get_running_loop().time() - start
        # The inner timeout must be what fired, not the outer; give
        # generous headroom (3x outer-floor slack) but assert the
        # publish did NOT take anywhere near the outer timeout.
        assert elapsed < outer_timeout - 1.0, (
            f"publish(timeout={inner_timeout}) took {elapsed:.2f}s -- "
            f"the inner timeout did not fire; the outer wait_for raised "
            f"instead (i.e. the PR's fix is not active)."
        )
    finally:
        # Tear down.  Close the peer sockets first so the publisher's
        # pending drain resolves with ConnectionResetError instead of
        # staying parked forever.
        for conn in accepted:
            try:
                conn.close()
            except Exception:  # pylint: disable=broad-except
                pass
        listener.close()
        if not accept_task.done():
            accept_task.cancel()
            try:
                await accept_task
            except (asyncio.CancelledError, Exception):  # pylint: disable=broad-except
                pass
        try:
            if server.pub_writer is not None:
                server.pub_writer.close()
        except Exception:  # pylint: disable=broad-except
            pass
        # Give the loop a tick so the observer callback consumes the
        # late drain outcome and no "Task was destroyed but pending"
        # warning fires.
        await asyncio.sleep(0)
