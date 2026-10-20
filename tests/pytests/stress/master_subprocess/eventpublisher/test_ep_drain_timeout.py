"""
Drain-timeout regression test for the ``PubServer`` (the workhorse
inside the EP subprocess).

This runs ``PubServer.publish_payload`` in-process on a Tornado / asyncio
loop rather than in a real EP subprocess.  Rationale: the drain-timeout
path fires when a subscriber's ``stream.write(...)`` future never
resolves.  Making that happen deterministically requires stubbing the
subscriber's write future to be non-resolving; we can't do that against
a real UNIX-domain socket without racing kernel-buffer autotuning.  So
we run ``PubServer`` in-process with a fake stream that returns a
never-resolving future, and assert:

* the drain task times out at ``publish_drain_timeout``;
* ``_discard_slow_client`` runs and removes the client;
* a well-behaved subscriber alongside it is unaffected;
* ``PubServer`` itself is still healthy for subsequent publishes.

The subprocess-level stress tests in ``test_ep_stress.py`` cover the
end-to-end wedge regression (fast subscriber not blocked by slow).
"""

from __future__ import annotations

import asyncio

import pytest
import tornado.ioloop

import salt.transport.tcp


@pytest.fixture
def pub_opts():
    """
    Minimal opts sufficient for ``PubServer`` -- it only reads
    ``ipc_write_buffer``, ``publish_drain_timeout`` and ``ssl``.
    """
    return {
        "transport": "tcp",
        "ipc_write_buffer": None,
        "publish_drain_timeout": 0.05,
    }


class _NeverResolvingStream:
    """
    IOStream stand-in whose ``write`` returns an ``asyncio.Future`` that
    never resolves.  Mimics a subscriber with a full kernel send buffer.
    """

    def __init__(self, name: str = "slow"):
        self.name = name
        self._closed = False
        self.write_calls = 0

    def closed(self):
        return self._closed

    def close(self):
        self._closed = True

    def write(self, payload):
        self.write_calls += 1
        return asyncio.get_event_loop().create_future()


class _FastStream:
    """
    IOStream stand-in whose ``write`` returns an already-resolved
    future.  Mimics a subscriber that drains as fast as we publish.
    """

    def __init__(self, name: str = "fast"):
        self.name = name
        self._closed = False
        self.writes = []

    def closed(self):
        return self._closed

    def close(self):
        self._closed = True

    def write(self, payload):
        self.writes.append(payload)
        fut = asyncio.get_event_loop().create_future()
        fut.set_result(None)
        return fut


def _make_subscriber(stream, name):
    sub = salt.transport.tcp.Subscriber(stream, name)
    sub.id_ = name
    return sub


@pytest.mark.timeout(30)
async def test_drain_timeout_discards_slow_subscriber(pub_opts):
    """
    A subscriber whose write future never resolves must be discarded
    from ``PubServer.clients`` after ``publish_drain_timeout``.  A
    parallel fast subscriber must be delivered every event and must
    stay in the set.  ``PubServer`` must not raise.
    """
    # publish_drain_timeout=0.05 comes from the ``pub_opts`` fixture.
    server = salt.transport.tcp.PubServer(
        pub_opts, io_loop=tornado.ioloop.IOLoop.current()
    )
    try:
        slow_stream = _NeverResolvingStream("slow")
        fast_stream = _FastStream("fast")
        slow_sub = _make_subscriber(slow_stream, "slow")
        fast_sub = _make_subscriber(fast_stream, "fast")
        server.clients = {slow_sub, fast_sub}

        # Send a burst; every write against slow gets a pending future,
        # each of which will time out; every write against fast is
        # already resolved.
        for i in range(3):
            await server.publish_payload({"idx": i})

        # Wait long enough for the drain tasks against slow to fire
        # their asyncio.TimeoutError branch (~drain_timeout).
        deadline = 5.0
        step = 0.02
        elapsed = 0.0
        while slow_sub in server.clients and elapsed < deadline:
            await asyncio.sleep(step)
            elapsed += step

        assert slow_sub not in server.clients, (
            "slow subscriber was not discarded after drain_timeout — "
            "_discard_slow_client did not fire"
        )
        assert slow_stream.closed(), "slow stream was not closed on discard"
        assert fast_sub in server.clients, "fast subscriber was collateral damage"
        assert (
            len(fast_stream.writes) == 3
        ), f"fast subscriber missed writes: got {len(fast_stream.writes)}/3"

        # Publisher must still work: fast subscriber gets another event.
        await server.publish_payload({"idx": 99})
        assert (
            len(fast_stream.writes) == 4
        ), "PubServer stopped serving after discarding slow subscriber"
    finally:
        server.close()


@pytest.mark.timeout(30)
async def test_drain_timeout_survives_hundreds_of_slow_subs(pub_opts, caplog):
    """
    Multiple concurrently-slow subscribers must not cause EP to crash
    or leak.  All slow subscribers should be discarded within a bounded
    window.
    """
    server = salt.transport.tcp.PubServer(
        pub_opts, io_loop=tornado.ioloop.IOLoop.current()
    )
    try:
        slow_streams = [_NeverResolvingStream(f"slow{i}") for i in range(50)]
        slow_subs = [_make_subscriber(s, s.name) for s in slow_streams]
        server.clients = set(slow_subs)

        await server.publish_payload({"idx": 0})

        # All slow subs must be discarded within a modest window.
        deadline = 5.0
        step = 0.02
        elapsed = 0.0
        while server.clients and elapsed < deadline:
            await asyncio.sleep(step)
            elapsed += step

        assert not server.clients, (
            f"{len(server.clients)} slow subs never discarded after " f"{elapsed:.2f}s"
        )
        for s in slow_streams:
            assert s.closed(), f"{s.name} stream not closed"
    finally:
        server.close()
