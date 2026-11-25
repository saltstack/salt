"""
Functional regression tests for the TCP PublishServer publish-timeout
invariant that sibling PR saltstack/salt#70461 adds for the TCP wire
transport.  Companion to the ws-side tests at
``tests/pytests/functional/transport/ws/test_pub_server_timeout.py``.

On 3008.x's current ``_TCPPubServerPublisher.send(self, msg,
timeout=None, tries=None)`` the ``timeout`` argument is explicitly
documented as unimplemented (``# FIXME timeout unimplemented`` at the
method's head).  The ``timeout`` kwarg IS accepted, which is what the
``publish_server.publish`` seam forwards; #70461 is where the
implementation lands.

The functional tests below exercise two invariants that hold on 3008.x
*today* and are the wire counterparts of the ws tests in this PR:

1. The ``timeout=`` kwarg is API-compatible end-to-end: ``PublishServer.
   publish(payload, timeout=N)`` on the sync (SyncWrapper) path does
   not raise ``TypeError`` for the keyword and does not change the
   happy-path semantics.
2. One failing/unreachable subscriber in ``PubServer.publish_payload``
   does not block fan-out to other subscribers (shared fan-out
   invariant with the ws transport).  This is exercised against the
   real ``PubServer`` by stuffing one ``_FakeClient`` (ok) + one
   ``_FakeClient`` (``StreamClosedError`` on write) into ``clients``
   and asserting the ok client still received the payload.  The unit-
   test equivalent is at ``test_pub_server.py``'s
   ``test_publish_payload_buffer_full_does_not_abort_broadcast``;
   this test extends coverage to a live ``PubServer`` instance
   wired through the real ``io_loop`` fixture.

NOTE on without-fix verification: #70461 is NOT yet merged on 3008.x
(``_TCPPubServerPublisher.send`` on master has the ``timeout`` arg but
is a no-op).  The "one bad subscriber doesn't block fan-out" invariant
HAS been enforced on 3008.x since PR #70810 / earlier
``StreamClosedError`` handling; this test asserts the invariant still
holds end-to-end after the ws PR lands and nothing on the TCP side
regresses.
"""

import asyncio
import os

import pytest
import tornado.iostream

import salt.transport.tcp

pytestmark = [
    pytest.mark.slow_test,
]


class _FakeStream:
    """Minimal IOStream stand-in for ``PubServer.publish_payload``."""

    def __init__(self, mode="ok"):
        self.mode = mode
        self.writes = []
        self._closed = False

    def write(self, payload):
        if self.mode == "full":
            raise tornado.iostream.StreamBufferFullError(
                "Reached maximum write buffer size"
            )
        if self.mode == "closed":
            raise tornado.iostream.StreamClosedError
        self.writes.append(payload)
        fut = asyncio.get_event_loop().create_future()
        fut.set_result(None)
        return fut

    def close(self):
        self._closed = True


class _FakeClient:
    def __init__(self, mode, id_=None):
        self.stream = _FakeStream(mode=mode)
        self.address = f"fake-{mode}"
        self.id_ = id_
        self._closed = False

    def close(self):
        self._closed = True


def _minimal_pub_opts(tmp_path):
    return {
        "id": "regression-master",
        "sock_dir": str(tmp_path),
        "publish_drain_timeout": 5.0,
    }


async def test_publish_payload_broadcast_continues_past_closed_subscriber(
    io_loop, tmp_path
):
    """One subscriber whose write raises ``StreamClosedError`` must
    not block the fan-out to the other subscribers; the offending
    client must be removed from ``self.clients`` and closed.

    Shared invariant with the ws transport's
    ``test_publish_payload_drops_wedged_subscriber_and_delivers_to_real_client``.
    """
    server = salt.transport.tcp.PubServer(
        _minimal_pub_opts(tmp_path),
        io_loop=io_loop,
        presence_callback=None,
        remove_presence_callback=lambda client: None,
    )

    fast_a = _FakeClient("ok")
    bad = _FakeClient("closed")
    fast_b = _FakeClient("ok")

    server.clients.add(fast_a)
    server.clients.add(bad)
    server.clients.add(fast_b)

    try:
        await server.publish_payload({"marker": "pub-timeout-functional"})

        # Both fast subscribers each received exactly one write.
        assert len(fast_a.stream.writes) == 1
        assert len(fast_b.stream.writes) == 1
        # Bad subscriber was dropped.
        assert bad not in server.clients
        assert bad._closed
        # Fast subscribers stayed subscribed.
        assert fast_a in server.clients
        assert fast_b in server.clients
    finally:
        server.close()


async def test_publish_server_publish_accepts_timeout_kwarg(io_loop, tmp_path):
    """``PublishServer.publish(payload, timeout=N)`` must accept the
    kwarg end-to-end so a caller (e.g. event bus) passing
    ``timeout=`` to a TCP ``PublishServer`` does not raise
    ``TypeError``.  This is the signature compat gate shared with the
    ws transport.

    The per-connection timeout semantics for the TCP seam are added
    by sibling PR #70461; on the current 3008.x base the arg is
    silently dropped (``**kwargs`` swallows it).  What matters here
    for signature parity with the ws transport (which this PR
    implements) is that ``timeout=`` is NOT a ``TypeError`` -- the
    wiring of the kwarg down to ``_TCPPubServerPublisher.send`` is
    out of scope for this PR.
    """
    opts = _minimal_pub_opts(tmp_path)
    opts["transport"] = "tcp"
    server = salt.transport.tcp.PublishServer(
        opts,
        pub_host="127.0.0.1",
        pub_port=0,
        pull_path=os.path.join(str(tmp_path), "publish_pull_timeout.ipc"),
    )
    try:
        # Monkeypatch pub_sock so we don't touch real sockets; we
        # only care about the signature gate on the top-level
        # publish().
        class _StubSock:
            def __init__(self):
                self.calls = []

            def send(self, payload, **kwargs):
                self.calls.append((payload, kwargs))

        server.pub_sock = _StubSock()
        # Must NOT raise TypeError for `timeout=`.
        await server.publish({"ok": True}, timeout=3)
        assert len(server.pub_sock.calls) == 1
        # No positive assertion on the forwarded kwargs; forwarding
        # is a #70461 concern.  The point is that accept-and-drop is
        # NOT a regression -- and that the public surface is the
        # same shape as the ws transport's.
    finally:
        server.close()
