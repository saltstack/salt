"""
Regression tests for salt-master 4505 publish-port stability.

See https://github.com/saltstack/salt/issues/66282 — under prolonged load a
single slow IPC subscriber stalls the entire TCP ``PubServer`` broadcast
loop because ``publish_payload`` ``yield``s each ``client.stream.write()``
serially.  Bytes accumulate in the tornado write buffer of the slow
client, the publisher coroutine can't service the next event from the
pull socket, and the master eventually appears wedged.
"""

import logging
import time

import pytest
import tornado.gen
import tornado.ioloop

import salt.transport.tcp

log = logging.getLogger(__name__)


class _FakeStream:
    """Mimic the bits of ``IOStream`` ``PubServer`` touches."""

    def __init__(self, write_delay=0.0, name=""):
        self.write_delay = write_delay
        self.name = name
        self.writes = []
        self._closed = False
        self.received_at = None

    def closed(self):
        return self._closed

    def close(self):
        self._closed = True

    @tornado.gen.coroutine
    def write(self, payload):
        # Record receipt time *before* sleeping so the assertion measures
        # the moment the broadcast loop actually reached this client, not
        # the moment it finished.
        self.received_at = time.monotonic()
        self.writes.append(payload)
        if self.write_delay:
            yield tornado.gen.sleep(self.write_delay)


def _make_subscriber(stream, name):
    sub = salt.transport.tcp.Subscriber(stream, name)
    sub.id_ = name
    return sub


@pytest.mark.timeout(60)
async def test_slow_subscriber_does_not_block_fast_subscriber(master_opts):
    """
    A single slow subscriber must not stall delivery to other subscribers.

    Without the fix, the ``for client in self.clients: yield ...write()``
    loop in ``PubServer.publish_payload`` is serial: when the slow client
    is iterated first, the fast client doesn't see its bytes until the
    slow client's write completes ~3 s later.  The test asserts the fast
    client receives its payload within 1 s of ``publish_payload`` being
    called.
    """
    master_opts["transport"] = "tcp"
    server = salt.transport.tcp.PubServer(
        master_opts, io_loop=tornado.ioloop.IOLoop.current()
    )
    try:
        slow_stream = _FakeStream(write_delay=3.0, name="slow")
        fast_stream = _FakeStream(write_delay=0.0, name="fast")
        slow_sub = _make_subscriber(slow_stream, "slow")
        fast_sub = _make_subscriber(fast_stream, "fast")
        # ``self.clients`` is a ``set`` in production so iteration order is
        # undefined.  Pin the order [slow, fast] so the bug is hit
        # deterministically.
        server.clients = [slow_sub, fast_sub]

        start = time.monotonic()
        # Don't await the broadcast — we want to observe the fast client
        # *during* the slow client's write.  ``publish_payload`` is a
        # tornado-coroutine that returns a ``tornado.concurrent.Future``;
        # ``convert_yielded`` makes it awaitable from an ``async def`` driven
        # by the IOLoop running this test.
        broadcast = tornado.gen.convert_yielded(server.publish_payload({"jid": "abc"}))
        # Poll up to 1 s for the fast client to have received the payload.
        deadline = start + 1.0
        while time.monotonic() < deadline and fast_stream.received_at is None:
            await tornado.gen.convert_yielded(tornado.gen.sleep(0.05))
        elapsed = (
            (fast_stream.received_at - start)
            if fast_stream.received_at is not None
            else None
        )
        # Let the broadcast finish so we don't leak the slow coroutine.
        await broadcast
    finally:
        server.close()

    assert elapsed is not None, (
        "fast subscriber did not receive the payload within 1s of publish; "
        "PubServer.publish_payload is broadcasting serially (#66282)"
    )
    assert elapsed < 1.0, (
        f"fast subscriber waited {elapsed:.2f}s behind slow subscriber; "
        "PubServer.publish_payload is broadcasting serially (#66282)"
    )
